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
   - Standardize on `...⇧` for AI goal execution and prompts, reserving `...⌘` for URLs (e.g. Grok) to avoid cross-set trigger collisions.

### Standardized AI Slash Command Matrix (Active in `AI prompt`):

| Abbr | Expansion | Token / Command | Description |
|---|---|---|---|
| `g⇧` | `/goal{delay:0.25}{tab}` | `[⏱️ goal]` | Background long-running goal loop |
| `br⇧` | `/browser{delay:0.25}{tab}` | `[browser]` | Web browser automation & search |
| `glm⇧` | `/grill-me{delay:0.25}{tab}` | `[grill-me]` | Interactive critical design interview |
| `sc⇧` | `/schedule{delay:0.25}{tab}` | `[schedule]` | One-shot timers or recurring cron jobs |
| `bo⇧` / `bs⇧` | `/boost{delay:0.25}{tab}` | `[boost]` | Multi-perspective deep reasoning mode (`bo⇧` in `AI prompt`, `bs⇧` in `Urls(browswers)`) |
| `lr⇧` | `/learn{delay:0.25}{tab}` | `[learn]` | Persist workflow behaviors & patterns |
| `tw⇧` | `/teamwork-preview{delay:0.25}{tab}` | `[teamwork-preview]` | Multi-agent collaboration preview |
| `gf⇧` | `/graphify{delay:0.25}{tab}` | `[graphify]` | Codebase knowledge graph analysis |
| `cp⇧` | `/compact{delay:0.25}{tab}` | `[compact]` | Context window compaction |
| `cl⇧` | `/clear{delay:0.25}{tab}` | `/clear` | Clear session / conversation history |
| `btw⇧` | `/btw{delay:0.25}{tab}` | `[btw]` | Ask side question without interrupting main flow |
| `nm⇧` / `not⇧` | `/notion-mcp-connector{delay:0.25}{tab}` | `[notion-mcp-connector]` | Notion MCP connector skill |
| `im⇧` / `ig⇧` | `/image-gen-with-api{delay:0.25}{tab}` | `[image-gen-with-api]` | Image generation via API skill |
| `skc⇧` | `/skill-creator{delay:0.25}{tab}` | `[skill-creator]` | Meta-skill for authoring new skills |
| `ski⇧` | `/skill-improver{delay:0.25}{tab}` | `[skill-improver]` | Meta-skill for hardening and evolving skills |
| `wc⇧` | `/wheel-check{delay:0.25}{tab}` | `[wheel-check]` | Search GitHub/npm before building custom wheels |

---

## 8. Prefix Shadowing & Collision Mechanics (Typinator Evaluation Engine)

Typinator processes keystrokes incrementally in real time across active rule sets ranked by priority order.

### The Prefix Collision Trap:
If rule $A$ (e.g. `img` in set `Midjourney`, priority #4) is a prefix of rule $B$ (e.g. `img⇧` in set `AI prompt`, priority #16):
1. When typing `i`, then `m`, then `g`, Typinator instantly matches `img`.
2. If rule $A$ has `whole_word=False`, Typinator immediately expands rule $A$ (`/imagine `) and consumes the input buffer.
3. The suffix key `⇧` is never reached in the context of the abbreviation.
4. **Typinator GUI Error**: Typinator flags rule $B$ in red as:
   ```text
   Disabled by "img" of set "Midjourney".
   ```

### Why "Whole Word" Still Collides with Modifier Symbols (`⇧`, `⌘`):
Typinator treats punctuation, spaces, tabs, and non-alphanumeric symbols (such as macOS modifier glyphs `⇧`, `⌘`, `⌥`) as word delimiters. Even if rule $A$ has "Whole Word" enabled:
- Typing `img⇧` causes Typinator to treat `img` as a whole word because `⇧` acts as a delimiter!
- Typinator expands `img` to `/imagine ` and then leaves `⇧` unhandled or appended.
- Therefore, rules sharing a bare prefix with a modifier suffix cannot coexist if evaluated in descending order.

### Diagnostic & Preflight Tooling (`typinator debug`):
Before creating or updating rules, use the CLI's Trie-based inspector:

```bash
# Debug by slash command or expansion token (e.g. /boost, /goal, /image-gen-with-api)
typinator debug /boost
typinator debug /goal

# Deep inspection of an existing rule's conflict status
typinator debug "im⇧"
typinator debug "g⇧"

# Preflight simulation before adding a new rule
typinator debug "img⇧"
```

The tool prints:
- `🟢 ACTIVE` or `🔴 DISABLED` status with exact shadowing cause and set priority ranking.
- Related rules across active sets sharing identical expansions (e.g. `bo⇧` and `bs⇧` for `/boost`).
- Actionable resolution strategies (prefix change, whole-word adjustment, or set reordering).
- Preflight simulation warning if adding a trigger would be shadowed or disable lower-priority rules.

