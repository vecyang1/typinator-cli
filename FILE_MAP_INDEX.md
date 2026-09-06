# File Map Index

> Scope: project-local — this file governs only this project root. Cross-project truth lives in the 2nd Brain vault: /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain (contract: 00 - System/contracts/project-link-bridge.md).

This file owns folder and document boundaries. Add a row when creating a new
durable path that future humans or agents must understand.

## Root Owner Docs

| Path | Owns | Does Not Own |
| --- | --- | --- |
| `README.md` when public/handoff ready | Public/community start page, first-run commands, install/build/test summary | Live task state or private agent evidence |
| `AGENTS.md` | Project agent rules, skill lookup routes, and inherited workspace rules | Current project status or copied skill bodies |
| `DESIGN.md` when user-facing | Design system and brand/UI source of truth | Task state, project history, or raw asset dumps |
| `docs/architecture.md` | System architecture and module/data/integration map | Raw database dumps, every schema detail, or execution evidence |
| `docs/funnel.md` when conversion work exists | Funnel control surface: audience, traffic, page/URL plan, page inventory, CTAs, conversion paths, lead management, measurement, journey verification, build queue, and experiments | Raw campaign evidence or full CRM logs |
| `docs/funnel-lead-products.md` when offers need sorting | Lead magnets, lead products, tripwires, core products, upsells, landing URLs, delivery URLs, follow-up paths, owners, `last_verified` proof, and required assets | Main project strategy or raw product research |
| `VAULT.md` | Current-state router, source pointers, preflight risks | Full history, full task board, all decisions |
| `task_plan.md` | Active/backlog tasks and recent completed work; every row includes `Created` and `Updated` dates | Multi-year task database or undated task rows |
| `progress.md` | Dated execution proof, verification, blockers | Current task board |
| `handoff.md` | Latest resume card with next actor/action | Permanent history |
| `decisions.md` | Durable decisions and supersession | Session proof |
| `PROJECT_LINKS.md` | Cross-root bridge pointers between A-coding repo, Notion, skill, and 2nd Brain router | Task state or copied status |
| `CHANGELOG.md` | Release-level or user-visible changes when needed | Every agent step |

## Skill Routing

Skill routes and canonical skills-called log belong in pointers, not copied
knowledge. `AGENTS.md` lists where to find installed skill packages.
`progress.md` is the only skills-called log for meaningful work blocks. Do not
split or duplicate skill-call records into `vault/sessions/`, `handoff.md`, or
route docs. Reference skills by name and source path; do not paste entire
`SKILL.md` bodies into the project. Owner-created marketing/audience skills
are preferred when available, with source-backed evidence in `vault/research/`.

## Operating Layer Routing

Static context, live connections, capabilities, and cadence should each have an
owner:

- Static context: `VAULT.md`, `docs/`, `resources/`, and local research proof.
- System map: `docs/architecture.md` explains what the app is, how modules
  connect, which data stores matter, which integrations exist, and when the map
  must be updated.
- Live connections: `operations/links.md`, APIs, dashboards, browser sessions,
  and any source that needs a fresh check before use.
- Capabilities: `AGENTS.md` Skill Lookup plus actual skill-call records in
  `progress.md` only.
- Cadence: `operations/cadence.md` for scheduled jobs, automation owners,
  success markers, retries, cost/risk checks, and review rhythm.

## Folder Ownership

| Path | Owns | Example |
| --- | --- | --- |
| `docs/` | Durable PRDs, API contracts, architecture notes | `docs/prd_price_alerts.md`, `docs/API.md` |
| `docs/architecture.md` | System architecture map and update triggers | Module map, data/storage map, integrations, runtime |
| `docs/funnel.md` | Funnel strategy, page/URL map, page inventory, conversion paths, measurement, journey verification, and lead management | `docs/funnel.md` |
| `docs/funnel-lead-products.md` | Lead-product and offer inventory with landing, delivery, follow-up, owner, and proof fields | `docs/funnel-lead-products.md` |
| `docs/strategy/` | Strategy docs, market analysis, and positioning | `docs/strategy/positioning.md` |
| `operations/` | Repeatable runbooks, live connection routes, health checks, and cadence | `operations/runbooks/local-dev.md`, `operations/links.md`, `operations/cadence.md` |
| `resources/` | Non-secret assets, imports, exports, research inputs | `resources/research/agoda-pricing.md` |
| `vault/sessions/` | Session evidence and operational notes | `vault/sessions/2026-06-11-init.md` |
| `vault/research/` | Source-backed research proof | `vault/research/2026-06-11-market-scan.md` |
| `vault/notes/` | Project-specific durable insights not yet decisions | `vault/notes/pricing-edge-cases.md` |
| `vault/snapshots/` | Backups of source-of-truth docs before risky edits | `vault/snapshots/2026-06-11-VAULT.md` |
| `vault/archive/` | Small local historical evidence | `vault/archive/old-probe-output.md` |
| `99 - Archive/` or `archived/` | Larger historical exports when the project grows | `99 - Archive/task-ledger/2026-completed-tasks.md` |

## Local Project Vault vs 2nd Brain Memory Center

Use this project's local `vault/` for project-specific evidence, snapshots,
session notes, and research proof.

Point or promote information to `/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/05 - Memory Center` only when it is stable, reusable outside this project, or needed as cross-project memory. Do not make the global Memory Center the only owner of local project evidence.

## 2nd Brain project index Reciprocal Link

Keep project-local owner docs and the cross-project router in sync without
making either one a duplicate source of truth.

- Local side: this file, `VAULT.md`, and `AGENTS.md` point agents to the local
  owner docs.
- Router side: the 2nd Brain project index should point back to this project
  root, owner-doc status, repo state, and push target:
  `/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/registries/project-index.md`.
- Search before assuming moved/missing/duplicate project state:

```bash
python3 "/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/scripts/find_project_context.py" "<project or task query>"
```

- Refresh after root moves, folder renames, repo/push-target changes, external
  SSD moves, or meaningful owner-doc additions:

```bash
python3 "/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/scripts/audit_project_index.py" --update --write-report
python3 "/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/scripts/audit_project_index.py" --check
```

## Pre-Existing Docs Found Before Init

| Path | Type | Source | Next Action |
| --- | --- | --- | --- |
| `CHANGELOG.md` | Existing log | Existing project artifact | Review and assign owner if still active. |
| `README.md` | Existing document | Existing project artifact | Review and assign owner if still active. |
| `SKILL.md` | Existing document | Existing project artifact | Review and assign owner if still active. |
| `references/applescript_api.md` | Existing document | Existing project artifact | Review and assign owner if still active. |
| `references/syntax_and_markers.md` | Existing document | Existing project artifact | Review and assign owner if still active. |
