"""Provider catalog: install guides, presets, secret names — UI-driven setup."""

from __future__ import annotations

from typing import Any


PROVIDER_CATALOG: list[dict[str, Any]] = [
    {
        "id": "demo",
        "name": "Demo",
        "tagline": "Works instantly — no install",
        "difficulty": "easiest",
        "cost": "Free",
        "needs_api_key": False,
        "needs_install": False,
        "default_base_url": None,
        "secret_name": None,
        "install": {
            "title": "Already built in",
            "steps": [
                "Select Demo and click Activate — nothing to download.",
                "Upgrade later to Ollama (local) or a cloud provider for richer chat.",
            ],
            "links": [],
        },
        "presets": [
            {"id": "demo", "label": "Demo agent", "model": "demo", "tier": "instant", "ram": "—"},
        ],
    },
    {
        "id": "ollama",
        "name": "Ollama (Local)",
        "tagline": "Free private AI on your PC",
        "difficulty": "easy",
        "cost": "Free",
        "needs_api_key": False,
        "needs_install": True,
        "default_base_url": "http://127.0.0.1:11434",
        "secret_name": None,
        "recommended_for": "finance",
        "install": {
            "title": "Install Ollama in 2 minutes",
            "steps": [
                "Download and install Ollama for your OS (Windows / Mac / Linux).",
                "Prefer a finance-ready preset below (or qwen2.5:7b / llama3.1:8b), then Pull from this UI.",
                "Detect → Test → Activate. FinAgent still grounds prices via tools — models can hallucinate numbers.",
            ],
            "links": [
                {"label": "Download Ollama", "url": "https://ollama.com/download"},
                {"label": "Model library", "url": "https://ollama.com/library"},
                {
                    "label": "Plutus (finance fine-tune)",
                    "url": "https://ollama.com/0xroyce/plutus",
                },
            ],
        },
        "presets": [
            {
                "id": "qwen25-7b",
                "label": "Qwen2.5 7B (recommended)",
                "model": "qwen2.5:7b",
                "tier": "balanced",
                "ram": "8–16 GB",
                "pull": "qwen2.5:7b",
                "recommended_for": "finance",
                "note": "Strong general model for finance reasoning; FinAgent tools supply live numbers.",
            },
            {
                "id": "llama31-8b",
                "label": "Llama 3.1 8B (recommended)",
                "model": "llama3.1:8b",
                "tier": "balanced",
                "ram": "8–16 GB",
                "pull": "llama3.1:8b",
                "recommended_for": "finance",
                "note": "Best local balance for tool-using finance chat.",
            },
            {
                "id": "plutus",
                "label": "Plutus (finance fine-tune)",
                "model": "0xroyce/plutus",
                "tier": "finance",
                "ram": "8–16 GB",
                "pull": "0xroyce/plutus",
                "recommended_for": "finance",
                "note": "Llama 3.1 8B finance fine-tune. Still verify all prices via FinAgent tools.",
            },
            {
                "id": "adaptllm-finance",
                "label": "AdaptLLM finance-chat 7B",
                "model": "hf.co/TheBloke/finance-chat-GGUF",
                "tier": "finance",
                "ram": "8–16 GB",
                "pull": "hf.co/TheBloke/finance-chat-GGUF",
                "recommended_for": "finance",
                "note": "Domain-adapted GGUF. Community model — may need Ollama HF support. Numbers still come from tools.",
            },
            {
                "id": "qwen25-3b",
                "label": "Qwen2.5 3B (CPU)",
                "model": "qwen2.5:3b",
                "tier": "fast",
                "ram": "4 GB+",
                "pull": "qwen2.5:3b",
                "note": "CPU-only fallback.",
            },
            {
                "id": "llama32-3b",
                "label": "Llama 3.2 3B (CPU friendly)",
                "model": "llama3.2:3b",
                "tier": "fast",
                "ram": "4 GB+",
                "pull": "llama3.2:3b",
            },
            {
                "id": "mistral-7b",
                "label": "Mistral 7B",
                "model": "mistral:7b",
                "tier": "balanced",
                "ram": "8–16 GB",
                "pull": "mistral:7b",
            },
            {
                "id": "llama31-70b",
                "label": "Llama 3.1 70B (GPU)",
                "model": "llama3.1:70b",
                "tier": "quality",
                "ram": "GPU 24 GB+",
                "pull": "llama3.1:70b",
            },
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "tagline": "GPT-4o / GPT-4o-mini",
        "difficulty": "easy",
        "cost": "Pay per use",
        "needs_api_key": True,
        "needs_install": False,
        "default_base_url": "https://api.openai.com/v1",
        "secret_name": "OPENAI_API_KEY",
        "recommended_for": "finance",
        "install": {
            "title": "Connect OpenAI",
            "steps": [
                "Create an API key at platform.openai.com → API keys.",
                "Paste the key below (stored encrypted on your server).",
                "Pick a model preset → Test → Activate.",
            ],
            "links": [
                {"label": "Get API key", "url": "https://platform.openai.com/api-keys"},
            ],
        },
        "presets": [
            {
                "id": "gpt4o-mini",
                "label": "GPT-4o mini (cheap & fast)",
                "model": "gpt-4o-mini",
                "tier": "fast",
                "ram": "cloud",
                "recommended_for": "finance",
            },
            {
                "id": "gpt4o",
                "label": "GPT-4o (quality)",
                "model": "gpt-4o",
                "tier": "quality",
                "ram": "cloud",
                "recommended_for": "finance",
            },
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "tagline": "Claude Sonnet / Haiku",
        "difficulty": "easy",
        "cost": "Pay per use",
        "needs_api_key": True,
        "needs_install": False,
        "default_base_url": "https://api.anthropic.com",
        "secret_name": "ANTHROPIC_API_KEY",
        "recommended_for": "finance",
        "install": {
            "title": "Connect Anthropic",
            "steps": [
                "Create an API key at console.anthropic.com.",
                "Paste the key below → pick Claude → Test → Activate.",
            ],
            "links": [
                {"label": "Get API key", "url": "https://console.anthropic.com/settings/keys"},
            ],
        },
        "presets": [
            {
                "id": "claude-haiku",
                "label": "Claude 3.5 Haiku (fast)",
                "model": "claude-3-5-haiku-latest",
                "tier": "fast",
                "ram": "cloud",
            },
            {
                "id": "claude-sonnet",
                "label": "Claude Sonnet (quality)",
                "model": "claude-sonnet-4-20250514",
                "tier": "quality",
                "ram": "cloud",
                "recommended_for": "finance",
            },
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "tagline": "One key → many models",
        "difficulty": "easy",
        "cost": "Pay per use",
        "needs_api_key": True,
        "needs_install": False,
        "default_base_url": "https://openrouter.ai/api/v1",
        "secret_name": "OPENROUTER_API_KEY",
        "install": {
            "title": "Connect OpenRouter",
            "steps": [
                "Sign up at openrouter.ai and create a key.",
                "Paste the key → choose any model id → Test → Activate.",
            ],
            "links": [
                {"label": "Get API key", "url": "https://openrouter.ai/keys"},
                {"label": "Browse models", "url": "https://openrouter.ai/models"},
            ],
        },
        "presets": [
            {
                "id": "or-gemini-flash",
                "label": "Google Gemini Flash",
                "model": "google/gemini-2.0-flash-001",
                "tier": "fast",
                "ram": "cloud",
            },
            {
                "id": "or-deepseek",
                "label": "DeepSeek Chat",
                "model": "deepseek/deepseek-chat",
                "tier": "balanced",
                "ram": "cloud",
            },
        ],
    },
    {
        "id": "groq",
        "name": "Groq",
        "tagline": "Very fast cloud inference",
        "difficulty": "easy",
        "cost": "Free tier / pay",
        "needs_api_key": True,
        "needs_install": False,
        "default_base_url": "https://api.groq.com/openai/v1",
        "secret_name": "GROQ_API_KEY",
        "install": {
            "title": "Connect Groq",
            "steps": [
                "Create a key at console.groq.com.",
                "Paste the key → pick Llama on Groq → Test → Activate.",
            ],
            "links": [{"label": "Get API key", "url": "https://console.groq.com/keys"}],
        },
        "presets": [
            {
                "id": "groq-llama",
                "label": "Llama 3.3 70B (Groq)",
                "model": "llama-3.3-70b-versatile",
                "tier": "quality",
                "ram": "cloud",
            },
            {
                "id": "groq-8b",
                "label": "Llama 3.1 8B Instant",
                "model": "llama-3.1-8b-instant",
                "tier": "fast",
                "ram": "cloud",
            },
        ],
    },
    {
        "id": "openai-compatible",
        "name": "Custom / LM Studio",
        "tagline": "Any OpenAI-compatible endpoint",
        "difficulty": "advanced",
        "cost": "Yours",
        "needs_api_key": False,
        "needs_install": True,
        "default_base_url": "http://127.0.0.1:1234/v1",
        "secret_name": "OPENAI_API_KEY",
        "install": {
            "title": "Point at your server",
            "steps": [
                "Start LM Studio / vLLM / LocalAI with an OpenAI-compatible API.",
                "Enter the Base URL (usually ends with /v1).",
                "Enter the model id your server expects → Test → Activate.",
            ],
            "links": [
                {"label": "LM Studio", "url": "https://lmstudio.ai/"},
            ],
        },
        "presets": [
            {
                "id": "lmstudio-local",
                "label": "LM Studio default",
                "model": "local-model",
                "tier": "custom",
                "ram": "your PC",
            },
        ],
    },
]


def get_catalog() -> list[dict[str, Any]]:
    return PROVIDER_CATALOG


def get_provider(provider_id: str) -> dict[str, Any] | None:
    for p in PROVIDER_CATALOG:
        if p["id"] == provider_id:
            return p
    return None
