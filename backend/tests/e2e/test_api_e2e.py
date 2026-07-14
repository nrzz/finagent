"""End-to-end API tests covering setup, settings, markets, portfolio, trading, automation."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Isolate DB before importing app
TEST_DATA = Path(__file__).resolve().parent / "_e2e_data"
TEST_DATA.mkdir(parents=True, exist_ok=True)
DB_FILE = TEST_DATA / "e2e.db"
if DB_FILE.exists():
    DB_FILE.unlink()

import os

os.environ["FINAGENT_DATA_DIR"] = str(TEST_DATA)
os.environ["FINAGENT_DATABASE_URL"] = "sqlite+aiosqlite:///e2e.db"
os.environ["FINAGENT_SECRET_KEY"] = "e2e-test-secret-key-for-fernet-derive"
os.environ["FINAGENT_JWT_SECRET"] = "e2e-jwt-secret-please-change-in-prod-32chars"
os.environ["FINAGENT_ALLOW_INSECURE_SECRETS"] = "1"

# Clear cached env if any
from finagent.config import get_env

get_env.cache_clear()

from finagent.db import _engine, _session_factory  # noqa: E402
import finagent.db as db_mod

db_mod._engine = None
db_mod._session_factory = None

from finagent.main import app  # noqa: E402
from finagent.trading.paper import get_paper_broker  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client: TestClient) -> str:
    status = client.get("/api/auth/status").json()
    assert status["needs_setup"] is True
    res = client.post(
        "/api/auth/setup",
        json={"username": "e2eadmin", "password": "password123"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["setup_complete"] is False
    return data["access_token"]


@pytest.fixture(scope="module")
def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["telemetry"] == "none"


def test_setup_idempotent(client: TestClient, auth: dict[str, str]) -> None:
    # second setup must fail
    r = client.post(
        "/api/auth/setup",
        json={"username": "other", "password": "password123"},
    )
    assert r.status_code == 400


def test_login_ok_and_bad(client: TestClient) -> None:
    ok = client.post(
        "/api/auth/login",
        json={"username": "e2eadmin", "password": "password123"},
    )
    assert ok.status_code == 200
    bad = client.post(
        "/api/auth/login",
        json={"username": "e2eadmin", "password": "wrong-password"},
    )
    assert bad.status_code == 401


def test_me_requires_auth(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/api/auth/me").status_code == 401
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["username"] == "e2eadmin"


def test_wizard_complete_and_settings(client: TestClient, auth: dict[str, str]) -> None:
    denied = client.post(
        "/api/settings/wizard/complete",
        headers=auth,
        json={"settings": {"trading": {"mode": "paper"}}},
    )
    assert denied.status_code == 400

    r = client.post(
        "/api/settings/wizard/complete",
        headers=auth,
        json={
            "settings": {
                "risk_acknowledged": True,
                "llm": {
                    "provider": "ollama",
                    "model": "llama3.2:3b",
                    "base_url": "http://127.0.0.1:11434",
                    "tool_mode": "auto",
                },
                "markets": {
                    "stocks_global": True,
                    "india": True,
                    "crypto": {"enabled": True, "exchanges": ["binance"]},
                },
                "appearance": {
                    "theme": "dark",
                    "base_currency": "INR",
                    "timezone": "Asia/Kolkata",
                    "number_format": "indian",
                },
                "trading": {"mode": "paper"},
            }
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["setup_complete"] is True
    assert r.json()["settings"]["risk_acknowledged"] is True

    s = client.get("/api/settings", headers=auth)
    assert s.status_code == 200
    assert s.json()["settings"]["llm"]["model"] == "llama3.2:3b"


def test_settings_validation_reject(client: TestClient, auth: dict[str, str]) -> None:
    r = client.put(
        "/api/settings",
        headers=auth,
        json={"settings": {"llm": {"timeout_s": 1}}},  # below min 5
    )
    assert r.status_code == 400


def test_trading_mode_requires_reauth(client: TestClient, auth: dict[str, str]) -> None:
    r = client.put(
        "/api/settings",
        headers=auth,
        json={"settings": {"trading": {"mode": "live"}}},
    )
    assert r.status_code == 403

    r2 = client.put(
        "/api/settings",
        headers=auth,
        json={
            "settings": {"trading": {"mode": "live", "kill_switch": False}},
            "reauth_password": "wrong",
        },
    )
    assert r2.status_code == 403

    # switch to live with correct password, then back to paper
    r3 = client.put(
        "/api/settings",
        headers=auth,
        json={
            "settings": {"trading": {"mode": "live"}},
            "reauth_password": "password123",
        },
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["settings"]["trading"]["mode"] == "live"

    r4 = client.put(
        "/api/settings",
        headers=auth,
        json={
            "settings": {"trading": {"mode": "paper"}},
            "reauth_password": "password123",
        },
    )
    assert r4.status_code == 200
    assert r4.json()["settings"]["trading"]["mode"] == "paper"


def test_secrets_masked(client: TestClient, auth: dict[str, str]) -> None:
    r = client.put(
        "/api/settings/secrets",
        headers=auth,
        json={
            "name": "OPENAI_API_KEY",
            "value": "sk-test-secret-value-1234",
            "reauth_password": "password123",
        },
    )
    assert r.status_code == 200
    assert "sk-test" not in r.json().get("masked", "")
    assert r.json()["masked"].endswith("1234") or "*" in r.json()["masked"]


def test_portfolio_add_and_csv(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/portfolio/holdings",
        headers=auth,
        json={
            "symbol": "RELIANCE.NS",
            "quantity": "10",
            "avg_cost": "2500",
            "currency": "INR",
            "asset_class": "equity",
        },
    )
    assert r.status_code == 200, r.text

    csv_body = "symbol,quantity,avg_cost,currency,asset_class\nTCS.NS,5,3500,INR,equity\n"
    files = {"file": ("holdings.csv", io.BytesIO(csv_body.encode()), "text/csv")}
    r2 = client.post("/api/portfolio/import-csv", headers=auth, files=files)
    assert r2.status_code == 200, r2.text
    assert r2.json()["imported"] == 1

    # invalid quantity should 422/400
    bad = client.post(
        "/api/portfolio/holdings",
        headers=auth,
        json={"symbol": "X", "quantity": "not-a-number", "avg_cost": "1"},
    )
    assert bad.status_code in {400, 422, 500}


def test_paper_order_lifecycle(client: TestClient, auth: dict[str, str]) -> None:
    get_paper_broker().reset()
    r = client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": "2",
            "price": "100",
            "asset_class": "equity",
            "idempotency_key": "e2e-order-1",
            "confirmed": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["order"]["status"] == "filled"

    # idempotent replay
    r2 = client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": "2",
            "price": "100",
            "idempotency_key": "e2e-order-1",
            "confirmed": True,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["order"]["idempotency_key"] == "e2e-order-1"

    blotter = client.get("/api/trading/blotter", headers=auth)
    assert blotter.status_code == 200
    assert len(blotter.json()["orders"]) >= 1


def test_kill_switch_blocks_orders(client: TestClient, auth: dict[str, str]) -> None:
    client.put(
        "/api/settings",
        headers=auth,
        json={
            "settings": {"trading": {"kill_switch": True}},
            "reauth_password": "password123",
        },
    )
    r = client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": "1",
            "price": "10",
            "confirmed": True,
        },
    )
    assert r.status_code == 200
    # either ok False from registry or rejected order
    body = r.json()
    if body.get("ok") is False:
        assert "kill" in body.get("error", "").lower() or "Kill" in body.get("error", "")
    else:
        assert body["order"]["status"] == "rejected"

    client.put(
        "/api/settings",
        headers=auth,
        json={
            "settings": {"trading": {"kill_switch": False}},
            "reauth_password": "password123",
        },
    )


def test_risk_limit_max_order_value(client: TestClient, auth: dict[str, str]) -> None:
    client.put(
        "/api/settings",
        headers=auth,
        json={"settings": {"trading": {"risk": {"max_order_value": 50}}}},
    )
    get_paper_broker().reset()
    r = client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": "10",
            "price": "100",
            "confirmed": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["order"]["status"] == "rejected"
    # restore
    client.put(
        "/api/settings",
        headers=auth,
        json={"settings": {"trading": {"risk": {"max_order_value": 100000}}}},
    )


def test_watchlist_and_automation(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/watchlist",
        headers=auth,
        json={"symbol": "INFY.NS", "name": "Infosys", "asset_class": "equity"},
    )
    assert r.status_code == 200
    w = client.get("/api/watchlist", headers=auth)
    assert any(i["symbol"] == "INFY.NS" for i in w.json()["items"])

    a = client.post(
        "/api/automation/alerts",
        headers=auth,
        json={"symbol": "BTC/USDT", "condition": "above", "threshold": "1000000"},
    )
    assert a.status_code == 200
    assert client.get("/api/automation/alerts", headers=auth).json()["alerts"]

    j = client.post(
        "/api/automation/jobs",
        headers=auth,
        json={
            "name": "e2e-dca",
            "job_type": "dca",
            "cron": "0 10 * * 1-5",
            "timezone": "Asia/Kolkata",
            "payload": {"symbol": "BTC/USDT", "quantity": "0.001", "asset_class": "crypto"},
        },
    )
    assert j.status_code == 200, j.text


def test_fno_greeks(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/trading/fno/greeks",
        headers=auth,
        json={"spot": 22000, "strike": 22000, "t_years": 0.08, "iv": 0.15, "option_type": "CE"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "delta" in body
    assert "margin_estimate" in body
    assert "lot_size" in body


def test_fno_paper_order_and_square_off(client: TestClient, auth: dict[str, str]) -> None:
    from datetime import date, timedelta

    import anyio

    from finagent.scheduler.jobs import square_off_expired_options

    get_paper_broker().reset()
    expiry = (date.today() - timedelta(days=1)).isoformat()
    r = client.post(
        "/api/trading/fno/order",
        headers=auth,
        json={
            "underlying": "NIFTY",
            "expiry": expiry,
            "strike": "22000",
            "option_type": "CE",
            "side": "buy",
            "quantity_lots": 1,
            "premium": "100",
            "confirmed": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["order"]["asset_class"] == "option"
    assert any("|" in s for s in get_paper_broker().account.positions)

    closed = anyio.run(square_off_expired_options)
    assert closed["closed"]
    assert not get_paper_broker().account.positions


def test_portfolio_xirr_and_corp_action(client: TestClient, auth: dict[str, str]) -> None:
    get_paper_broker().reset()
    client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "SPLITME",
            "side": "buy",
            "quantity": "10",
            "price": "100",
            "confirmed": True,
        },
    )
    cf1 = client.post(
        "/api/portfolio/cashflows",
        headers=auth,
        json={"amount": "-1000", "on_date": "2024-01-01", "note": "invest"},
    )
    assert cf1.status_code == 200, cf1.text
    cf2 = client.post(
        "/api/portfolio/cashflows",
        headers=auth,
        json={"amount": "200", "on_date": "2024-06-01", "note": "partial"},
    )
    assert cf2.status_code == 200
    x = client.get("/api/portfolio/xirr", headers=auth)
    assert x.status_code == 200
    body = x.json()
    assert "cashflows" in body
    assert len(body["cashflows"]) >= 2

    split = client.post(
        "/api/portfolio/corporate-action",
        headers=auth,
        json={"symbol": "SPLITME", "ratio_num": "2", "ratio_den": "1"},
    )
    assert split.status_code == 200, split.text
    assert split.json()["ok"] is True
    lots = get_paper_broker().account.positions.get("SPLITME")
    assert lots
    assert sum(lot.quantity for lot in lots) == 20


def test_automation_analysis_job_and_notifications(client: TestClient, auth: dict[str, str]) -> None:
    j = client.post(
        "/api/automation/jobs",
        headers=auth,
        json={
            "name": "e2e-analysis",
            "job_type": "analysis",
            "cron": "0 8 * * 1-5",
            "timezone": "Asia/Kolkata",
            "payload": {"symbols": ["AAPL"]},
        },
    )
    assert j.status_code == 200, j.text
    jobs = client.get("/api/automation/jobs", headers=auth)
    assert jobs.status_code == 200
    assert any(row["name"] == "e2e-analysis" for row in jobs.json()["jobs"])

    notes = client.get("/api/notifications", headers=auth)
    assert notes.status_code == 200
    assert "items" in notes.json()


def test_paper_persists_across_reload(client: TestClient, auth: dict[str, str]) -> None:
    import anyio

    from finagent.db import get_session_factory
    from finagent.trading.persist import load_paper_from_db, save_paper_to_db

    get_paper_broker().reset()
    r = client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "PERSIST",
            "side": "buy",
            "quantity": "3",
            "price": "50",
            "confirmed": True,
            "idempotency_key": "persist-e2e-1",
        },
    )
    assert r.status_code == 200, r.text
    cash_before = get_paper_broker().account.cash

    async def _roundtrip() -> None:
        async with get_session_factory()() as session:
            await save_paper_to_db(session)
        get_paper_broker().reset()
        assert "PERSIST" not in get_paper_broker().account.positions
        async with get_session_factory()() as session:
            await load_paper_from_db(session)

    anyio.run(_roundtrip)
    assert "PERSIST" in get_paper_broker().account.positions
    assert get_paper_broker().account.cash == cash_before


def test_brokers_list(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/api/trading/brokers", headers=auth)
    assert r.status_code == 200
    names = [b["name"] for b in r.json()["brokers"]]
    assert "paper" in names
    assert {"zerodha", "angel", "alpaca"}.issubset(set(names))


def test_audit_log(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/api/audit", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_export_settings_no_secrets(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/api/settings/export", headers=auth)
    assert r.status_code == 200
    assert "secrets" not in r.json() or r.json().get("note")
    text = r.text.lower()
    assert "sk-test-secret" not in text


def test_unauthenticated_api_blocked(client: TestClient) -> None:
    assert client.get("/api/portfolio").status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401


def test_multi_llm_profiles_catalog_and_activate(client: TestClient, auth: dict[str, str]) -> None:
    cat = client.get("/api/settings/llm/catalog", headers=auth)
    assert cat.status_code == 200
    providers = {p["id"]: p for p in cat.json()["providers"]}
    assert {"demo", "ollama", "openai", "anthropic", "openrouter", "groq"}.issubset(providers)
    ollama_presets = providers["ollama"]["presets"]
    models = {p["model"] for p in ollama_presets}
    assert "qwen2.5:7b" in models
    assert "0xroyce/plutus" in models
    assert any(p.get("recommended_for") == "finance" for p in ollama_presets)

    s = client.get("/api/settings", headers=auth)
    assert s.status_code == 200
    assert "catalog" in s.json()
    assert len(s.json()["catalog"]) >= 5

    demo = client.post(
        "/api/settings/llm/profiles",
        headers=auth,
        json={
            "name": "Demo primary",
            "provider": "demo",
            "model": "demo",
            "make_active": True,
        },
    )
    assert demo.status_code == 200, demo.text
    demo_id = demo.json()["profile"]["id"]

    ollama = client.post(
        "/api/settings/llm/profiles",
        headers=auth,
        json={
            "name": "Home Ollama",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "base_url": "http://127.0.0.1:11434",
            "make_fallback": True,
        },
    )
    assert ollama.status_code == 200, ollama.text
    ollama_id = ollama.json()["profile"]["id"]

    profiles = client.get("/api/settings/llm/profiles", headers=auth)
    assert profiles.status_code == 200
    body = profiles.json()
    assert body["active_profile_id"] == demo_id
    assert body["fallback_profile_id"] == ollama_id
    assert len(body["profiles"]) >= 2

    act = client.post(
        "/api/settings/llm/activate",
        headers=auth,
        json={"profile_id": ollama_id, "role": "chat"},
    )
    assert act.status_code == 200
    assert act.json()["settings"]["llm"]["chat_profile_id"] == ollama_id

    probe = client.post(
        "/api/settings/llm/probe",
        headers=auth,
        json={"provider": "demo"},
    )
    assert probe.status_code == 200
    assert probe.json()["ok"] is True

    test = client.post(f"/api/settings/llm/test/{demo_id}", headers=auth)
    assert test.status_code == 200
    assert test.json()["ok"] is True


def test_demo_chat_quote_flow(client: TestClient, auth: dict[str, str]) -> None:
    # Ensure demo LLM is Active (clears chat/analysis task routing)
    client.put(
        "/api/settings",
        headers=auth,
        json={"settings": {"llm": {"provider": "demo", "model": "demo", "tool_mode": "auto"}}},
    )
    # Confirm router sees demo
    probe = client.post("/api/settings/llm/test", headers=auth)
    assert probe.status_code == 200
    assert probe.json().get("provider") == "demo" or probe.json().get("ok") is True
    r = client.post(
        "/api/chat",
        headers=auth,
        json={"message": "What's the quote for AAPL?", "history": []},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "content" in body
    # Either got a tool trace (network quote) or a helpful demo final
    assert body["content"] or body.get("tool_trace")


def test_paper_order_requires_chat_confirmation(client: TestClient, auth: dict[str, str]) -> None:
    from finagent.agent.tools import execute_tool
    import anyio

    async def _run() -> dict:
        return await execute_tool(
            "place_paper_order",
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": "1",
                "price": "100",
                "confirmed": False,
            },
        )

    result = anyio.run(_run)
    assert result["ok"] is True
    assert result["result"]["pending_confirmation"] is True
    assert result["result"]["draft"]["symbol"] == "AAPL"

    placed = client.post(
        "/api/trading/order",
        headers=auth,
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": "1",
            "price": "100",
            "confirmed": True,
        },
    )
    assert placed.status_code == 200, placed.text
    assert placed.json()["ok"] is True


@pytest.mark.network
def test_market_quote_best_effort(client: TestClient, auth: dict[str, str]) -> None:
    """Live market call — skip soft-fail if network blocked."""
    r = client.get("/api/market/quote/AAPL", headers=auth)
    if r.status_code != 200:
        pytest.skip(f"market unavailable: {r.text}")
    q = r.json()
    assert "price" in q
    assert "source" in q
    assert "as_of" in q


def test_wizard_cannot_enable_live(client: TestClient, auth: dict[str, str]) -> None:
    r = client.post(
        "/api/settings/wizard/complete",
        headers=auth,
        json={
            "settings": {
                "risk_acknowledged": True,
                "trading": {"mode": "live"},
            }
        },
    )
    assert r.status_code == 403


def test_secrets_require_reauth(client: TestClient, auth: dict[str, str]) -> None:
    r = client.put(
        "/api/settings/secrets",
        headers=auth,
        json={"name": "DUMMY_KEY", "value": "secret-value-xyz"},
    )
    assert r.status_code == 403


def test_health_ready(client: TestClient) -> None:
    r = client.get("/api/health/ready")
    assert r.status_code in (200, 503)
    body = r.json()
    assert "checks" in body
    assert "database" in body["checks"]


def test_chat_history_endpoint(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/api/chat/history?limit=10", headers=auth)
    assert r.status_code == 200
    assert "messages" in r.json()


def test_agent_ignores_confirmed_true(client: TestClient, auth: dict[str, str]) -> None:
    """LLM cannot force-fill paper orders via confirmed=true."""
    import anyio

    from finagent.agent.tools import execute_tool

    async def _run() -> dict:
        return await execute_tool(
            "place_paper_order",
            {
                "symbol": "MSFT",
                "side": "buy",
                "quantity": "1",
                "price": "10",
                "confirmed": True,
            },
        )

    result = anyio.run(_run)
    assert result["ok"] is True
    assert result["result"].get("pending_confirmation") is True


def test_url_safety_blocks_metadata() -> None:
    from finagent.security.url_safety import is_safe_llm_base_url

    ok, _ = is_safe_llm_base_url("http://169.254.169.254/")
    assert ok is False
    ok2, _ = is_safe_llm_base_url("http://127.0.0.1:11434")
    assert ok2 is True


def test_ollama_exclusive_endpoint(client: TestClient, auth: dict[str, str]) -> None:
    """Exclusive unload is best-effort when Ollama is offline."""
    r = client.post(
        "/api/settings/llm/ollama/exclusive",
        headers=auth,
        json={"model": "qwen2.5:3b", "base_url": "http://127.0.0.1:11434", "warm": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert "unloaded" in body or "message" in body


def test_backup_download(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get("/api/settings/backup", headers=auth)
    # DB may live under data dir — 200 or 404 if path not resolved in test
    assert r.status_code in (200, 404)
