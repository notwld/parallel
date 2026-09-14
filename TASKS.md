# Parallel implementation backlog

This file is the single authority for task status. Dependencies refer to stable IDs. Future file paths are targets, not a claim that the files exist. Read AGENTS.md and the referenced specification sections before implementing a task.

States: `todo`, `in_progress`, `blocked`, `done`, `deferred`. Only start a task when all dependencies are `done`. Run `python scripts/check_backlog.py` for eligible tasks. Record evidence in docs/WORKLOG.md; never check off a feature because its scaffolding exists.

## Milestones

- **Foundation:** P000. Initial project and durable handoff, not playable software.
- **Technical prototype:** P001–P011. Different knowledge, audited sharing, one persistent consequence.
- **Closed alpha:** P012–P037 plus all dependencies. One curated world for 50–500 participants.
- **Optional improvements:** P038–P039; do not delay the secrecy/consequence milestone.
- **Later roadmap:** P040–P045. Scope into smaller tasks before execution; not alpha commitments.
- **Project tooling:** P046. User-requested skills, independently verifiable.

For every feature task: add a focused failing acceptance test, implement the smallest working slice, run negative permission tests where applicable, update migrations/API schema, and checkpoint task status and handoff. PostgreSQL integration is mandatory for concurrency and transactional claims. Live-provider and load acceptance must state the environment and actual measured result.

## Foundation and technical prototype

### P000 — Initialize the portable project
Status: in_progress
Depends on: none
Spec: 1.2, 10, 14, 16.2, 20.2, Appendix B
Files: backend/config/, backend/apps/accounts/, frontend/, docker-compose.yml, .github/workflows/ci.yml, AGENTS.md, CLAUDE.md, .cursor/rules/parallel.mdc, docs/, TASKS.md

Deliver a locked Django/React starter, UUID account model/migration, local services, health check, CI definition, complete ordered source transcription, product/architecture decisions, and cross-tool task continuation.

Acceptance: clean dependency installation, backend smoke tests and migration check pass, frontend typecheck/build passes, Compose validates, and the backlog has no missing or cyclic dependencies. Document which services were actually started and tested. Preserve the DOCX unchanged. Record a local Git checkpoint.

### P001 — Verify infrastructure and dependency readiness
Status: todo
Depends on: P000
Spec: 16.1–16.2, 18.2, 22.1
Files: backend/config/urls.py, backend/tests/test_readiness.py, docker-compose.yml, .github/workflows/ci.yml, docs/WORKLOG.md

Add `/api/v1/ready/` that returns 200 only after a bounded PostgreSQL query and Redis ping; return a generic 503 without connection strings or exceptions otherwise. Keep `/health/` process-only. Record database migrations, Redis connectivity, Celery worker ping, and frontend API proxy behavior. Add a Redis service to CI when readiness tests require it.

Acceptance: test DB unavailable and Redis unavailable independently, both yield 503; healthy dependencies yield 200; readiness discloses no credentials. Run backend tests on PostgreSQL. A running worker alone does not prove queued domain jobs exist.

### P002 — Model worlds, roles, membership, and characters
Status: todo
Depends on: P000
Spec: 2.3, 4, 6.2–6.3, 6.12, 11.2
Files: backend/apps/worlds/models.py, backend/apps/characters/models.py, their migrations/, backend/tests/test_world_models.py, backend/config/settings/base.py

Create World, WorldMembership, RoleTemplate, Location, Character using UUIDs. Represent status separately from visibility. Store UTC/world clock, rules, simulation config, rating, creator, role capabilities, starter relations, and location hierarchy. One membership and one character per account/world. No public world mutation API yet; auditable services follow P003/P004.

Acceptance: uniqueness enforced by the database; cross-world role/location assignment rejected through the supported write boundary; location parent cycles rejected; role slot limits designed for atomic allocation; migrations apply forward. Start with the detailed P002 plan in docs/superpowers/plans/2026-09-14-world-foundation.md.

### P003 — Add immutable audit and transactional outbox primitives
Status: todo
Depends on: P002
Spec: 2.3, 10.4, 10.6, 11.5
Files: backend/apps/audit/models.py, backend/apps/events/models.py, backend/apps/events/services.py, backend/tests/test_event_atomicity.py

Create auditable change records and OutboxEvent with world, actor, cause, timestamp, idempotency key, payload hash, delivery state, and sequence. Define append-only write boundaries and operational protection against mutation. Define deletion-safe actor references. Add an atomic service helper used by subsequent world writes.

