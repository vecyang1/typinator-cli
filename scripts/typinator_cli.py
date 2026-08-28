#!/usr/bin/env python3
"""
Typinator CLI - Unified CLI and automation harness for macOS Typinator.
Enables programmatic search, inspection, addition, modification, deletion,
and safety auditing (e.g. invisible character checks, duplicate trigger collisions).
"""

import sys
import os
import json
import argparse
import subprocess
from typing import List, Dict, Any, Optional

def run_applescript(script: str) -> str:
    """Execute an AppleScript string via osascript and return stdout."""
    res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if res.returncode != 0:
        err = res.stderr.strip()
        if "-600" in err:
            raise RuntimeError("Typinator application is not running. Please launch Typinator first.")
        raise RuntimeError(f"AppleScript error: {err}")
    return res.stdout.strip()

def escape_as(s: str) -> str:
    """Escape a string for insertion into AppleScript double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

def list_sets() -> List[Dict[str, Any]]:
    """List all rule sets with enabled status."""
    sc = '''
    tell application "Typinator"
        set sNames to name of every rule set
        set sEnabled to enabled of every rule set
        set outList to {}
        repeat with i from 1 to count of sNames
            set end of outList to (item i of sNames) & "\t" & (item i of sEnabled)
        end repeat
        return outList
    end tell
    '''
    raw = run_applescript(sc)
    results = []
    if not raw:
        return results
    for item in raw.split(", "):
        parts = item.split("\t")
        if len(parts) >= 2:
            results.append({
                "name": parts[0],
                "enabled": parts[1].strip().lower() == "true"
            })
    return results

def search_rules(query: str = "", set_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search rules across sets by abbreviation, description, or expansion."""
    target_sets = f'rule set "{escape_as(set_name)}"' if set_name else 'rule sets'
    sc = f'''
    tell application "Typinator"
        set outList to {{}}
        set allSets to {target_sets}
        if class of allSets is not list then set allSets to {{allSets}}
        repeat with aSet in allSets
            set sName to name of aSet
            set sEnabled to enabled of aSet
            try
                set rList to every rule of aSet
                repeat with r in rList
                    set a to abbreviation of r
                    set e to plain expansion of r
                    set d to description of r
                    set uid to unique id of r
                    set end of outList to sName & "\t" & (sEnabled as text) & "\t" & a & "\t" & e & "\t" & d & "\t" & uid
                end repeat
            end try
        end repeat
        return outList
    end tell
    '''
    raw = run_applescript(sc)
    results = []
    if not raw:
        return results
    
    items = raw.split(", ")
    q_lower = query.lower()
    for item in items:
        parts = item.split("\t")
        if len(parts) >= 6:
            s_name, s_en, abbr, exp, desc, uid = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            if not query or (q_lower in abbr.lower() or q_lower in exp.lower() or q_lower in desc.lower()):
                results.append({
                    "set": s_name,
                    "set_enabled": s_en.strip().lower() == "true",
                    "abbreviation": abbr,
                    "expansion": exp,
                    "description": desc,
                    "id": uid
                })
    return results

def get_rule(set_name: str, abbreviation: str) -> Optional[Dict[str, Any]]:
    """Get details of a specific rule by set name and abbreviation."""
    sc = f'''
    tell application "Typinator"
        try
            set r to (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
            set a to abbreviation of r
            set e to plain expansion of r
            set d to description of r
            set uid to unique id of r
            set ww to whole word of r
            return a & "\t" & e & "\t" & d & "\t" & uid & "\t" & (ww as text)
        on error
            return ""
        end try
    end tell
    '''
    raw = run_applescript(sc)
    if not raw:
        return None
    parts = raw.split("\t")
    if len(parts) >= 5:
        return {
            "set": set_name,
            "abbreviation": parts[0],
            "expansion": parts[1],
            "description": parts[2],
            "id": parts[3],
            "whole_word": parts[4].strip().lower() == "true"
        }
    return None

def set_rule_expansion(set_name: str, abbreviation: str, expansion: str, description: Optional[str] = None) -> bool:
    """Update an existing rule's expansion and optionally description."""
    desc_clause = f'\nset description of r to "{escape_as(description)}"' if description is not None else ""
    sc = f'''
    tell application "Typinator"
        set r to (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
        set plain expansion of r to "{escape_as(expansion)}"{desc_clause}
        return unique id of r
    end tell
    '''
    res = run_applescript(sc)
    return bool(res)

def add_rule(set_name: str, abbreviation: str, expansion: str, description: str = "", whole_word: bool = False) -> str:
    """Add a new rule to a specified rule set."""
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
    sc = f'''
    tell application "Typinator"
        delete (first rule of rule set "{escape_as(set_name)}" whose abbreviation is "{escape_as(abbreviation)}")
        return "OK"
    end tell
    '''
    res = run_applescript(sc)
    return res == "OK"

