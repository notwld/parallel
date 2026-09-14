# Work log

## 2026-09-14 — Initialization in progress

- Read all 449 paragraphs and 64 tables in the original DOCX and saved an ordered transcription. Preserved the original file.
- Recorded the user's Earth-2097 premise, architecture invariants, deferred scope, and explicit unresolved choices.
- Created Django/React foundation, UUID account migration, Compose services, smoke checks, and a CI definition.
- Observed health tests fail with 404 before implementing the endpoint; all four backend tests pass after implementation. System check and migration drift check pass.
- Frontend typecheck and Vite production build passed.
- User additionally requested Ponytail, Impeccable, and Spec Kit installed for this project. Installation is P046.
- Container verification, skill verification, backlog validation, and Git checkpoint remain in progress. This entry is not a completion claim.

## 2026-09-14 — P000 and P046 completed

Closed out both interrupted tasks by verifying the parts the previous session left unproven.

- Verified: 4 backend smoke tests pass (SQLite settings), `makemigrations --check` clean, `manage.py check` clean, frontend typecheck + Vite build pass, `check_backlog.py` validates 47 tasks, `docker compose config` valid.
- Services actually started and exercised: PostgreSQL 17 (all migrations applied, confirmed via `showmigrations` in the container), Redis 7.4 healthy, Celery worker answered `inspect ping`, backend health endpoint 200, Vite dev server 200 and proxying `/api` to the backend.
- Fixed a real startup failure: the frontend container exited with `Cannot find module '@rolldown/binding-linux-x64-gnu'`. Root cause is npm/cli#4828, not a bad Dockerfile step. Added `npm install --include=optional --no-save` after `npm ci` in `frontend/Dockerfile` and `.github/workflows/ci.yml` (D015), then proved it with `docker compose build --no-cache frontend`.
- Wrote `readme.md`, which was empty despite `AGENTS.md` citing it for commands.
- Wrote `docs/SKILLS.md` with Ponytail, Impeccable (skill 0.1.5, CLI 4.0.0), and Spec Kit 1.0.5 provenance, commands, reload behavior, and unconfigured items. Added a skills section to `AGENTS.md` so Codex and Claude Code discover them. Recorded D014: one canonical `.cursor/skills/` path rather than per-tool copies.
- Removed a dangling `docs/superpowers/plans/2026-09-14-world-foundation.md` reference from P002; that file was never created.
- Changed paths: `readme.md`, `docs/SKILLS.md`, `docs/STATUS.md`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `TASKS.md`, `AGENTS.md`, `frontend/Dockerfile`, `.github/workflows/ci.yml`.
- Unresolved: CI has never run (no remote configured, D013). PostgreSQL was exercised only through migrations and the health path; no relational integrity or concurrency tests exist yet.
- Next exact action: choose P001 or P002, set it `in_progress` in `TASKS.md`, and read its specification sections.

## 2026-09-14 — P001 completed

Added `/api/v1/ready/` with a bounded PostgreSQL `SELECT 1` and Redis `PING` (1s socket timeouts). Failures return `{"status":"unavailable"}` 503 with no exception text, hosts, or credentials. `/api/v1/health/` remains process-only. Compose backend healthcheck now hits `/ready/`. CI backend job has a Redis 7.4 service and `REDIS_URL`.

- Tests: `/ready/` 404d before the view existed. After: SQLite smoke `11 tests, OK (skipped=1 live PG+Redis)`. PostgreSQL via Compose: `11 tests, OK` including live 200 and independent DB/Redis 503 cases. `makemigrations --check` clean. `manage.py check` clean. `docker compose config --quiet` valid.
- Live: rebuilt backend; healthcheck reports healthy. `showmigrations` shows accounts/admin/auth/contenttypes/sessions applied. Redis healthy. Celery `inspect ping` → 1 node online (this does not prove queued domain jobs exist). `GET /api/v1/ready/` 200 on :8000 and via Vite proxy :5173.
- Changed paths: `backend/config/urls.py`, `backend/tests/test_readiness.py`, `backend/config/settings/base.py`, `docker-compose.yml`, `.github/workflows/ci.yml`, `readme.md`, `TASKS.md`, `docs/STATUS.md`, `docs/WORKLOG.md`.
- Unresolved: CI has never run (no remote, D013). Previous P000/P046 files remain uncommitted.
- Next exact action: start P002 (world/character models). Set it `in_progress`, read spec 2.3, 4, 6.2–6.3, 6.12, 11.2.

## 2026-09-14 — P002 completed

Added World, WorldMembership, RoleTemplate, Location, and Character with UUID primary keys. Status and visibility are separate on World. Database unique constraints enforce one membership and one character per account/world, unique role names and location slugs per world. Model `save()`/`clean()` is the write boundary: cross-world role/location/parent assignment and location parent cycles raise ValidationError. `RoleTemplate.max_slots` is the slot-limit field; P004 must `SELECT FOR UPDATE` that row when allocating. No public mutation API.

- Tests: import failed before the apps existed. After: SQLite `22 tests, OK (skipped=1)`. PostgreSQL Compose `22 tests, OK`. `makemigrations --check` clean. `worlds.0001_initial` and `characters.0001_initial` applied on Compose PostgreSQL.
- Changed paths: `backend/apps/worlds/`, `backend/apps/characters/`, `backend/config/settings/base.py`, `backend/tests/test_world_models.py`, `TASKS.md`, `docs/STATUS.md`, `docs/WORKLOG.md`, `docs/ARCHITECTURE.md`.
- Skipped: django-mptt, organization FK (P005), slot allocation service (P004), any world API.
- Next exact action: start P003 (audit + transactional outbox). Set it `in_progress`, read spec 2.3, 10.4, 10.6, 11.5.

## 2026-09-14 — LangChain / LangGraph / OpenRouter stub

User asked to add LangChain, LangGraph, and OpenRouter, then push to GitHub.

- Installed langchain 1.4.0, langgraph 1.2.11, langchain-openrouter 0.2.8. `backend/common/ai/` has FakeProvider (no key) and a one-node LangGraph proposal graph with no tools. Live `ChatOpenRouter` is not constructed unless `OPENROUTER_API_KEY` is set. No API or worker calls it.
- Tests: 4 AI tests pass without network. Full SQLite suite 26 OK (1 skipped).
- `websockets` lock moved 17.1 → 16.1.1 because langgraph-sdk requires `<17`.
- langchain_core warns that Pydantic V1 is incompatible with Python 3.14; imports still work.
- Recorded D016. P019 remains todo.
- Changed paths: `backend/common/ai/`, `backend/tests/test_ai_provider.py`, `backend/requirements.txt`, `backend/requirements.in`, `backend/config/settings/base.py`, `.env.example`, `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, `docs/STATUS.md`, `docs/WORKLOG.md`, `TASKS.md`, `readme.md`.
- Next exact action after push: P003.