Acceptance: forced rollback leaves neither state nor outbox/audit writes; duplicate keys cannot create duplicate effects; ordinary app paths cannot edit or delete history; audit reads require privileged policy. Sequence allocation is safe under concurrent PostgreSQL transactions.

### P004 — Build authentication and audited onboarding APIs
Status: todo
Depends on: P002, P003
Spec: 5.1, 6.1–6.3, 12.4–12.5
Files: backend/apps/accounts/api.py, backend/apps/worlds/api.py, backend/apps/characters/services.py, backend/tests/test_onboarding.py

Implement signup, email verification/recovery, session login/logout, one chosen OAuth provider, active-session listing/revocation, account preferences, world landing/join, character creation/profile. Joining and role allocation must be atomic, audited, capability-safe, and idempotent. Add CSRF bootstrap and enforce login CSRF even for anonymous login requests. Allocate privileged role slots by invitation rather than trusting a client role string.

Acceptance: sign in/out/recover works; revoked sessions fail; duplicate/concurrent joins do not allocate extra characters or office slots; paused/invite-only restrictions apply; profile excludes account identity; CSRF-negative and auth-rate-limit tests pass. Provider/email selection is a documented external prerequisite.

### P005 — Model organizations and enforce capabilities
Status: todo
Depends on: P003, P004
Spec: 6.8, 11.2, 12.2
Files: backend/apps/organizations/models.py, backend/apps/organizations/policies.py, backend/apps/organizations/services.py, backend/tests/test_org_authority.py

Create organization types, memberships, roles/capabilities, public profiles, invitations, and audited role changes. Define object policies for active world membership and organization membership. Authorities must be rechecked on writes; neither client-supplied org identity nor a cached UI flag grants access.

Acceptance: ordinary member cannot publish as leader, outsider cannot read internal records, revocation takes effect immediately, and every referenced character belongs to the organization's world. Concurrent leadership allocation obeys authored constraints.

### P006 — Implement truth, claims, knowledge, and evidence metadata
Status: todo
Depends on: P003, P005
Spec: 3, 6.5, 11.2–11.4, 22.2
Files: backend/apps/knowledge/models.py, backend/apps/knowledge/services.py, backend/tests/test_knowledge_models.py

Implement Fact, Claim, KnowledgeEdge, Evidence, ClaimEvidenceLink, and Transmission. Fact has no public serializer. Enforce world consistency, confidence 0–1, vocabulary in spec 3.3, exactly one character/org owner, and provenance. Support competing claims and support/contradiction/context evidence relations. Claim mutation creates a derived claim and source link, not an overwrite.

Acceptance: false and contradictory claims persist without canonical truth in ordinary reads; invalid ownership/confidence/world references fail; provenance preserves the original source; indexes cover owner/world/time selectors. Binary upload is P014.

### P007 — Create audience projections and the first leak suite
Status: todo
Depends on: P006
Spec: 2.3, 9.7, 12.2–12.3, 15.2
Files: backend/apps/knowledge/selectors.py, backend/apps/knowledge/policies.py, backend/apps/knowledge/api.py, backend/tests/security/test_knowledge_leaks.py

Implement `project_claim_for_character(claim, character)` and intel/evidence selectors with explicit allowlists. Resolve world membership before object permissions. Omit canonical links, truth metadata, invisible evidence IDs, upstream confidential identities, and existence/count side channels. Return consistent unavailable-object responses.

Acceptance: A knows a canary secret; B and a different-world character cannot recover its text, IDs, truth state, or source through list/detail/search filters. Revoked access is denied. Test response bodies and nested metadata, not only visible UI labels. Reuse these projections in P020.

### P008 — Implement sharing, leaks, and verification provenance
Status: todo
Depends on: P007
Spec: 3.4–3.6, 6.5–6.7, 22.2
Files: backend/apps/knowledge/services.py, backend/apps/knowledge/api.py, backend/tests/test_transmission.py

Implement typed sharing with explicit recipient/audience and shareability checks. Record transmission and resulting KnowledgeEdge atomically with audit/outbox. Support a weaker derived claim while preserving the original assertion. Verification creates an evidence assessment/event with uncertainty; it never silently copies canonical truth. Confidential public citation uses a safe source projection.

Acceptance: approved sharing grants only the selected claim/evidence; unauthorized redistribution is rejected; retries do not duplicate transmission; source lineage is reconstructable by authorized staff; recipient sees only permitted evidence and identity.

