# Production readiness plan for MiniLisa

## Goal

Prepare the application for a safe production handoff and future deployment while keeping local development usable on Python 3.12 and an OpenRouter-backed model setup.

## Current baseline

- Python target: 3.12
- App stack: FastAPI + SQLAlchemy + Redis + LiteLLM
- AI model path: OpenRouter via the LiteLLM adapter and configurable OpenRouter model names
- The repo is intended to be GitHub-ready and continues from another station without requiring a full environment rebuild

## Immediate production actions

### 1. Model and AI configuration

- Use OpenRouter as the default model provider for development and staging.
- Store the OpenRouter API key in `.env` or a secret manager; never commit it.
- Add explicit model health checks for:
  - chat model availability,
  - embedding model availability,
  - timeouts and retry budgets,
  - fallback behavior when OpenRouter is unreachable.

### 2. Security hardening

- Require JWT authentication for all protected endpoints by default.
- Remove or gate any silent fallback to a demo user when no auth header is present.
- Keep CORS restricted to an allow-list, never `*` in production.
- Store runtime secrets in a proper secret manager, not in committed files.
- Keep upload validation active: extension check, size check, header validation, malware scan integration, and quarantine workflow.
  - The scanner is pluggable via `VIRUS_SCANNER_TYPE`: `mock` (EICAR-only, dev/test) or `clamd` (real ClamAV over TCP, fail-closed). Production must use `clamd` with `ALLOW_MOCK_VIRUS_SCANNER=false`.

### 3. Data and workflow durability

- Move workflow state away from process-memory-only storage.
- Use a durable checkpoint table or persisted state store.
- Use an outbox pattern so database writes and event publication remain consistent.
- Add event consumer groups and dead-letter handling for Redis Streams or worker queues.
- Make ERP posting and human approval actions idempotent.

### 4. Reliability and operations

- Add retry budgets for LLM calls and external system calls.
- Add dead-letter queues and alerting on repeated failures.
- Track correlation IDs end-to-end across the API, workflow engine, tools, and external adapters.
- Add structured logging and key metrics: command latency, queue lag, approval rate, rejection rate, failure rate, and LLM cost.

### 5. Data model and migrations

- Use Alembic migrations for schema changes instead of relying on `create_all()` in startup.
- Apply the checked-in initial revision with `alembic upgrade head` before production startup.
- Back up PostgreSQL with `pg_dump` before migrations and validate restores in an isolated database.
- Configure retention policies for invoices, audit logs, uploaded artifacts, and workflow checkpoints.

### 6. Deployment topology

- Separate API and worker processes.
- Use managed PostgreSQL and Redis in non-local environments.
- Place the API behind TLS termination and a reverse proxy or load balancer.
- Run containers as non-root users and enforce resource limits.

## Recommended rollout order

1. Stabilize local config and model connectivity with OpenRouter.
2. Enforce auth and secure defaults.
3. Persist checkpoints and event outbox.
4. Add observability and retries.
5. Introduce production deployment environment and secret management.
6. Run smoke tests and production security review before opening to users.

## Handover notes for the next station

- The project is intentionally left in a GitHub-safe state, not a live-production deployment state.
- The next station should focus on: durable workflow storage, production deployment configuration, and OpenRouter connectivity validation.
- Before production release, review environment variables and secret rotation for all non-local credentials.

## OpenRouter configuration

Example environment settings for local development:

```env
LLM_PROVIDER=openrouter
LLM_MODEL=google/gemma-4-26b-a4b-it:free
EMBEDDING_MODEL=openai/text-embedding-3-small
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-openrouter-api-key
LLM_MAX_TOKENS=4096
```

## Exit criteria for the next phase

The next phase is ready when all of the following are true:

- API starts without demo auth fallback,
- OpenRouter chat and embedding endpoints are reachable,
- workflow state persists across restarts,
- queue/event reliability is implemented,
- CI tests pass in the chosen environment,
- secrets are managed outside the repository.
