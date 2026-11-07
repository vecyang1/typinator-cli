#!/usr/bin/env python3
"""
Typinator CLI - Production-Grade Automation & Management Harness for macOS Typinator.
Supports programmatic rule querying, live in-memory updates, batch export/import,
safety auditing (invisible Unicode characters & trigger collision detection),
and full AppleScript / Open Scripting Architecture (OSA) integration.
"""

import sys
import os
import re
import json
import argparse
import plistlib
import shutil
import struct
import subprocess
import tempfile
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Callable

VERSION = "1.6.0"

def _resolve_default_sync_repo() -> str:
    env_val = os.environ.get("TYPINATOR_SYNC_REPO")
    if env_val:
        return os.path.expanduser(env_val)
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Documents", "A-coding", "A-Sync", "typinator-sync"),
        os.path.join(home, ".local", "share", "typinator-sync"),
    ]
    for c in candidates:
        if os.path.isdir(os.path.join(c, ".git")):
            return c
    return candidates[0]


DEFAULT_SYNC_REPO = _resolve_default_sync_repo()
DEFAULT_LIVE_SETS = os.path.expanduser(
    os.environ.get("TYPINATOR_SETS_DIR", os.path.join("~", "Library", "Application Support", "Typinator", "Sets"))
)
DEFAULT_MUTATION_LOG = os.path.expanduser(
    os.environ.get("TYPINATOR_MUTATION_LOG", os.path.join("~", ".config", "typinator", "time-machine", "mutations.jsonl"))
)

TYPINATOR_APP_PATH = "/Applications/Typinator.app"

# Typinator 9.x opens its main window on every launch while its
# "Open Window at Start" preference is on, whoever launches it; `open -g -j`
# does not prevent that. Passing the key in the NSUserDefaults argument domain
# overrides it for this one launch and leaves the saved preference untouched.
# Measured 2026-11-07, see vault/sessions/2026-11-07-silent-cli.md.
QUIET_LAUNCH_ARGS = ["--args", "-Open Window at Start", "NO"]

NESTED_REFERENCE_PATTERN = re.compile(r'\{"([^"\n]+)"\}')
REVERSED_TAB_DELAY_PATTERN = re.compile(r'\{tab\}\s*(\{delay:[^}]+\})', re.IGNORECASE)
MALFORMED_NESTED_REF_PATTERN = re.compile(r'\{\{"([^"\n]+)"\}\}')
DELAY_TAB_SEQUENCE_PATTERN = re.compile(r'\{delay:[^}]+\}\s*\{tab\}', re.IGNORECASE)
KEY_MARKER_STRIP_PATTERN = re.compile(r'\{(?:return|enter|tab|delay:[^}]+|key:[^}]+)\}', re.IGNORECASE)
CLIPBOARD_PASTE_CHAR_THRESHOLD = 100
DIRECT_STRING_MAX_CHARS = 200
DIRECT_STRING_EXCEPTIONS = ("--", '"', "'")

# In-process cache of rules mutated via AppleScript before Typinator flushes .tyset to disk
_RECENT_IN_MEMORY_UPDATES: Dict[Tuple[str, str], Dict[str, Any]] = {}


def resolve_nested_expansion(
    abbr: str,
    rules_by_abbr: Dict[str, str],
    raw_expansion: Optional[str] = None,
    _visited: Optional[set] = None
) -> str:
    """
    Recursively resolve Typinator nested references `{"other_abbr"}` into the final flat string.
    Guards against self-recursion and cyclic references via `_visited`.
    """
    if _visited is None:
        _visited = set()
    if abbr in _visited:
        return f"[CYCLE:{abbr}]"
    _visited = _visited | {abbr}
    exp = raw_expansion if raw_expansion is not None else rules_by_abbr.get(abbr, "")

    def _repl(match: re.Match) -> str:
        ref = match.group(1)
        if ref not in rules_by_abbr:
            return match.group(0)
        return resolve_nested_expansion(ref, rules_by_abbr, _visited=_visited)

    return NESTED_REFERENCE_PATTERN.sub(_repl, exp)

INVISIBLE_CHARS_MAP = {
    '\u2028': 'LINE_SEPARATOR (\\u2028)',
    '\u2029': 'PARAGRAPH_SEPARATOR (\\u2029)',
    '\ufeff': 'ZERO_WIDTH_NO_BREAK_SPACE (\\ufeff)',
    '\u200b': 'ZERO_WIDTH_SPACE (\\u200b)',
}


def is_word_char(ch: str) -> bool:
    """
    Return True if character is an alphanumeric word character in Typinator.
    Typinator's internal wordCharacterSet uses +[NSCharacterSet alphanumericCharacterSet].
    Non-word characters (symbols like ⇧, ⌘, punctuation, whitespace) act as word delimiters.
    """
    return ch.isalnum()


class PrefixTrie:
    """
    High-performance prefix trie for sub-millisecond prefix collision and shadowing detection.
    Supports case-insensitive prefix search across thousands of active rules.
    """
    def __init__(self):
        self.root: Dict[str, Any] = {}

    def insert(self, rule: Dict[str, Any]) -> None:
        abbr = rule.get("abbreviation", "")
        if not abbr:
            return
        node = self.root
        for ch in abbr.lower():
            if ch not in node:
                node[ch] = {"_rules": []}
            node = node[ch]
        node.setdefault("_rules", []).append(rule)

    def find_prefixes(self, abbr: str) -> List[Dict[str, Any]]:
        """Find all rules whose abbreviation is a strict prefix of `abbr`."""
        if not abbr:
            return []
        prefixes = []
        node = self.root
        abbr_lower = abbr.lower()
        for i, ch in enumerate(abbr_lower):
            if ch not in node:
                break
            node = node[ch]
            # Any rule at this node before the final character of `abbr` is a strict prefix
            if i < len(abbr_lower) - 1 and node.get("_rules"):
                prefixes.extend(node["_rules"])
        return prefixes

    def find_extensions(self, abbr: str) -> List[Dict[str, Any]]:
        """Find all rules that have `abbr` as a strict prefix (i.e. extensions of `abbr`)."""
        if not abbr:
            return []
        node = self.root
        for ch in abbr.lower():
            if ch not in node:
                return []
            node = node[ch]

        extensions = []
        def _collect(curr: Dict[str, Any], is_root: bool = False):
            if not is_root and curr.get("_rules"):
                extensions.extend(curr["_rules"])
            for k, child in curr.items():
                if k != "_rules" and isinstance(child, dict):
                    _collect(child, is_root=False)

        _collect(node, is_root=True)
        return extensions


def run_applescript(script: str, timeout_sec: int = 30) -> str:
    """Execute an AppleScript string via osascript and return stdout.

    A script that targets Typinator while the app is quit would make osascript
    launch it, and that launch shows Typinator's main window. Launch it quietly
    first so osascript only ever talks to a running app.
    """
    if 'application "Typinator"' in script and not is_typinator_running():
        launch_typinator_quietly()
    try:
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"AppleScript execution timed out after {timeout_sec} seconds.")

    if res.returncode != 0:
        err = res.stderr.strip()
        if "-600" in err:
            raise RuntimeError(
                "Typinator is not running (or quit during the call). "
                "Run `typinator restart` to relaunch it in the background without its window."
            )
        if "-1728" in err:
            raise LookupError(f"Target object not found in Typinator: {err}")
        raise RuntimeError(f"AppleScript error: {err}")
    return res.stdout.strip()


def escape_as(s: str) -> str:
    """Escape a string safely for insertion into AppleScript double quotes."""
    if s is None:
        return ""
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\t", "\\t")
    )


def is_typinator_running() -> bool:
    """Check if Typinator is currently running on macOS."""
    res = subprocess.run(["pgrep", "-x", "Typinator"], capture_output=True)
    return res.returncode == 0


def _typinator_pids() -> List[int]:
    res = subprocess.run(["pgrep", "-x", "Typinator"], capture_output=True, text=True)
    return [int(p) for p in res.stdout.split() if p.isdigit()]