### P009 — Accept typed actions and dispatch the outbox
Status: todo
Depends on: P008
Spec: 6.9, 9.3, 10.4–10.6, 12.5
Files: backend/apps/events/actions.py, backend/apps/events/api.py, backend/apps/events/tasks.py, backend/tests/test_action_idempotency.py

Add Action and a finite command registry beginning with publish/report/request-investigation. Validate schema, actor ownership, world status, capabilities, preconditions, and cost quotas before accepting. Implement `submit_action(actor, world, action_type, payload, idempotency_key)`. Persist outbox entries and dispatch with retry/backoff, durable deduplication, and failed-delivery inspection.

Acceptance: identical retry returns the original action, changed payload with same scoped key conflicts, concurrent submissions commit once, duplicate delivery causes one downstream effect, and crash-after-publish-before-mark-delivered is recoverable. Test transaction behavior on PostgreSQL.

### P010 — Commit deterministic consequences and causal history
Status: todo
Depends on: P009
Spec: 6.9, 6.11, 9.3–9.4, 11.2
Files: backend/apps/events/services.py, backend/apps/events/selectors.py, backend/apps/simulation/contracts.py, backend/tests/test_consequence_commit.py

Create WorldEvent, EventCause, narrow candidate schema, and a deterministic fixture planner. Candidate operations are an explicit allowlist, never arbitrary field assignment. Validate/recheck authority, world version, pause status, source references, and preconditions at commit. Write state, history, cause links, knowledge grants, audit, and outbox in one transaction. Provide projected timeline/detail APIs.

Acceptance: supported candidate survives restart; unsupported operation, stale version, hidden/cross-world ref, or lost authority yields no partial mutation; duplicate candidate commits once; visible causal graph omits secret causes. This proves pipeline mechanics, not live AI quality.

### P011 — Seed Earth-2097 and prove the core loop
Status: todo
Depends on: P010
Spec: 1.3, 8.4, 17.3, 20.3; docs/PRODUCT.md
Files: backend/apps/worlds/management/commands/seed_earth2097.py, backend/tests/fixtures/golden_world/, backend/tests/test_golden_world.py, docs/DEMO.md

Create an idempotent development seed: Atlantic city, public aircraft sighting, scientist A, journalist B, citizen C, seeded institutions/locations, a backend-only canary fact, an incomplete claim, and evidence. Do not embed passwords in fixtures; accept explicit development credentials or create unusable passwords. Seed all world writes with provenance.

Acceptance: A shares a weaker claim with B; B publishes/takes an action; one validated consequence persists; C sees only public information; safe deterministic briefing for B cannot reveal the fact; staff can reconstruct the chain. Repeat seed/retry/restart without duplicated history. Confirm D009 clock choice before finalizing seed.

## Closed alpha

### P012 — Publish API contracts and the typed browser client
Status: todo
Depends on: P010
Spec: 10.5, 12.1, 14.1, 14.5
Files: backend/config/urls.py, backend/common/api/, docs/api/openapi.yaml, frontend/src/api/, frontend/src/app/

Export OpenAPI, define `{code, detail, fields?}` business errors, UUID/world conventions, stable cursor pagination, and session/CSRF semantics. Add generated client types and schema drift checks. Introduce world-scoped routing, query caching, and an error boundary when implementing actual server data flows.

Acceptance: schema generation is reproducible; generated client typecheck passes; 403/404/409/validation responses are mapped; logout/world switch clears private cache; cookies and CSRF work through the development proxy. Authenticated errors cannot leak hidden object IDs.

### P013 — Build the first-session user flow
Status: todo
Depends on: P011, P012
Spec: 5.1–5.3, 6.1–6.3, 14.2
Files: frontend/src/features/auth/, frontend/src/features/worlds/, frontend/src/features/onboarding/, frontend/src/components/layout/

Implement login/recovery, world landing, role selection, character profile, public/private briefing separation, and world navigation with loading/empty/error states. Do not show seeded privileged roles as freely claimable. Present private information in visibly separate surfaces.

Acceptance: real APIs drive the flow; refresh preserves session; duplicate submit does not create another character; keyboard navigation works; first-session route handles already-joined and rejected-role cases. Browser tests prove no canonical secret arrives during onboarding.

### P014 — Secure evidence uploads and media access
Status: todo
Depends on: P007, P012
Spec: 6.6, 15.1, 16.1
Files: backend/apps/knowledge/media.py, backend/apps/moderation/media.py, frontend/src/features/intel/EvidenceViewer.tsx, backend/tests/security/test_media_access.py

