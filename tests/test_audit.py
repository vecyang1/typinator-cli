#!/usr/bin/env python3
"""Unit tests for invisible character and trigger collision auditing logic."""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
from typinator_cli import INVISIBLE_CHARS_MAP


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


if __name__ == '__main__':
    unittest.main()
