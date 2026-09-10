# Project Docs

Use this folder for durable project documentation that future humans and agents
should read directly.

If this is a coding application or software project, always use the `/prd` skill
(PRD Generator) to plan features, define acceptance criteria, and track build
progress. Save PRDs here (e.g. `docs/prd_[feature].md` or `tasks/prd-[feature-name].md`)
and update them as implementation progresses.

When coding work depends on library, framework, SDK, API, model, deployment, or
platform behavior that may drift, use Context7 or official docs before coding.
Record the source or `last_verified` proof in the PRD, `docs/API.md`, or
`progress.md`.

Examples:

| Path Example | Purpose |
| --- | --- |
| `docs/prd_[feature].md` | Product or feature PRD. |
| `docs/API.md` or `docs/API_CONTRACT.md` | Shared API/schema contract. |
| `docs/architecture.md` | System architecture map: what the app is, module/data/integration boundaries, runtime, and update triggers. |
| `docs/strategy/market_analysis.md` | Polished market analysis and decision implications. |
| `docs/strategy/audience_analysis.md` | Target audience, jobs-to-be-done, segments, objections, and channels. |
| `docs/strategy/positioning.md` | Category, promise, differentiation, and messaging direction. |
| `docs/funnel.md` | Funnel control surface: goal, audience, traffic, pages, URLs, page inventory, CTAs, conversion paths, lead management, measurement, journey verification, build queue, and experiment log. |
| `docs/funnel-lead-products.md` | Sortable lead magnet, lead product, tripwire, product, upsell, landing URL, delivery URL, follow-up path, owner, proof, and asset inventory. |
| `docs/release-checklist.md` | Release gate and verification checklist. |

Strategy docs are created when a project is business/product/customer-facing or
the owner asks for marketing, audience, positioning, or go-to-market analysis.
Use them as polished owner docs, not raw research dumps.

`docs/architecture.md` is the app/system map. Read it before database/schema
spelunking, API tracing, feature planning, or architecture-impacting edits.
Update it in the same work block when modules, shared schemas, data stores,
integrations, runtime, deployment, or config ownership changes. Keep raw schema
dumps and proof in `vault/research/` or subsystem docs; this file should stay
short enough to orient a future agent quickly.

Funnel docs are optional owner docs for websites, ecommerce projects, creator
funnels, lead-gen systems, launches, course/product funnels, and conversion
work. Use `docs/funnel.md` as the control surface and
`docs/funnel-lead-products.md` as the sortable offer inventory with separate
landing URLs, delivery URLs, follow-up paths, owners, and `last_verified` proof. Use
`funnel-planner` first when funnel work needs routing into copy, CRO,
lead-product, traffic, ecommerce, checkout, or lead-management specialist
skills.


> Prefer an owner-created marketing or audience skill when available; otherwise
> choose the narrowest specialist skill, record the choice in `progress.md`, and
> keep source-backed evidence in `vault/research/`.

Do not store raw evidence here. Put source captures, session proof, and snapshots
under `vault/` or the chosen archive owner.