Integrate selected S3-compatible storage, bounded uploads, content/type validation, scanning/quarantine, integrity hashes, and chain of custody. Authorize each upload/download and issue short-lived URLs. Published copies must preserve internal provenance while hiding confidential sources and metadata. Never serve quarantined media.

Acceptance: outsider, revoked member, expired URL, wrong content type, oversized file, and malicious file are denied/quarantined; public copy reveals only allowed fields. Storage/scanning selection is required before enabling uploads for alpha users.

### P015 — Implement posts, articles, comments, reactions, and follows
Status: todo
Depends on: P008, P012, P014
Spec: 6.4, 6.6, 8.2
Files: backend/apps/social/models.py, backend/apps/social/services.py, backend/apps/social/api.py, backend/tests/test_publication.py

Support character/org posts and articles, claim/evidence citations, audiences, location tags, constrained rich text, revision/correction history, comments, reactions, and follows. Publishing must grant only the intended projection. Organization authorship requires current authority. Keep false claims representable.

Acceptance: correction remains visible; XSS payload renders inert; private evidence cannot be attached without permitted publication; idempotent actions produce one revision/event; blocked/cross-world interactions fail; reactions cannot bypass content visibility.

### P016 — Build World Pulse and public sharing
Status: todo
Depends on: P013, P015
Spec: 5.3, 6.4, 7.3, 14.3
Files: backend/apps/social/selectors.py, backend/apps/social/ranking.py, frontend/src/features/feed/, backend/tests/security/test_feed_projection.py

Deliver mixed event/post/article/statement cards, cursor pagination, filters, permissions-first ranking, role relevance, recency, and crisis diversity caps. Add public event share URLs/cards from a dedicated public projection path; never capture the private UI. Respect account discoverability and world visibility.

Acceptance: no forbidden item is scored or counted; pagination is stable during new events; different characters see distinct valid feeds; public preview does not reveal private notification text or causal IDs; cards work with keyboard and small screens.

### P017 — Implement private conversations and organization channels
Status: todo
Depends on: P005, P008, P012, P014
Spec: 6.7, 15.3
Files: backend/apps/messaging/models.py, backend/apps/messaging/services.py, backend/apps/messaging/api.py, backend/tests/security/test_conversation_access.py

Build 1:1/groups/org channels, participant policies, claim/evidence attachments, confidentiality, replies, unread receipts, pagination, and message-request controls. Account blocking and sanctions must be enforced through a policy hook completed at P029 before alpha. Private messages stay out of simulation by default.

Acceptance: nonparticipants cannot list/read/send/attach; revoked org membership removes channel access; retries do not duplicate messages; receipts disclose only authorized participants. Clearly document moderation access and no E2EE claim.

### P018 — Add authorized realtime delivery and catch-up
Status: todo
Depends on: P009, P016, P017
Spec: 13, 14.5
Files: backend/config/asgi.py, backend/common/realtime/, frontend/src/app/websocket/, backend/tests/security/test_websocket_access.py

Add Channels consumers with session/origin checks and private user/character/org/conversation authorization. Clients request resource subscriptions, not arbitrary group names. Broadcast only safe projections/IDs; include event cursors for REST catch-up and invalidate narrow query keys. Revoke access on membership changes.

Acceptance: unauthorized subscription/origin is rejected; disconnect/reconnect recovers missed changes; duplicate/out-of-order delivery is harmless; world switching and revocation cannot leave stale private subscriptions. Test with two real authenticated connections.

### P019 — Install the typed AI provider boundary and job audit
Status: todo
Depends on: P010
Spec: 9.1–9.4, 9.8, 11.2, Appendix C
Files: backend/common/ai/, backend/apps/simulation/models.py, backend/apps/simulation/providers.py, backend/tests/ai_evals/test_provider_contract.py

Define task/purpose, trusted rules, untrusted source blocks, audience, allowed source IDs, strict response schema, timeout, and bounded retries. Add deterministic fake provider and one user-selected live provider. Store AIJob status, template/model version, source IDs, output hash, token/cost metrics, and redacted errors. Do not give models database or network tools.

Acceptance: unknown fields/operations rejected; timeout/provider failure leaves job retryable without partial mutation; fake-provider tests require no credentials; one explicit live contract evaluation is recorded before calling live integration done. Credentials/model/budget are user choices.

### P020 — Assemble permission-safe AI context
Status: todo
Depends on: P007, P019
Spec: 9.5–9.8, 14.4, Appendix C
Files: backend/apps/simulation/context.py, backend/tests/ai_evals/test_context_boundaries.py