def launch_typinator_quietly(timeout_sec: float = 5.0) -> int:
    """Launch Typinator in the background with no main window and no focus change.

    The single launch site for the whole CLI. Returns the running PID. Does
    nothing when Typinator already runs: `open` against a running app sends a
    reopen event, and Typinator answers that by showing its main window.
    """
    pids = _typinator_pids()
    if pids:
        return pids[0]
    if not os.path.isdir(TYPINATOR_APP_PATH):
        raise FileNotFoundError(f"Typinator application not found at '{TYPINATOR_APP_PATH}'")

    res = subprocess.run(
        ["open", "-g", "-j", "-a", TYPINATOR_APP_PATH, *QUIET_LAUNCH_ARGS],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to launch Typinator: {res.stderr.strip()}")

    deadline = time.time() + timeout_sec
    while True:
        pids = _typinator_pids()
        if pids:
            return pids[0]
        if time.time() >= deadline:
            raise TimeoutError(f"Typinator did not start within {timeout_sec} seconds after launch.")
        time.sleep(0.3)


def get_status() -> Dict[str, Any]:
    """Retrieve overall Typinator application and rule status."""
    running = is_typinator_running()
    if not running:
        return {
            "status": "not_running",
            "message": "Typinator is not running on this machine."
        }

    sc = '''
    tell application "Typinator"
        set sNames to name of every rule set
        set sEnabled to enabled of every rule set
        set totalRules to count of rules of every rule set
        set enabledSets to 0
        repeat with i from 1 to count of sNames
            if (item i of sEnabled) is true then
                set enabledSets to enabledSets + 1
            end if
        end repeat
        return (count of sNames as text) & "\t" & (enabledSets as text) & "\t" & (totalRules as text)
    end tell
    '''
    raw = run_applescript(sc)
    parts = raw.split("\t")
    total_sets = int(parts[0]) if len(parts) > 0 else 0
    enabled_sets = int(parts[1]) if len(parts) > 1 else 0
    total_rules = int(parts[2]) if len(parts) > 2 else 0

    return {
        "status": "running",
        "total_rule_sets": total_sets,
        "enabled_rule_sets": enabled_sets,
        "total_rules": total_rules
    }


def list_sets() -> List[Dict[str, Any]]:
    """List all rule sets with enabled status and rule counts."""
    sc = '''
    tell application "Typinator"
        set sNames to name of every rule set
        set sEnabled to enabled of every rule set
        set outStr to ""
        repeat with i from 1 to count of sNames
            set aSet to item i of rule sets
            set rCount to 0
            try
                set rCount to count of rules of aSet
            end try
            set outStr to outStr & (item i of sNames) & "\t" & (item i of sEnabled as text) & "\t" & (rCount as text) & "===TYPINATOR_ITEM_DELIMITER==="
        end repeat
        return outStr
    end tell
    '''
    raw = run_applescript(sc)
    results = []
    if not raw:
        return results
    for item in raw.split("===TYPINATOR_ITEM_DELIMITER==="):
        if not item.strip():
            continue
        parts = item.split("\t")
        if len(parts) >= 3:
            results.append({
                "name": parts[0],
                "enabled": parts[1].strip().lower() == "true",
                "count": int(parts[2].strip())
            })
    return results


def toggle_set(set_name: str, enabled: bool) -> bool:
    """Enable or disable a specific rule set."""
    sc = f'''
    tell application "Typinator"
        set enabled of (first rule set whose name is "{escape_as(set_name)}") to {str(enabled).lower()}
        return "OK"
    end tell
    '''
    res = run_applescript(sc)
    return res == "OK"


def search_rules(query: str = "", set_name: Optional[str] = None, deep: bool = False) -> List[Dict[str, Any]]:
    """
    Search rules across sets by abbreviation, description, or expansion.
    Uses bulk `rule table` and `whole word` OSA properties for sub-second retrieval across thousands of rules.
    Annotates each rule with set_priority, rule_index, and whole_word.
    """
    if set_name:
        sc = f'''
        tell application "Typinator"
            try
                set sNames to name of every rule set
                set setIdx to 0
                repeat with i from 1 to count of sNames
                    if item i of sNames is "{escape_as(set_name)}" then
                        set setIdx to i - 1
                        exit repeat
                    end if
                end repeat
                set aSet to (item (setIdx + 1) of rule sets)
                set sEn to enabled of aSet
                set t to rule table of aSet
                set oldDelims to AppleScript's text item delimiters
                set AppleScript's text item delimiters to ","
                set wwStr to (whole word of every rule of aSet) as text
                set AppleScript's text item delimiters to oldDelims
                return "===TYPINATOR_SET_DELIMITER===" & "{escape_as(set_name)}" & "===SET===" & (sEn as text) & "===ENABLED===" & (setIdx as text) & "===PRIORITY===" & wwStr & "===WW===" & t
            on error
                return ""
            end try
        end tell
        '''
    else:
        sc = '''
        tell application "Typinator"
            set sNames to name of every rule set
            set sEnabled to enabled of every rule set
            set outStr to ""
            set oldDelims to AppleScript's text item delimiters
            repeat with i from 1 to count of sNames
                set aSet to (item i of rule sets)
                set sName to item i of sNames
                set sEn to item i of sEnabled
                set t to ""
                try
                    set t to rule table of aSet
                end try
                set wwStr to ""
                try
                    set AppleScript's text item delimiters to ","
                    set wwStr to (whole word of every rule of aSet) as text
                end try
                set outStr to outStr & "===TYPINATOR_SET_DELIMITER===" & sName & "===SET===" & (sEn as text) & "===ENABLED===" & wwStr & "===WW===" & t
            end repeat
            set AppleScript's text item delimiters to oldDelims
            return outStr
        end tell
        '''

    raw = run_applescript(sc)
    results = []
    if not raw:
        return results

    q_lower = query.lower()
    set_blocks = raw.split("===TYPINATOR_SET_DELIMITER===")

    set_index = 0
    for block in set_blocks:
        if "===SET===" not in block or "===ENABLED===" not in block:
            continue
        header, content = block.split("===ENABLED===", 1)
        s_name, s_en_str = header.split("===SET===", 1)
        s_enabled = s_en_str.strip().lower() == "true"

        if "===PRIORITY===" in content:
            pri_part, content = content.split("===PRIORITY===", 1)
            try:
                set_priority_val = int(pri_part.strip())
            except ValueError:
                set_priority_val = set_index
        else:
            set_priority_val = set_index

        if "===WW===" in content:
            ww_raw, table_content = content.split("===WW===", 1)
            ww_flags = [v.strip().lower() == "true" for v in ww_raw.split(",") if v.strip()]
        else:
            ww_flags = []
            table_content = content

        s_name_clean = s_name.strip()
        live_rules_map: Dict[str, Dict[str, Any]] = {}
        if os.path.isdir(DEFAULT_LIVE_SETS):
            try:
                live_rules_map = load_set_rules_at_ref(s_name_clean, ref="LIVE")
            except Exception:
                live_rules_map = {}

        rule_idx = 0
        for line in table_content.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                abbr = parts[0]
                uid = parts[1]
                exp_or_desc = "\t".join(parts[2:]) if len(parts) > 2 else ""
                is_ww = ww_flags[rule_idx] if rule_idx < len(ww_flags) else False

                cached = _RECENT_IN_MEMORY_UPDATES.get((s_name_clean, abbr))
                live_rule = live_rules_map.get(abbr)
                if cached is not None:
                    exp_val = cached.get("expansion", exp_or_desc)
                    desc_val = cached.get("description", "")
                elif live_rule is not None:
                    # Typinator's OSA `rule table` returns `description` (comment) in column 3
                    # instead of `expansion` whenever `description` is non-empty, and flattens
                    # multiline / external X* payloads. Overlay the decoded .tyset rule payload.
                    exp_val = live_rule.get("expansion", exp_or_desc)
                    desc_val = live_rule.get("description", "")
                else:
                    exp_val = exp_or_desc
                    desc_val = ""

                if not query or (
                    q_lower in abbr.lower()
                    or q_lower in exp_val.lower()
                    or q_lower in desc_val.lower()
                    or q_lower in exp_or_desc.lower()
                ):
                    results.append({
                        "set": s_name_clean,
                        "set_enabled": s_enabled,
                        "set_priority": set_priority_val,
                        "rule_index": rule_idx,
                        "abbreviation": abbr,
                        "expansion": exp_val,
                        "description": desc_val,
                        "id": uid,
                        "whole_word": is_ww
                    })
                rule_idx += 1
        set_index += 1
    return results


def get_rule(set_name: str, abbreviation: str) -> Optional[Dict[str, Any]]:
    """Get details of a single rule by set name and abbreviation."""
    sc = f'''
    tell application "Typinator"
        try
            set r to (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
            set a to abbreviation of r
            set e to plain expansion of r
            set d to description of r
            set uid to unique id of r
            set ww to whole word of r
            set uCount to 0
            try
                set uCount to expansion count of r
            end try
            return a & "===TYPINATOR_FIELD_DELIMITER===" & e & "===TYPINATOR_FIELD_DELIMITER===" & d & "===TYPINATOR_FIELD_DELIMITER===" & uid & "===TYPINATOR_FIELD_DELIMITER===" & (ww as text) & "===TYPINATOR_FIELD_DELIMITER===" & (uCount as text)
        on error
            return ""
        end try
    end tell
    '''
    raw = run_applescript(sc)
    if not raw:
        return None
    parts = raw.split("===TYPINATOR_FIELD_DELIMITER===")
    if len(parts) >= 6:
        exp_count = 0
        try:
            exp_count = int(parts[5].strip())
        except (ValueError, TypeError):
            pass
        return {
            "set": set_name,
            "abbreviation": parts[0],
            "expansion": parts[1],
            "description": parts[2],
            "id": parts[3],
            "whole_word": parts[4].strip().lower() == "true",
            "expansion_count": exp_count
        }
    return None


def record_mutation_journal(
    action: str,
    set_name: str,
    abbreviation: str,
    old_rule: Optional[Dict[str, Any]] = None,
    new_expansion: Optional[str] = None,
    new_description: Optional[str] = None,
    new_whole_word: Optional[bool] = None,
    journal_path: str = DEFAULT_MUTATION_LOG
) -> None:
    """Append a local Time Machine pre-mutation journal entry before modifying or deleting a rule."""
    try:
        os.makedirs(os.path.dirname(journal_path), exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "set": set_name,
            "abbreviation": abbreviation,
            "old_expansion": old_rule.get("expansion") if old_rule else None,
            "old_description": old_rule.get("description") if old_rule else None,
            "old_whole_word": old_rule.get("whole_word") if old_rule else None,
            "new_expansion": new_expansion,
            "new_description": new_description,
            "new_whole_word": new_whole_word,
        }
        with open(journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def set_rule_expansion(
    set_name: str,
    abbreviation: str,
    expansion: Optional[str] = None,
    description: Optional[str] = None,
    whole_word: Optional[bool] = None
) -> bool:
    """Update an existing rule's expansion, description, or whole-word option."""
    updates = []
    if expansion is not None:
        updates.append(f'set plain expansion of r to "{escape_as(expansion)}"')
    if description is not None:
        updates.append(f'set description of r to "{escape_as(description)}"')
    if whole_word is not None:
        updates.append(f'set whole word of r to {str(whole_word).lower()}')

    if not updates:
        return True

    old_rule = None
    try:
        old_rule = get_rule(set_name, abbreviation)
    except Exception:
        pass

    update_block = "\n".join(updates)
    sc = f'''
    tell application "Typinator"
        set r to (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
        {update_block}
        return unique id of r
    end tell
    '''
    res = run_applescript(sc)
    ok = bool(res)
    if ok:
        final_exp = expansion if expansion is not None else (old_rule.get("expansion", "") if old_rule else "")
        final_desc = description if description is not None else (old_rule.get("description", "") if old_rule else "")
        final_ww = whole_word if whole_word is not None else (old_rule.get("whole_word", False) if old_rule else False)
        _RECENT_IN_MEMORY_UPDATES[(set_name, abbreviation)] = {
            "expansion": final_exp,
            "description": final_desc,
            "whole_word": final_ww,
        }
    if ok and old_rule:
        record_mutation_journal(
            action="update",
            set_name=set_name,
            abbreviation=abbreviation,
            old_rule=old_rule,
            new_expansion=expansion if expansion is not None else old_rule.get("expansion"),
            new_description=description if description is not None else old_rule.get("description"),
            new_whole_word=whole_word if whole_word is not None else old_rule.get("whole_word"),
        )
    return ok


def add_rule(
    set_name: str,
    abbreviation: str,
    expansion: str,
    description: str = "",
    whole_word: bool = False
) -> str:
    """Add a new rule to a specified rule set."""
    # Check if already exists in this set
    existing = get_rule(set_name, abbreviation)
    if existing:
        raise ValueError(f"Rule '{abbreviation}' already exists in set '{set_name}'. Use 'set' subcommand to update.")

    sc = f'''
    tell application "Typinator"
        tell rule set "{escape_as(set_name)}"
            set newRule to make new rule at end of rules with properties {{abbreviation:"{escape_as(abbreviation)}", plain expansion:"{escape_as(expansion)}", description:"{escape_as(description)}", whole word:{str(whole_word).lower()}}}
            return unique id of newRule
        end tell
    end tell
    '''
    uid = run_applescript(sc)
    if uid:
        _RECENT_IN_MEMORY_UPDATES[(set_name, abbreviation)] = {
            "expansion": expansion,
            "description": description,
            "whole_word": whole_word,
        }
        record_mutation_journal(
            action="create",
            set_name=set_name,
            abbreviation=abbreviation,
            old_rule=None,
            new_expansion=expansion,
            new_description=description,
            new_whole_word=whole_word,
        )
    return uid


def delete_rule(set_name: str, abbreviation: str) -> bool:
    """Delete a rule from a specified rule set."""
    existing = get_rule(set_name, abbreviation)
    if not existing:
        raise LookupError(f"Rule '{abbreviation}' not found in set '{set_name}'.")

    sc = f'''
    tell application "Typinator"
        delete (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
        return "OK"
    end tell
    '''
    res = run_applescript(sc)
    ok = res == "OK"
    if ok:
        _RECENT_IN_MEMORY_UPDATES.pop((set_name, abbreviation), None)
        record_mutation_journal(
            action="delete",
            set_name=set_name,
            abbreviation=abbreviation,
            old_rule=existing,
            new_expansion=None,
            new_description=None,
            new_whole_word=None,
        )
    return ok


def export_rules(set_name: Optional[str] = None) -> Dict[str, Any]:
    """Export rules from all or a specific set into a structured JSON payload."""
    rules = search_rules(set_name=set_name)
    export_payload = {
        "exported_at": datetime.now().isoformat(),
        "source": "typinator-cli",
        "version": VERSION,
        "set_filter": set_name,
        "total_rules": len(rules),
        "rules": rules
    }
    return export_payload


def import_rules(data: Dict[str, Any], target_set: Optional[str] = None, overwrite: bool = False) -> Dict[str, int]:
    """Import rules from a JSON structure into Typinator."""
    rules = data.get("rules", [])
    created = 0
    updated = 0
    skipped = 0

    for r in rules:
        s_name = target_set or r.get("set") or "Default Set"
        abbr = r.get("abbreviation")
        exp = r.get("expansion")
        desc = r.get("description", "")
        ww = r.get("whole_word", False)

        if not abbr or exp is None:
            skipped += 1
            continue

        existing = get_rule(s_name, abbr)
        if existing:
            if overwrite:
                set_rule_expansion(s_name, abbr, expansion=exp, description=desc, whole_word=ww)
                updated += 1
            else:
                skipped += 1
        else:
            add_rule(s_name, abbr, exp, description=desc, whole_word=ww)
            created += 1

    return {"created": created, "updated": updated, "skipped": skipped}


def validate_nested_references(
    expansion: str,
    current_abbr: Optional[str] = None,
    rules_cache: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """Validate any nested references in expansion text against active rule sets."""
    warnings = []
    matches = NESTED_REFERENCE_PATTERN.findall(expansion)
    if not matches:
        return warnings

    remaining_matches = []
    for ref_abbr in matches:
        if current_abbr and ref_abbr == current_abbr:
            warnings.append({
                "type": "circular_nested_reference",
                "ref": ref_abbr,
                "message": f"Circular reference: rule '{current_abbr}' references itself."
            })
        else:
            remaining_matches.append(ref_abbr)

    if not remaining_matches:
        return warnings

    if rules_cache is not None:
        global_rules = rules_cache
    else:
        try:
            global_rules = search_rules()
        except Exception:
            global_rules = []

    global_abbr_to_sets: Dict[str, List[str]] = {}
    for r in global_rules:
        if r.get("set_enabled", True):
            global_abbr_to_sets.setdefault(r["abbreviation"], []).append(r["set"])

    for ref_abbr in remaining_matches:
        if ref_abbr not in global_abbr_to_sets:
            warnings.append({
                "type": "dangling_nested_reference",
                "ref": ref_abbr,
                "message": f"Referenced abbreviation '{ref_abbr}' not found in any active rule set."
            })
        elif len(global_abbr_to_sets[ref_abbr]) > 1:
            sets = global_abbr_to_sets[ref_abbr]
            warnings.append({
                "type": "ambiguous_nested_reference",
                "ref": ref_abbr,
                "active_in_sets": sets,
                "message": f"Referenced abbreviation '{ref_abbr}' exists in multiple active sets: {sets}. Typinator will evaluate the highest-ranked set."
            })
    return warnings


def audit_rules(fix: bool = False, set_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Audit rules for:
    1. Invisible / rogue Unicode control characters (\\u2028, \\u2029, \\ufeff, \\u200b).
    2. Duplicate abbreviation triggers across enabled rule sets (cross-set global collision detection).
    3. Prefix collisions / prefix shadowing (where an active rule like 'img' shadows longer rules like 'img⇧').
    4. Empty abbreviation triggers in active sets.
    5. Nested reference integrity ({"abbr"}): dangling, ambiguous (multi-set shadow), or circular references.
    """
    global_rules = search_rules()

    # Active rules sorted strictly by set priority (0-indexed list order) and rule index
    active_rules = [
        r for r in global_rules
        if r.get("set_enabled", True) and r.get("abbreviation")
    ]
    active_rules.sort(key=lambda x: (x.get("set_priority", 0), x.get("rule_index", 0)))

    global_abbr_to_sets: Dict[str, List[str]] = {}
    for r in active_rules:
        s_name = r["set"]
        if s_name not in global_abbr_to_sets.setdefault(r["abbreviation"], []):
            global_abbr_to_sets[r["abbreviation"]].append(s_name)

    issues = []
    fixed_count = 0

    # 1. Empty abbreviation detection
    for r in global_rules:
        if r.get("set_enabled", True) and not r.get("abbreviation", ""):
            issues.append({
                "type": "empty_abbreviation",
                "set": r["set"],
                "abbreviation": "",
                "note": "Active rule has an empty abbreviation trigger and cannot expand"
            })

    # 2. Exact duplicate trigger collisions
    checked_collision_abbrs = set()
    for r in active_rules:
        abbr = r["abbreviation"]
        if abbr not in checked_collision_abbrs:
            active_sets = global_abbr_to_sets.get(abbr, [])
            if len(active_sets) > 1:
                checked_collision_abbrs.add(abbr)
                issues.append({
                    "type": "duplicate_trigger_collision",
                    "abbreviation": abbr,
                    "active_in_sets": active_sets,
                    "primary_set": active_sets[0],
                    "shadowed_sets": active_sets[1:],
                    "note": f"Set '{active_sets[0]}' has priority and will shadow sets {active_sets[1:]}"
                })

    # 3. Prefix collisions / prefix shadowing using high-performance Trie
    trie = PrefixTrie()
    for r in active_rules:
        abbr_r = r["abbreviation"]
        ww_r = r.get("whole_word", False)
        set_r = r["set"]
        pri_r = r.get("set_priority", 0)

        prefixes = trie.find_prefixes(abbr_r)
        for p in prefixes:
            abbr_p = p["abbreviation"]
            ww_p = p.get("whole_word", False)
            set_p = p["set"]
            pri_p = p.get("set_priority", 0)

            next_char = abbr_r[len(abbr_p)]
            if not ww_p or not is_word_char(next_char):
                reason = (
                    f'Disabled by "{abbr_p}" of set "{set_p}".'
                    if set_p != set_r
                    else f'Disabled by earlier rule "{abbr_p}" in same set.'
                )
                boundary_desc = "does not require a whole word boundary" if not ww_p else f"triggers on non-word delimiter '{next_char}'"
                explanation = (
                    f"Rule '{abbr_p}' in set '{set_p}' (priority #{pri_p + 1}) is a prefix of '{abbr_r}' in set '{set_r}' (priority #{pri_r + 1}). "
                    f"Because '{abbr_p}' {boundary_desc}, "
                    f"typing '{abbr_p}' expands immediately, preventing '{abbr_r}' from ever completing."
                )
                issues.append({
                    "type": "prefix_collision",
                    "set": set_r,
                    "abbreviation": abbr_r,
                    "disabled_set": set_r,
                    "disabled_abbreviation": abbr_r,
                    "disabled_whole_word": ww_r,
                    "shadowed_by_set": set_p,
                    "shadowed_by_abbreviation": abbr_p,
                    "shadowed_by_whole_word": ww_p,
                    "reason": reason,
                    "explanation": explanation
                })

        trie.insert(r)

    # 4. Invisible character, marker syntax, paste-race hazard & nested reference checks
    if set_name:
        target_rules = [r for r in global_rules if r["set"] == set_name]
    else:
        target_rules = global_rules

    # Map highest-priority active expansion per abbreviation for recursive resolution
    active_exp_by_abbr: Dict[str, str] = {}
    for ar in active_rules:
        a_key = ar.get("abbreviation", "")
        if a_key and a_key not in active_exp_by_abbr:
            active_exp_by_abbr[a_key] = ar.get("expansion", "")

    for r in target_rules:
        abbr = r.get("abbreviation", "")
        exp = r.get("expansion", "")
        s_name = r.get("set", "")
        updated_exp = exp
        needs_save = False

        found_inv = [desc for ch, desc in INVISIBLE_CHARS_MAP.items() if ch in updated_exp]
        if found_inv:
            issue_item = {
                "type": "invisible_character",
                "set": s_name,
                "abbreviation": abbr,
                "detected": found_inv,
                "raw_expansion": repr(exp)
            }
            issues.append(issue_item)
            if fix:
                for ch in INVISIBLE_CHARS_MAP:
                    updated_exp = updated_exp.replace(ch, "\n" if ch in ['\u2028', '\u2029'] else "")
                needs_save = True

        if REVERSED_TAB_DELAY_PATTERN.search(updated_exp):
            issues.append({
                "type": "reversed_tab_delay",
                "set": s_name,
                "abbreviation": abbr,
                "raw_expansion": repr(exp),
                "note": "Reversed '{tab}{delay:...}' fires Tab before the slash dropdown renders; must be '{delay:...}{tab}'."
            })
            if fix:
                updated_exp = REVERSED_TAB_DELAY_PATTERN.sub(r'\1{tab}', updated_exp)
                needs_save = True

        if MALFORMED_NESTED_REF_PATTERN.search(updated_exp):
            issues.append({
                "type": "malformed_nested_reference",
                "set": s_name,
                "abbreviation": abbr,
                "raw_expansion": repr(exp),
                "note": 'Double-braced \'{{"abbr"}}\' leaves literal braces around nested expansion; must be \'{"abbr"}\'.'
            })
            if fix:
                updated_exp = MALFORMED_NESTED_REF_PATTERN.sub(r'{"\1"}', updated_exp)
                needs_save = True

        if needs_save and fix:
            set_rule_expansion(s_name, abbr, expansion=updated_exp)
            active_exp_by_abbr[abbr] = updated_exp
            fixed_count += 1

        for match in NESTED_REFERENCE_PATTERN.finditer(updated_exp):
            ref_abbr = match.group(1)
            if ref_abbr == abbr:
                issues.append({
                    "type": "circular_nested_reference",
                    "set": s_name,
                    "abbreviation": abbr,
                    "target_abbreviation": ref_abbr,
                    "note": "Rule references itself directly, creating an infinite loop"
                })
            elif ref_abbr not in global_abbr_to_sets:
                issues.append({
                    "type": "dangling_nested_reference",
                    "set": s_name,
                    "abbreviation": abbr,
                    "target_abbreviation": ref_abbr,
                    "note": f"Referenced abbreviation '{ref_abbr}' does not exist in any active rule set"
                })
            elif len(global_abbr_to_sets[ref_abbr]) > 1:
                issues.append({
                    "type": "ambiguous_nested_reference",
                    "set": s_name,
                    "abbreviation": abbr,
                    "target_abbreviation": ref_abbr,
                    "active_in_sets": global_abbr_to_sets[ref_abbr],
                    "note": f"Referenced abbreviation '{ref_abbr}' exists in multiple active sets: {global_abbr_to_sets[ref_abbr]}. Higher ranked set will shadow lower sets."
                })

        if r.get("set_enabled", True) and abbr:
            resolved_exp = resolve_nested_expansion(abbr, active_exp_by_abbr, raw_expansion=updated_exp)
            dt_matches = list(DELAY_TAB_SEQUENCE_PATTERN.finditer(resolved_exp))
            if dt_matches:
                trailing_text = KEY_MARKER_STRIP_PATTERN.sub("", resolved_exp[dt_matches[0].end():])
                issues.append({
                    "type": "multi_tab_paste_hazard",
                    "set": s_name,
                    "abbreviation": abbr,
                    "delay_tab_count": len(dt_matches),
                    "first_delay_tab_offset": dt_matches[0].start(),
                    "trailing_segment_length": len(trailing_text),
                    "resolved_length": len(resolved_exp),
                    "note": (
                        f"Resolved expansion ({len(resolved_exp)} chars) has {len(dt_matches)} '{{delay:...}}{{tab}}' sequence(s) "
                        f"(first at char {dt_matches[0].start()}, trailing text {len(trailing_text)} chars). "
                        f"In Paseo and web/Electron chat composers, '{{delay:...}}{{tab}}' when 'No commands found' is shown "
                        f"is not preventDefault()ed and jumps DOM focus from <textarea> onto the '+' button, dropping trailing text/paste and stranding the cursor. "
                        f"Use the full canonical '/<command> ' with a plain trailing space instead of '{{delay:...}}{{tab}}'."
                    ),
                })

    if set_name:
        filtered_issues = []
        for issue in issues:
            if (
                issue.get("set") == set_name
                or issue.get("disabled_set") == set_name
                or issue.get("shadowed_by_set") == set_name
                or set_name in issue.get("active_in_sets", [])
            ):
                filtered_issues.append(issue)
        issues = filtered_issues
        scanned_count = len(target_rules)
    else:
        scanned_count = len(global_rules)

    return {
        "total_rules_scanned": scanned_count,
        "issues_found": len(issues),
        "fixed": fixed_count,
        "details": issues
    }


def debug_trigger(
    abbreviation: str,
    set_name: Optional[str] = None,
    by_expansion: bool = False
) -> Dict[str, Any]:
    """
    Deeply inspect and debug an abbreviation trigger or slash command:
    - If abbreviation matches a rule: evaluates active status, set priority rank, whole_word rules,
      prefix shadowing conflicts (who disables it, or whom it disables), invisible chars, related
      rules sharing identical expansions, and gives actionable recommendations.
    - If query matches an expansion or slash command (e.g. '/boost', '/goal', '/imagine'):
      inspects each active rule producing that command token with full trigger diagnostics,
      and performs a preflight simulation if the command token were used as an abbreviation.
    - If rule does not exist: runs preflight simulation to check if creating it would
      be shadowed by an existing rule or shadow any existing active rule.
    """
    global_rules = search_rules()
    active_rules = [
        r for r in global_rules
        if r.get("set_enabled", True) and r.get("abbreviation")
    ]
    active_rules.sort(key=lambda x: (x.get("set_priority", 0), x.get("rule_index", 0)))

    matching_rules = []
    matched_by = "abbreviation"

    if by_expansion:
        q = abbreviation.lower()
        for r in global_rules:
            if set_name and r.get("set") != set_name:
                continue
            exp = r.get("expansion", "").lower()
            if q in exp or exp.startswith("/" + q.lstrip("/")):
                matching_rules.append(r)
        matched_by = "expansion"
    else:
        for r in global_rules:
            if set_name and r.get("set") != set_name:
                continue
            if r.get("abbreviation", "").lower() == abbreviation.lower():
                matching_rules.append(r)

        # Smart fallback to slash command / expansion query if no exact abbreviation matched
        if not matching_rules:
            q = abbreviation.lower()
            candidate_rules = []
            for r in global_rules:
                if set_name and r.get("set") != set_name:
                    continue
                exp = r.get("expansion", "").lower()
                desc = r.get("description", "").lower()
                # Exact prefix match on expansion (e.g. /boost matching /boost{delay:...} or bo⇧)
                if exp.startswith(q) or (q.startswith("/") and exp.startswith(q)) or (not q.startswith("/") and exp.startswith("/" + q)):
                    candidate_rules.append(r)
                elif len(q) >= 3 and (q in exp or q in desc):
                    candidate_rules.append(r)
            if candidate_rules:
                matching_rules = candidate_rules
                matched_by = "expansion"

    trie = PrefixTrie()
    for r in active_rules:
        trie.insert(r)

    if matching_rules:
        analyzed_rules = []
        for r in matching_rules:
            s_name = r["set"]
            abbr = r["abbreviation"]
            is_enabled = r.get("set_enabled", True)
            pri = r.get("set_priority", 0)
            rule_idx = r.get("rule_index", 0)
            ww = r.get("whole_word", False)

            detailed = get_rule(s_name, abbr) or r
            expansion = detailed.get("expansion", r.get("expansion", ""))
            desc = detailed.get("description", r.get("description", ""))
            exp_count = detailed.get("expansion_count", 0)

            shadowed_by = []
            if is_enabled:
                prefixes = trie.find_prefixes(abbr)
                for p in prefixes:
                    p_pri = p.get("set_priority", 0)
                    p_idx = p.get("rule_index", 0)
                    p_abbr = p.get("abbreviation", "")
                    p_ww = p.get("whole_word", False)
                    p_set = p.get("set", "")

                    if (p_pri < pri) or (p_pri == pri and p_idx < rule_idx):
                        next_char = abbr[len(p_abbr)]
                        if not p_ww or not is_word_char(next_char):
                            shadowed_by.append({
                                "shadowed_by_set": p_set,
                                "shadowed_by_abbreviation": p_abbr,
                                "shadowed_by_priority": p_pri,
                                "shadowed_by_whole_word": p_ww,
                                "reason": f'Disabled by "{p_abbr}" of set "{p_set}".',
                                "cause": (
                                    f"Set '{p_set}' (priority #{p_pri + 1}) is evaluated before '{s_name}' (priority #{pri + 1}). "
                                    f"Typing '{p_abbr}' expands immediately into '{p.get('expansion', '')[:30]}...', "
                                    f"preventing '{abbr}' from ever completing."
                                )
                            })

            shadows_rules = []
            if is_enabled:
                extensions = trie.find_extensions(abbr)
                for ext in extensions:
                    ext_pri = ext.get("set_priority", 0)
                    ext_idx = ext.get("rule_index", 0)
                    ext_abbr = ext.get("abbreviation", "")
                    ext_set = ext.get("set", "")

                    if (pri < ext_pri) or (pri == ext_pri and rule_idx < ext_idx):
                        next_char = ext_abbr[len(abbr)]
                        if not ww or not is_word_char(next_char):
                            shadows_rules.append({
                                "disabled_set": ext_set,
                                "disabled_abbreviation": ext_abbr,
                                "disabled_priority": ext_pri,
                                "reason": f"Disables '{ext_abbr}' in set '{ext_set}'"
                            })

            duplicate_sets = [
                x["set"] for x in active_rules
                if x["abbreviation"].lower() == abbr.lower() and x["set"] != s_name
            ]

            # Cross-reference rules sharing the same expansion
            related_rules = []
            if expansion:
                for other in active_rules:
                    if (
                        other["abbreviation"].lower() != abbr.lower()
                        and other.get("expansion", "").strip() == expansion.strip()
                    ):
                        related_rules.append({
                            "set": other["set"],
                            "abbreviation": other["abbreviation"],
                            "expansion": other.get("expansion", ""),
                            "set_priority": other.get("set_priority", 0)
                        })

            if not is_enabled:
                status = "INACTIVE_SET"
            elif shadowed_by:
                status = "DISABLED"
            elif duplicate_sets:
                status = "DUPLICATE_COLLISION"
            else:
                status = "ACTIVE"

            recommendations = []
            if shadowed_by:
                recommendations.append(
                    f"Change abbreviation '{abbr}' in set '{s_name}' to an uncontested trigger prefix (e.g., replace leading '{shadowed_by[0]['shadowed_by_abbreviation']}' with alternate letters)."
                )
                if not shadowed_by[0]["shadowed_by_whole_word"]:
                    recommendations.append(
                        f"If '{shadowed_by[0]['shadowed_by_abbreviation']}' in set '{shadowed_by[0]['shadowed_by_set']}' should only match whole words, enable 'whole word' on that rule."
                    )
                if pri > shadowed_by[0]["shadowed_by_priority"]:
                    recommendations.append(
                        f"Drag set '{s_name}' above set '{shadowed_by[0]['shadowed_by_set']}' in Typinator's set priority list."
                    )

            analyzed_rules.append({
                "set": s_name,
                "abbreviation": abbr,
                "expansion": expansion,
                "description": desc,
                "whole_word": ww,
                "set_priority": pri,
                "rule_index": rule_idx,
                "set_enabled": is_enabled,
                "expansion_count": exp_count,
                "status": status,
                "shadowed_by": shadowed_by,
                "shadows_rules": shadows_rules,
                "duplicate_sets": duplicate_sets,
                "related_rules": related_rules,
                "recommendations": recommendations
            })

        out = {
            "mode": "inspection",
            "abbreviation": abbreviation,
            "matched_by": matched_by,
            "exists": True,
            "rules": analyzed_rules
        }

        if matched_by == "expansion":
            pf_shadowers = []
            prefixes = trie.find_prefixes(abbreviation)
            for p in prefixes:
                p_ww = p.get("whole_word", False)
                next_char = abbreviation[len(p["abbreviation"])]
                if not p_ww or not is_word_char(next_char):
                    pf_shadowers.append({
                        "set": p["set"],
                        "abbreviation": p["abbreviation"],
                        "whole_word": p_ww,
                        "set_priority": p.get("set_priority", 0),
                        "reason": f"Active rule '{p['abbreviation']}' in set '{p['set']}' would disable '{abbreviation}' if added to a lower-ranked set."
                    })
            pf_disabled = []
            extensions = trie.find_extensions(abbreviation)
            for ext in extensions:
                pf_disabled.append({
                    "set": ext["set"],
                    "abbreviation": ext["abbreviation"],
                    "whole_word": ext.get("whole_word", False),
                    "set_priority": ext.get("set_priority", 0),
                    "reason": f"Active rule '{ext['abbreviation']}' in set '{ext['set']}' would be disabled if '{abbreviation}' is added with whole_word=False to a higher-ranked set."
                })
            out["preflight"] = {
                "abbreviation": abbreviation,
                "is_safe": len(pf_shadowers) == 0 and len(pf_disabled) == 0,
                "potential_shadowers": pf_shadowers,
                "potential_disabled": pf_disabled
            }

        return out

    else:
        potential_shadowers = []
        prefixes = trie.find_prefixes(abbreviation)
        for p in prefixes:
            p_ww = p.get("whole_word", False)
            next_char = abbreviation[len(p["abbreviation"])]
            if not p_ww or not is_word_char(next_char):
                potential_shadowers.append({
                    "set": p["set"],
                    "abbreviation": p["abbreviation"],
                    "whole_word": p_ww,
                    "set_priority": p.get("set_priority", 0),
                    "reason": f"Active rule '{p['abbreviation']}' in set '{p['set']}' would disable '{abbreviation}' if added to a lower-ranked set."
                })

        potential_disabled = []
        extensions = trie.find_extensions(abbreviation)
        for ext in extensions:
            potential_disabled.append({
                "set": ext["set"],
                "abbreviation": ext["abbreviation"],
                "whole_word": ext.get("whole_word", False),
                "set_priority": ext.get("set_priority", 0),
                "reason": f"Active rule '{ext['abbreviation']}' in set '{ext['set']}' would be disabled if '{abbreviation}' is added with whole_word=False to a higher-ranked set."
            })

        is_safe = len(potential_shadowers) == 0 and len(potential_disabled) == 0

        return {
            "mode": "preflight_simulation",
            "abbreviation": abbreviation,
            "matched_by": "none",
            "exists": False,
            "is_safe": is_safe,
            "potential_shadowers": potential_shadowers,
            "potential_disabled": potential_disabled
        }


def expand_text(text: str) -> str:
    """Trigger Typinator to expand a given text string programmatically."""
    sc = f'''
    tell application "Typinator"
        expand string "{escape_as(text)}"
        return "OK"
    end tell
    '''
    return run_applescript(sc)


def quick_search(query: str = "") -> str:
    """Trigger Typinator's built-in quick search popup."""
    q_arg = f' "{escape_as(query)}"' if query else ""
    sc = f'''
    tell application "Typinator"
        quick search{q_arg}
        return "OK"
    end tell
    '''
    return run_applescript(sc)


def restart_typinator(force: bool = False, timeout_sec: int = 5) -> Dict[str, Any]:
    """
    Safely restart the Typinator macOS application.
    Recovers from frozen, unresponsive, or stalled event-tap states.
    Attempts a graceful AppleScript quit first, falling back to SIGTERM/SIGKILL if
    unresponsive or when force=True. Relaunches via launch_typinator_quietly() (no main
    window, no focus change) and verifies
    clean startup.
    """
    res = subprocess.run(["pgrep", "-x", "Typinator"], capture_output=True, text=True)
    pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
    old_pids = list(pids)
    quit_method = "none"

    if pids:
        if not force:
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Typinator" to quit'],
                    capture_output=True,
                    timeout=3
                )
                quit_method = "applescript_graceful"
            except Exception:
                pass

            start = time.time()
            while time.time() - start < 3.0:
                time.sleep(0.3)
                chk = subprocess.run(["pgrep", "-x", "Typinator"], capture_output=True, text=True)
                if not chk.stdout.strip():
                    break

        chk = subprocess.run(["pgrep", "-x", "Typinator"], capture_output=True, text=True)
        remaining = [int(p) for p in chk.stdout.strip().split() if p.isdigit()]
        if remaining:
            quit_method = "forced_sigkill"
            for p in remaining:
                try:
                    os.kill(p, 9)
                except ProcessLookupError:
                    pass
                except Exception:
                    subprocess.run(["kill", "-9", str(p)], check=False)
            time.sleep(0.5)

    new_pid = launch_typinator_quietly(timeout_sec=timeout_sec)

    time.sleep(0.5)
    status_info = get_status()

    return {
        "status": "restarted",
        "old_pids": old_pids,
        "new_pid": new_pid,
        "quit_method": quit_method,
        "app_status": status_info
    }


def decode_typinator_archive(data: bytes) -> bytes:
    """
    Decode (or encode) a Typinator `.tyset/Index` or `.tyset/X*` binary archive.
    Reverse-engineered from `+[Abbreviation prepareArchiveData:]` (`0x100016573` in Typinator 9.2):
    An involutory LCG byte-stream XOR cipher seeded with `len(data) & 0xFF`.
    """
    bl = len(data) & 0xFF
    out = bytearray(data)
    for i in range(len(out)):
        bl = (bl * 0x5D + 1) & 0xFF
        out[i] ^= bl
    return bytes(out)


def _deref_uid(objects: List[Any], val: Any) -> Any:
    if isinstance(val, plistlib.UID):
        idx = val.data
        if 0 <= idx < len(objects):
            return objects[idx]
    return val


def decode_x_payload(raw_bytes: bytes) -> str:
    """
    Decode an external `.tyset/X{exp_id:08X}` payload file into its expansion string.
    Supports both modern `NSKeyedArchiver` (`bplist00`) and legacy `NSArchiver` (`streamtyped`).
    """
    if not raw_bytes:
        return ""
    dec = decode_typinator_archive(raw_bytes)
    if dec.startswith(b"bplist00"):
        try:
            pl = plistlib.loads(dec)
            objs = pl.get("$objects", [])
            if len(objs) <= 1 or not isinstance(objs[1], dict):
                return ""
            root = objs[1]
            keys = [_deref_uid(objs, k) for k in root.get("NS.keys", [])]
            vals = [_deref_uid(objs, v) for v in root.get("NS.objects", [])]
            d = dict(zip(keys, vals))
            exp = d.get("Expansion")
            if isinstance(exp, str):
                return exp
            if isinstance(exp, dict) and "NS.string" in exp:
                return str(exp["NS.string"])
            if "Formatted" in d:
                return "<Formatted RTF/HTML Expansion>"
            if "Picture" in d:
                return "<Picture Expansion>"
        except Exception:
            return "<Corrupted bplist00 Expansion>"
    elif dec.startswith(b"\x04\x0bstreamtyped"):
        marker = b"Expansion\x86\x92"
        idx = dec.find(marker)
        if idx != -1:
            sub = dec[idx + len(marker):]
            m2 = sub.find(b"\x97\x98")
            if m2 != -1:
                pos = m2 + 2
                if pos < len(sub) and sub[pos] == 0x2B:
                    pos += 1
                if pos < len(sub):
                    b0 = sub[pos]
                    if b0 < 0x80:
                        slen = b0
                        s_start = pos + 1
                    elif b0 == 0x81 and pos + 3 <= len(sub):
                        slen = struct.unpack("<H", sub[pos + 1:pos + 3])[0]
                        s_start = pos + 3
                    elif b0 == 0x82 and pos + 5 <= len(sub):
                        slen = struct.unpack("<I", sub[pos + 1:pos + 5])[0]
                        s_start = pos + 5
                    else:
                        slen = 0
                        s_start = pos
                    if slen > 0:
                        return sub[s_start:s_start + slen].decode("utf-8", errors="replace")
        if b"Formatted" in dec or b"NSAttributedString" in dec:
            return "<Formatted RTF/HTML Expansion>"
        if b"Picture" in dec or b"NSImage" in dec:
            return "<Picture Expansion>"
    return ""


def parse_tyset_from_bytes(
    index_bytes: bytes,
    x_loader: Callable[[str], Optional[bytes]],
    set_name: str = "",
    only_abbreviation: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Parse a `.tyset/Index` binary blob and resolve any external `X*` payloads via `x_loader`.
    When `only_abbreviation` is provided, only loads the external `X*` payload for that rule
    (making historical commit walking 100x faster).
    Returns a dict keyed by abbreviation trigger string.
    """
    dec = decode_typinator_archive(index_bytes)
    if not dec.startswith(b"bplist00"):
        return {}
    pl = plistlib.loads(dec)
    objs = pl.get("$objects", [])
    if len(objs) <= 1 or not isinstance(objs[1], dict):
        return {}
    root = objs[1]
    resolved_set_name = _deref_uid(objs, root.get("name")) or set_name
    abbr_list_obj = _deref_uid(objs, root.get("abbreviations"))
    if not isinstance(abbr_list_obj, dict):
        return {}

    rules_by_abbr: Dict[str, Dict[str, Any]] = {}
    for idx, item_uid in enumerate(abbr_list_obj.get("NS.objects", [])):
        r = _deref_uid(objs, item_uid)
        if not isinstance(r, dict):
            continue
        abbr_val = _deref_uid(objs, r.get("abbreviation"))
        if isinstance(abbr_val, dict):
            abbr_val = abbr_val.get("NS.string", "")
        abbr_str = str(abbr_val or "")
        if not abbr_str:
            continue
        if only_abbreviation is not None and abbr_str != only_abbreviation:
            continue

        exp_val = _deref_uid(objs, r.get("expansion"))
        if isinstance(exp_val, dict):
            exp_val = exp_val.get("NS.string", "")
        exp_id = r.get("exp ID")
        x_file = None
        if exp_id:
            x_file = f"X{int(exp_id):08X}"
            x_raw = x_loader(x_file)
            if x_raw is not None:
                exp_str = decode_x_payload(x_raw)
            else:
                exp_str = str(exp_val or "")
        else:
            exp_str = str(exp_val or "")

        opts_obj = _deref_uid(objs, r.get("abbrOptions"))
        desc_str = ""
        whole_word = False
        if isinstance(opts_obj, dict) and "NS.keys" in opts_obj:
            okeys = [_deref_uid(objs, k) for k in opts_obj.get("NS.keys", [])]
            ovals = [_deref_uid(objs, v) for v in opts_obj.get("NS.objects", [])]
            odict = dict(zip(okeys, ovals))
            comment_val = odict.get("comment", "")
            if isinstance(comment_val, dict):
                comment_val = comment_val.get("NS.string", "")
            desc_str = str(comment_val or "")
            whole_word = bool(odict.get("wholeWord", False))

        rules_by_abbr[abbr_str] = {
            "set": str(resolved_set_name),
            "abbreviation": abbr_str,
            "expansion": exp_str,
            "description": desc_str,
            "whole_word": whole_word,
            "exp_id": int(exp_id) if exp_id else None,
            "x_file": x_file,
            "rule_index": idx,
        }
    return rules_by_abbr


def load_set_rules_at_ref(
    set_name: str,
    ref: str = "HEAD",
    repo_dir: str = DEFAULT_SYNC_REPO,
    live_sets_dir: str = DEFAULT_LIVE_SETS,
    only_abbreviation: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Load and decode rules of `set_name` either from live disk (`ref="LIVE"`)
    or from a Git commit/ref in `repo_dir` (`ref="HEAD"`, `<sha>`, etc.).
    """
    set_folder = f"{set_name}.tyset" if not set_name.endswith(".tyset") else set_name
    clean_name = set_folder[:-6] if set_folder.endswith(".tyset") else set_folder

    if ref.upper() == "LIVE":
        folder_path = os.path.join(live_sets_dir, set_folder)
        index_path = os.path.join(folder_path, "Index")
        if not os.path.isfile(index_path):
            return {}
        with open(index_path, "rb") as f:
            index_bytes = f.read()

        def _live_x_loader(x_name: str) -> Optional[bytes]:
            xp = os.path.join(folder_path, x_name)
            if os.path.isfile(xp):
                with open(xp, "rb") as xf:
                    return xf.read()
            return None

        return parse_tyset_from_bytes(
            index_bytes, _live_x_loader, set_name=clean_name, only_abbreviation=only_abbreviation
        )

    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        raise FileNotFoundError(f"Typinator sync Git repository not found at '{repo_dir}'")

    rel_dir = f"Sets/{set_folder}"
    res_idx = subprocess.run(
        ["git", "-C", repo_dir, "show", f"{ref}:{rel_dir}/Index"],
        capture_output=True
    )
    if res_idx.returncode != 0 or not res_idx.stdout:
        return {}

    def _git_x_loader(x_name: str) -> Optional[bytes]:
        rx = subprocess.run(
            ["git", "-C", repo_dir, "show", f"{ref}:{rel_dir}/{x_name}"],
            capture_output=True
        )
        return rx.stdout if rx.returncode == 0 else None

    return parse_tyset_from_bytes(
        res_idx.stdout, _git_x_loader, set_name=clean_name, only_abbreviation=only_abbreviation
    )


def list_set_names_at_ref(
    ref: str = "HEAD",
    repo_dir: str = DEFAULT_SYNC_REPO,
    live_sets_dir: str = DEFAULT_LIVE_SETS
) -> List[str]:
    """List all `.tyset` set names available at `ref` (`LIVE` or a Git commit)."""
    if ref.upper() == "LIVE":
        if not os.path.isdir(live_sets_dir):
            return []
        return sorted(
            d[:-6] for d in os.listdir(live_sets_dir)
            if d.endswith(".tyset") and os.path.isdir(os.path.join(live_sets_dir, d))
        )
    res = subprocess.run(
        ["git", "-C", repo_dir, "ls-tree", "--name-only", f"{ref}:Sets"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return []
    return sorted(
        line.strip()[:-6] for line in res.stdout.splitlines()
        if line.strip().endswith(".tyset")
    )


def diff_snapshots(
    ref_a: str = "HEAD",
    ref_b: str = "LIVE",
    set_name: Optional[str] = None,
    repo_dir: str = DEFAULT_SYNC_REPO,
    live_sets_dir: str = DEFAULT_LIVE_SETS
) -> Dict[str, Any]:
    """
    Compare decoded Typinator rules between `ref_a` (default `HEAD` in typinator-sync)
    and `ref_b` (default `LIVE` disk sets, or another commit SHA).
    Returns human-readable added (`+`), deleted (`-`), and modified (`~`) rules.
    """
    if set_name:
        clean_set = set_name[:-6] if set_name.endswith(".tyset") else set_name
        candidate_sets = [clean_set]
    else:
        if ref_a.upper() != "LIVE" and ref_b.upper() != "LIVE":
            # Optimization: only inspect sets touched between ref_a and ref_b
            diff_res = subprocess.run(
                ["git", "-C", repo_dir, "diff", "--name-only", ref_a, ref_b, "--", "Sets"],
                capture_output=True, text=True
            )
            touched = set()
            for line in diff_res.stdout.splitlines():
                parts = line.strip().split("/")
                if len(parts) >= 2 and parts[0] == "Sets" and parts[1].endswith(".tyset"):
                    touched.add(parts[1][:-6])
            candidate_sets = sorted(touched)
        else:
            sets_a = set(list_set_names_at_ref(ref_a, repo_dir=repo_dir, live_sets_dir=live_sets_dir))
            sets_b = set(list_set_names_at_ref(ref_b, repo_dir=repo_dir, live_sets_dir=live_sets_dir))
            candidate_sets = sorted(sets_a | sets_b)

    changes: List[Dict[str, Any]] = []
    for s_name in candidate_sets:
        rules_a = load_set_rules_at_ref(s_name, ref=ref_a, repo_dir=repo_dir, live_sets_dir=live_sets_dir)
        rules_b = load_set_rules_at_ref(s_name, ref=ref_b, repo_dir=repo_dir, live_sets_dir=live_sets_dir)
        all_abbrs = sorted(set(rules_a.keys()) | set(rules_b.keys()))
        for abbr in all_abbrs:
            ra = rules_a.get(abbr)
            rb = rules_b.get(abbr)
            if ra is None and rb is not None:
                changes.append({
                    "change": "added",
                    "set": s_name,
                    "abbreviation": abbr,
                    "old_expansion": None,
                    "new_expansion": rb["expansion"],
                    "old_description": None,
                    "new_description": rb["description"],
                })
            elif ra is not None and rb is None:
                changes.append({
                    "change": "deleted",
                    "set": s_name,
                    "abbreviation": abbr,
                    "old_expansion": ra["expansion"],
                    "new_expansion": None,
                    "old_description": ra["description"],
                    "new_description": None,
                })
            elif ra is not None and rb is not None:
                if (
                    ra["expansion"] != rb["expansion"]
                    or ra["description"] != rb["description"]
                    or ra["whole_word"] != rb["whole_word"]
                ):
                    changes.append({
                        "change": "modified",
                        "set": s_name,
                        "abbreviation": abbr,
                        "old_expansion": ra["expansion"],
                        "new_expansion": rb["expansion"],
                        "old_description": ra["description"],
                        "new_description": rb["description"],
                        "old_whole_word": ra["whole_word"],
                        "new_whole_word": rb["whole_word"],
                    })

    return {
        "ref_a": ref_a,
        "ref_b": ref_b,
        "set_filter": set_name,
        "total_changes": len(changes),
        "changes": changes,
    }


def trace_rule_history(
    abbreviation: str,
    set_name: Optional[str] = None,
    limit: int = 25,
    repo_dir: str = DEFAULT_SYNC_REPO,
    live_sets_dir: str = DEFAULT_LIVE_SETS,
    journal_path: str = DEFAULT_MUTATION_LOG
) -> Dict[str, Any]:
    """
    Walk the Time Machine Git history in `typinator-sync` (plus live disk state and
    local pre-mutation journal) to reconstruct the complete version timeline of `abbreviation`.
    """
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        raise FileNotFoundError(f"Typinator sync Git repository not found at '{repo_dir}'")

    target_sets: List[str] = []
    if set_name:
        clean_set = set_name[:-6] if set_name.endswith(".tyset") else set_name
        target_sets = [clean_set]
    else:
        # Discover which set(s) currently or historically contain `abbreviation`
        for s_name in list_set_names_at_ref("LIVE", repo_dir=repo_dir, live_sets_dir=live_sets_dir):
            rules = load_set_rules_at_ref(
                s_name, ref="LIVE", repo_dir=repo_dir, live_sets_dir=live_sets_dir, only_abbreviation=abbreviation
            )
            if abbreviation in rules:
                target_sets.append(s_name)
        if not target_sets:
            for s_name in list_set_names_at_ref("HEAD", repo_dir=repo_dir, live_sets_dir=live_sets_dir):
                rules = load_set_rules_at_ref(
                    s_name, ref="HEAD", repo_dir=repo_dir, live_sets_dir=live_sets_dir, only_abbreviation=abbreviation
                )
                if abbreviation in rules:
                    target_sets.append(s_name)
        if not target_sets:
            # Fallback: scan all sets in HEAD
            target_sets = list_set_names_at_ref("HEAD", repo_dir=repo_dir, live_sets_dir=live_sets_dir)

    history_by_set: Dict[str, List[Dict[str, Any]]] = {}

    for s_name in target_sets:
        rel_set = f"Sets/{s_name}.tyset"
        log_res = subprocess.run(
            ["git", "-C", repo_dir, "log", "--pretty=format:%H\t%h\t%ci\t%s", "--", rel_set],
            capture_output=True, text=True
        )
        if log_res.returncode != 0 or not log_res.stdout.strip():
            continue

        commits = []
        for line in log_res.stdout.strip().splitlines():
            parts = line.split("\t", 3)
            if len(parts) == 4:
                commits.append(parts)

        # Walk oldest-to-newest so we accurately record every state transition
        versions: List[Dict[str, Any]] = []
        prev_state: Optional[Tuple[Optional[str], Optional[str], Optional[bool]]] = None

        for full_sha, short_sha, cdate, subj in reversed(commits):
            rules = load_set_rules_at_ref(
                s_name, ref=full_sha, repo_dir=repo_dir, live_sets_dir=live_sets_dir, only_abbreviation=abbreviation
            )
            r = rules.get(abbreviation)
            if r is None:
                curr_state = (None, None, None)
            else:
                curr_state = (r["expansion"], r["description"], r["whole_word"])

            if curr_state != prev_state:
                if curr_state == (None, None, None):
                    if prev_state is not None:
                        versions.append({
                            "source": "git",
                            "commit": full_sha,
                            "short_commit": short_sha,
                            "date": cdate,
                            "subject": subj,
                            "event": "deleted",
                            "set": s_name,
                            "abbreviation": abbreviation,
                            "expansion": None,
                            "description": None,
                            "whole_word": None,
                            "x_file": None,
                        })
                else:
                    event_type = "created" if prev_state in (None, (None, None, None)) else "modified"
                    versions.append({
                        "source": "git",
                        "commit": full_sha,
                        "short_commit": short_sha,
                        "date": cdate,
                        "subject": subj,
                        "event": event_type,
                        "set": s_name,
                        "abbreviation": abbreviation,
                        "expansion": r["expansion"],
                        "description": r["description"],
                        "whole_word": r["whole_word"],
                        "x_file": r.get("x_file"),
                    })
                prev_state = curr_state

        # Also check LIVE disk state vs latest Git state
        live_rules = load_set_rules_at_ref(
            s_name, ref="LIVE", repo_dir=repo_dir, live_sets_dir=live_sets_dir, only_abbreviation=abbreviation
        )
        lr = live_rules.get(abbreviation)
        live_state = (lr["expansion"], lr["description"], lr["whole_word"]) if lr else (None, None, None)
        if live_state != prev_state and (lr is not None or prev_state is not None):
            versions.append({
                "source": "live_disk",
                "commit": "LIVE",
                "short_commit": "LIVE",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S (unsynced live)"),
                "subject": "Live ~/Library/Application Support/Typinator/Sets",
                "event": "deleted_live" if lr is None else ("created_live" if prev_state in (None, (None, None, None)) else "modified_live"),
                "set": s_name,
                "abbreviation": abbreviation,
                "expansion": lr["expansion"] if lr else None,
                "description": lr["description"] if lr else None,
                "whole_word": lr["whole_word"] if lr else None,
                "x_file": lr.get("x_file") if lr else None,
            })

        if versions:
            # Return newest-first, capped at `limit`
            history_by_set[s_name] = list(reversed(versions))[:max(1, int(limit))]

    journal_entries: List[Dict[str, Any]] = []
    if os.path.isfile(journal_path):
        try:
            with open(journal_path, "r", encoding="utf-8") as jf:
                for line in jf:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if item.get("abbreviation") == abbreviation and (not set_name or item.get("set") == set_name):
                        journal_entries.append(item)
        except Exception:
            pass

    return {
        "abbreviation": abbreviation,
        "set_filter": set_name,
        "sets": history_by_set,
        "local_mutation_journal": list(reversed(journal_entries))[:max(1, int(limit))],
    }


def restore_single_rule(
    commit: str,
    set_name: str,
    abbreviation: str,
    dry_run: bool = False,
    repo_dir: str = DEFAULT_SYNC_REPO,
    live_sets_dir: str = DEFAULT_LIVE_SETS
) -> Dict[str, Any]:
    """
    Surgical single-rule Time Machine recovery:
    Decodes `<abbreviation>` from `<commit>` in `typinator-sync` for `<set_name>`
    and restores ONLY that rule into live Typinator via AppleScript OSA (`set_rule_expansion`
    or `add_rule`), with zero app restart and zero overwrite of newer sibling rules in the set.
    """
    clean_set = set_name[:-6] if set_name.endswith(".tyset") else set_name
    rules_at_commit = load_set_rules_at_ref(
        clean_set, ref=commit, repo_dir=repo_dir, live_sets_dir=live_sets_dir, only_abbreviation=abbreviation
    )
    if abbreviation not in rules_at_commit:
        raise LookupError(
            f"Rule '{abbreviation}' not found in set '{clean_set}' at snapshot '{commit}'."
        )

    target_rule = rules_at_commit[abbreviation]
    live_existing = None
    if is_typinator_running():
        try:
            live_existing = get_rule(clean_set, abbreviation)
        except Exception:
            live_existing = None
    if live_existing is None:
        live_disk_rules = load_set_rules_at_ref(
            clean_set, ref="LIVE", repo_dir=repo_dir, live_sets_dir=live_sets_dir, only_abbreviation=abbreviation
        )
        live_existing = live_disk_rules.get(abbreviation)

    result = {
        "status": "dry_run" if dry_run else "restored",
        "commit": commit,
        "set": clean_set,
        "abbreviation": abbreviation,
        "operation": "update_existing" if live_existing else "recreate_deleted",
        "before_expansion": live_existing.get("expansion") if live_existing else None,
        "restored_expansion": target_rule["expansion"],
        "restored_description": target_rule["description"],
        "restored_whole_word": target_rule["whole_word"],
        "x_file": target_rule.get("x_file"),
    }

    if dry_run:
        return result

    existing_osa = get_rule(clean_set, abbreviation)
    if existing_osa:
        set_rule_expansion(
            clean_set,
            abbreviation,
            expansion=target_rule["expansion"],
            description=target_rule["description"],
            whole_word=target_rule["whole_word"],
        )
    else:
        add_rule(
            clean_set,
            abbreviation,
            expansion=target_rule["expansion"],
            description=target_rule["description"],
            whole_word=target_rule["whole_word"],
        )

    return result


def list_snapshots(
    limit: int = 15,
    set_name: Optional[str] = None,
    decode: bool = False,
    repo_dir: str = DEFAULT_SYNC_REPO
) -> List[Dict[str, Any]]:
    """
    List recent Git backup snapshots from the Typinator sync repository
    ($TYPINATOR_SYNC_REPO).
    When `decode=True`, also decodes `.tyset` diffs against `commit~1` to list exact rule changes.
    """
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        raise FileNotFoundError(f"Typinator sync Git repository not found at '{repo_dir}'")

    cmd = [
        "git", "-C", repo_dir, "log",
        f"-n{max(1, int(limit))}",
        "--pretty=format:===COMMIT===%H\t%h\t%ci\t%s",
        "--name-status"
    ]
    if set_name:
        target_rel = f"Sets/{set_name}.tyset" if not set_name.endswith(".tyset") else f"Sets/{set_name}"
        cmd.extend(["--", target_rel])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Git log failed: {res.stderr.strip()}")

    snapshots: List[Dict[str, Any]] = []
    for block in res.stdout.split("===COMMIT==="):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        header = lines[0].split("\t", 3)
        if len(header) < 4:
            continue
        full_sha, short_sha, commit_date, subject = header
        files = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                files.append({"status": parts[0], "path": parts[1]})
        snap_item: Dict[str, Any] = {
            "commit": full_sha,
            "short_commit": short_sha,
            "date": commit_date,
            "subject": subject,
            "changed_files": files
        }
        if decode:
            try:
                diff_info = diff_snapshots(
                    ref_a=f"{full_sha}~1",
                    ref_b=full_sha,
                    set_name=set_name,
                    repo_dir=repo_dir
                )
                snap_item["rule_changes"] = diff_info.get("changes", [])
            except Exception:
                snap_item["rule_changes"] = []
        snapshots.append(snap_item)
    return snapshots


def restore_snapshot(
    commit: str,
    set_name: Optional[str] = None,
    dry_run: bool = False,
    repo_dir: str = DEFAULT_SYNC_REPO,
    live_sets_dir: str = DEFAULT_LIVE_SETS
) -> Dict[str, Any]:
    """
    Safely restore a specific rule set (or all sets) from a Git commit in the
    Typinator sync repository.

    Critical Invariant:
    When applying a restore to live `.tyset` files, Typinator MUST be terminated
    via SIGKILL (`killall -9 Typinator`) BEFORE copying files on disk. Graceful
    quit triggers Typinator's shutdown save (`SAVE started`), which overwrites
    restored `.tyset` files with the stale in-memory model.
    """
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        raise FileNotFoundError(f"Typinator sync Git repository not found at '{repo_dir}'")

    verify = subprocess.run(
        ["git", "-C", repo_dir, "rev-parse", "--verify", f"{commit}^{{commit}}"],
        capture_output=True, text=True
    )
    if verify.returncode != 0:
        raise ValueError(f"Commit '{commit}' not found in '{repo_dir}'")
    resolved_commit = verify.stdout.strip()

    set_folder = None
    if set_name:
        set_folder = f"{set_name}.tyset" if not set_name.endswith(".tyset") else set_name

    with tempfile.TemporaryDirectory(prefix="typinator-restore-") as tmp_dir:
        archive_paths = ["Sets"] if not set_folder else [f"Sets/{set_folder}", "Sets/Set Mark"]
        archive_proc = subprocess.Popen(
            ["git", "-C", repo_dir, "archive", resolved_commit, "--"] + archive_paths,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        tar_proc = subprocess.Popen(
            ["tar", "-x", "-C", tmp_dir],
            stdin=archive_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if archive_proc.stdout:
            archive_proc.stdout.close()
        _, tar_err = tar_proc.communicate()
        archive_err = archive_proc.stderr.read().decode("utf-8", errors="replace") if archive_proc.stderr else ""
        if archive_proc.wait() != 0 or tar_proc.returncode != 0:
            raise RuntimeError(f"Failed to extract snapshot '{resolved_commit}': {archive_err} {tar_err.decode('utf-8', errors='replace')}".strip())

        extracted_sets = os.path.join(tmp_dir, "Sets")
        if set_folder:
            src_dir = os.path.join(extracted_sets, set_folder)
            dst_dir = os.path.join(live_sets_dir, set_folder)
            if not os.path.isdir(src_dir):
                raise FileNotFoundError(f"Rule set '{set_folder}' not found in commit '{resolved_commit[:7]}'")
        else:
            src_dir = extracted_sets
            dst_dir = live_sets_dir

        os.makedirs(dst_dir, exist_ok=True)
        dry_cmd = [
            "rsync", "-anic", "--no-times", "--delete", "--exclude=.DS_Store",
            f"{src_dir}/", f"{dst_dir}/"
        ]
        dry_res = subprocess.run(dry_cmd, capture_output=True, text=True, check=True)
        diff_lines = [
            l for l in dry_res.stdout.splitlines()
            if l.strip() and not l.startswith(".f") and not l.startswith(".d")
        ]

        if dry_run:
            return {
                "status": "dry_run",
                "commit": resolved_commit,
                "set": set_name or "ALL",
                "diff_lines": diff_lines,
                "changed_count": len(diff_lines)
            }

        # 1. Force-kill Typinator so in-memory state cannot overwrite restored disk files on quit
        subprocess.run(["killall", "-9", "Typinator"], capture_output=True)
        time.sleep(0.8)

        # 2. Apply rsync from extracted commit snapshot to live Sets
        apply_cmd = [
            "rsync", "-a", "--delete", "--omit-dir-times", "--exclude=.DS_Store",
            f"{src_dir}/", f"{dst_dir}/"
        ]
        subprocess.run(apply_cmd, capture_output=True, text=True, check=True)

        extracted_mark = os.path.join(extracted_sets, "Set Mark")
        if os.path.isfile(extracted_mark):
            shutil.copy2(extracted_mark, os.path.join(live_sets_dir, "Set Mark"))

        # 3. Relaunch Typinator in the background without its main window.
        # The restored files are already on disk, so a failed relaunch must not
        # abort the backup sync below; it is reported in the result instead.
        relaunch_error = None
        try:
            launch_typinator_quietly(timeout_sec=4.5)
        except (OSError, RuntimeError) as exc:
            relaunch_error = str(exc)
        time.sleep(1.0)

        # 4. Sync backup repository if sync.sh exists so HEAD matches restored state
        sync_script = os.path.join(repo_dir, "sync.sh")
        if os.path.isfile(sync_script) and os.access(sync_script, os.X_OK):
            subprocess.run([sync_script], capture_output=True, text=True, check=False)

        return {
            "status": "restored",
            "commit": resolved_commit,
            "set": set_name or "ALL",
            "diff_lines": diff_lines,
            "changed_count": len(diff_lines),
            "relaunch_error": relaunch_error,
            "app_status": get_status()
        }


# --- CLI Interface ---

def main():
    parser = argparse.ArgumentParser(
        description="Typinator CLI - macOS Automation & Management Harness for Typinator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # status
    p_status = subparsers.add_parser("status", help="Show Typinator application status and rule totals")
    p_status.add_argument("--json", action="store_true", help="Output raw JSON")

    # list-sets
    p_sets = subparsers.add_parser("list-sets", help="List all Typinator rule sets with counts and enabled state")
    p_sets.add_argument("--json", action="store_true", help="Output raw JSON")

    # toggle-set
    p_toggle = subparsers.add_parser("toggle-set", help="Enable or disable a specific rule set")
    p_toggle.add_argument("set", help="Name of the rule set")
    group_toggle = p_toggle.add_mutually_exclusive_group(required=True)
    group_toggle.add_argument("--enable", action="store_true", help="Enable the rule set")
    group_toggle.add_argument("--disable", action="store_true", help="Disable the rule set")

    # search
    p_search = subparsers.add_parser("search", help="Search rules by keyword or filter by set")
    p_search.add_argument("query", nargs="?", default="", help="Keyword to search in abbreviation, expansion, or description")
    p_search.add_argument("--set", help="Filter by rule set name")
    p_search.add_argument("--json", action="store_true", help="Output raw JSON")

    # get
    p_get = subparsers.add_parser("get", help="Get full details of a specific rule")
    p_get.add_argument("set", help="Rule set name")
    p_get.add_argument("abbreviation", help="Rule abbreviation")
    p_get.add_argument("--json", action="store_true", help="Output raw JSON")

    # set
    p_set = subparsers.add_parser("set", help="Update an existing rule's expansion, description, or options")
    p_set.add_argument("set", help="Rule set name")
    p_set.add_argument("abbreviation", help="Rule abbreviation")
    p_set.add_argument("--expansion", help="New expansion text")
    p_set.add_argument("--desc", help="New description")
    p_set.add_argument("--whole-word", dest="whole_word", action="store_true", default=None, help="Match whole word only")
    p_set.add_argument("--no-whole-word", dest="whole_word", action="store_false", help="Disable whole word match")

    # add
    p_add = subparsers.add_parser("add", help="Add a new rule to a rule set")
    p_add.add_argument("set", help="Rule set name")
    p_add.add_argument("abbreviation", help="Rule abbreviation trigger")
    p_add.add_argument("--expansion", required=True, help="Expansion text or script")
    p_add.add_argument("--desc", default="", help="Optional description")
    p_add.add_argument("--whole-word", action="store_true", help="Match whole word only")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a rule from a rule set")
    p_del.add_argument("set", help="Rule set name")
    p_del.add_argument("abbreviation", help="Rule abbreviation")
    p_del.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # export
    p_export = subparsers.add_parser("export", help="Export rules to a JSON file")
    p_export.add_argument("--set", help="Optional rule set name to export")
    p_export.add_argument("-o", "--output", required=True, help="Target JSON output file path")

    # import
    p_import = subparsers.add_parser("import", help="Import rules from a JSON backup file")
    p_import.add_argument("-i", "--input", required=True, help="Input JSON file path")
    p_import.add_argument("--set", help="Target rule set (overrides set name in JSON)")
    p_import.add_argument("--overwrite", action="store_true", help="Overwrite existing rules with matching abbreviations")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit rules for invisible characters, duplicate collisions, and prefix shadowing")
    p_audit.add_argument("--set", help="Audit specific rule set only")
    p_audit.add_argument("--fix", action="store_true", help="Automatically sanitize invisible control characters")
    p_audit.add_argument("--json", action="store_true", help="Output raw JSON")

    # debug
    p_debug = subparsers.add_parser("debug", help="Deeply inspect an abbreviation trigger or slash command for conflicts, prefix shadowing, or preflight safety")
    p_debug.add_argument("abbreviation", help="Abbreviation trigger or slash command to inspect or simulate (e.g. 'img⇧', 'bo⇧', '/boost', '/goal')")
    p_debug.add_argument("--set", help="Filter by specific rule set")
    p_debug.add_argument("-e", "--expansion", action="store_true", help="Force matching by expansion/command text rather than abbreviation")
    p_debug.add_argument("--json", action="store_true", help="Output raw JSON")

    # expand
    p_exp = subparsers.add_parser("expand", help="Simulate typing and expanding a string")
    p_exp.add_argument("text", help="Text or abbreviation string to expand")

    # quick-search
    p_qs = subparsers.add_parser("quick-search", help="Open Typinator quick search popup")
    p_qs.add_argument("query", nargs="?", default="", help="Optional search prefill")

    # restart
    p_restart = subparsers.add_parser(
        "restart",
        help="Restart Typinator application (recovers frozen, hung, or unresponsive state)",
        description="Restart Typinator application (recovers frozen, hung, or unresponsive state)"
    )
    p_restart.add_argument("-f", "--force", action="store_true", help="Force immediate SIGKILL without attempting graceful quit")
    p_restart.add_argument("--json", action="store_true", help="Output raw JSON")

    # snapshots
    p_snaps = subparsers.add_parser(
        "snapshots",
        help="List recent Git backup snapshots from typinator-sync repository",
        description="List recent Git backup snapshots from $TYPINATOR_SYNC_REPO"
    )
    p_snaps.add_argument("-n", "--limit", type=int, default=15, help="Max commits to list (default: 15)")
    p_snaps.add_argument("--set", help="Filter commits that modified a specific rule set (e.g. 'AI prompt')")
    p_snaps.add_argument("--decode", action="store_true", help="Decode binary .tyset blobs to list exact rule changes per commit")
    p_snaps.add_argument("--json", action="store_true", help="Output raw JSON")

    # restore-snapshot
    p_restore = subparsers.add_parser(
        "restore-snapshot",
        help="Safely restore a rule set (or all sets) from a typinator-sync Git snapshot",
        description="Safely restore a rule set (or all sets) from a typinator-sync Git commit (uses SIGKILL before disk copy so Typinator does not overwrite restored files on quit)"
    )
    p_restore.add_argument("commit", help="Git commit hash or ref from typinator-sync")
    p_restore.add_argument("--set", help="Restore only a specific rule set (e.g. 'AI prompt')")
    p_restore.add_argument("--dry-run", action="store_true", help="Preview file changes without modifying live sets")
    p_restore.add_argument("--json", action="store_true", help="Output raw JSON")

    # trace / history
    p_trace = subparsers.add_parser(
        "trace",
        aliases=["history"],
        help="Trace complete Time Machine version history of any rule across Git snapshots and local mutation log",
        description="Decode binary .tyset archives across historical Git commits in typinator-sync to trace every version of an abbreviation"
    )
    p_trace.add_argument("abbreviation", help="Rule abbreviation trigger to trace (e.g. 'wc⇧', 'mbb⇧')")
    p_trace.add_argument("--set", help="Optional rule set name to scope the trace (e.g. 'AI prompt')")
    p_trace.add_argument("-n", "--limit", type=int, default=25, help="Max historical state transitions to return (default: 25)")
    p_trace.add_argument("--json", action="store_true", help="Output raw JSON")

    # diff
    p_diff = subparsers.add_parser(
        "diff",
        help="Decode and compare rules between two snapshots or a snapshot and LIVE disk state",
        description="Decode binary .tyset files and compare rules between ref_a (default: HEAD) and ref_b (default: LIVE disk)"
    )
    p_diff.add_argument("ref_a", nargs="?", default="HEAD", help="Base Git commit/ref or LIVE (default: HEAD)")
    p_diff.add_argument("ref_b", nargs="?", default="LIVE", help="Target Git commit/ref or LIVE (default: LIVE)")
    p_diff.add_argument("--set", help="Filter comparison to a specific rule set (e.g. 'AI prompt')")
    p_diff.add_argument("--json", action="store_true", help="Output raw JSON")

    # restore-rule
    p_restore_rule = subparsers.add_parser(
        "restore-rule",
        help="Surgical single-rule Time Machine recovery from a historical Git snapshot without restarting Typinator",
        description="Extract a single rule from a historical commit in typinator-sync and restore ONLY that rule via OSA without overwriting sibling rules"
    )
    p_restore_rule.add_argument("commit", help="Git commit hash or ref from typinator-sync (e.g. '7532d3f')")
    p_restore_rule.add_argument("set", help="Rule set name (e.g. 'AI prompt')")
    p_restore_rule.add_argument("abbreviation", help="Rule abbreviation trigger to restore (e.g. 'wc⇧')")
    p_restore_rule.add_argument("--dry-run", action="store_true", help="Preview before/after expansion without modifying live Typinator")
    p_restore_rule.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "status":
            res = get_status()
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                if res["status"] == "running":
                    print("🟢 Typinator:           Running")
                    print(f"📁 Total Rule Sets:     {res['total_rule_sets']}")
                    print(f"✅ Active Rule Sets:    {res['enabled_rule_sets']}")
                    print(f"📝 Total Rules:         {res['total_rules']}")
                else:
                    print("🔴 Typinator:           Not Running")

        elif args.command == "list-sets":
            sets = list_sets()
            if args.json:
                print(json.dumps(sets, indent=2, ensure_ascii=False))
            else:
                print(f"{'RULE SET NAME':<38} {'ENABLED':<10} {'RULES':<6}")
                print("-" * 56)
                for s in sets:
                    status_icon = "✅ YES" if s["enabled"] else "❌ NO"
                    print(f"{s['name']:<38} {status_icon:<10} {s['count']:<6}")

        elif args.command == "toggle-set":
            target_state = True if args.enable else False
            ok = toggle_set(args.set, target_state)
            if ok:
                state_str = "ENABLED" if target_state else "DISABLED"
                print(f"✅ Rule set '{args.set}' is now {state_str}.")

        elif args.command == "search":
            res = search_rules(args.query, set_name=args.set)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"Found {len(res)} match(es):")
                for r in res:
                    en_tag = " [ENABLED]" if r["set_enabled"] else " [DISABLED]"
                    desc_tag = f" ({r['description']})" if r["description"] else ""
                    exp_preview = r["expansion"][:50].replace("\n", "↵")
                    print(f"• [{r['set']}]{en_tag} '{r['abbreviation']}'{desc_tag} ➔ {exp_preview}")

        elif args.command == "get":
            rule = get_rule(args.set, args.abbreviation)
            if not rule:
                print(f"Error: Rule '{args.abbreviation}' not found in set '{args.set}'.", file=sys.stderr)
                sys.exit(1)
            if args.json:
                print(json.dumps(rule, indent=2, ensure_ascii=False))
            else:
                print(f"Rule Set:         {rule['set']}")
                print(f"Abbreviation:     {rule['abbreviation']}")
                print(f"Expansion:        {rule['expansion']}")
                print(f"Description:      {rule['description']}")
                print(f"Whole Word Only:  {rule['whole_word']}")
                print(f"Expansion Count:  {rule['expansion_count']}")
                print(f"Unique ID:        {rule['id']}")

        elif args.command == "set":
            if args.expansion:
                warns = validate_nested_references(args.expansion, current_abbr=args.abbreviation)
                for w in warns:
                    print(f"⚠️ Warning ({w['type']}): {w['message']}", file=sys.stderr)
            ok = set_rule_expansion(
                args.set,
                args.abbreviation,
                expansion=args.expansion,
                description=args.desc,
                whole_word=args.whole_word
            )
            if ok:
                print(f"✅ Successfully updated rule '{args.abbreviation}' in set '{args.set}'.")
            else:
                print(f"❌ Failed to update rule.", file=sys.stderr)
                sys.exit(1)

        elif args.command == "add":
            if args.expansion:
                warns = validate_nested_references(args.expansion, current_abbr=args.abbreviation)
                for w in warns:
                    print(f"⚠️ Warning ({w['type']}): {w['message']}", file=sys.stderr)
            dbg = debug_trigger(args.abbreviation, set_name=args.set)
            if dbg.get("mode") == "inspection":
                existing_sets = [r['set'] for r in dbg.get('rules', [])]
                print(f"⚠️ Preflight Warning: Trigger '{args.abbreviation}' already exists in active set(s): {existing_sets}", file=sys.stderr)
            elif dbg.get("mode") == "preflight_simulation" and not dbg.get("is_safe"):
                for sh in dbg.get("potential_shadowers", []):
                    print(f"⚠️ Preflight Warning: {sh['reason']}", file=sys.stderr)
                for dis in dbg.get("potential_disabled", []):
                    print(f"⚠️ Preflight Warning: {dis['reason']}", file=sys.stderr)

            uid = add_rule(
                args.set,
                args.abbreviation,
                args.expansion,
                description=args.desc,
                whole_word=args.whole_word
            )
            print(f"✅ Successfully created rule '{args.abbreviation}' in set '{args.set}' (ID: {uid}).")

        elif args.command == "delete":
            if not args.yes:
                confirm = input(f"Are you sure you want to delete rule '{args.abbreviation}' from set '{args.set}'? [y/N]: ")
                if confirm.strip().lower() != "y":
                    print("Deletion aborted.")
                    sys.exit(0)
            ok = delete_rule(args.set, args.abbreviation)
            if ok:
                print(f"✅ Successfully deleted rule '{args.abbreviation}' from set '{args.set}'.")

        elif args.command == "export":
            payload = export_rules(set_name=args.set)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            print(f"✅ Successfully exported {payload['total_rules']} rule(s) to '{args.output}'.")

        elif args.command == "import":
            if not os.path.exists(args.input):
                print(f"Error: File '{args.input}' not found.", file=sys.stderr)
                sys.exit(1)
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
            stats = import_rules(data, target_set=args.set, overwrite=args.overwrite)
            print(f"✅ Import completed: Created {stats['created']}, Updated {stats['updated']}, Skipped {stats['skipped']}.")

        elif args.command == "audit":
            res = audit_rules(fix=args.fix, set_name=args.set)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"=== Typinator Audit Summary ===")
                print(f"Total Rules Scanned: {res['total_rules_scanned']}")
                print(f"Issues Detected:     {res['issues_found']}")
                print(f"Fixed Items:         {res['fixed']}")
                print("-" * 52)
                for d in res["details"]:
                    t = d["type"]
                    if t == "invisible_character":
                        print(f"⚠️ Invisible Character in [{d['set']}] '{d['abbreviation']}': {d['detected']}")
                    elif t == "duplicate_trigger_collision":
                        print(f"⚠️ Duplicate Trigger '{d['abbreviation']}' across active sets: {d['active_in_sets']}")
                        print(f"   Note: {d.get('note')}")
                    elif t == "prefix_collision":
                        print(f"⚠️ Prefix Collision in [{d['set']}] '{d['abbreviation']}':")
                        print(f"   {d['reason']}")
                        if d.get("explanation"):
                            print(f"   Note: {d['explanation']}")
                    elif t == "empty_abbreviation":
                        print(f"⚠️ Empty Abbreviation in [{d['set']}]: {d.get('note')}")
                    elif t == "dangling_nested_reference":
                        print(f"⚠️ Dangling Nested Reference in [{d['set']}] '{d['abbreviation']}': target '{d['target_abbreviation']}' not found in any active set")
                    elif t == "ambiguous_nested_reference":
                        print(f"⚠️ Ambiguous Nested Reference in [{d['set']}] '{d['abbreviation']}': target '{d['target_abbreviation']}' in multiple sets {d['active_in_sets']}")
                    elif t == "circular_nested_reference":
                        print(f"⚠️ Circular Nested Reference in [{d['set']}] '{d['abbreviation']}': references itself '{d['target_abbreviation']}'")
                if res["issues_found"] == 0:
                    print("✨ All rules are clean! Zero anomalies detected.")

        elif args.command == "debug":
            res = debug_trigger(args.abbreviation, set_name=args.set, by_expansion=args.expansion)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                if res["mode"] == "inspection":
                    if res.get("matched_by") == "expansion":
                        print(f"=== Typinator Trigger Inspection: '{res['abbreviation']}' (matched by expansion/slash command) ===")
                    else:
                        print(f"=== Typinator Trigger Inspection: '{res['abbreviation']}' ===")
                    print(f"Found {len(res['rules'])} matching rule(s):\n")
                    for i, r in enumerate(res["rules"], 1):
                        en_str = "YES" if r["set_enabled"] else "NO"
                        status_icon = "🟢" if r["status"] == "ACTIVE" else "🔴"
                        print(f"[Rule #{i}] Set: '{r['set']}' (Priority #{r['set_priority'] + 1}, Enabled: {en_str})")
                        print(f"  Abbreviation:     '{r['abbreviation']}'")
                        print(f"  Expansion:        {r['expansion']}")
                        if r['description']:
                            print(f"  Description:      {r['description']}")
                        print(f"  Whole Word Only:  {r['whole_word']}")
                        print(f"  Expansion Count:  {r['expansion_count']}")
                        print(f"  Status:           {status_icon} {r['status']}")

                        if r.get("related_rules"):
                            print("\n  ℹ️ Related rules sharing identical expansion:")
                            for rel in r["related_rules"]:
                                print(f"    • [{rel['set']}] '{rel['abbreviation']}' (Priority #{rel['set_priority'] + 1})")

                        if r["shadowed_by"]:
                            print("\n  ⚠️ Shadowing & Conflicts:")
                            for s in r["shadowed_by"]:
                                print(f"    • {s['reason']}")
                                print(f"      Cause: {s['cause']}")

                        if r["shadows_rules"]:
                            print("\n  ⚠️ This rule shadows later rules:")
                            for sr in r["shadows_rules"]:
                                print(f"    • {sr['reason']}")

                        if r["duplicate_sets"]:
                            print(f"\n  ⚠️ Duplicate trigger exists in other sets: {r['duplicate_sets']}")

                        if r["recommendations"]:
                            print("\n  💡 Actionable Recommendations:")
                            for rec in r["recommendations"]:
                                print(f"    • {rec}")
                        print("-" * 52)

                    if "preflight" in res:
                        pf = res["preflight"]
                        print(f"\n=== Trigger Preflight Simulation for '{res['abbreviation']}': ===")
                        if pf["is_safe"]:
                            print(f"✨ Safe to Add '{res['abbreviation']}' directly as an abbreviation trigger! No prefix shadowing detected.")
                        else:
                            print(f"⚠️ Preflight Warning if adding '{res['abbreviation']}' as an abbreviation:")
                            for sh in pf["potential_shadowers"]:
                                print(f"  • {sh['reason']}")
                            for dis in pf["potential_disabled"]:
                                print(f"  • {dis['reason']}")
                else:
                    print(f"=== Typinator Trigger Preflight: '{res['abbreviation']}' ===")
                    print(f"Rule '{res['abbreviation']}' does not exist in any set.\n")
                    if res["is_safe"]:
                        print("✨ Safe to Add! No prefix shadowing or collision conflicts detected.")
                    else:
                        print("⚠️ Preflight Collision Risk:")
                        for sh in res["potential_shadowers"]:
                            print(f"  • {sh['reason']}")
                        for dis in res["potential_disabled"]:
                            print(f"  • {dis['reason']}")

        elif args.command == "expand":
            expand_text(args.text)
            print(f"✅ Expand event sent for: '{args.text}'")

        elif args.command == "quick-search":
            quick_search(args.query)
            print("✅ Quick search palette opened.")

        elif args.command == "restart":
            res = restart_typinator(force=args.force)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                old_str = ", ".join(map(str, res["old_pids"])) if res["old_pids"] else "None (was not running)"
                print("🔄 Typinator restarted successfully.")
                print(f"  Old PID(s):   {old_str}")
                print(f"  New PID:      {res['new_pid']}")
                print(f"  Quit Method:  {res['quit_method']}")
                app_stat = res.get("app_status", {})
                if app_stat.get("status") == "running":
                    print(f"  Status:       🟢 Running ({app_stat.get('total_rules', 0)} rules in {app_stat.get('enabled_rule_sets', 0)} active sets)")
                else:
                    print(f"  Status:       ⚠️ {app_stat.get('status', 'unknown')}")

        elif args.command == "snapshots":
            snaps = list_snapshots(limit=args.limit, set_name=args.set, decode=args.decode)
            if args.json:
                print(json.dumps(snaps, indent=2, ensure_ascii=False))
            else:
                set_label = f" (Set: '{args.set}')" if args.set else ""
                print(f"=== Typinator Backup Snapshots{set_label} ===")
                for s in snaps:
                    print(f"• {s['short_commit']} | {s['date']} | {s['subject']}")
                    if args.decode and s.get("rule_changes"):
                        for ch in s["rule_changes"]:
                            sym = {"added": "+", "deleted": "-", "modified": "~"}.get(ch["change"], "?")
                            exp_prev = (ch.get("new_expansion") or ch.get("old_expansion") or "").replace("\n", "↵")[:60]
                            print(f"    [{sym}] [{ch['set']}] '{ch['abbreviation']}' ➔ {exp_prev}")
                    else:
                        for f in s["changed_files"]:
                            print(f"    [{f['status']}] {f['path']}")

        elif args.command == "restore-snapshot":
            res = restore_snapshot(args.commit, set_name=args.set, dry_run=args.dry_run)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                if res["status"] == "dry_run":
                    print(f"🔍 Dry Run Restore from commit {res['commit'][:7]} (Set: {res['set']}):")
                    print(f"   Changed file entries: {res['changed_count']}")
                    for line in res["diff_lines"]:
                        print(f"   {line}")
                else:
                    print(f"✅ Restored Typinator set '{res['set']}' from commit {res['commit'][:7]} ({res['changed_count']} file delta(s)).")
                    app_stat = res.get("app_status", {})
                    if app_stat.get("status") == "running":
                        print(f"   Status: 🟢 Running ({app_stat.get('total_rules', 0)} rules in {app_stat.get('enabled_rule_sets', 0)} active sets)")

        elif args.command in ("trace", "history"):
            res = trace_rule_history(args.abbreviation, set_name=args.set, limit=args.limit)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"=== Typinator Time Machine Version Trace: '{res['abbreviation']}' ===")
                if not res["sets"] and not res["local_mutation_journal"]:
                    print("No historical versions found across Git snapshots or local mutation journal.")
                for s_name, versions in res["sets"].items():
                    print(f"\n📁 Rule Set: '{s_name}' ({len(versions)} distinct version transition(s)):")
                    print("-" * 68)
                    for idx, v in enumerate(versions, 1):
                        ev = v["event"].upper()
                        x_tag = f" [{v['x_file']}]" if v.get("x_file") else ""
                        print(f"  #{idx} [{v['short_commit']}] {v['date']} | {ev}{x_tag}")
                        if v.get("description"):
                            print(f"     Description: {v['description']}")
                        if v.get("expansion") is not None:
                            exp_lines = v["expansion"].splitlines() or [""]
                            print(f"     Expansion ({len(v['expansion'])} chars):")
                            for el in exp_lines[:8]:
                                print(f"       {el}")
                            if len(exp_lines) > 8:
                                print(f"       ... (+{len(exp_lines) - 8} more lines)")
                if res["local_mutation_journal"]:
                    print(f"\n📓 Local Pre-Mutation Journal ({len(res['local_mutation_journal'])} entry/entries):")
                    for j in res["local_mutation_journal"]:
                        print(f"  • {j['timestamp']} | {j['action'].upper()} [{j['set']}] '{j['abbreviation']}'")
                        if j.get("old_expansion") is not None:
                            print(f"    Before: {j['old_expansion'][:80].replace(chr(10), '↵')}")
                        if j.get("new_expansion") is not None:
                            print(f"    After:  {j['new_expansion'][:80].replace(chr(10), '↵')}")

        elif args.command == "diff":
            res = diff_snapshots(ref_a=args.ref_a, ref_b=args.ref_b, set_name=args.set)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                set_label = f" (Set: '{args.set}')" if args.set else ""
                print(f"=== Typinator Decoded Rule Diff: {res['ref_a']} ➔ {res['ref_b']}{set_label} ===")
                print(f"Total Rule Changes: {res['total_changes']}")
                print("-" * 68)
                for ch in res["changes"]:
                    sym = {"added": "+ ADDED", "deleted": "- DELETED", "modified": "~ MODIFIED"}.get(ch["change"], ch["change"])
                    print(f"{sym} [{ch['set']}] '{ch['abbreviation']}'")
                    if ch["change"] == "added":
                        if ch.get("new_description"):
                            print(f"  + Desc: {ch['new_description']}")
                        print(f"  + Exp:  {(ch.get('new_expansion') or '').replace(chr(10), '↵')}")
                    elif ch["change"] == "deleted":
                        if ch.get("old_description"):
                            print(f"  - Desc: {ch['old_description']}")
                        print(f"  - Exp:  {(ch.get('old_expansion') or '').replace(chr(10), '↵')}")
                    else:
                        if ch.get("old_description") != ch.get("new_description"):
                            print(f"  - Desc: {ch.get('old_description')}")
                            print(f"  + Desc: {ch.get('new_description')}")
                        print(f"  - Before: {(ch.get('old_expansion') or '').replace(chr(10), '↵')}")
                        print(f"  + After:  {(ch.get('new_expansion') or '').replace(chr(10), '↵')}")

        elif args.command == "restore-rule":
            res = restore_single_rule(
                args.commit,
                args.set,
                args.abbreviation,
                dry_run=args.dry_run
            )
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                mode_tag = "🔍 [DRY RUN]" if res["status"] == "dry_run" else "✅ [RESTORED]"
                print(f"{mode_tag} Single-Rule Time Machine Recovery ({res['operation']}):")
                print(f"  Commit:       {res['commit']}")
                print(f"  Rule Set:     {res['set']}")
                print(f"  Abbreviation: {res['abbreviation']}")
                if res.get("before_expansion") is not None:
                    print(f"  Before:       {res['before_expansion'].replace(chr(10), '↵')}")
                print(f"  Restored:     {res['restored_expansion'].replace(chr(10), '↵')}")

    except (LookupError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"System Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
