# Task Plan

> Active and near-term work only. Keep this file small; archive old
> completed/dropped rows before it becomes a giant database.
> Every task row includes `Created` (first entered into this ledger) and
> `Updated` (last change to the row, status, or evidence), both as `YYYY-MM-DD`.

## Active

| ID | Status | Created | Updated | Task | Owner | Next Action | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | completed | 2026-09-06 | 2026-09-06 | Promote typinator-cli to A-coding standalone root | agent | Verified standalone repo, VAULT scaffold | `A-coding/26.09.06-typinator-cli` |
| T-002 | completed | 2026-09-06 | 2026-09-06 | Add bin wrapper, pyproject 1.1.0, test suite expansion | agent | 13 tests passed | `tests/test_typinator_cli.py`, `tests/test_live_e2e.py` |
| T-003 | completed | 2026-09-06 | 2026-09-06 | Push to GitHub as AGPL-3.0 repo | agent | Pushed commits to origin/main | `https://github.com/vecyang1/typinator-cli` |
| T-004 | completed | 2026-09-06 | 2026-09-06 | Sync with Notion Product[OS] database | agent | Updated page properties and markdown body | Notion page `3cae1b43-2393-81e6-8c81-c3bf32691292` |
| T-006 | completed | 2026-09-06 | 2026-09-06 | Configure ;;o SSOT alias pointing to ;;a | agent | Verified nested snippet grammar {"abbreviation"} | `typinator get "Shortcut / Url" ";;o"` -> `{\";;a\"}` |
| T-007 | completed | 2026-09-06 | 2026-09-06 | Harden audit with global cross-set collision & nested validation (v1.2.0) | agent | 17 tests passed, cross-set blind spot eliminated | `CHANGELOG.md`, `tests/test_audit.py` |

## Backlog

| ID | Priority | Created | Updated | Task | Why It Matters | Link |
| --- | --- | --- | --- | --- | --- | --- |
| T-005 | low | 2026-09-06 | 2026-09-06 | PyPI publication setup | Enable global pip install directly from PyPI | `pyproject.toml` |

## Rollover Rule

When this file reaches roughly 80-120 task rows or roughly 60 completed/dropped
rows, move older closed rows to `99 - Archive/task-ledger/YYYY-completed-tasks.md`
or the project's chosen archive owner, then leave a pointer here.