Separate privileged consequence-planner context from public/organization/personal renderer context. Reuse allowlist selectors with explicit audience, source IDs, world/entity filters, and bounded structured summaries. Exclude private notes and DMs by default. Add hashes/versioning so permission changes invalidate cached context.

Acceptance: public context lacks canary facts, secret IDs, confidential source identity, and private notes; adversarial fake system messages remain untrusted data; revoked/cross-world context is denied; identical permitted source sets can cache safely without cross-audience leakage.

### P021 — Plan, validate, and review AI consequences
Status: todo
Depends on: P020, P010
Spec: 6.9, 9.3–9.4, 15.4, 17.2
Files: backend/apps/simulation/planner.py, backend/apps/simulation/validators.py, backend/apps/simulation/critic.py, backend/tests/ai_evals/test_candidate_validation.py

Connect provider proposals to deterministic commit. Enforce schemas, allowlisted operations, authority, source validity, causality, world coherence, preconditions, severity, pause status, and version conflicts. Run a critic when useful; it cannot bypass rule validation. Queue high-impact outcomes for authorized review using D008's reviewed rules.

Acceptance: impossible authority, unsupported op, stale state, hidden refs in public output, and unknown mutation fields reject without writes; retry commits once; reviewed outcomes record reviewer/cause. Evaluate proportionality and coherence with golden scenarios before enabling live jobs.

### P022 — Render events and audience-specific briefings
Status: todo
Depends on: P020, P021
Spec: 6.10–6.11, 9.7, 17.2
Files: backend/apps/simulation/renderers.py, backend/apps/simulation/briefings.py, frontend/src/features/feed/BriefingPanel.tsx, backend/tests/ai_evals/test_briefing_leaks.py

Render committed events and public/org/personal editions from their permitted sources. Save per-paragraph provenance and prompt/model versions. Preserve contradictions and uncertainty. Validate source citations/entities and add adversarial leakage checks; reject or safely fall back when output cannot be validated. Never use secret truth to silently correct the audience.

Acceptance: B's briefing cannot disclose A's secret in text, metadata, source links, or paraphrase evals; conflicting claims remain conflicting; regeneration is auditable; fallback reveals no extra data; source links reauthorize at read time.

### P023 — Schedule simulation with budgets and recovery
Status: todo
Depends on: P021, P022
Spec: 6.9, 9.9, 15.4, 18.2
Files: backend/apps/simulation/tasks.py, backend/apps/simulation/budgets.py, backend/config/celery.py, docker-compose.yml, backend/tests/test_simulation_scheduling.py

Add explicit immediate, delayed, tick, and daily-briefing scheduling. Separate AI queue concurrency, reserve budget atomically before calls, reconcile actual usage, cap retries/tokens, and implement per-feature/world kill switches. Add a single scheduler service, deduplicated tick keys, failed-job inspection, and backpressure.

Acceptance: simultaneous jobs cannot exceed quota; paused world creates no new effects; scheduler retry creates one tick; worker restart recovers accepted actions; timeouts have bounded cost; no expensive call occurs on feed reads. Record configured limits chosen with the user.

### P024 — Build Intel and evidence workflows
Status: todo
Depends on: P008, P013, P014, P022
Spec: 6.5, 14.3
Files: frontend/src/features/intel/, frontend/src/tests/intel.spec.ts

Implement encountered claims, confidence/stance/verification, evidence viewer, permitted source trail, contradictions, private notes, and share/leak/publish/verify interactions. Notes must remain excluded from AI unless explicitly shared. Keep secret intel out of persisted global browser storage.

Acceptance: server-denied actions show clear errors; confidential sources stay anonymous where required; switching account/world clears intel; two-character browser tests confirm distinct network payloads and valid share propagation.

### P025 — Build typed action status and causal timeline
Status: todo
Depends on: P012, P013, P018, P021
Spec: 6.9, 6.11, 14.3
Files: frontend/src/features/actions/, frontend/src/features/timeline/, frontend/src/tests/consequences.spec.ts

Show role-aware action forms and accepted/processing/resolved/failed/review states from the server. Preserve idempotency keys across retries; do not show uncommitted world changes as real. Render timeline filters and only permitted causal links, including restart/reconnect catch-up.

Acceptance: repeated click yields one action; network loss recovers status; stale permissions are handled; historical event persists after restart; secret causal edges never arrive in browser responses.

