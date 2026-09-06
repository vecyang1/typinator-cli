# Typinator CLI (macOS Automation Harness)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)](https://www.ergonis.com/products/typinator/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)](pyproject.toml)

A robust, production-grade command-line interface and automation harness for **Typinator** on macOS.

Enables programmatic rule search, live in-memory expansion updates, batch export/import, rule creation, deletion, simulation, and safety auditing (detecting invisible Unicode control characters and cross-set duplicate trigger collisions).

---

## Key Capabilities

- ⚡️ **Live In-Memory Control**: Add, update, toggle, or delete Typinator rules instantly via AppleScript / Open Scripting Architecture (OSA) without restarting the application.
- 🚀 **Sub-Second Bulk Search**: Uses native `rule table` IPC streaming to search across 4,800+ rules in **under 0.4 seconds**.
- 🛡️ **Safety & Hygiene Audit**:
  - Automatically flags invisible Unicode characters (such as `\u2028` line separators or `\u2029` paragraph separators) that break autocompletion in browser address bars or terminals.
  - Detects duplicate abbreviation triggers across multiple enabled rule sets that cause unintentional shadowing.
  - Trie-based **prefix collision engine** detecting rules disabled by higher-priority prefixes (`Disabled by "x" of set "y"`).
  - Built-in `--fix` option to automatically sanitize invisible control characters across all active rules.
- 🔍 **Deep Trigger Debugging & Preflight**:
  - `typinator debug <abbr>` inspects rule activation status, shadowing causes, shadowed descendants, and duplicate triggers.
  - Preflight simulation mode to check if a new trigger is safe to register before adding it.
- 💾 **Backup & Migration**: One-command JSON export and import for rule sets.
- ⏱️ **Delay & Keystroke Support**: Full support for Typinator syntax including `{delay:1.5}`, `{tab}`, `{return}`, and key combinations (`{key:⌘↩}`).
- 📦 **Zero External Dependencies**: Implemented strictly using Python's standard library.

---

## Installation & Setup

### Prerequisites
* macOS with **Typinator** installed and running.
* Python 3.8+ (standard library only).

### Option 1: Global Pip / Pipx Install
```bash
git clone https://github.com/vecyang1/typinator-cli.git
cd typinator-cli
pip install .
# Or with pipx:
pipx install .
```

### Option 2: Direct Execution / Symlink
```bash
git clone https://github.com/vecyang1/typinator-cli.git
cd typinator-cli
chmod +x bin/typinator scripts/typinator_cli.py

# Optional: Add to PATH
ln -sf "$(pwd)/bin/typinator" ~/.local/bin/typinator
ln -sf "$(pwd)/bin/typinator" ~/.local/bin/typinator-cli
```


---

## CLI Reference

### 1. Check Application Status
```bash
python3 scripts/typinator_cli.py status
```

### 2. List Rule Sets & Rule Counts
```bash
python3 scripts/typinator_cli.py list-sets
```

### 3. Enable or Disable a Rule Set
```bash
python3 scripts/typinator_cli.py toggle-set "AI prompt" --enable
python3 scripts/typinator_cli.py toggle-set "Old Set" --disable
```

### 4. High-Speed Rule Search
```bash
# Search by keyword across all rule sets (<0.4s for 4,800+ rules)
python3 scripts/typinator_cli.py search "keyword"

# Search inside a specific rule set with JSON output
python3 scripts/typinator_cli.py search "g⌘" --set "AI prompt" --json
```

### 5. Get Rule Details
```bash
python3 scripts/typinator_cli.py get "AI prompt" "g⌘"
```

### 6. Update Rule Expansion
```bash
python3 scripts/typinator_cli.py set "AI prompt" "g⌘" --expansion "/g{delay:1.5}{tab}"
```

### 7. Create a New Rule
```bash
python3 scripts/typinator_cli.py add "AI prompt" "ggg⌘" --expansion "/g{delay:1.5}{tab}" --desc "Quick command with 1.5s delay"
```

### 8. Delete a Rule
```bash
python3 scripts/typinator_cli.py delete "AI prompt" "old_abbr" --yes
```

### 9. Export & Import Rules (Backup / Migration)
```bash
# Export all rules or a specific set
python3 scripts/typinator_cli.py export --set "AI prompt" -o ai_prompts.json

# Import rules into Typinator
python3 scripts/typinator_cli.py import -i ai_prompts.json --overwrite
```

### 10. Deep Trigger Debugging & Preflight Simulation
```bash
# Debug by slash command or expansion token
python3 scripts/typinator_cli.py debug /boost
python3 scripts/typinator_cli.py debug /goal

# Inspect existing rule status and any shadowing conflicts
python3 scripts/typinator_cli.py debug "im⇧"
python3 scripts/typinator_cli.py debug "img"

# Preflight test if a prospective abbreviation is safe to add
python3 scripts/typinator_cli.py debug "img⇧"
```

### 11. Run Safety Audit & Auto-Clean
```bash
# Scan for invisible control characters (\u2028), duplicate triggers, and prefix collisions
python3 scripts/typinator_cli.py audit

# Audit specific rule set
python3 scripts/typinator_cli.py audit --set "AI prompt"

# Auto-fix invisible characters across all rules
python3 scripts/typinator_cli.py audit --fix
```

### 12. Programmatic Expansion & Quick Search
```bash
# Trigger expansion of a string programmatically
python3 scripts/typinator_cli.py expand "ggg⌘"

# Open Typinator quick search palette
python3 scripts/typinator_cli.py quick-search "git"
```

---

## Marker & Syntax Reference

| Marker | Description | Example |
|---|---|---|
| `{delay:n}` | Pauses expansion execution for `n` seconds (float or int) | `{delay:1.5}` |
| `{tab}` | Simulates a Tab keystroke | `{tab}` |
| `{return}` | Simulates a Return/Enter keystroke | `{return}` |
| `{key:⌘↩}` | Key combination (e.g. Command + Enter) | `{key:⌘↩}` |
| `{/AppleScript delay n}` | Inline AppleScript delay fallback | `{/AppleScript delay 1.5}` |
| `{/Shell sleep n}` | Inline Shell sleep delay | `{/Shell sleep 1.5}` |

---

## Testing

Run the full unit and live integration test suite:

```bash
python3 -m unittest discover -s tests -v
```

---

## License

[GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) © 2026 V
