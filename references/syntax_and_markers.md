# Typinator Marker Syntax & Keystroke Reference

## 1. Keystroke Markers

Typinator supports simulating keystrokes directly within expansions:

| Marker | Description |
|---|---|
| `{tab}` | Inserts a Tab keystroke |
| `{return}` | Inserts a Return / Enter keystroke |
| `{esc}` | Inserts an Escape keystroke |
| `{key:⌘↩}` | Key combination (e.g. Command + Return) |
| `{key:⇧tab}` | Shift + Tab |
| `{key:⌥↩}` | Option + Return |
| `{key:name}` | Generic keystroke modifier syntax |

---

## 2. Delay & Pause Markers

| Marker | Description | Example |
|---|---|---|
| `{delay:n}` | Pauses expansion execution for `n` seconds (float or int). | `{delay:1.5}` waits 1.5 seconds before next action |
| `{/AppleScript delay n}` | Inline AppleScript delay (fallback for universal compatibility). | `{/AppleScript delay 1.5}` |
| `{/Shell sleep n}` | Inline Shell sleep delay. | `{/Shell sleep 1.5}` |
| `{X>}` | Suppress next replacement (pauses Typinator for the very next abbreviation). | `{X>}` |
| `{X}` | Suppress this replacement (prevents expanding the trigger word itself). | `{X}` |

---

## 3. Inline Scripts

Typinator compiles and runs inline scripts during expansion:

* **AppleScript**: `{/AppleScript return "Hello " & (current date)}`
* **Shell**: `{/Shell date "+%Y-%m-%d"}`
* **Python**: `{/Python import sys; sys.stdout.write("output")}`

---

## 4. Known Pitfalls & Gotchas

1. **Invisible Control Characters (`\u2028` Line Separator)**:
   - When copying multi-line text or pressing Shift+Enter into the Typinator GUI, macOS may insert `\u2028` (Unicode Line Separator) or `\u2029`.
   - Typinator will send this as a raw newline/enter event to the target application immediately, breaking search box autocompletions before `{delay:...}` or `{tab}` can execute.
   - **Fix**: Run `python3 scripts/typinator_cli.py audit --fix` to sanitize expansions.

2. **Trailing Space before Delay**:
   - For web/browser address bars or slash commands (e.g. `/g`), avoid putting a space before `{delay:...}` (i.e. use `/g{delay:1.5}{tab}` rather than `/g {delay:1.5}{tab}`), otherwise the address bar treats it as a search query string rather than a keyword shortcut.

3. **Rule Set Collisions**:
   - If two active rule sets have the same abbreviation trigger (e.g. `g⌘` in both `AI prompt` and `Urls(AI)`), Typinator resolves top-to-bottom based on the rule set list order.