### P026 — Build organization workspaces
Status: todo
Depends on: P005, P013, P015, P017
Spec: 6.8, 14.3
Files: frontend/src/features/organizations/, frontend/src/tests/organizations.spec.ts

Provide public organization pages, permitted internal feed/documents, membership management, channel access, organization-owned knowledge, and statement/action entrypoints. Show capability hints while reauthorizing server-side.

Acceptance: role changes update available actions; outsider cannot fetch internal tabs by URL; revoked user loses internal data/cache; authorized spokesperson can publish a statement with auditable attribution.

### P027 — Build message and notification surfaces
Status: todo
Depends on: P013, P017, P018, P028
Spec: 6.7, 6.16, 14.3
Files: frontend/src/features/messaging/, frontend/src/features/notifications/, frontend/src/tests/messaging.spec.ts

Create conversation list/thread, confidentiality context, attachments, claim-sharing controls, unread state, notification center, and notification preferences. Preview text must respect visibility and opt-out settings. Include offline/retry states and accessible live announcements.

Acceptance: intended recipient gets message and unread change once; blocked/revoked delivery is denied; private notification text never appears in public previews; browser tests cover reconnect and switching character.

### P028 — Implement safe notification fan-out
Status: todo
Depends on: P009, P017, P018
Spec: 6.16, 13, 14.5
Files: backend/apps/notifications/models.py, backend/apps/notifications/services.py, backend/apps/notifications/api.py, backend/tests/security/test_notifications.py

Store per-recipient projections for consequence, intel, direct social, world shift, and digest classes. Apply preferences, deduplicate by domain event, and expose read/unread APIs. Recheck current access at delivery/read; avoid long-lived copies of revoked intel. In-app delivery first; external channels require explicit configuration.

Acceptance: duplicate outbox delivery creates one notification; wrong recipient/world is denied; revocation strips or suppresses payload; prioritization favors consequences; user preferences persist without suppressing required account safety messages.

### P029 — Enforce platform moderation and abuse controls
Status: todo
Depends on: P004, P014, P015, P017, P019
Spec: 6.18, 12.5, 15.1–15.4
Files: backend/apps/moderation/, backend/tests/security/test_moderation.py, frontend/src/features/moderation/

Implement report/block/mute/sanction flows, platform/world rules, separate fictional-content versus real-abuse classification, auth/post/message/action throttles, spam signals, media routing, and logged privileged access. Close the P017 policy hook. Creators cannot disable platform safeguards. Resolve content rating and DM moderation disclosures.

Acceptance: blocked user cannot message through REST/WS/attachments; sanctioned user cannot act; world moderator cannot escalate globally; rate limits bound expensive jobs; reports are inspectable with role checks; moderation decisions and access are audited.

### P030 — Build creator and simulation review controls
Status: todo
Depends on: P005, P011, P023, P029
Spec: 6.17, 15.4, 22.4
Files: backend/apps/worlds/admin.py, backend/apps/simulation/admin.py, frontend/src/features/creator/, backend/tests/test_creator_controls.py

Use Django admin first where adequate; expose a scoped studio for rules/roles/seeds, versioned configuration, queue/failure inspection, budgets, pause/resume, and high-impact review. Validate seed imports and prevent cross-world references. Resolve role slots, clock, age rating, NPC falsehood policy, and approval classes before alpha.

Acceptance: unauthorized creator is denied; concurrent config edit conflicts; paused simulation cannot commit; approval/rejection leaves traceable state; role/knowledge seed changes are audited and do not leak to public APIs.

### P031 — Define and implement privacy, deletion, and retention
Status: todo
Depends on: P017, P019, P029
Spec: 11.5, 15.3, 17.3, 18.3
Files: backend/apps/accounts/services.py, backend/apps/audit/retention.py, docs/PRIVACY-DESIGN.md, backend/tests/security/test_deletion.py

Resolve retention periods with the user. Implement account deletion/export, anonymized historical actor references, evidence/message policy, private prompt/log minimization, and audited staff access. Preserve necessary world history without unrestricted cascades or retaining unnecessary personal data. Export is an authorized projection.

Acceptance: deleted account cannot authenticate; history remains structurally valid; export cannot reveal others' secrets; expired private AI data is purged; privileged reads are logged; tests cover revoked access and deletion in golden fixtures.

### P032 — Add operational and product observability
Status: todo
Depends on: P009, P018, P023, P029
Spec: 18, 16.1
Files: backend/common/observability/, docs/OPERATIONS.md, backend/tests/test_telemetry_redaction.py

