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

4. **Leading Space Convention for Slash Commands (` /<command>{delay:0.25}{tab}`)**:
   - Always prefix AI/IDE slash command expansions with a leading space ` ` (e.g. ` /goal{delay:0.35}{tab}`, ` /typinator-manager{delay:0.25}{tab}`).
   - **Rationale**: In modern IDEs and chat interfaces (Antigravity, Gemini, Claude, VS Code), slash command autocomplete chips are only triggered when preceded by whitespace or at the start of an input line. Without a leading space, typing an abbreviation mid-sentence or chaining commands (e.g. `prev/goal`) gets stuck to adjacent words or punctuation and fails to trigger autocomplete.
   - If followed by trailing text (e.g. `if need; `), also append a space after `{tab}` (e.g. ` /boost{delay:0.25}{tab} if need; `) so the trailing parameter is cleanly separated from the command token.

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

## 7. AI Slash Command Strategy (Paseo / Antigravity / Gemini / Claude Code / Codex)

Across Paseo (`module 4869` / `module 4872`), Antigravity, Claude Code, Cursor, and Codex, slash commands and skills must use the **canonical full command name + trailing space (` /<command> `)** with **zero `{delay:...}{tab}`**:

### The Golden Formula:
```text
 /<command> 
```

### Key Invariants:
1. **Full Canonical Command/Skill Name (`/starting-with-readiness` vs `/starting-with`)**:
   - Always write the complete canonical skill or slash command name (e.g. ` /starting-with-readiness `, ` /finishing-with-writeback `, ` /image-gen-with-api `, ` /betterlinks-wordpress `, ` /fluentcommunity-ops `, ` /fluentcrm-ops `, ` /hyperdx-telemetry `, ` /tikhub-social-data `, ` /gemini-deep-research-cli `, ` /chrome-devtools `, ` /adspower-browser `).
2. **Never Use `{delay:0.25}{tab}` in Slash Commands**:
   - In Paseo (`findActiveSlashCommand`, `module 4872`), any slash command preceded by a space or inline text (`position: "inline"`) or any skill not in Paseo's provider list displays `No commands found` (`s.options.length === 0`).
   - In Paseo's `useAutocomplete` (`module 4869`), when `0 === s.options.length`, Paseo **does NOT call `t.preventDefault()` on `Tab`**. Sending `{tab}` executes native browser Tab navigation, jumping DOM focus out of the `<textarea>` onto the `+` (`Add attachment`) `<button>`, stranding the cursor, dropping all trailing text/paste, and causing any trailing `Space` or `{return}` to click the `+` file-upload button!
   - Conversely, even when Paseo's `/` menu *does* match a command, `applySlashCommandReplacement` (`module 4872`) literally outputs `/<command> ` (command + space), and typing a plain space `' '` immediately closes the `/` popup (`const o = /[/\s\n\r\t"']/;`) while keeping focus 100% inside `<textarea>`.
3. **Suffix Convention (`⇧` for Prompts/Commands, `⌘` for URLs/Midjourney)**:
   - Standardize on `...⇧` for AI prompts and skills, and `...⌘` for URLs and app-specific triggers (e.g. `Midjourney` uses `img⌘` -> `/imagine ` so `img⇧` in `AI prompt` is never prefix-shadowed).

### Standardized AI Slash Command Matrix (Active in `AI prompt` & `Urls(browswers)`):

| Abbr | Expansion | Token / Command | Description |
|---|---|---|---|
| `gg⇧` / `g⇧` | ` /goal ` / `{"gg⇧"}{return}` | `/goal` | Background long-running goal loop (`g⇧` auto-submits) |
| `br⇧` | ` /browser ` | `/browser` | Web browser automation & search |
| `glm⇧` | ` /grill-me ` | `/grill-me` | Interactive critical design interview |
| `sc⇧` / `scc⇧` | ` /scheduled-task-rescheduler for above to see if need create cadance or audit, updates ; {"pt⇧"} {"cj⇧"}...` | `/scheduled-task-rescheduler` | Scheduled task cadence & sidecar audit prompt (`scc⇧` appends `{return}`) |
| `pt⇧` | `plz scan patterns, ur log or other intake data source /feedback source and see how should be productive enough as input and audit sidecard if need;...` | Sub-block | Pattern & intake/feedback sidecar audit block referenced by `sc⇧` |
| `bo⇧` / `bs⇧` | ` /boost ` / ` /boost proactively if need or solo mode; ` | `/boost` | Multi-perspective deep reasoning mode (`bo⇧` in `AI prompt`, `bs⇧` in `Urls(browswers)`) |
| `lr⇧` | ` /learn ` | `/learn` | Persist workflow behaviors & patterns |
| `tw⇧` / `baa⇧` | ` /teamwork-preview ` | `/teamwork-preview` | Multi-agent collaboration preview |
| `gf⇧` | ` /graphify ` | `/graphify` | Codebase knowledge graph analysis |
| `cp⇧` | ` /compact {return}` | `/compact` | Context window compaction |
| `cl⇧` | ` /clear ` | `/clear` | Clear session / conversation history |
| `bt⇧` / `btt⇧` | ` /btw {return}` | `/btw` | Ask side question without interrupting main flow |
| `ns⇧` / `nt⇧` / `not⇧` | ` /notion-mcp-connector ` | `/notion-mcp-connector` | Notion MCP connector skill (`not⇧` points to `{"ns⇧"}`) |
| `img⇧` / `im⇧` / `ig⇧` | ` /image-gen-with-api ` | `/image-gen-with-api` | Image generation via API skill (`img⇧` and `ig⇧` alias `{"im⇧"}`; `Midjourney` uses `img⌘`) |
| `cz⇧` | ` /image-gen-with-api via chatgpt2api-ops ` | `/image-gen-with-api` | Image generation via `chatgpt2api-ops` |
| `sk⇧` | ` /skill-creator do i need or absorb or skip; ` | `/skill-creator` | Atomic skill-creator evaluation prompt |
| `ski⇧` | ` /skill-improver ` | `/skill-improver` | Meta-skill for hardening and evolving skills |
| `wc⇧` | ` /wheel-check or use context7 ... /1password if need; /graphify` | `/wheel-check ...` | Atomic tab-free wheel-check + anti-fragmentation + UI observability + 1Password + Graphify macro (stored in `AI prompt.tyset/X3EF1387A`) |

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

---

## 9. The 200-Char `directString` Clipboard Threshold + Paseo `No commands found` `{tab}` Focus Jump

### Binary Internals (`Typinator 9.2` @ `0x1000bf63a` & `AppSettings.plist` + Paseo `module 4869`):
In `-[TYStringPiece needsClipboard]` (`0x1000bf63a`) and `/Applications/Typinator.app/Contents/Resources/AppSettings.plist`:
1. **`directString = 200` (`0x1000bf715`–`0x1000bf752`)**:
   - Any text piece with `length <= 200` characters, containing none of `directException = "/--/\"/\'/"` (`--`, `"`, `'`), and `splitPostingPartsForString: <= 20` returns `needsClipboard = NO (0)`. Typinator sends it via `-[TYKeyGenerator sendString:]` (`CGEventKeyboardSetUnicodeString` direct keystroke stream).
   - Any text piece with **`length > 200` characters** (or containing `--`, `"`, `'`) returns **`needsClipboard = YES (1)`** (`0x1000bfadd`), forcing Typinator to send that piece via **`⌘V` Clipboard Paste (`copyToClipboard` + `Cmd+V`)**.
