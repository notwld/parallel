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

## 2026-09-15 — P003 completed

Immutable audit + transactional outbox primitives.

- `AuditRecord`: append-only (save/delete/QS update blocked), deletion-safe `actor_type`/`actor_id`/`actor_label` (no FK to User), unique `(world, idempotency_key)` and `(world, sequence)`. Staff-only `list_audit_for_world`.
- `OutboxEvent`: same identity fields + delivery state; payload immutable; `mark_outbox_delivered` may update delivery fields only. Partial index on pending rows.
- `WorldSequence` + `record_world_mutation`: one transaction locks the sequence row, optional `mutate()`, then writes audit+outbox. Same key/same payload returns originals; changed payload raises `IdempotencyConflict`.
- Tests: SQLite 7 OK + 1 skip; Compose PostgreSQL 8/8 OK (concurrent sequences 1..8). Thread workers close connections so test DB teardown succeeds.
- Skipped: django-pgtrigger / DB triggers (app write boundary only), Celery outbox relay (P009), public APIs.
- Changed paths: `backend/apps/audit/`, `backend/apps/events/`, `backend/config/settings/base.py`, `backend/tests/test_event_atomicity.py`, `TASKS.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/WORKLOG.md`.
- Next exact action: start P004. Set `in_progress`, read spec 5.1, 6.1–6.3, 12.4–12.5.

## 2026-09-15 — P004 completed

Session auth + audited world join/onboarding APIs.

- Auth: CSRF bootstrap; signup/verify/login/logout/password-reset; preferences; session list/revoke; per-IP auth rate limit. Login CSRF enforced via `@csrf_protect` (not DRF anonymous bypass). OAuth returns empty providers (D005 prerequisite).
- Worlds: public landing (claimable roles only); `POST .../join/` with Idempotency-Key; character profile omits account identity.
- `join_world`: paused/invite-only/role-invite/slot checks; `SELECT FOR UPDATE` on role; membership+character via `record_world_mutation`.
- Tests: SQLite onboarding 9 OK + concurrent skip; full suite 44 OK (3 skipped). PG: concurrent join keeps one slot holder; concurrent sequence still OK.
- Skipped: real OAuth provider, production email (tokens returned in local responses), frontend screens (P013).
- Changed paths: `backend/apps/accounts/`, `backend/apps/characters/services.py`, `backend/apps/worlds/api.py`, `backend/apps/worlds/urls.py`, `backend/apps/worlds/models.py`, `backend/config/urls.py`, `backend/config/settings/`, `backend/tests/test_onboarding.py`, `TASKS.md`, `docs/*`.
- Next exact action: start P005 (organizations).

## 2026-09-15 — P005 interrupted; Discord Stage 1 started

User requested Daphne + Discord-like guilds/channels/DMs from `docs/source/discord.md` (Stage 1). P005 reset to `todo` (draft org models/services exist; no tests). Recorded D017. Backlog P050–P055.

- Next exact action: P050 Daphne install, then P051–P055.

## 2026-09-15 — P050–P055 completed (realtime chat)

Account-scoped chat module `apps/chat` (product naming: servers/channels/DMs—not Discord). Stage 1 per design notes + D017.

- Daphne 4.2.3; `daphne` first in INSTALLED_APPS; ProtocolTypeRouter HTTP+WS; Dockerfile CMD Daphne.
- Models: Server, ServerMember, Role bitfield, Channel, overwrites, DmParticipant, Message (channel_id, id DESC), Invite, ServerBan, ReadState. Snowflake IDs.
- REST `/api/v1/chat/…`; WS `/ws/chat/channels/<id>/` after VIEW_CHANNEL check; Redis group `chat.channel.{id}`.
- Tests: `tests.test_chat_security` (perms, DM isolation, invite/ban, outsider 403, WS accept/reject). Full suite 51 OK (3 skipped).
- Skipped: Scylla/search/voice/threads UI; world-linked P017 messaging.
- Changed paths: `backend/apps/chat/`, `backend/config/asgi.py`, `backend/Dockerfile`, `backend/requirements.*`, `backend/config/settings/base.py`, `backend/config/urls.py`, `backend/tests/test_chat_security.py`, `TASKS.md`, `docs/*`.
- Next exact action: resume P005 or other eligible todo.

## 2026-09-15 — Chat typing indicators

Discord-shaped ephemeral typing (official API: POST typing lasts 10s, Gateway `TYPING_START`; no durable DB).

- `POST /api/v1/chat/channels/<id>/typing/` → 204; requires SEND_MESSAGES; broadcasts `typing.start`.
- `GET …/typing/` → current typers (Redis/cache TTL; excludes self).
- WS client may send `{"type":"typing.start"}`; same broadcast (`expires_in: 10`).
- Tests cover REST + WS. Clients should refresh while typing and clear on expiry or `message.create` from that user.

