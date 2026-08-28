#!/usr/bin/env python3
"""
Typinator CLI - Production-Grade Automation & Management Harness for macOS Typinator.
Supports programmatic rule querying, live in-memory updates, batch export/import,
safety auditing (invisible Unicode characters & trigger collision detection),
and full AppleScript / Open Scripting Architecture (OSA) integration.
"""

import sys
import os
import json
import argparse
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

VERSION = "1.1.0"

INVISIBLE_CHARS_MAP = {
    '\u2028': 'LINE_SEPARATOR (\\u2028)',
    '\u2029': 'PARAGRAPH_SEPARATOR (\\u2029)',
    '\ufeff': 'ZERO_WIDTH_NO_BREAK_SPACE (\\ufeff)',
    '\u200b': 'ZERO_WIDTH_SPACE (\\u200b)',
}


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
        set totalRules to 0
        set enabledSets to 0
        repeat with i from 1 to count of sNames
            if (item i of sEnabled) is true then
                set enabledSets to enabledSets + 1
            end if
            try
                set totalRules to totalRules + (count of rules of (item i of rule sets))
            end try
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
    Uses bulk `rule table` for sub-second retrieval across thousands of rules.
    """
    if set_name:
        sc = f'''
        tell application "Typinator"
            try
                set aSet to (first rule set whose name is "{escape_as(set_name)}")
                set sEn to enabled of aSet
                set t to rule table of aSet
                return "===TYPINATOR_SET_DELIMITER===" & "{escape_as(set_name)}" & "===SET===" & (sEn as text) & "===ENABLED===" & t
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
            repeat with i from 1 to count of sNames
                set sName to item i of sNames
                set sEn to item i of sEnabled
                try
                    set t to rule table of (item i of rule sets)
                    set outStr to outStr & "===TYPINATOR_SET_DELIMITER===" & sName & "===SET===" & (sEn as text) & "===ENABLED===" & t
                end try
            end repeat
            return outStr
        end tell
        '''

    raw = run_applescript(sc)
    results = []
    if not raw:
        return results

    q_lower = query.lower()
    set_blocks = raw.split("===TYPINATOR_SET_DELIMITER===")

    for block in set_blocks:
        if "===SET===" not in block or "===ENABLED===" not in block:
            continue
        header, table_content = block.split("===ENABLED===", 1)
        s_name, s_en_str = header.split("===SET===", 1)
        s_enabled = s_en_str.strip().lower() == "true"

        for line in table_content.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                abbr = parts[0]
                uid = parts[1]
                exp_or_desc = parts[2] if len(parts) > 2 else ""

                if not query or (q_lower in abbr.lower() or q_lower in exp_or_desc.lower()):
                    results.append({
                        "set": s_name.strip(),
                        "set_enabled": s_enabled,
                        "abbreviation": abbr,
                        "expansion": exp_or_desc,
                        "description": "",
                        "id": uid
                    })
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
            return a & "\t" & e & "\t" & d & "\t" & uid & "\t" & (ww as text) & "\t" & (uCount as text)
        on error
            return ""
        end try
    end tell
    '''
    raw = run_applescript(sc)
    if not raw:
        return None
    parts = raw.split("\t")
    if len(parts) >= 6:
        return {
            "set": set_name,
            "abbreviation": parts[0],
            "expansion": parts[1],
            "description": parts[2],
            "id": parts[3],
            "whole_word": parts[4].strip().lower() == "true",
            "expansion_count": int(parts[5].strip())
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


def audit_rules(fix: bool = False, set_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Audit rules for:
    1. Invisible / rogue Unicode control characters (\u2028 line separator, \u2029, \ufeff, \u200b).
    2. Duplicate abbreviation triggers across enabled rule sets.
    """
    all_rules = search_rules(set_name=set_name)
    issues = []
    seen_abbrs: Dict[str, List[str]] = {}
    fixed_count = 0

    for r in all_rules:
        # Check active set collisions
        if r["set_enabled"]:
            seen_abbrs.setdefault(r["abbreviation"], []).append(r["set"])

        # Check invisible characters
        exp = r["expansion"]
        found_inv = [desc for ch, desc in INVISIBLE_CHARS_MAP.items() if ch in exp]
        if found_inv:
            issue_item = {
                "type": "invisible_character",
                "set": r["set"],
                "abbreviation": r["abbreviation"],
                "detected": found_inv,
                "raw_expansion": repr(exp)
            }
            issues.append(issue_item)
            if fix:
                clean_exp = exp
                for ch in INVISIBLE_CHARS_MAP:
                    clean_exp = clean_exp.replace(ch, "\n" if ch in ['\u2028', '\u2029'] else "")
                set_rule_expansion(r["set"], r["abbreviation"], expansion=clean_exp)
                fixed_count += 1

    # Filter duplicate trigger collisions across different sets
    collisions = {k: v for k, v in seen_abbrs.items() if len(v) > 1}
    for abbr, sets in collisions.items():
        issues.append({
            "type": "duplicate_trigger_collision",
            "abbreviation": abbr,
            "active_in_sets": sets,
            "note": "The higher ranked set in Typinator will shadow the lower sets"
        })

    return {
        "total_rules_scanned": len(all_rules),
        "issues_found": len(issues),
        "fixed": fixed_count,
        "details": issues
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
    p_audit = subparsers.add_parser("audit", help="Audit rules for invisible characters and duplicate collisions")
    p_audit.add_argument("--set", help="Audit specific rule set only")
    p_audit.add_argument("--fix", action="store_true", help="Automatically sanitize invisible control characters")
    p_audit.add_argument("--json", action="store_true", help="Output raw JSON")

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
                    if d["type"] == "invisible_character":
                        print(f"⚠️ Invisible Character in [{d['set']}] '{d['abbreviation']}': {d['detected']}")
                    elif d["type"] == "duplicate_trigger_collision":
                        print(f"⚠️ Duplicate Trigger '{d['abbreviation']}' across active sets: {d['active_in_sets']}")
                if res["issues_found"] == 0:
                    print("✨ All rules are clean! Zero anomalies detected.")

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
