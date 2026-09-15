# Decisions and open product questions

Recorded 2026-09-14. These are working implementation defaults, not claims that the user resolved every question in section 21.2. Revisit at the specified task; do not silently change them.

| ID | Decision | Basis / revisit |
| --- | --- | --- |
| D001 | Keep one repository with backend and frontend. Start with the specified modular Django monolith. | Spec 1.2, 10, 16.4, Appendix B. |
| D002 | React + TypeScript + Vite, Python 3.14, Django 5.2 LTS, DRF, PostgreSQL 17, Redis 7.4, Celery, Channels. | Spec stack; versions are setup choices. Package locks contain resolved versions. Container patch tags float; pin image digests at P036. |
| D003 | Earth-2097 is the flagship. User examples override the DOCX's illustrative Earth-1842 setting. | User direction; seed at P011. |
| D004 | One character per account per world. Powerful role slots are finite and allocated by moderator invitation for alpha. | Spec 6.3, 8.2; enforce at P002/P004. |
| D005 | Same-origin browser deployment, HttpOnly session cookies, CSRF. Vite proxies API requests in development. OAuth provider and outbound email delivery are still unselected external prerequisites for P004; email/password session APIs ship without them. | Spec 12.4. OAuth provider choice remains open. |
| D006 | Private notes and DMs do not enter simulation AI by default. Explicitly shared actions may. Moderator access is separate and audited. | Spec 9.5, 15.3; privacy disclosure at P017/P031. |
| D007 | AI disabled until typed validation and audience projections exist. Deterministic fake provider when `OPENROUTER_API_KEY` is empty. OpenRouter is the chosen live vendor (D016); do not mark P019 done until the typed contract and a recorded live eval exist. | Spec 9, 20.3; user 2026-09-14. |
| D008 | Major irreversible consequences require review. Initial proposal: severity >= 0.8 plus authored high-impact action classes; configurable per world. | Spec 6.9, 15.4. Threshold is a proposed default to review at P021/P030. |
| D009 | UTC real timestamps plus explicit world time. Proposed clock starts at 2097-01-01 and progresses 1:1 while live, pauses when paused. | Spec 11.2, 21.2. Confirm pacing before P011 seed is finalized. |
| D010 | Original DOCX remains unchanged. Ordered Markdown extraction is searchable source context. TASKS.md owns task status. | User request for cross-tool continuation. |
| D011 | Implement secrets and provenance before the polished social feed. | Spec 20.3 is prioritized over the illustrative 12-week sequencing in 20.2. |
| D012 | SQLite is allowed only for explicit fast test settings. Development/integration/production use PostgreSQL. | Transactional consistency requirements. |
| D013 | No software license is selected on the user's behalf. Remote is `https://github.com/notwld/parallel.git`; public/private and release remain the user's GitHub settings. | User asked to push on 2026-09-14. |
| D014 | Skill bodies live only in `.cursor/skills/`. Codex and Claude Code reach them through `AGENTS.md`/`CLAUDE.md` pointers instead of copies in `.agents/skills/` and `.claude/skills/`. | P046. Copying Impeccable's reference tree and platform binary per tool triples a large tree for no behavioral gain. Revisit if a tool needs native auto-activation. |
| D015 | `npm ci` is followed by `npm install --include=optional --no-save` in the frontend image and CI. | npm/cli#4828 intermittently skips the platform's native Rolldown binding, which made the frontend container exit at startup. Remove when npm fixes the bug. |
| D016 | Live model access is OpenRouter through `langchain-openrouter` and a one-node LangGraph proposal graph with no tools. Default model `openai/gpt-4o-mini`. | User request 2026-09-14. `langgraph-sdk` pins `websockets<17`, so the lock uses 16.1.1. P019 still owns AIJob, schemas, and a live eval. |
| D017 | Stage-1 realtime chat (`apps/chat`) is account-scoped and world-agnostic. Server/channel/message IDs are snowflakes; people are UUID FKs to `accounts.User`. Messages live in PostgreSQL; Scylla/OpenSearch deferred. Daphne serves HTTP+WebSocket. Design notes live in `docs/source/discord.md`; product naming is chat/servers, not Discord. | User 2026-09-15. Revisit message store when timeline volume demands it. |

## Questions that block their owning task, not initialization

- **P004/P030:** which OAuth provider, email delivery service, minimum age/content rating, and account recovery policy? Implement provider-independent contracts first; external login cannot be called finished without a tested provider.
- **P011/P030:** confirm world clock, powerful role allocation, and how often system NPCs may knowingly circulate false claims. Default seed fixture should identify its public/claim/canonical layers explicitly.
- **P017/P029/P031:** determine private-message moderation access and disclosure; select prompt/log, account, evidence, and moderation retention periods. Avoid copying raw private data into analytics or long-term model logs.
- **P014/P029:** select object storage and scanning service before enabling uploads to users. Text-only development is acceptable; it does not fulfill alpha evidence-upload acceptance.
- **P019/P023:** OpenRouter is selected (D016). Still need typed validation, AIJob audit, budget ceilings, and a recorded live contract eval before calling P019 done. Failed or paused generation must leave accepted actions recoverable.
- **P036/P037:** select hosting, domain, backup retention/RPO/RTO, and release access. Perform the spec's name/trademark/domain checks before public launch.

## Version references checked during initialization

- [Django 5.2 release compatibility](https://docs.djangoproject.com/en/5.2/releases/5.2/)
- [Django supported releases](https://www.djangoproject.com/download/)
- [DRF requirements](https://www.django-rest-framework.org/)
- [Vite runtime requirements](https://vite.dev/guide/)

Use the checked-in locks to reproduce the current setup. Recheck upstream compatibility before changing major versions.