Add structured request/job correlation, error tracking, API percentiles, queue age, WS lag, DB contention, AI cost/rejection/leak metrics, and moderation time-to-action. Capture consequential actions, human dependencies, propagation depth, evidence interaction, and return-after-consequence using metadata. Set alert thresholds from measured baselines.

Acceptance: a sample action can be traced across API/outbox/job/event; dashboard queries reproduce counts; logs and analytics contain no raw DM, secrets, credentials, or unrestricted prompt dumps; alerts can be triggered in staging.

### P033 — Gate releases with golden-world and browser tests
Status: todo
Depends on: P016, P024, P025, P026, P027, P029, P031
Spec: 8.4, 15.2, 17, Appendix C
Files: backend/tests/security/, backend/tests/ai_evals/, frontend/src/tests/, .github/workflows/ci.yml

Automate onboarding, private share, weaker claim, publication, org decision, corrected article, action consequence, reconnect, block/report, revocation, deletion, retry, and model-change scenarios. Add leak canaries to every exposed endpoint, notification, search, WebSocket, export, and share preview. Add browser test tooling and recorded live model evals where appropriate.

Acceptance: CI gates regressions; adversarial prompt injection cannot reveal truth or mutate state; API/schema/client agree; fake and live eval results are labeled separately; no known critical authorization or knowledge-leak failure remains.

### P034 — Measure load and worker recovery
Status: todo
Depends on: P023, P032, P033
Spec: 16.3, 17.1, 18.2
Files: tests/load/, docs/LOAD-RESULTS.md, backend/apps/social/selectors.py, backend/apps/events/tasks.py

Create reproducible synthetic workloads for feed reads, messaging bursts, concurrent actions, event fan-out, and AI queue backlog. Measure against an explicit target profile for closed alpha; thousands-user claims require their own run. Optimize measured queries/indexes and queue behavior; inject worker/broker failures.

Acceptance: report concurrency, hardware, fixture size, p95/p99, error rate, DB locks, queue lag, and costs; show restart recovery and bounded backpressure with no lost/duplicate domain effects. Do not claim capacity from a local smoke run.

### P035 — Prove backups, snapshots, and compensation
Status: todo
Depends on: P010, P023, P030, P031
Spec: 2.3, 16.5, 22.4
Files: backend/apps/events/snapshots.py, docs/RESTORE.md, backend/tests/test_world_reconstruction.py

Implement snapshots with sequence/hash, export of relevant configuration/state, reconstruction from events plus snapshot, and compensating events for problematic consequences. Define encrypted database/media backup policy and test a restore into an isolated environment. Choose RPO/RTO and retention explicitly.

Acceptance: restored world matches expected state and causal history; replay is deterministic within documented boundaries; corrections append history instead of deleting it; tested restore duration and data-loss window are recorded; export respects staff-only secrets.

### P036 — Prepare staging and deployment automation
Status: todo
Depends on: P032, P033, P034, P035
Spec: 15.1, 16, 22.4
Files: .github/workflows/, backend/config/settings/production.py, deployment/, docs/DEPLOYMENT.md

Select hosting with the user. Separate staging/prod secrets, domains, AI budgets, DB/storage, and accounts. Add static asset serving, trusted proxy/HTTPS handling, secure worker users, image digests, migrations/rollback procedure, readiness/liveness checks, protected admin access, and backup/alert wiring. Run Django deployment checks against real configuration.

Acceptance: staging has end-to-end tests and a restore/release drill; production settings fail closed; secrets are absent from images/client bundles; migrations have an explicit recovery plan. Deployment beyond local development needs the user's explicit release authorization.

### P037 — Run the closed-alpha readiness review
Status: todo
Depends on: P001, P030, P033, P034, P035, P036
Spec: 1.3, 5.1, 8.4, 20.1, 22.4
Files: docs/ALPHA-READINESS.md, docs/OPERATIONS.md, docs/WORKLOG.md

Run a 50–500 participant rollout plan with recruiting, seeded institutions, role availability, support/moderation coverage, incident/pause process, and user-facing privacy/world rules. Evaluate return motivation, human dependency, provenance, coherent events, and first meaningful action within ten minutes. Complete name/domain checks from the source spec.

Acceptance: every alpha dependency is verified; no known critical leak/auth issue; backup restore, budgets, moderation, pause, and incident ownership are operational; user review authorizes invitations/release. Report observed product outcomes honestly, including failures.

## Optional improvements

### P038 — Add explainable reputation and role progression
Status: deferred
Depends on: P015, P030, P033
Spec: 6.3, 6.13
Files: backend/apps/characters/reputation.py, frontend/src/features/characters/