2. **Paseo `No commands found` Tab Behavior (`module 4869` & `module 4872`)**:
   - When an expansion starts with a leading space and slash command (`" /wheel-check"` or `" /ego-browser"`), Paseo's `findActiveSlashCommand` classifies it as `position: "inline"` and filters for `source === "provider" && command.kind === "skill"`.
   - In Paseo's Antigravity (`Gemini 4 Argon`) sessions, `s.options` is empty (`No commands found`).
   - In `useAutocomplete` (`module 4869`): `if (!s.isVisible || 0 === s.options.length) return !1;` — when `No commands found` is displayed, Paseo **does NOT call `t.preventDefault()` on `Tab`**, so `{delay:0.25}{tab}` executes a native browser `Tab` and jumps DOM focus from `<textarea>` onto the `+` (`Add attachment`) `<button>`!
   - When the trailing text piece after `{tab}` exceeds **200 characters** (like `wc⇧` at 349 chars, vs `eg⇧` at 199 chars), Typinator sends the trailing piece via **`⌘V` Clipboard Paste**, which is **100% ignored/dropped by the focused `+` `<button>`**!

### The Golden Safe-Expansion Rules (Enforced by `typinator audit`):
1. **Never Use `{delay:0.25}{tab}` When Followed by `> 200` Chars (or Quotes/`--`), or When the Full `/skill-name` Is Already Followed by Prompt Text**:
   - In Paseo (`applySlashCommandReplacement`, `module 4872`), selecting a slash command with `Tab` literally outputs `/command ` (command name + trailing space), and typing a space after `/command` immediately closes the `/` popup (`const o = /[/\s\n\r\t"']/;`).
   - Therefore, long prompt macros (`wc⇧`, `wcc⇧`, `sc⇧`, `scc⇧`, `sk⇧`, `mm⇧`, `mmm⇧`, `zq⇧`, `bag⇧`, `eg⇧`, `ggg⇧`, `egm⇧`, `egg⇧`) use a plain space after `/wheel-check`, `/scheduled-task-rescheduler`, `/skill-creator`, `/memory-vault`, or `/ego-browser` with **zero `{delay:0.25}{tab}`**, pasting the entire prompt in a single atomic `⌘V` while focus remains inside the `<textarea>`.
2. **Modular Sub-Command Hierarchy (`0` `{tab}`s in Reusable Building Blocks)**:
   - **Level-0 Atomic Blocks (`0` `{tab}`s)**: `fl⇧` (file-owner thinking), `crd⇧` (credentials/readiness/docs check), `dy⌘` (SSOT & unidirectional data flow), `ct⇧` (E2E verification + `{"fl⇧"}` + single-language output), `ck⇧` (context/tools/memory check), `pt⇧` (pattern/log/intake sidecar audit), `mm⇧` (`/memory-vault check or note down if need; `), `sk⇧` (`/skill-creator do i need or absorb or skip; `), `cj⇧` (`output in chinese`).
   - **Level-1 Long Slash Prompt Macros (`0` `{tab}`s, Atomic Paste)**: `wc⇧`, `wcc⇧`, `sc⇧` (composes `{"pt⇧"} {"cj⇧"}`), `scc⇧` (`{"sc⇧"}{return}`), `mmm⇧` (`{"mm⇧"}{return}`), `eg⇧`, `ggg⇧`, `egm⇧`, `egg⇧`, `zq⇧`, `bag⇧`.
   - **Level-2 Composite Prompts (`0` `{tab}`s, composed via `{"..."}`)**: `tl⌘` (composes `{"dy⌘"}`, `{"crd⇧"}`, `{"ct⇧"}`, `{"cj⇧"}`), `tll⌘` (extends `{"tl⌘"}`), `doc⇧` / `sv⇧` (extends `{"ct⇧"}`), `ll⇧` / `lll⇧`, `ba⇧`, `bug⇧` (extends `{"tl⌘"}`), `ss⇧`.