## 2026-09-15 — P005 completed

World-scoped organizations with capability policies.

- Models: Organization, OrgMembership, OrgInvitation; cross-world character rejected.
- Policies: publish_as_org / read_internal / manage / leader; revocation clears caps immediately.
- Services use `record_world_mutation`; leadership via `select_for_update` + in-Python leader count (SQLite-safe).
- Tests: `test_org_authority` — member cannot publish as org, outsider denied internal, revoke, cross-world, second leader rejected; PG concurrent leadership OK.
- Full suite: 58 OK (4 skipped). Next: P006 knowledge models.

## 2026-09-15 — P006 completed

Epistemic core models (Fact/Claim/KnowledgeEdge/Evidence/ClaimEvidenceLink/Transmission).

- Fact is server-only (no `apps.knowledge.serializers`). Claim has optional `linked_fact` never included in `ordinary_claim_read`.
- Mutate creates derived claim + Transmission; source proposition unchanged.
- XOR owner (character|org), confidence 0–1, world consistency, evidence relations supports/contradicts/context.
- Indexes: owner/acquired_at, claim+owner, world+verification/created.
- Tests: 7 OK. Full suite 65 OK (4 skipped). Binary upload deferred (P014).
- Next: P007 audience projections + leak suite.

## 2026-09-15 — P007 completed

Audience allowlist projections and first knowledge leak suite.

- `project_claim_for_character` builds allowlisted dicts (no pop-secrets). Confidential sources → `Confidential source` without ref.
- World membership before character/object access; missing vs unauthorized → identical 404 body.
- Intel API under `/api/v1/knowledge/worlds/<slug>/intel/…` (list/search, claim detail, evidence detail).
- `tests/security/test_knowledge_leaks.py`: canary hidden from peer list/detail/search/evidence and foreign world; revoke denies; owner sees claim without fact ids.
- Next: P008 sharing/transmission services.

## 2026-09-15 — Frontend foundation + authz/filter decisions

- D018: capability-based backend authz; FE mirrors `allowed_actions` only.
- D019: Vite/React19, Tailwind v4 + shadcn, Axios+CSRF, TanStack Query/Router, Zod, RHF; django-filter defaults.
- Structure: `src/app`, `src/api`, `src/features/{home,auth,worlds}`, `src/components/{ui,layout}`.
- CORS: `django-cors-headers`, credentialed origins from env; tests in `tests/test_cors.py`.
- Build: frontend typecheck+build OK. Skipped: full P012 OpenAPI client, P013 onboarding UI, Zustand.
- Next: P008 or wire auth/world routes on this shell.

## 2026-09-15 — FE async/WS layer + auth surfaces

- FE066: ChannelSocket (backoff+jitter, ping/pong, outbound queue), TanStack Query online mode + mutation scopes, idempotency helper.
- FE060/061: QueryState/skeletons, AppShell, login/signup/reset/account+sessions.
- Placeholders for `/w/$worldSlug` and `/chat` until FE062–063.
- Build: `npm run build` OK.
- Next: FE062 world landing/join, FE063 chat+WS, FE064 intel.

## 2026-09-15 — FE062–FE065 pages for shipped APIs

Used [API inventory](f11deff3-78e4-4625-a8cf-f2512b0dafe6) to scope UI to existing HTTP/WS only (no org UI).

- Worlds: landing/join/character (`Idempotency-Key`, claimable roles only).
- Chat: servers/channels/messages + ChannelSocket catch-up; ConnectionBanner.
- Intel: claim list/search, claim + evidence detail (audience fields only).
- Router: `/w/$slug`, intel routes, `/chat`, `/chat/servers/$serverId`.
- `check_backlog.py` accepts FEnnn task IDs.
- Verify: `npm --prefix frontend run build` OK (typecheck + vite).
- Next: unblocked backend (e.g. P008) or live-backend FE polish; no org UI until org REST.

## 2026-09-15 — P008 completed

Sharing, derived rumors, and verification assessments without leaking canonical truth.

- `share_claim`: rejects private/off-record; confidential/shareable/public OK; Transmission + recipient edge atomically with audit/outbox; optional evidence SHARED + custody; weaker `derived_proposition` keeps source claim intact; idempotent key returns same transmission.
- `submit_verification_assessment`: updates character edge verification (+ optional link assessment); outbox payload has no fact ids.
- API share/verify under intel claims; unknown/unauthorized → identical 404.
- Policies: `can_redistribute`; SHARED evidence access; projection `allowed_actions` omits share when blocked.
- Verify: `manage.py test tests.test_transmission tests.security.test_knowledge_leaks` → 12 OK (SQLite smoke).
- Next: P009 typed actions + outbox dispatch.