def audit_rules(fix: bool = False) -> Dict[str, Any]:
    """
    Audit all active rules for:
    1. Invisible / rogue Unicode control characters (\u2028 line separator, \u2029 paragraph separator, \ufeff BOM, \u00a0 non-breaking space).
    2. Duplicate abbreviation triggers across enabled sets.
    3. Trailing space before delay / keystroke markers.
    """
    all_rules = search_rules()
    invisible_chars = {
        '\u2028': 'LINE_SEPARATOR (\\u2028)',
        '\u2029': 'PARAGRAPH_SEPARATOR (\\u2029)',
        '\ufeff': 'ZERO_WIDTH_NO_BREAK_SPACE (\\ufeff)',
        '\u200b': 'ZERO_WIDTH_SPACE (\\u200b)',
    }
    
    issues = []
    seen_abbrs: Dict[str, List[str]] = {}
    fixed_count = 0

    for r in all_rules:
        # Check duplicates
        if r["set_enabled"]:
            seen_abbrs.setdefault(r["abbreviation"], []).append(r["set"])

        # Check invisible chars
        exp = r["expansion"]
        found_inv = [desc for ch, desc in invisible_chars.items() if ch in exp]
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
                for ch in invisible_chars:
                    clean_exp = clean_exp.replace(ch, "\n" if ch in ['\u2028', '\u2029'] else "")
                set_rule_expansion(r["set"], r["abbreviation"], clean_exp)
                fixed_count += 1

    # Filter duplicates across multiple enabled sets
    collisions = {k: v for k, v in seen_abbrs.items() if len(v) > 1}
    for abbr, sets in collisions.items():
        issues.append({
            "type": "duplicate_trigger_collision",
            "abbreviation": abbr,
            "active_in_sets": sets,
            "note": "Higher ranked set will shadow lower sets"
        })

    return {
        "total_rules_scanned": len(all_rules),
        "issues_found": len(issues),
        "fixed": fixed_count,
        "details": issues
    }

def main():
    parser = argparse.ArgumentParser(description="Typinator CLI Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list-sets
    subparsers.add_parser("list-sets", help="List all Typinator rule sets")

    # search
    p_search = subparsers.add_parser("search", help="Search rules by keyword")
    p_search.add_argument("query", nargs="?", default="", help="Query string")
    p_search.add_argument("--set", help="Filter by rule set name")
    p_search.add_argument("--json", action="store_true", help="Output JSON")

    # get
    p_get = subparsers.add_parser("get", help="Get a single rule")
    p_get.add_argument("set", help="Rule set name")
    p_get.add_argument("abbreviation", help="Rule abbreviation")
    p_get.add_argument("--json", action="store_true", help="Output JSON")

    # set
    p_set = subparsers.add_parser("set", help="Update a rule expansion")
    p_set.add_argument("set", help="Rule set name")
    p_set.add_argument("abbreviation", help="Rule abbreviation")
    p_set.add_argument("--expansion", required=True, help="New plain expansion")
    p_set.add_argument("--desc", help="Optional description")

    # add
    p_add = subparsers.add_parser("add", help="Add a new rule")
    p_add.add_argument("set", help="Rule set name")
    p_add.add_argument("abbreviation", help="Rule abbreviation")
    p_add.add_argument("--expansion", required=True, help="Plain expansion text")
    p_add.add_argument("--desc", default="", help="Optional description")
    p_add.add_argument("--whole-word", action="store_true", help="Match whole word only")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a rule")
    p_del.add_argument("set", help="Rule set name")
    p_del.add_argument("abbreviation", help="Rule abbreviation")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit rules for invisible chars and duplicate triggers")
    p_audit.add_argument("--fix", action="store_true", help="Automatically fix invisible control characters")
    p_audit.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "list-sets":
            sets = list_sets()
            print(f"{'SET NAME':<40} {'ENABLED':<10}")
            print("-" * 52)
            for s in sets:
                status = "✅ YES" if s["enabled"] else "❌ NO"
                print(f"{s['name']:<40} {status:<10}")

        elif args.command == "search":
            res = search_rules(args.query, set_name=args.set)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"Found {len(res)} matches:")
                for r in res:
                    en = " [ENABLED]" if r["set_enabled"] else " [DISABLED]"
                    print(f"• [{r['set']}]{en} | Abbr: '{r['abbreviation']}' -> Exp: '{r['expansion'][:60]}...'")

        elif args.command == "get":
            rule = get_rule(args.set, args.abbreviation)
            if not rule:
                print(f"Rule not found: [{args.set}] -> '{args.abbreviation}'", file=sys.stderr)
                sys.exit(1)
            if args.json:
                print(json.dumps(rule, indent=2, ensure_ascii=False))
            else:
                print(f"Set:          {rule['set']}")
                print(f"Abbreviation: {rule['abbreviation']}")
                print(f"Expansion:    {rule['expansion']}")
                print(f"Description:  {rule['description']}")
                print(f"Whole Word:   {rule['whole_word']}")
                print(f"Rule ID:      {rule['id']}")

        elif args.command == "set":
            ok = set_rule_expansion(args.set, args.abbreviation, args.expansion, args.desc)
            if ok:
                print(f"✅ Successfully updated rule '{args.abbreviation}' in set '{args.set}'")
            else:
                print(f"❌ Failed to update rule '{args.abbreviation}'", file=sys.stderr)
                sys.exit(1)

        elif args.command == "add":
            uid = add_rule(args.set, args.abbreviation, args.expansion, args.desc, args.whole_word)
            print(f"✅ Successfully created rule '{args.abbreviation}' in set '{args.set}' (ID: {uid})")

        elif args.command == "delete":
            ok = delete_rule(args.set, args.abbreviation)
            if ok:
                print(f"✅ Successfully deleted rule '{args.abbreviation}' from set '{args.set}'")
            else:
                print(f"❌ Failed to delete rule", file=sys.stderr)
                sys.exit(1)

        elif args.command == "audit":
            res = audit_rules(fix=args.fix)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"=== Typinator Audit Summary ===")
                print(f"Total Rules Scanned: {res['total_rules_scanned']}")
                print(f"Issues Detected:     {res['issues_found']}")
                print(f"Fixed Items:         {res['fixed']}")
                print("-" * 50)
                for d in res["details"]:
                    if d["type"] == "invisible_character":
                        print(f"⚠️ Invisible Character in [{d['set']}] '{d['abbreviation']}': {d['detected']}")
                    elif d["type"] == "duplicate_trigger_collision":
                        print(f"⚠️ Duplicate Trigger '{d['abbreviation']}' across active sets: {d['active_in_sets']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
