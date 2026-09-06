# Changelog

All notable changes to the `typinator-cli` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-09-06

### Added
- **Global Cross-Set Collision Detection in Set Auditing**: `typinator audit --set <name>` now indexes all active rule sets globally to detect cross-set abbreviation shadowing without silent blind spots.
- **Nested Reference Validation Engine**: `{"abbr"}` dynamic syntax parser detecting dangling (missing target), ambiguous (multi-set collision), and circular self-references.
- **CLI Preflight Warnings**: `typinator add` and `typinator set` automatically validate nested reference integrity and print warnings to `stderr` before mutation.
- **Expanded Unit Test Suite**: Added 4 new automated unit tests in `tests/test_audit.py` (17 tests total passing).

## [1.1.1] - 2026-09-06

### Documentation
- Documented anti-collision trigger suffix conventions (`⌘`, `⇧`, `⌥`) in `references/syntax_and_markers.md`.
- Added guidelines for agents adding new URL/prompt rules without bare Latin collision.
- Documented macOS input methods and micro-expansions for generating `⌘` (U+2318).

## [1.1.0] - 2026-08-28

### Added
- Sub-second bulk rule table extraction engine (`rule table` OSA property), accelerating database-wide searches by ~100x (<0.4s for 4,800+ rules).
- Full live E2E lifecycle test suite (`tests/test_live_e2e.py`) validating create, read, update, delete, export, and search workflows.
- GitHub Actions CI workflow (`.github/workflows/tests.yml`) testing across Python 3.9–3.12 on macOS.
- `status`, `toggle-set`, `export`, `import`, `expand`, and `quick-search` subcommands.
- GNU Affero General Public License v3.0 (`AGPL-3.0`) compliance.

### Fixed
- Fixed whole-word property validation distinction for modifier-ending vs word-based abbreviations.
- Sanitized invisible unicode control characters (`\u2028` line separators, `\u2029`, `\ufeff`) breaking autocompletion in browser address bars and terminals.

## [1.0.0] - 2026-08-28

### Added
- Initial release of `typinator-cli` with AppleScript OSA integration.
- Subcommands: `list-sets`, `search`, `get`, `set`, `add`, `delete`, `audit`.
- Documentation: `SKILL.md`, `syntax_and_markers.md`, `applescript_api.md`.
