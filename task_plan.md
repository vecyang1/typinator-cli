# Task Plan

> Active and near-term work only. Keep this file small; archive old
> completed/dropped rows before it becomes a giant database.
> Every task row includes `Created` (first entered into this ledger) and
> `Updated` (last change to the row, status, or evidence), both as `YYYY-MM-DD`.

## Active

| ID | Status | Created | Updated | Task | Owner | Next Action | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | completed | 2026-09-06 | 2026-09-06 | Promote typinator-cli to A-coding standalone root | agent | Verified standalone repo, VAULT scaffold | `A-coding/26.09.06-typinator-cli` |
| T-002 | completed | 2026-09-06 | 2026-09-06 | Add bin wrapper, pyproject 1.1.0, test suite expansion | agent | 12 tests passed | `tests/test_typinator_cli.py` |
| T-003 | in_progress | 2026-09-06 | 2026-09-06 | Push to GitHub as AGPL-3.0 repo | agent | Commit and git push to vecyang1/typinator-cli | `gh repo view vecyang1/typinator-cli` |
| T-004 | in_progress | 2026-09-06 | 2026-09-06 | Sync with Notion Product[OS] database | agent | Update page properties and callable surfaces | Notion page `3cae1b43-2393-81e6-8c81-c3bf32691292` |

## Backlog

| ID | Priority | Created | Updated | Task | Why It Matters | Link |
| --- | --- | --- | --- | --- | --- | --- |
| T-005 | low | 2026-09-06 | 2026-09-06 | PyPI publication setup | Enable global pip install directly from PyPI | `pyproject.toml` |

## Rollover Rule

When this file reaches roughly 80-120 task rows or roughly 60 completed/dropped
rows, move older closed rows to `99 - Archive/task-ledger/YYYY-completed-tasks.md`
or the project's chosen archive owner, then leave a pointer here.
