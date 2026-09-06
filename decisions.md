# Decisions

> Scope: project-local — this file governs only this project root. Cross-project truth lives in the 2nd Brain vault: /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain (contract: 00 - System/contracts/project-link-bridge.md).

Use this file for durable choices, supersession, reversals, and rationale.
Keep execution proof in `progress.md` or `vault/sessions/`.

| ID | Date | Decision | Status | Rationale | Evidence | Supersedes |
| --- | --- | --- | --- | --- | --- | --- |
| D-001 | 2026-09-06 | Use V.A.U.L.T. owner-doc structure for project continuity | accepted | Future agents need one owner per truth type | `VAULT.md`, `FILE_MAP_INDEX.md` | - |
| D-002 | 2026-09-06 | Standalone Git repository placement in `A-coding/26.09.06-typinator-cli` pushing to `vecyang1/typinator-cli` | accepted | Decouple maintained CLI source code from skill docs while keeping unified toolchain | `git remote -v`, `pyproject.toml` | - |
| D-003 | 2026-09-06 | License as GNU Affero General Public License v3.0 (AGPL-3.0) | accepted | Enforce copyleft freedom and ensure community improvements remain open | `LICENSE`, `pyproject.toml` | - |
| D-004 | 2026-09-06 | Provide dual CLI commands `typinator` and `typinator-cli` in PATH | accepted | Minimize typing friction and enable future agent discovery across all shells | `bin/typinator`, `~/.local/bin/typinator` | - |
