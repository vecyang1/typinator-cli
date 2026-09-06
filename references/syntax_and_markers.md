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
   - For web/browser address bars or slash commands (e.g. `/goal`), avoid putting a space before `{delay:...}` (i.e. use `/goal{delay:0.25}{tab}` rather than `/goal {delay:0.25}{tab}`), otherwise the address bar or input component treats it as raw text/search string rather than triggering autocomplete.

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
4. **Cross-Set Shadowing Awareness (Crucial)**:
   - When referencing `{"abbr"}`, Typinator resolves the abbreviation using its global set rank order (top-to-bottom in the UI).
   - If `abbr` exists in multiple enabled rule sets (e.g. `rp⇧` in both `Urls(AI)` and `Urls(creator)`), Typinator **silently** selects the higher-ranked set's expansion.
   - **Agent Defense Rule**: Before configuring a dynamic alias `{"target"}`, always run `typinator audit` or check `global_abbr_to_sets` to ensure `target` is unique across all active sets. Never audit sets in isolation with `--set` without verifying global uniqueness.

---

## 7. AI Slash Command & Chip Autocomplete Strategy (Antigravity / Gemini / Codec)

Modern AI IDEs (Antigravity, Cursor, VS Code, Gemini, Codec, Claude Code) use structured slash-command "chips" or "pills" (e.g. `[⏱️ goal]`) rather than raw text.

### The Golden Formula:
```text
/<command>{delay:0.25}{tab}
```

### Key Invariants:
1. **Full Command Name (`/goal` vs `/g` or `/go`)**:
   - Typing only `/g` is ambiguous if the workspace or platform offers multiple commands (e.g. `/goal` and `/grill-me`).
   - Typing the full name `/goal` uniquely resolves the match across all AI IDEs and prevents dropdown mis-selection.
2. **The 250ms Delay Window (`{delay:0.25}`)**:
   - Typing `/goal` triggers asynchronous React/Vue UI state transitions to mount and filter the command menu.
   - Sending `{tab}` with 0ms delay causes a race condition: the browser executes native Tab navigation (blurring input or focusing UI buttons) before the autocomplete listener is ready.
   - `{delay:0.25}` gives ~15-20 frames for the UI thread to mount and select the item while remaining imperceptibly instantaneous to the user.
3. **The Keystroke Marker (`{tab}`)**:
   - Converts the filtered candidate into the native IDE badge/pill `[⏱️ goal]`.
4. **Suffix Convention (`⇧` for Prompts/Commands, `⌘` for URLs)**:
   - Standardize on `g⇧` for AI goal execution, reserving `g⌘` for URLs (e.g. Grok) to avoid cross-set trigger collisions.
