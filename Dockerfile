# syntax=docker/dockerfile:1
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FINAGENT_DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY backend/ /app/backend/
RUN pip install --no-cache-dir /app/backend
COPY --from=frontend /app/frontend/dist /app/frontend/dist
COPY config/config.example.yaml /app/config/config.example.yaml
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "finagent.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/backend/src"]
