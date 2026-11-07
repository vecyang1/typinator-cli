# Graph Report - 26.09.06-typinator-cli  (2026-11-07)

## Corpus Check
- 21 files · ~20,566 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 2 file(s) not represented in the graph (top: (none) 2)

## Summary
- 333 nodes · 561 edges · 20 communities (11 shown, 9 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 66 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5326a414`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- typinator_cli.py
- TestTypinatorAuditLogic
- Changelog
- include_macos
- test_quiet_launch.py
- CLI Reference
- escape_as
- typinator-manager
- Typinator Marker Syntax & Keystroke Reference
- FakeMac
- System Architecture Map - 26.09.06-typinator-cli
- decode_x_payload
- live_check_silent_launch.sh
- docs/README.md
- resources/README.md
- typinator-cli

## God Nodes (most connected - your core abstractions)
1. `main()` - 26 edges
2. `TestTypinatorAuditLogic` - 21 edges
3. `Module Map` - 21 edges
4. `audit_rules()` - 19 edges
5. `escape_as()` - 18 edges
6. `run_applescript()` - 16 edges
7. `debug_trigger()` - 15 edges
8. `CLI Reference` - 15 edges
9. `get_rule()` - 14 edges
10. `TestTypinatorCli` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Added` --references--> `PrefixTrie`  [INFERRED]
  CHANGELOG.md → scripts/typinator_cli.py
- `Fixed` --references--> `launch_typinator_quietly()`  [INFERRED]
  CHANGELOG.md → scripts/typinator_cli.py
- `Module Map` --references--> `escape_as()`  [INFERRED]
  docs/architecture.md → scripts/typinator_cli.py
- `Fixed` --references--> `search_rules()`  [INFERRED]
  CHANGELOG.md → scripts/typinator_cli.py
- `Fixed` --references--> `get_rule()`  [INFERRED]
  CHANGELOG.md → scripts/typinator_cli.py

## Import Cycles
- None detected.

## Communities (20 total, 9 thin omitted)

### Community 0 - "typinator_cli.py"
Cohesion: 0.08
Nodes (27): Added, Module Map, add_rule(), delete_rule(), diff_snapshots(), expand_text(), export_rules(), get_rule() (+19 more)

### Community 1 - "TestTypinatorAuditLogic"
Cohesion: 0.09
Nodes (8): audit_rules(), debug_trigger(), is_word_char(), PrefixTrie, _collect(), resolve_nested_expansion(), validate_nested_references(), TestTypinatorAuditLogic

### Community 2 - "Changelog"
Cohesion: 0.06
Nodes (35): [1.0.0] - 2026-08-28, [1.1.0] - 2026-08-28, [1.1.1] - 2026-09-06, [1.2.0] - 2026-09-06, [1.3.0] - 2026-09-06, [1.3.1] - 2026-09-07, [1.4.0] - 2026-10-17, [1.5.0] - 2026-11-07 (+27 more)

### Community 3 - "include_macos"
Cohesion: 0.06
Nodes (30): concurrency, cancel-in-progress, group, default, description, required, type, include_macos (+22 more)

### Community 5 - "CLI Reference"
Cohesion: 0.08
Nodes (24): 10. Deep Trigger Debugging & Preflight Simulation, 11. Run Safety Audit & Auto-Clean, 12. Programmatic Expansion & Quick Search, 13. Restart Application (Frozen / Stalled Recovery), 14. Time Machine Version Trace, Diff & Recovery, 1. Check Application Status, 2. List Rule Sets & Rule Counts, 3. Enable or Disable a Rule Set (+16 more)

### Community 6 - "escape_as"
Cohesion: 0.11
Nodes (4): escape_as(), is_typinator_running(), TestTypinatorEscaping, TestTypinatorCli

### Community 7 - "typinator-manager"
Cohesion: 0.11
Nodes (14): Add a Rule, Application Interface, Classes & Properties, Common Code Patterns, Delete a Rule, `rule`, `rule set`, Typinator AppleScript / Open Scripting Architecture (OSA) Reference (+6 more)

### Community 8 - "Typinator Marker Syntax & Keystroke Reference"
Cohesion: 0.11
Nodes (19): 1. Keystroke Markers, 2. Delay & Pause Markers, 3. Inline Scripts, 4. Known Pitfalls & Gotchas, 5. Trigger Suffix Conventions & Modifier Symbols, 6. Nested Snippets & Abbreviation Inclusion (SSOT), 7. AI Slash Command Strategy (Paseo / Antigravity / Gemini / Claude Code / Codex), 8. Prefix Shadowing & Collision Mechanics (Typinator Evaluation Engine) (+11 more)

### Community 10 - "System Architecture Map - 26.09.06-typinator-cli"
Cohesion: 0.22
Nodes (8): App Summary, Data And Storage, Integrations And External Services, Open Questions, Runtime And Deployment, System Architecture Map - 26.09.06-typinator-cli, System Diagram, Update Triggers

### Community 11 - "decode_x_payload"
Cohesion: 0.31
Nodes (4): decode_typinator_archive(), decode_x_payload(), _deref_uid(), parse_tyset_from_bytes()

### Community 12 - "live_check_silent_launch.sh"
Cohesion: 0.67
Nodes (5): check(), close_main_window(), front(), main_window_width(), live_check_silent_launch.sh script

## Knowledge Gaps
- **1 isolated node(s):** `typinator-cli`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 173 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Changelog` connect `Changelog` to `typinator-manager`?**
  _High betweenness centrality (0.240) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Module Map` (e.g. with `add_rule()` and `audit_rules()`) actually correct?**
  _`Module Map` has 20 INFERRED edges - model-reasoned connections that need verification._
- **What connects `typinator-cli` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `typinator_cli.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08382936507936507 - nodes in this community are weakly interconnected._
- **Why does `Typinator Marker Syntax & Keystroke Reference` connect `Typinator Marker Syntax & Keystroke Reference` to `typinator-manager`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `audit_rules()` (e.g. with `Module Map` and `.find_prefixes()`) actually correct?**
  _`audit_rules()` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `TestTypinatorAuditLogic` be split into smaller, more focused modules?**
  _Cohesion score 0.0859465737514518 - nodes in this community are weakly interconnected._