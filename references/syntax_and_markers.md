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

---

## 5. Trigger Suffix Conventions & Modifier Symbols

1. **Anti-Collision Suffix Pattern (`⌘`, `⇧`, `⌥`)**:
   - In rule sets like `Urls(browswers)`, `AI prompt`, and `Shortcut / Url`, abbreviations commonly terminate with a modifier glyph (most frequently `⌘`, U+2318).
   - **Rationale**: Prevents accidental expansions when typing natural English or acronyms (e.g. `pfm` as a word vs `pfm⌘` as the explicit Preply URL trigger).
   - **Agent Rule**: When adding new browser URL shortcuts or custom prompts, check the surrounding set's convention; do not add bare abbreviations without user confirmation if the set standardizes on `⌘` suffixes.

2. **Typing `⌘`, `⇧`, `⌥` on macOS**:
   - `Control + Command + Space`: Opens the Character Viewer.
   - Micro-expansion rules:
     - `;;c` ➔ `⌘` (Command)
     - `;;s` ➔ `⇧` (Shift)
     - `;;a` ➔ `⌥` (Alt / Option canonical source)
     - `;;o` ➔ `{";;a"}` (Option alias referencing `;;a`)

---

## 6. Nested Snippets & Abbreviation Inclusion (SSOT)

Typinator natively supports referencing another abbreviation dynamically:

| Marker | Description | Example |
|---|---|---|
| `{"abbreviation"}` | Dynamically evaluates and inserts another rule's expansion | `{";;a"}` evaluates `;;a` and inserts `⌥` |

### Best Practices:
1. **Prevent Source Rot**: When aliases or multiple abbreviations should yield the same output, establish one as the canonical source of truth (SSOT) and point other triggers to it via `{"<primary_abbr>"}`.
2. **Pre-Processing Execution**: Abbreviation substitutions occur *before* other nested markers are processed.
3. **No Circular Loops**: Ensure references are directed acyclic graphs (DAGs) to prevent recursion loops.

