# AI Reliability & Evaluation Platform

Evaluate multiple LLMs on the same versioned dataset, compare quality, latency, cost and failure rate, detect regressions against a baseline, and get an explainable model recommendation.

Status: **Day 1 of 7** - scaffold, schema, health endpoints, worker skeleton, mock adapter.

## Stack

FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis + RQ, React + TypeScript + Vite, Docker Compose. LiteLLM arrives on Day 4; until then all model calls are deterministic mocks (demo mode).

## Quick start

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000 (`/health`, `/ready`, `/docs`)

The `api` container runs `alembic upgrade head` on start.

## Local development without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, RQ worker, tests
frontend/   React + Vite dashboard shell
datasets/   Synthetic demo dataset
infra/      docker-compose.yml
```

## Security notes

- Secrets live only in `.env` (git-ignored); `.env.example` has placeholders.
- Live LLM calls are off by default (`ENABLE_LIVE_LLM=false`).
- CORS is restricted to `CORS_ORIGINS`.

## Roadmap

See the project specification: P0 MVP over 7 days; judge models, auth, scheduling are P1+.