Implement separate credibility, expertise, institutional trust, reach, and reliability dimensions as auditable events. Support configured promotions and role transfer with concurrency checks. Acceptance: users can inspect causes; scores cannot reveal canonical truth; no paid authority or hidden global truth score; revoked powers cannot be used through cached clients.

### P039 — Add richer locations and accessible map views
Status: deferred
Depends on: P002, P025, P033
Spec: 6.12, 14.2
Files: backend/apps/worlds/locations.py, frontend/src/features/map/

Extend the initial location hierarchy with a simple two-dimensional or list-based map, permitted event filters, and authored travel constraints. Acceptance: secret sites and character presence do not leak; keyboard/list alternative works; move actions are validated/audited. No 3D engine or pathfinding unless later justified.

## Later roadmap

### P040 — Establish private-beta creator operations
Status: deferred
Depends on: P037
Spec: 20.1 phase 2
Files: docs/roadmap/private-beta.md

Scope a measurable beta plan for world operation over weeks with low staff intervention and bounded AI spend. Improve creator workflows, quality review, privacy controls, and reliability using alpha evidence. Acceptance: user approves a decomposed plan with success measures derived from observed alpha problems; no automatic broad feature expansion.

### P041 — Add selected multi-world creation and forks
Status: deferred
Depends on: P040
Spec: 6.2, 20.1 phase 3
Files: docs/roadmap/multi-world.md

Plan selected creator launches, reusable configuration, world isolation/migrations, discovery, invite context, and historical forks. Acceptance: fork preserves ancestry without cross-world private data leakage; all caches, queries, subscriptions, and retrieval remain scoped. Split migrations, creation, discovery, and fork work into new tasks before implementation.

### P042 — Design ledger-based economy and markets
Status: deferred
Depends on: P040
Spec: 6.14, 8.2
Files: docs/roadmap/economy.md

Specify character/org accounts, assets, contracts, jobs, and market orders only when product evidence warrants it. Use double-entry or equivalent balanced immutable ledger entries; balances are projections. Acceptance: decomposed plan includes atomic transfer, duplicate order handling, ownership/authority, replay, and abuse tests. No real-money/crypto system is implied.

### P043 — Design configurable governance and elections
Status: deferred
Depends on: P040
Spec: 6.15, 8.2
Files: docs/roadmap/governance.md

Scope offices, proposals, votes, terms, quorum, authority, and world-configured rules. Acceptance: a detailed plan handles eligibility, secret/public ballots, concurrent office changes, recount/audit, role abuse, and persistent causal consequences without hardcoding a real country's system.

### P044 — Evaluate monetization and platform scale
Status: deferred
Depends on: P041
Spec: 16.3, 19, 20.1 phase 4
Files: docs/roadmap/platform.md

Evaluate premium cosmetics/archives, creator budgets, private communities, and curated passes. Scope marketplace/discovery, billing, native clients, and scale work only after evidence of demand. Acceptance: approved plans bound AI costs, maintain usable core communication, avoid selling truth/authority, and use measured load to justify infrastructure splits.

### P045 — Evaluate optional advanced capabilities
Status: deferred
Depends on: P040
Spec: 6.1, 6.3, 6.5, 6.7, 9.2, 16.4
Files: docs/roadmap/optional-capabilities.md

Track passkeys, multiple characters, knowledge-graph visualization, disappearing messages/E2EE, semantic embeddings, and additional NPC capabilities as explicit options. None is implemented by installing tooling. Acceptance: each selected option receives its own threat model, product rationale, compatibility analysis, and new dependency-scoped tasks; decline unneeded options rather than building them speculatively.

## Project tooling

### P046 — Install portable Ponytail, Impeccable, and Spec Kit skills
Status: in_progress
Depends on: none
Spec: User follow-up on 2026-09-14
Files: .agents/skills/, .claude/skills/, .cursor/skills/, .specify/, docs/SKILLS.md, AGENTS.md

Install the existing Ponytail skill and verified upstream Impeccable/Spec Kit integrations locally for this repository. Preserve project instructions and track version/source provenance. Map Spec Kit feature tasks to stable TASKS.md IDs so framework-specific files do not become conflicting project status sources.

Acceptance: installed skill files and referenced templates/scripts exist; Codex, Cursor, and Claude Code have discoverable project integrations; installation has no unrelated global configuration edits; handoff explains commands, updates, and reload requirements. Record any intentionally unconfigured optional services separately from installed skills.
