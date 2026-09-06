# Project Agent Instructions

This file is the local agent constitution for this project. Keep it compact and
project-specific; do not copy giant workspace policies here when a parent
`AGENTS.md` can be referenced.

## Inheritance

- Inherit workspace-level rules from `../AGENTS.md` when that file exists.
- Local instructions in this file win for this project.
- `CLAUDE.md` and `GEMINI.md`, when present, should only point here.

## Read Order

1. `AGENTS.md`
2. `VAULT.md`
3. `docs/architecture.md` when present, before database/schema spelunking or architecture-impacting edits
4. `README.md` when present for public/community or broad human handoff
5. `DESIGN.md` when present for user-facing, brand, website, app, or visual asset work
6. `docs/funnel.md` when present for website, ecommerce, lead-gen, launch, creator funnel, course/product funnel, or conversion work
7. `task_plan.md`
8. `progress.md`
9. `handoff.md`
10. `FILE_MAP_INDEX.md`

## Skill Lookup

- Before specialized work, check relevant skills from the active agent's skill list.
- Installed skill sources usually live at `~/.gemini/antigravity/skills`,
  `~/.codex/skills`, `~/.agents/skills`, or `~/.claude/skills`.
- Canonical skills-called log: `progress.md` is the only skills-called log for
  every meaningful work block. Do not split or duplicate skill-call records into
  `vault/sessions/`, `handoff.md`, or route docs.
- Do not copy full skill bodies into project docs. Reference the skill name and
  source path, then load the source skill when needed.

## 2nd Brain Reciprocal Project Index

Use a two-way pointer between this project and the cross-project router. The
local owner docs should explain what this project owns; the 2nd Brain project
index should point back to this root, owner-doc status, repo state, and push
target.

- 2nd Brain router: `/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/VAULT.md`
- 2nd Brain project index: `/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/registries/project-index.md`
- Find existing/moved/related projects before creating new roots:

```bash
python3 "/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/scripts/find_project_context.py" "<project or task query>"
```

- Refresh after root moves, folder renames, repo/push-target changes, external
  SSD moves, or meaningful owner-doc additions:

```bash
python3 "/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/scripts/audit_project_index.py" --update --write-report
python3 "/Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/scripts/audit_project_index.py" --check
```

## Context, Connections, Capabilities, Cadence

- Context: static project knowledge lives in `VAULT.md`, `docs/`, `resources/`,
  and local `vault/research/` evidence.
- Connections: live data routes, dashboards, SaaS/admin URLs, APIs, and browser
  surfaces belong in `operations/links.md` or the relevant runbook.
- `LINKS.md` and `operations/links.md` are routing surfaces, not design value
  databases. Do not copy physical token values or component recipes into them;
  point to `DESIGN.md`, the token manifest, and the executable token authority.
- Capabilities: skills, scripts, and reusable workflows are routes, not copied
  manuals. Point to lookup roots from `AGENTS.md`, then log actual skill calls
  in `progress.md` only.
- Cadence: scheduled or recurring automation needs an owner, success marker,
  retry behavior, cost/risk check, and review rhythm before it runs unattended.

## Connection Freshness And Cadence

- Treat docs as static context unless they include a recent `last_verified`
  value or fresh runtime evidence.
- When a task depends on live state, verify through the API, CLI, browser,
  dashboard, or official source before acting.
- Before scheduling automation, document the cadence route in
  `operations/cadence.md` or the chosen runbook and record proof in
  `progress.md`.

## Operating Rules

- Wheel-check existing local work, official docs, and good open-source options before building from scratch.
- Read before writing: no owner check, no new durable file.
- Keep `VAULT.md` as a compact router; put tasks, decisions, progress, and file ownership in their owner docs.
- System Architecture Map: Read `docs/architecture.md` before database/schema spelunking, API tracing, feature planning, or architecture-impacting edits. Update it in the same work block when app purpose, modules, shared schemas, data stores, integrations, runtime, deployment, or config ownership changes.
- Read or create `DESIGN.md` before changing customer-facing UI, brand, email, or social asset surfaces.
- For a new web project without an existing design owner, Create DESIGN.md first:
  create `DESIGN.md`
  first with `python3 ~/.gemini/antigravity/skills/init-vault-method/scripts/init_vault.py --design-doc .`,
  then initialize the executable design contract:
  `node ~/.agents/skills/design-md/scripts/design-md.mjs init-config --project . --lane system --tokens styles/tokens.css --design-md DESIGN.md --scan styles,assets/pages`.
  Keep physical token values in `styles/tokens.css` and shared layout/component
  behavior in `styles/main.css`; pages and briefs consume variables and shared
  classes. If the delivery target is WordPress, set
  `delivery.platform: "wordpress"` with the `novamira-ops` adapter and run the
  generated `wordpressDesign` gate through `design_gate.py` before any page
  write. Local lint alone is not deployment proof.
- Read or create `docs/funnel.md` before planning conversion pages, lead capture, lead magnets, product funnels, checkout paths, or traffic campaigns. Use its page inventory to plan required pages/states before build work, record measurement ownership with `last_verified` proof, and fill the journey verification gate before demo, launch, or paid traffic. Use `docs/funnel-lead-products.md` when offers need a sortable inventory; keep landing URL, delivery URL, follow-up path, owner, and `last_verified` proof separate before marking an offer live. Use `funnel-planner` to route funnel work to specialist skills before filling copy, CRO, ads, ecommerce, checkout, or lead-management details; run `python3 ~/.agents/skills/funnel-planner/scripts/funnel_docs.py . --check-skills` to surface missing local specialist skills, `python3 ~/.agents/skills/funnel-planner/scripts/funnel_docs.py . --audit-skills` to surface stale specialist frontmatter before routing to alternatives, and `python3 ~/.agents/skills/funnel-planner/scripts/funnel_docs.py . --audit-docs` as a read-only funnel doc contract check. Use `--strict-doc-audit` before claiming build handoff, demo, launch, or paid-traffic readiness.
- If this is a coding application or software project, always use the `/prd` skill (PRD Generator) to plan features, define acceptance criteria, and track build progress before/during implementation.
- For coding apps, pair PRD planning with current technical context: use Context7 or official docs before implementation when library, framework, SDK, API, model, deployment, or platform behavior may have changed, and record the source or `last_verified` proof.
- Use local `vault/` for project-specific evidence and sessions.
- Promote only stable cross-project facts to the 2nd Brain Memory Center.
- Never hardcode secrets; document secret names and lookup routes only.
- Verify with real commands or runtime checks before claiming work is complete.
