# AI Reliability & Evaluation Platform

Run several LLMs over the same **versioned dataset**, score every answer, and compare them on quality, latency, token use, estimated cost and failure rate. Pick a **baseline run**, get **regression findings** with explanations, and see an **explainable model recommendation** that respects hard constraints.

Everything is private to the signed-in account. Demo mode runs deterministic mock models, so nothing calls a paid provider unless you opt in.

## What it does

- **Datasets and versions**: import JSON, immutable versions with a SHA-256 content hash; identical content is rejected.
- **Asynchronous runs**: a case x model matrix runs on a worker with bounded concurrency, retries only for transient errors, per-model spend caps, cancellation, and idempotent job delivery.
- **Scoring**: exact match, contains, regex, JSON Schema and classification evaluators. Unscorable cases are `null`, never zero.
- **Comparison**: per-model success/failure rate, quality, p50/p95 latency (successful calls), tokens, and estimated cost. Missing usage or price is shown as *unavailable*, never as 0.
- **Regression detection**: compares against a compatible baseline (same dataset content and profile) using configurable thresholds, with sample-size guards and severities.
- **Recommendation**: hard constraints first, then a documented weighted score (quality 0.60, latency 0.25, cost 0.15 by default). Each excluded model gets its reasons.
- **Case inspection**: prompt, expected output and every model's answer for one case.
- **Accounts**: email and password sign-in, private data per account, rate limits and quotas.

## Architecture

```mermaid
flowchart LR
    B[Browser<br/>React + Vite] -->|"/api (cookie session)"| P[Proxy<br/>nginx or Vercel rewrite]
    P --> A[FastAPI API]
    A --> DB[(PostgreSQL)]
    A -->|rate limits, queue| R[(Redis)]
    A -.->|inline mode| W
    R --> W[Evaluation worker<br/>RQ]
    W --> DB
    W -->|mock or LiteLLM| M[Model providers<br/>mock / Ollama / OpenAI ...]
```

A run moves through `queued -> running -> completed | completed_with_errors | failed | cancelled` with atomic compare-and-set transitions. When it finishes, per-model summaries are stored, and if a baseline is set the regression findings are computed and stored.

## Quick start (local, Docker)

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

- App: http://localhost:3000 (create an account on first visit; it comes with a private copy of the demo dataset)
- API docs: http://localhost:8000/docs
- Postgres is published on host port **5433** to avoid clashing with a local install.

Run compose from the repository root and pass `--env-file .env`; compose does not read the root `.env` when invoked from `infra/`.

Existing data from before accounts existed is claimed by the **first account you register**.

### Live models (optional)

