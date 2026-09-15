# Current project status

Updated: 2026-09-15

Current task: none in progress. P050–P055 (realtime chat) `done`. P005 remains `todo` (interrupted draft). Next eligible: P005.

## Last verified

- SQLite: `51 tests, OK (skipped=3)` including chat security + WS authz.
- Daphne 4.2.3 installed; backend Dockerfile CMD uses Daphne; `ASGI_APPLICATION` + ProtocolTypeRouter wired.
- Product module: `apps/chat` (servers/channels/DMs)—not branded Discord.

## Next step

Resume P005 organizations (finish tests/migrations) or continue Parallel world backlog. Chat APIs under `/api/v1/chat/`; WS `ws/chat/channels/<id>/`.

## Git checkpoint

Large uncommitted tree (P003–P004, chat P050–P055, draft orgs). Commit only if asked.
