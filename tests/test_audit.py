#!/usr/bin/env python3
"""Unit tests for invisible character and trigger collision auditing logic."""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
from unittest.mock import patch
from typinator_cli import INVISIBLE_CHARS_MAP, NESTED_REFERENCE_PATTERN, validate_nested_references


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


if __name__ == '__main__':
    unittest.main()
