# Current project status

Updated: 2026-09-14

Current task: none in progress. P000, P001, P002, and P046 are `done`. OpenRouter/LangChain/LangGraph stub is installed (D016); P019 is still `todo`. Next eligible backlog task is P003.

## Last verified

- SQLite smoke: `26 tests, OK (skipped=1 live PG+Redis)`, including 4 AI provider tests with no network.
- LangChain 1.4.0, LangGraph 1.2.11, langchain-openrouter 0.2.8 installed. Empty `OPENROUTER_API_KEY` selects `FakeProvider`.

## What does not exist yet

No public world/character APIs, login, audit/outbox, knowledge models, or live model calls. P019 is not done.

## Next step

Set P003 to `in_progress` in `TASKS.md`. Read spec 2.3, 10.4, 10.6, 11.5.

## Git checkpoint

Commit and push to `origin` (`https://github.com/notwld/parallel.git`) after this change.
