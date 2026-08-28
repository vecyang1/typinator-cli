# Typinator CLI (macOS Automation Harness)

A robust, agent-friendly command-line interface and automation harness for **Typinator** on macOS.

Enables programmatic search, rule inspection, hot in-memory expansion updates, rule creation, deletion, and safety auditing (detecting invisible Unicode control characters and cross-set duplicate trigger collisions).

---

## Features

- ⚡️ **Live In-Memory Control**: Add, update, or remove Typinator rules instantly via AppleScript / Open Scripting Architecture (OSA) without restarting the application.
- 🔍 **Global Rule Search**: Search across thousands of rules and dozens of rule sets by abbreviation, expansion text, or description with JSON/CLI output options.
- 🛡️ **Safety & Hygiene Audit**:
  - Automatically flags invisible Unicode characters (such as `\u2028` line separators or `\u2029` paragraph separators) that break autocompletion in browser address bars or terminals.
  - Detects duplicate abbreviation triggers across multiple enabled rule sets that cause unintentional shadowing.
  - Built-in `--fix` option to automatically sanitize invisible control characters across all active rules.
- ⏱️ **Delay & Keystroke Support**: Full support for Typinator syntax including `{delay:1.5}`, `{tab}`, `{return}`, and key combinations (`{key:⌘↩}`).

---

## Installation & Setup

### Prerequisites
* macOS with **Typinator** installed and running.
* Python 3.8+ (uses standard library only — zero external dependencies).

### Usage

```bash
# Clone the repository
git clone https://github.com/vecyang1/typinator-cli.git
cd typinator-cli

# Make the CLI executable
chmod +x scripts/typinator_cli.py
```

---

## CLI Reference

### 1. List Rule Sets
```bash
python3 scripts/typinator_cli.py list-sets
```

### 2. Search Rules
```bash
# Search by keyword across all rule sets
python3 scripts/typinator_cli.py search "keyword"

# Search inside a specific rule set with JSON output
python3 scripts/typinator_cli.py search "g⌘" --set "AI prompt" --json
```

### 3. Get Rule Details
```bash
python3 scripts/typinator_cli.py get "AI prompt" "g⌘"
```

### 4. Update Rule Expansion
```bash
python3 scripts/typinator_cli.py set "AI prompt" "g⌘" --expansion "/g{delay:1.5}{tab}"
```

### 5. Create a New Rule
```bash
python3 scripts/typinator_cli.py add "AI prompt" "ggg⌘" --expansion "/g{delay:1.5}{tab}" --desc "Quick command with 1.5s delay"
```

### 6. Delete a Rule
```bash
python3 scripts/typinator_cli.py delete "AI prompt" "old_abbr"
```

### 7. Run Safety Audit & Auto-Clean
```bash
# Scan for invisible control characters (\u2028) and duplicate triggers
python3 scripts/typinator_cli.py audit

# Auto-fix invisible characters across all rules
python3 scripts/typinator_cli.py audit --fix
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

Run unit tests via standard Python unittest:

```bash
python3 -m unittest discover -s tests
```

---

## License

[MIT License](LICENSE) © 2026 V
