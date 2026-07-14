"""Pydantic-validated application settings schema."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    DEMO = "demo"
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    OPENAI_COMPATIBLE = "openai-compatible"


class ToolMode(str, Enum):
    NATIVE = "native"
    JSON_FALLBACK = "json-fallback"
    AUTO = "auto"


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Theme(str, Enum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


class NumberFormat(str, Enum):
    INDIAN = "indian"
    WESTERN = "western"


def _profile_id() -> str:
    return uuid4().hex[:12]


class LLMProfile(BaseModel):
    """One saved LLM connection (provider + model + credentials ref)."""

    id: str = Field(default_factory=_profile_id)
    name: str = "Default"
    provider: LLMProvider = LLMProvider.DEMO
    model: str = "demo"
    base_url: str | None = None
    api_key_name: str | None = None
    tool_mode: ToolMode = ToolMode.AUTO
    timeout_s: int = Field(default=120, ge=5, le=600)
    max_context_tokens: int = Field(default=8192, ge=1024, le=128000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    enabled: bool = True


class LLMConfig(BaseModel):
    """Multi-LLM hub: profiles + active/fallback + per-task routing."""

    provider: LLMProvider = LLMProvider.DEMO
    model: str = "demo"
    base_url: str | None = None
    api_key_ref: str | None = None
    tool_mode: ToolMode = ToolMode.AUTO
    timeout_s: int = Field(default=120, ge=5, le=600)
    max_context_tokens: int = Field(default=8192, ge=1024, le=128000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tool_iterations: int = Field(default=8, ge=1, le=20)
    chat_model: str | None = None
    analysis_model: str | None = None

    profiles: list[LLMProfile] = Field(default_factory=list)
    active_profile_id: str | None = None
    fallback_profile_id: str | None = None
    chat_profile_id: str | None = None
    analysis_profile_id: str | None = None

    def ensure_profiles(self) -> LLMConfig:
        if self.profiles:
            return self
        pid = _profile_id()
        self.profiles = [
            LLMProfile(
                id=pid,
                name=self.provider.value.title(),
                provider=self.provider,
                model=self.model,
                base_url=self.base_url,
                api_key_name=self.api_key_ref,
                tool_mode=self.tool_mode,
                timeout_s=self.timeout_s,
                max_context_tokens=self.max_context_tokens,
                temperature=self.temperature,
            )
        ]
        self.active_profile_id = pid
        return self

    def get_profile(self, profile_id: str | None = None) -> LLMProfile:
        self.ensure_profiles()
        pid = profile_id or self.active_profile_id or self.profiles[0].id
        for p in self.profiles:
            if p.id == pid:
                return p
        return self.profiles[0]

    def sync_legacy_from_active(self) -> None:
        active = self.get_profile(self.active_profile_id)
        self.provider = active.provider
        self.model = active.model
        self.base_url = active.base_url
        self.api_key_ref = active.api_key_name
        self.tool_mode = active.tool_mode
        self.timeout_s = active.timeout_s
        self.max_context_tokens = active.max_context_tokens
        self.temperature = active.temperature


class CryptoMarketsConfig(BaseModel):
    enabled: bool = True
    exchanges: list[str] = Field(default_factory=lambda: ["binance"])


class MarketsConfig(BaseModel):
    stocks_global: bool = True
    india: bool = True
    crypto: CryptoMarketsConfig = Field(default_factory=CryptoMarketsConfig)
    quote_cache_ttl_s: int = Field(default=30, ge=5, le=3600)


class RiskConfig(BaseModel):
    max_position_pct: float = Field(default=10.0, ge=0.1, le=100.0)
    max_daily_loss_pct: float = Field(default=3.0, ge=0.1, le=100.0)
    max_order_value: float = Field(default=100_000.0, ge=1.0)


class TradingConfig(BaseModel):
    mode: TradingMode = TradingMode.PAPER
    kill_switch: bool = False
    require_order_confirmation: bool = True
    risk: RiskConfig = Field(default_factory=RiskConfig)
    paper_starting_cash: float = Field(default=1_000_000.0, ge=1000.0)
    paper_currency: str = "INR"


class AppearanceConfig(BaseModel):
    theme: Theme = Theme.DARK
    base_currency: str = "INR"
    locale: str = "en-IN"
    number_format: NumberFormat = NumberFormat.INDIAN
    timezone: str = "Asia/Kolkata"


class AppSettings(BaseModel):
    setup_complete: bool = False
    risk_acknowledged: bool = False
    risk_acknowledged_at: str | None = None
    llm: LLMConfig = Field(default_factory=LLMConfig)
    markets: MarketsConfig = Field(default_factory=MarketsConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)

    @field_validator("llm", mode="before")
    @classmethod
    def coerce_llm(cls, v: Any) -> Any:
        return v or {}

    def public_dict(self) -> dict[str, Any]:
        llm = self.llm.model_copy(deep=True)
        llm.ensure_profiles()
        llm.sync_legacy_from_active()
        payload = self.model_dump(mode="json")
        payload["llm"] = llm.model_dump(mode="json")
        return payload


DEFAULT_SETTINGS = AppSettings()
DEFAULT_SETTINGS.llm.ensure_profiles()
DEFAULT_SETTINGS.llm.sync_legacy_from_active()
