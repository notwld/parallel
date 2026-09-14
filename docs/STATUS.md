# Current project status

Updated: 2026-09-14

Current work: P000 project initialization and P046 user-requested skill installation.

Verified so far: four backend smoke tests pass with explicit SQLite test settings; Django system check passes; migrations have no drift; frontend typecheck and production build pass.

In progress: container build/startup, full backlog/handoff verification, official project-local skill installation, and initial Git checkpoint.

No gameplay features are implemented. Auth is only the Django account model/admin infrastructure; there are no user-facing login endpoints, world records, knowledge models, or model-provider calls.

Next action if interrupted: inspect git status and TASKS.md, verify container status with `docker compose ps`, review installed skill files, and finish P000/P046 evidence before starting feature work.
