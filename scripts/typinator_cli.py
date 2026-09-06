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
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

VERSION = "1.3.1"

NESTED_REFERENCE_PATTERN = re.compile(r'\{"([^"\n]+)"\}')

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
    """Execute an AppleScript string via osascript and return stdout."""
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
            raise RuntimeError("Typinator application is not running. Please launch Typinator first.")
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

        rule_idx = 0
        for line in table_content.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                abbr = parts[0]
                uid = parts[1]
                exp_or_desc = "\t".join(parts[2:]) if len(parts) > 2 else ""
                is_ww = ww_flags[rule_idx] if rule_idx < len(ww_flags) else False

                if not query or (q_lower in abbr.lower() or q_lower in exp_or_desc.lower()):
                    results.append({
                        "set": s_name.strip(),
                        "set_enabled": s_enabled,
                        "set_priority": set_priority_val,
                        "rule_index": rule_idx,
                        "abbreviation": abbr,
                        "expansion": exp_or_desc,
                        "description": "",
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

    update_block = "\n".join(updates)
    sc = f'''
    tell application "Typinator"
        set r to (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
        {update_block}
        return unique id of r
    end tell
    '''
    res = run_applescript(sc)
    return bool(res)


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
    return run_applescript(sc)


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
    return res == "OK"


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

    # 4. Invisible character & nested reference checks
    if set_name:
        target_rules = [r for r in global_rules if r["set"] == set_name]
    else:
        target_rules = global_rules

    for r in target_rules:
        abbr = r.get("abbreviation", "")
        exp = r.get("expansion", "")
        s_name = r.get("set", "")

        found_inv = [desc for ch, desc in INVISIBLE_CHARS_MAP.items() if ch in exp]
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
                clean_exp = exp
                for ch in INVISIBLE_CHARS_MAP:
                    clean_exp = clean_exp.replace(ch, "\n" if ch in ['\u2028', '\u2029'] else "")
                set_rule_expansion(s_name, abbr, expansion=clean_exp)
                fixed_count += 1

        for match in NESTED_REFERENCE_PATTERN.finditer(exp):
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

    except (LookupError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"System Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
