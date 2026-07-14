# Installation

## Docker (recommended)

```bash
cp .env.example .env
# generate secrets:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose up --build
```

Open `http://localhost:8000` and complete the setup wizard.

## Bare metal

1. Python 3.11+ and Node 20+
2. `pip install -e backend/[dev]`
3. `cd frontend && npm install && npm run build`
4. `uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir backend/src`

## Ollama

Install [Ollama](https://ollama.com), pull a model (`ollama pull llama3.2:3b`), then select **ollama** in the wizard.
