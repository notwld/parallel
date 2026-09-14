# Installed project skills

Task P046. These skills are workflow guidance for coding agents. None of them is a product feature, and installing them implements nothing in `TASKS.md`. All files are tracked in Git so any tool can read them; do not add `.cursor/skills` to `.gitignore`.

## What is installed

| Skill | Version | Location | Purpose |
| --- | --- | --- | --- |
| Ponytail | in-repo copy | `.cursor/skills/ponytail/SKILL.md` | Laziest correct solution: YAGNI, reuse, stdlib before dependencies. Intensity is fixed to `full` for this project. |
| Impeccable | skill 0.1.5, CLI 4.0.0 | `.cursor/skills/impeccable/` | Frontend and UI/UX work: design, audit, polish, typography, motion, accessibility. |
| Spec Kit | 1.0.5 | `.specify/` and `.cursor/skills/speckit-*/` | Spec-driven flow: constitution, specify, clarify, plan, tasks, implement, analyze. |

Provenance and file hashes for the Spec Kit install are in `.specify/integrations/speckit.manifest.json`; its install options are in `.specify/init-options.json`. The Impeccable CLI version comes from `.cursor/skills/impeccable/scripts/VERSION` and `impeccable --version`.

## Discovery per tool

Skill bodies live in one canonical place, `.cursor/skills/`, rather than being copied per tool. Duplicating Impeccable's reference set and platform binary into `.claude/skills/` and `.agents/skills/` would triple a large tree for no behavioral gain, so each tool is pointed at the canonical path instead.

- **Cursor** loads `.cursor/rules/parallel.mdc` automatically and discovers `.cursor/skills/*/SKILL.md` natively.
- **Codex** reads `AGENTS.md`, which names the skills and their paths.
- **Claude Code** reads `CLAUDE.md`, which defers to `AGENTS.md`.

For Codex and Claude Code, read the relevant `SKILL.md` directly before doing the matching work; they will not auto-activate it.

## Commands

Spec Kit commands are invoked as `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, plus `/speckit-analyze`, `/speckit-checklist`, `/speckit-converge`, and `/speckit-taskstoissues`. Impeccable starts with `/impeccable init` when design context is missing.

Its helper scripts are PowerShell (`"script": "ps"`). Before a feature exists they exit non-zero with `Feature directory not found`, which is the expected state, not a broken install:

```powershell
powershell -NoProfile -File .specify/scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly
.cursor/skills/impeccable/scripts/impeccable.cmd --version
```

`.cursor/hooks.json` registers an Impeccable pre-edit hook. It is guarded by a file-existence test, so it is inert if the script is ever absent. Cursor reloads hooks and skills when the workspace is reopened; edits to `SKILL.md` files take effect in the next session.

## Boundaries

`TASKS.md` remains the single status authority. Spec Kit writes its own artifacts under `.specify/`; when a Spec Kit feature maps to project work, reference the stable `Pxxx` ID so those files never become a competing status source.

Installation touched only this repository. No global tool configuration was modified, and no paid provider, credential, or external service was configured.

## Not configured

PowerShell 7 (`pwsh`) is absent on the current machine; Windows PowerShell 5.1 runs the Spec Kit scripts. Only the Windows Impeccable binary (`scripts/bin/windows-x64/`) is present, so another platform needs its own Impeccable install.

## Updating

Reinstall a skill from its upstream source into the same path, then update the version and hashes recorded here and in `.specify/integrations/`. Record the change in `docs/WORKLOG.md`.
