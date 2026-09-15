# Parallel

A persistent multiplayer world where characters hold different, incomplete knowledge. Canonical truth is server-only; what a character believes, shares, or leaks is separate from what is true. See `docs/PRODUCT.md` for the Earth-2097 direction and `docs/ARCHITECTURE.md` for boundaries.

Only the foundation exists today: a Django/DRF backend with UUID accounts, worlds/characters, knowledge/orgs/chat, and a React SPA shell (TanStack Query/Router, Axios, Tailwind/shadcn). LangChain/LangGraph/OpenRouter are installed; they stay idle unless `OPENROUTER_API_KEY` is set, and they are not used by any API yet. Full gameplay UI is still backlog. `TASKS.md` is the authoritative backlog.

## Agents and contributors start here

Read `AGENTS.md`, then `docs/HANDOFF.md`, `docs/STATUS.md`, `docs/DECISIONS.md`, and `TASKS.md`. Run `python scripts/check_backlog.py` and resume the `in_progress` task before starting anything new.

## Requirements

Python 3.14, Node.js 22.12+, and Docker with Compose. Verified on Windows with Python 3.14.6, Node 24.19.0, and Docker 29.7.2.

## Local setup

```bash
cp .env.example .env          # Windows: Copy-Item .env.example .env
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt   # Linux/macOS: .venv/bin/python
npm --prefix frontend ci
```

`.env` holds local-only development values. Never commit it or put real credentials in it.

## Run the stack

```bash
docker compose up -d --build
```

This starts PostgreSQL 17, Redis 7.4, a one-shot `migrate` job, the API (Daphne HTTP+WebSocket) on <http://127.0.0.1:8000>, a Celery worker, and the Vite dev server on <http://127.0.0.1:5173>. The dev server proxies `/api` to the backend, so use port 5173 in the browser. Stop with `docker compose down`; add `-v` to discard the database volume.

Realtime chat (account-scoped servers/channels/DMs) is at `/api/v1/chat/` and `ws://…/ws/chat/channels/<id>/`.

## Checks

```bash
.venv/Scripts/python backend/manage.py test tests --settings=config.settings.test
.venv/Scripts/python backend/manage.py makemigrations --check --dry-run --settings=config.settings.test
.venv/Scripts/python backend/manage.py check --settings=config.settings.test
npm --prefix frontend run build     # runs typecheck, then Vite build
python scripts/check_backlog.py
docker compose config --quiet
```

The `config.settings.test` suite runs on in-memory SQLite and is a fast smoke check only. Relational integrity, locking, concurrency, JSON, and outbox behavior must be verified against PostgreSQL — run those against the Compose stack:

```bash
docker compose exec backend python manage.py showmigrations
docker compose exec worker celery -A config inspect ping
```

`/api/v1/health/` is process liveness only. `/api/v1/ready/` returns 200 after PostgreSQL `SELECT 1` and Redis `PING`, otherwise a generic 503. A worker ping does not mean domain jobs exist.

## Known environment issue

`npm ci` sometimes skips the platform's native Rolldown binding that Vite 8 needs ([npm/cli#4828](https://github.com/npm/cli/issues/4828)), which makes the frontend container exit immediately with `Cannot find module '@rolldown/binding-linux-x64-gnu'`. The Dockerfile and CI follow `npm ci` with `npm install --include=optional --no-save` to refetch it without rewriting the lockfile. If a host install hits the same failure, run that command in `frontend/`.
