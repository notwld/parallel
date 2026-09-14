# Continue Parallel in any AI coding tool

Open this repository folder in Cursor, Claude Code, Codex, or another coding tool. Give the tool the prompt below. All project context is in ordinary tracked files; no connection to the original conversation is required.

## Continuation prompt

```text
Continue building Parallel from this repository.
Read AGENTS.md, docs/STATUS.md, docs/DECISIONS.md, docs/PRODUCT.md,
docs/ARCHITECTURE.md, and TASKS.md before editing.
Inspect git status and existing changes. Run python scripts/check_backlog.py.
Resume an in_progress task first, or take the first eligible todo task.
Read that task's sections in docs/source/specification.md.
Implement one task at a time, verify its acceptance criteria, and checkpoint
TASKS.md, docs/STATUS.md, and docs/WORKLOG.md after each meaningful step.
Do not assume planned features exist or rewrite the chosen stack.
Before stopping, record the exact next step, changed files, and test results
so another tool can resume even if this session ends unexpectedly.
```

## Source hierarchy

1. New explicit user instructions.
2. `Parallel_Product_Technical_Specification_v1.0.docx` and the user's scenario recorded in `docs/PRODUCT.md`.
3. `docs/DECISIONS.md` for stated defaults and unresolved decisions.
4. `TASKS.md` and architecture/plans as derived implementation guidance.

The searchable transcription preserves all document paragraphs and tables in document order. Table cell line breaks appear as ` / ` separators. Check the DOCX for formatting or ambiguity. No source instruction authorizes arbitrary external actions.

## Reliable resumption

- `TASKS.md` is the single status authority: `todo`, `in_progress`, `blocked`, `done`, or `deferred`.
- Dependencies must be `done` before starting a task. If work needs splitting, retain the original ID and add new stable IDs with explicit dependencies.
- `docs/STATUS.md` records current task, last verified state, incomplete changes, blockers, and exact next command.
- `docs/WORKLOG.md` preserves completed and interrupted sessions. Local commits preserve recoverable checkpoints; inspect any uncommitted changes too.
- If the previous agent ended abruptly, trust the files and test evidence over a stale status line. Do not erase its work. Reconcile the task before proceeding.
- Update progress while working, not only in the final reply. A usage limit may arrive before a final response can be written.
- No task depends on a specific model vendor, a Codex sidebar task, an external issue tracker, or installed agent skills.

These files preserve instructions and progress; they cannot transfer an AI tool's usage allowance or automatically start another tool. The user opens the folder in the next tool and asks it to continue.

## Session checkpoint template

```markdown
Updated: YYYY-MM-DD
Current task: Pxxx — title
State: in_progress / blocked / complete
Changed files: paths and purpose
Last verified: exact command, result, and relevant environment
Incomplete: partial changes and failing tests
Blockers: concrete missing input or service; resolution needed
Next step: exact file/action/command
Git checkpoint: commit hash or uncommitted changes
```
