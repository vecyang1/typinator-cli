---
name: typinator-manager
description: Use when an agent needs to inspect, search, add, update, delete, export, import, or audit Typinator text expansion snippets, rules, keystrokes, delay markers, and rule sets on macOS via native AppleScript automation.
---

# typinator-manager

## Skill Metadata

- **Origin:** `local`
- **Source:** `https://github.com/vecyang1/typinator-cli`
- **Author:** V
- **Created:** 2026-08-28
- **Updated:** 2026-11-07
- **Version:** 1.6.1
- **Review status:** `reviewed`

Manage, configure, query, export, import, and audit Typinator expansion rules on macOS programmatically without manual UI interaction.

---

## 🚀 Quick CLI Operations

All operations are unified under the globally available CLI (`typinator` or `typinator-cli`, symlinked in `~/.local/bin/`):

```bash
# Check status
typinator status

# Restart application (recovers frozen, hung, or unresponsive state)
typinator restart
typinator restart --force

# List all rule sets and counts
typinator list-sets

# Sub-second high-speed search across all sets (<0.4s for 4,400+ rules)
typinator search "keyword"

# Search rules in a specific set (outputs JSON if needed)
typinator search "g⌘" --set "AI prompt" --json

# Get details of a single rule
typinator get "AI prompt" "g⌘"

# Deeply inspect trigger or slash command for prefix collisions, shadowing, and preflight safety
typinator debug /boost
typinator debug /goal
typinator debug "im⇧"
typinator debug "img"

# Add a new expansion rule (preflight checks nested references and prefix shadowing)
typinator add "AI prompt" "g⇧" --expansion "/goal{delay:0.25}{tab}"

# Update an existing rule's expansion
typinator set "AI prompt" "g⇧" --expansion "/goal{delay:0.25}{tab}"

# Toggle rule set enable/disable
typinator toggle-set "AI prompt" --enable

# Export & import rule sets
typinator export --set "AI prompt" -o backup.json
typinator import -i backup.json --overwrite

# Delete a rule
typinator delete "AI prompt" "unwanted_abbr" -y

# Audit for invisible control characters, prefix collisions, and nested reference integrity
typinator audit
typinator audit --set "AI prompt"

# Auto-fix invisible control characters across all rules
typinator audit --fix

# Restart Typinator (recovers frozen, hung, or unresponsive app state)
typinator restart
typinator restart --force --json

# List hourly Git backup snapshots from $TYPINATOR_SYNC_REPO (use --decode to see rule changes)
typinator snapshots --set "AI prompt" -n 10
typinator snapshots --set "AI prompt" -n 5 --decode

# Trace complete Time Machine version history of any rule across all Git commits & local mutation journal
typinator trace "wc⇧" --set "AI prompt"
typinator history "mbb⇧" --set "AI prompt"

# Compare decoded binary .tyset rules between two commits or between HEAD and LIVE disk
typinator diff 7532d3f 21ae618 --set "AI prompt"
typinator diff HEAD LIVE --set "AI prompt"

# Surgical single-rule Time Machine recovery (restores ONLY one rule via OSA without restarting Typinator)
typinator restore-rule 7532d3f "AI prompt" "wc⇧" --dry-run
typinator restore-rule 7532d3f "AI prompt" "wc⇧"

# Preview or restore an entire rule set from a Git snapshot (uses SIGKILL before disk copy)
typinator restore-snapshot <commit> --set "AI prompt" --dry-run
typinator restore-snapshot <commit> --set "AI prompt"
```

---

## 📖 Key References

* [Marker Syntax & Keystroke Reference](references/syntax_and_markers.md): Delay markers (`{delay:n}`), keystrokes (`{tab}`, `{key:...}`), inline scripts, prefix collision mechanics, and formatting gotchas.
* [AppleScript OSA API](references/applescript_api.md): Typinator scripting classes, properties, and dictionary methods.
* [Changelog](CHANGELOG.md): Version history and improvements.

---

## ⚠️ Critical Agent Rules

1. **Avoid Invisible Line Separators (`\u2028`)**: When setting multi-line expansions or pasting strings, never include `\u2028` or `\u2029`. Use `\n` or the CLI audit cleaner.
2. **Check Set Collisions**: Before adding a new abbreviation, use `search` or `audit` to ensure it is not shadowed by an active rule set ranked higher in Typinator's evaluation order.
3. **Execution Sandbox**: Calls to `osascript` targeting running GUI applications require outside-sandbox execution (`BypassSandbox: true`) on macOS.
4. **Dynamic Reference Precaution**: Before configuring a dynamic alias `{"<target>"}`, ensure `<target>` is unique across all active sets. `typinator audit` and CLI mutation commands will alert on ambiguous or dangling targets.
5. **Prefix Collision Verification (`typinator debug <abbr>`)**: If a shorter prefix (e.g. `img`) exists in a higher-priority set without whole-word constraints, longer triggers starting with that prefix (e.g. `img⇧`) are automatically disabled by Typinator (`Disabled by "img" of set "Midjourney"`). Always run `typinator debug <abbr>` to preflight triggers before adding or modifying them.
6. **Git Snapshot Recovery & SIGKILL Invariant (`typinator snapshots` / `typinator restore-snapshot`)**: Hourly binary `.tyset` backups live in `$TYPINATOR_SYNC_REPO` (driven by `com.vec.typinator-sync.plist`). Long expansions (>250B) are stored in external `X...` payload files inside `<Set>.tyset/`. When restoring from a Git commit, always use `typinator restore-snapshot <commit> [--set <set>]`, which terminates Typinator via `SIGKILL` (`killall -9 Typinator`) *before* syncing `.tyset` files on disk so Typinator's graceful shutdown save (`SAVE started`) cannot overwrite restored files with stale in-memory state. For single-rule recovery without restarting Typinator or overwriting newer sibling rules, prefer `typinator restore-rule <commit> <set> <abbr>`.
7. **Top-Right Search Filter Illusion in Typinator UI**: When a search filter is active in Typinator's top-right search bar (`Q <query>`), the left sidebar displays only the count of matching rules per set (e.g. `AI prompt: 4` instead of `143`). Always verify true rule counts via `typinator list-sets` before assuming rules were mass-deleted.
8. **Never Launch Typinator Yourself (Silent Operation)**: Typinator opens its main window on every launch (its `Open Window at Start` preference), and `open -a`, `open -g -j`, `tell application "Typinator" to activate`, or an osascript call while the app is quit all show it. Let the CLI launch it: `typinator restart`, or any rule command, launches with a one-launch override that keeps the window closed and focus unchanged. Only `typinator quick-search` is visible, by design. After a Typinator update, run `scripts/live_check_silent_launch.sh` once (exit 0 = still silent); the unit tests cannot notice a renamed preference key.
9. **Single Leading `{delay:0.25}{tab}` & 100-Char Paste Threshold (`multi_tab_paste_hazard`)**: Typinator switches from keystroke typing (`<= 100` chars) to async `⌘V` clipboard paste (`> 100` chars). Never place `{delay:0.25}{tab}` (or nested sub-commands containing `{tab}`) after `> 100` characters or chain multiple `{delay:0.25}{tab}` sequences in a single rule — doing so drops middle clipboard segments and fires raw `Tab` focus jumps out of chat composers (e.g. Paseo's `+` button). Keep reusable sub-commands (`fl⇧`, `crd⇧`, `dy⌘`, `ct⇧`, `ck⇧`, `tl⌘`) free of `{tab}` markers; see [Marker Syntax & Keystroke Reference — Section 9](references/syntax_and_markers.md).
