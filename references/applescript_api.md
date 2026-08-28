# Typinator AppleScript / Open Scripting Architecture (OSA) Reference

Typinator includes built-in AppleScript automation support.

## Application Interface

```applescript
tell application "Typinator"
    -- Check status
    pause expansions
    resume expansions
    
    -- List rule sets
    set setNames to name of every rule set
    set setEnabled to enabled of every rule set
end tell
```

## Classes & Properties

### `rule set`
- `name` (text, r/w)
- `unique id` (text, r)
- `enabled` (boolean, r/w)
- `rule type` (abbreviations / regular expressions, r)
- `purpose` (expansion / correction, r/w)
- `rules` (list of `rule`, r)

### `rule`
- `name` / `abbreviation` (text, r/w)
- `plain expansion` (text, r/w)
- `formatted expansion` (rich text, r)
- `description` (text, r/w)
- `whole word` (boolean, r/w)
- `case handling` (case sensitive / case insensitive / case does not matter, r/w)
- `expansion count` (integer, r)
- `last expanded` (date, r)
- `unique id` (text, r)

## Common Code Patterns

### Add a Rule
```applescript
tell application "Typinator"
    tell rule set "AI prompt"
        make new rule at end of rules with properties {abbreviation:"my_abbr", plain expansion:"my_expansion"}
    end tell
end tell
```

### Update a Rule
```applescript
tell application "Typinator"
    set r to (first rule of rule set "AI prompt" whose abbreviation is "my_abbr")
    set plain expansion of r to "new_expansion"
end tell
```

### Delete a Rule
```applescript
tell application "Typinator"
    delete (first rule of rule set "AI prompt" whose abbreviation is "my_abbr")
end tell
```