Mock models are always available. To add a real one, set `ENABLE_LIVE_LLM=true` and `LIVE_MODELS` in `.env`. A free local option is [Ollama](https://ollama.com):

```bash
ollama pull llama3.2:3b
# .env
ENABLE_LIVE_LLM=true
LIVE_MODELS={"llama-local":"ollama/llama3.2:3b"}
OLLAMA_API_BASE=http://host.docker.internal:11434
LIVE_TIMEOUT_SECONDS=120
```

Local models report a cost of 0 through LiteLLM; hosted models are priced from LiteLLM's price map when it knows the model, otherwise the cost is *unavailable*.

## Accounts and security model

| Concern | How it is handled |
|---|---|
| Passwords | argon2id hashes; minimum 10 characters; the same error for every login failure; hashes are upgraded when parameters change |
| Sessions | signed token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` when `COOKIE_SECURE=true`); expires after `SESSION_DAYS`; bumping a user's `token_version` revokes it |
| CSRF | every state-changing `/api` call must carry `X-Requested-With: fetch`; browsers cannot add it cross-origin without a CORS preflight, which is denied |
| Data isolation | every dataset and run belongs to one account; another account's resources return `404`; idempotency keys are scoped per account |
| Abuse limits | per-address rate limits (general, run creation, sign-in, sign-up), per-account dataset quota and active-run cap, a global active-run cap, request size cap, no chunked uploads |
| Secrets | `.env` is git-ignored; production refuses to start with the development secret or insecure cookies |
| Logs | structured JSON with request IDs; query strings and credentials are never logged; provider errors are redacted |

Not implemented (see Limitations): email verification, password reset, roles, SSO.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL`, `REDIS_URL` | local | connections (`postgres://` URLs are accepted and normalised) |
| `ENVIRONMENT` | `development` | `production` enforces `SECRET_KEY` and `COOKIE_SECURE` |
| `SECRET_KEY` | dev key | signs sessions; use 32+ random characters in production |
| `COOKIE_SECURE` | `false` | set `true` behind HTTPS |
| `ALLOW_REGISTRATION` | `true` | close sign-up |
| `TRUSTED_PROXY_HOPS` | `0` | reverse proxies that append to `X-Forwarded-For` |
| `RUN_WORKER_INLINE` | `false` | run evaluations inside the API process (single-service hosting) |
| `DEMO_MODE` | `true` | seed the demo dataset for new accounts |
| `ENABLE_LIVE_LLM`, `LIVE_MODELS` | off | live providers via LiteLLM |
| `LIVE_BUDGET_USD_PER_MODEL` | `0.05` | per-run spend cap for each priced model |
| `MAX_ACTIVE_RUNS`, `MAX_ACTIVE_RUNS_GLOBAL`, `MAX_DATASETS_PER_USER` | 3, 10, 20 | quotas |
| `RATE_LIMIT_*`, `AUTH_*_PER_WINDOW` | see `config.py` | rate limits |
| `REGRESSION_*`, `RANK_*` | see `config.py` | regression thresholds, ranking constraints and weights |

## Cost controls

- Live calls are off by default; the public demo uses mock models only.
- Per-model USD cap per run (`LIVE_BUDGET_USD_PER_MODEL`, per-alias overrides). It applies to priced calls only, and calls already in flight can push spend slightly over.
- Per-run caps on models, cases, concurrency and duration; per-account run and dataset quotas; rate limits.
- Cost is an estimate from provider-reported usage and LiteLLM pricing. It is not an invoice.

## Testing and quality gates

```bash
# backend (needs Postgres; the test database is created if missing)
cd backend
pip install -e ".[dev,live]"
export TEST_DATABASE_URL=postgresql+psycopg://aireliability:change-me@localhost:5433/aireliability_test
ruff check app tests && pytest -q && pip-audit --skip-editable

# frontend
cd frontend
npm ci && npm run typecheck && npm run lint && npm test && npm run build && npm audit
```

CI (`.github/workflows/ci.yml`) runs the same checks and builds both production images on every push and pull request.

## Deployment

### A. Production-style Docker Compose

```bash
# .env.prod needs at least POSTGRES_PASSWORD and SECRET_KEY
docker compose -p aireliability-prod -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build
```

Serves the built frontend with nginx on http://localhost:8080 (nginx also proxies `/api`), runs the API and a separate worker from the production image, and publishes no database ports. Use `ENVIRONMENT=development COOKIE_SECURE=false` if you test over plain HTTP on a host other than `localhost`.

### B. Free hosting: Render (API) + Vercel (frontend)

Free-tier behaviour, per [Render's documentation](https://render.com/docs/free): a free web service **spins down after 15 idle minutes and takes about a minute to wake**; the free Postgres database **expires 30 days after creation** (1 GB, one per workspace); free Key Value is in-memory, so rate-limit counters reset on restart. Free workers are not offered, so the blueprint runs evaluations inside the API process (`RUN_WORKER_INLINE=true`; incomplete runs are resumed on start-up, which assumes a single API instance).

1. Push the repository to GitHub.
2. In Render choose **New > Blueprint**, select the repository, and when asked for `TRUSTED_PROXY_HOPS` enter `1`. [`render.yaml`](render.yaml) creates the database, the Key Value instance and the API service.
3. Note the API address. If it is not `https://ai-reliability-api.onrender.com`, edit both destinations in [`frontend/vercel.json`](frontend/vercel.json).
4. In Vercel choose **Add New > Project**, import the repository, set **Root Directory** to `frontend`, and deploy. Vercel forwards `/api/*` to Render, so the browser sees one origin and no CORS is needed.
5. Open the Vercel URL and create an account.
6. **Check the client address** the API sees, because rate limits are keyed on it. Sign in, then look at a recent request line in the Render logs: `client_ip` should be your own public address. If it shows an address that is not yours, increase `TRUSTED_PROXY_HOPS` by one and redeploy; repeat until it matches. Then confirm spoofing is ignored: `curl -H "X-Forwarded-For: 1.2.3.4" https://<your-vercel-url>/health`, and make sure the logged `client_ip` is not `1.2.3.4`.

The first request after an idle period is slow (the service is waking). The UI reports a gateway error with a Retry button in that case.

## API overview

Interactive docs are served at `/docs`. All endpoints except `/health`, `/ready` and `/api/v1/auth/*` need a session.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/v1/auth/register`, `login`, `logout`; `GET /api/v1/auth/me` |
| Datasets | `POST/GET /api/v1/datasets`, `GET /{id}`, `POST/GET /{id}/versions`, `GET /{id}/versions/{n}` |
| Runs | `POST/GET /api/v1/runs` (`Idempotency-Key` supported), `GET /{id}`, `POST /{id}/cancel`, `POST /{id}/baseline`, `GET /{id}/results`, `/{id}/cases/{key}` |
| Analysis | `GET /api/v1/runs/{id}/comparison`, `/regressions`, `/report` |
| Catalog | `GET /api/v1/models`, `/api/v1/evaluation-profiles` |

Errors always use `{code, message, details?}`. Validation errors are `400`, missing or foreign resources `404`, conflicts `409`, rate limits and quotas `429`.

## Limitations

- Mock models classify by keywords, so their results are only meaningful on the bundled demo dataset. They demonstrate the platform; they say nothing about real models.
- Small samples give weak signals. Regression checks and the recommendation are skipped or flagged below a minimum sample size, but they are not statistical tests.
- No email verification, password reset, roles or SSO. Sign-up is open by default (`ALLOW_REGISTRATION=false` closes it).
- Rate limits are per client address and depend on a correct `TRUSTED_PROXY_HOPS`.
- Inline-worker mode supports one API instance only.
- Estimated cost is not an invoice, and some providers report no usage.
- Judge-model evaluation and scheduled runs are not built.

## Roadmap

Email verification and password reset, OAuth sign-in, LLM-as-a-judge evaluators with calibration, scheduled and CI-triggered runs, per-user budgets for live models, exportable reports, and statistical confidence for small datasets.

## Repository layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, evaluators, worker, tests
frontend/   React + TypeScript dashboard, tests, production nginx config
datasets/   Synthetic demo dataset
infra/      Docker Compose files (development and production-style)
docs/       Specification and the smoke-test checklist
render.yaml Render Blueprint for the hosted demo
```
