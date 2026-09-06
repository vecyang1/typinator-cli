#!/usr/bin/env python3
"""Unit tests for invisible character and trigger collision auditing logic."""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
from unittest.mock import patch
from typinator_cli import (
    INVISIBLE_CHARS_MAP,
    NESTED_REFERENCE_PATTERN,
    validate_nested_references,
    PrefixTrie,
    audit_rules,
    debug_trigger,
    is_word_char
)


class TestTypinatorAuditLogic(unittest.TestCase):
    def test_invisible_char_detection(self):
        sample_clean = "/g{delay:1.5}{tab}"
        sample_dirty_line_sep = "/g \u2028{delay:1.5}{tab}"
        sample_dirty_bom = "\ufeffhello world"
        sample_dirty_zero_width = "zero\u200bwidth"

        def find_invisible(s):
            return [desc for ch, desc in INVISIBLE_CHARS_MAP.items() if ch in s]

        self.assertEqual(find_invisible(sample_clean), [])
        self.assertIn("LINE_SEPARATOR (\\u2028)", find_invisible(sample_dirty_line_sep))
        self.assertIn("ZERO_WIDTH_NO_BREAK_SPACE (\\ufeff)", find_invisible(sample_dirty_bom))
        self.assertIn("ZERO_WIDTH_SPACE (\\u200b)", find_invisible(sample_dirty_zero_width))

    def test_invisible_char_cleanup(self):
        dirty = "/g \u2028{delay:1.5}\u200b{tab}"
        clean = dirty
        for ch in INVISIBLE_CHARS_MAP:
            clean = clean.replace(ch, "\n" if ch in ['\u2028', '\u2029'] else "")
        self.assertEqual(clean, "/g \n{delay:1.5}{tab}")

    def test_nested_reference_pattern_extraction(self):
        text = 'Prefix {"ref1"} middle {"nested_abbr_2"} suffix'
        matches = NESTED_REFERENCE_PATTERN.findall(text)
        self.assertEqual(matches, ["ref1", "nested_abbr_2"])

    @patch("typinator_cli.search_rules")
    def test_validate_nested_references_dangling(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "existing_rule", "set": "SetA", "set_enabled": True}
        ]
        warns = validate_nested_references('{"unknown_rule"}')
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]["type"], "dangling_nested_reference")

    @patch("typinator_cli.search_rules")
    def test_validate_nested_references_ambiguous(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "dup_rule", "set": "SetA", "set_enabled": True},
            {"abbreviation": "dup_rule", "set": "SetB", "set_enabled": True},
        ]
        warns = validate_nested_references('{"dup_rule"}')
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]["type"], "ambiguous_nested_reference")
        self.assertEqual(warns[0]["active_in_sets"], ["SetA", "SetB"])

    def test_validate_nested_references_circular(self):
        warns = validate_nested_references('{"self_rule"}', current_abbr="self_rule")
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]["type"], "circular_nested_reference")

    def test_prefix_trie_operations(self):
        trie = PrefixTrie()
        trie.insert({"abbreviation": "img", "set": "Midjourney", "whole_word": False})
        trie.insert({"abbreviation": "im", "set": "Midjourney", "whole_word": False})

        prefixes = trie.find_prefixes("img⇧")
        abbrs = [p["abbreviation"] for p in prefixes]
        self.assertIn("im", abbrs)
        self.assertIn("img", abbrs)

        extensions = trie.find_extensions("im")
        ext_abbrs = [e["abbreviation"] for e in extensions]
        self.assertIn("img", ext_abbrs)

    @patch("typinator_cli.search_rules")
    def test_audit_prefix_collision_non_whole_word(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "img", "set": "Midjourney", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": False, "expansion": "/imagine "},
            {"abbreviation": "img⇧", "set": "AI prompt", "set_enabled": True, "set_priority": 1, "rule_index": 0, "whole_word": False, "expansion": "/image-gen-with-api"}
        ]
        res = audit_rules()
        prefix_issues = [i for i in res["details"] if i["type"] == "prefix_collision"]
        self.assertEqual(len(prefix_issues), 1)
        issue = prefix_issues[0]
        self.assertEqual(issue["disabled_set"], "AI prompt")
        self.assertEqual(issue["disabled_abbreviation"], "img⇧")
        self.assertEqual(issue["shadowed_by_set"], "Midjourney")
        self.assertEqual(issue["shadowed_by_abbreviation"], "img")
        self.assertEqual(issue["reason"], 'Disabled by "img" of set "Midjourney".')

    @patch("typinator_cli.search_rules")
    def test_audit_prefix_collision_whole_word_with_delimiter(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "test", "set": "SetA", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": True, "expansion": "val"},
            {"abbreviation": "test⇧", "set": "SetB", "set_enabled": True, "set_priority": 1, "rule_index": 0, "whole_word": False, "expansion": "val2"}
        ]
        res = audit_rules()
        prefix_issues = [i for i in res["details"] if i["type"] == "prefix_collision"]
        self.assertEqual(len(prefix_issues), 1)
        self.assertEqual(prefix_issues[0]["disabled_abbreviation"], "test⇧")

    @patch("typinator_cli.search_rules")
    def test_audit_prefix_collision_whole_word_with_word_char_no_collision(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "cat", "set": "SetA", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": True, "expansion": "feline"},
            {"abbreviation": "catch", "set": "SetB", "set_enabled": True, "set_priority": 1, "rule_index": 0, "whole_word": False, "expansion": "grab"}
        ]
        res = audit_rules()
        prefix_issues = [i for i in res["details"] if i["type"] == "prefix_collision"]
        self.assertEqual(len(prefix_issues), 0)

    @patch("typinator_cli.search_rules")
    def test_audit_prefix_collision_set_filter(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "img", "set": "Midjourney", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": False, "expansion": "/imagine "},
            {"abbreviation": "img⇧", "set": "AI prompt", "set_enabled": True, "set_priority": 1, "rule_index": 0, "whole_word": False, "expansion": "/image-gen-with-api"},
            {"abbreviation": "unrelated", "set": "Other", "set_enabled": True, "set_priority": 2, "rule_index": 0, "whole_word": False, "expansion": "x"}
        ]
        res = audit_rules(set_name="AI prompt")
        self.assertEqual(len(res["details"]), 1)
        self.assertEqual(res["details"][0]["disabled_abbreviation"], "img⇧")

    @patch("typinator_cli.search_rules")
    def test_audit_empty_abbreviation(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "", "set": "Temporary", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": False, "expansion": "empty_trigger"}
        ]
        res = audit_rules()
        empty_issues = [i for i in res["details"] if i["type"] == "empty_abbreviation"]
        self.assertEqual(len(empty_issues), 1)

    @patch("typinator_cli.search_rules")
    @patch("typinator_cli.get_rule")
    def test_debug_trigger_conflicted(self, mock_get, mock_search):
        mock_search.return_value = [
            {"abbreviation": "img", "set": "Midjourney", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": False, "expansion": "/imagine "},
            {"abbreviation": "img⇧", "set": "AI prompt", "set_enabled": True, "set_priority": 1, "rule_index": 0, "whole_word": False, "expansion": "/image-gen-with-api"}
        ]
        mock_get.return_value = {
            "set": "AI prompt", "abbreviation": "img⇧", "expansion": "/image-gen-with-api",
            "description": "Slash command", "whole_word": False, "expansion_count": 0, "id": "123"
        }
        res = debug_trigger("img⇧")
        self.assertEqual(res["mode"], "inspection")
        self.assertEqual(res["rules"][0]["status"], "DISABLED")
        self.assertEqual(len(res["rules"][0]["shadowed_by"]), 1)
        self.assertEqual(res["rules"][0]["shadowed_by"][0]["shadowed_by_set"], "Midjourney")

    @patch("typinator_cli.search_rules")
    def test_debug_trigger_preflight(self, mock_search):
        mock_search.return_value = [
            {"abbreviation": "img", "set": "Midjourney", "set_enabled": True, "set_priority": 0, "rule_index": 0, "whole_word": False, "expansion": "/imagine "}
        ]
        clean_res = debug_trigger("clean_trigger")
        self.assertEqual(clean_res["mode"], "preflight_simulation")
        self.assertTrue(clean_res["is_safe"])

        conflicted_res = debug_trigger("img_something")
        self.assertEqual(conflicted_res["mode"], "preflight_simulation")
        self.assertFalse(conflicted_res["is_safe"])
        self.assertEqual(conflicted_res["potential_shadowers"][0]["set"], "Midjourney")


if __name__ == '__main__':
    unittest.main()
