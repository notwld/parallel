# Parallel agent instructions

This repository is the durable project memory. Work must remain continuable without the original chat, account, model, editor, or any paid AI provider.

## Start every session

1. Read `docs/HANDOFF.md`, `docs/STATUS.md`, `docs/DECISIONS.md`, and `TASKS.md`.
2. Inspect `git status --short` and the current changes before editing. Preserve work from people and previous agents.
3. Run `python scripts/check_backlog.py`. Resume the `in_progress` task first; otherwise choose an unblocked `todo` task whose dependencies are `done`. Read its source specification sections in `docs/source/specification.md`.
4. Set that task's status to `in_progress` in `TASKS.md`. Write its ID, intended changes, and immediate next step in `docs/STATUS.md` BEFORE implementing it.
5. Work on one reviewable task at a time. This repository does not require any agent framework or installed skill package. Tools may use their own equivalent workflows.

## Product and architecture

- Latest explicit user direction takes precedence over derived plans. The original DOCX is the source specification; the Markdown transcription provides searchable text. `docs/PRODUCT.md` records the user's Earth-2097 direction and alpha scope.
- Django/DRF modular monolith, PostgreSQL, Redis/Celery, Channels, React/TypeScript. Do not replace the stack or introduce microservices without a documented reason and user agreement.
- One curated flagship world and one character per account per world for alpha. The data model must still enforce world boundaries from day one.
- Canonical facts are server-only. Claims, evidence, and each character's knowledge are distinct objects. Never send truth flags, hidden fact IDs, or confidential source identities to unauthorized audiences.
- Use positive allowlist projections before API serialization, AI context, caching, search, exports, notifications, and WebSocket delivery. Backend authorization is authoritative.
- Every world mutation must have actor, world, cause, timestamp, and idempotency information in an immutable event or audit record. Use atomic transactions and a transactional outbox; handlers must tolerate duplicate delivery.
- AI proposes typed candidates. Deterministic server services validate and commit. No SQL, arbitrary code, network tools, or direct writes from model output.
- Public renderers receive public projections only. Store provenance IDs and model/prompt versions internally. Private notes and DMs stay out of simulation context by default.
- Keep credentials out of Git. Browser credentials use HttpOnly sessions and CSRF; do not store bearer tokens or private intel in localStorage.
- Add app modules when their task needs them. Keep business services out of serializers. Do not implement deferred economy, governance, NPC swarms, or 3D maps ahead of the core loop.

## Verify and checkpoint

- For nontrivial behavior, first add a focused regression/acceptance test and verify its failure. Exercise actual behavior and negative authorization cases.
- `python backend/manage.py test tests --settings=config.settings.test` is a fast SQLite smoke suite ONLY. PostgreSQL is required for relational integrity, locking, concurrency, JSON, and outbox integration tests. Never describe SQLite checks as proof of PostgreSQL behavior.
- Run relevant tests, migrations checks, and frontend build. Use commands in `readme.md`; record exact results and anything untested.
- Checkpoint after each meaningful step, before switching tasks, and before the context/usage limit. Update `docs/STATUS.md` even if tests fail or work is incomplete.
- Mark `done` only when that task's acceptance criteria have evidence. If blocked, record the concrete blocker and what would resolve it; continue an independent eligible task if possible.
- Keep statuses authoritative in `TASKS.md`. `docs/STATUS.md` is a narrative snapshot, not a second task database.
- Append a concise entry to `docs/WORKLOG.md` on task completion or interruption. Record changed paths, commands/results, unresolved issues, and the next exact action.
- Make a local commit for a completed task when Git is available. Never discard uncommitted work, fabricate test outcomes, amend another person's commits, or push/deploy merely to finish a task.
- Before stopping, leave a next step that another agent can execute immediately. An interrupted session's dirty working tree is part of the handoff.
