---
name: typinator-manager
description: Use when an agent needs to inspect, search, add, update, delete, export, import, or audit Typinator text expansion snippets, rules, keystrokes, delay markers, and rule sets on macOS via native AppleScript automation.
---

# typinator-manager

## Skill Metadata

- **Origin:** `local`
- **Source:** `/Users/vecsatfoxmailcom/Documents/A-coding/26.09.06-typinator-cli`
- **Author:** V
- **Created:** 2026-08-28
- **Updated:** 2026-08-28
- **Version:** 1.1.0
- **Review status:** `reviewed`

Manage, configure, query, export, import, and audit Typinator expansion rules on macOS programmatically without manual UI interaction.

---

## 🚀 Quick CLI Operations

All operations are unified under the globally available CLI (`typinator` or `typinator-cli`, symlinked in `~/.local/bin/`):

```bash
# Check status
typinator status

# List all rule sets and counts
typinator list-sets

# Sub-second high-speed search across all sets (<0.4s for 4,400+ rules)
typinator search "keyword"

# Search rules in a specific set (outputs JSON if needed)
typinator search "g⌘" --set "AI prompt" --json

# Get details of a single rule
typinator get "AI prompt" "g⌘"

# Add a new expansion rule
typinator add "AI prompt" "ggg⌘" --expansion "/g{delay:1.5}{tab}"

# Update an existing rule's expansion
typinator set "AI prompt" "g⌘" --expansion "/g{delay:1.5}{tab}"

# Toggle rule set enable/disable
typinator toggle-set "AI prompt" --enable

# Export & import rule sets
typinator export --set "AI prompt" -o backup.json
typinator import -i backup.json --overwrite

# Delete a rule
typinator delete "AI prompt" "unwanted_abbr" -y

# Audit for invisible control characters (\u2028 line breaks) and duplicate trigger collisions
typinator audit

# Auto-fix invisible control characters across all rules
typinator audit --fix
```

---

## 📖 Key References

* [Marker Syntax & Keystroke Reference](references/syntax_and_markers.md): Delay markers (`{delay:n}`), keystrokes (`{tab}`, `{key:...}`), inline scripts, and formatting gotchas.
* [AppleScript OSA API](references/applescript_api.md): Typinator scripting classes, properties, and dictionary methods.
* [Changelog](CHANGELOG.md): Version history and improvements.

---

## ⚠️ Critical Agent Rules

1. **Avoid Invisible Line Separators (`\u2028`)**: When setting multi-line expansions or pasting strings, never include `\u2028` or `\u2029`. Use `\n` or the CLI audit cleaner.
2. **Check Set Collisions**: Before adding a new abbreviation, use `search` or `audit` to ensure it is not shadowed by an active rule set ranked higher in Typinator's evaluation order.
3. **Execution Sandbox**: Calls to `osascript` targeting running GUI applications require outside-sandbox execution (`BypassSandbox: true`) on macOS.
