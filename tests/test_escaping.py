#!/usr/bin/env python3
"""Unit tests for string and character escaping in Typinator CLI."""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
from typinator_cli import escape_as


class TestTypinatorEscaping(unittest.TestCase):
    def test_basic_strings(self):
        self.assertEqual(escape_as("hello world"), "hello world")
        self.assertEqual(escape_as(""), "")
        self.assertEqual(escape_as(None), "")

    def test_quotes_and_backslashes(self):
        self.assertEqual(escape_as('say "hello"'), 'say \\"hello\\"')
        self.assertEqual(escape_as('C:\\path\\to\\file'), 'C:\\\\path\\\\to\\\\file')

    def test_newlines_and_tabs(self):
        self.assertEqual(escape_as("line1\nline2\rline3\ttab"), "line1\\nline2\\rline3\\ttab")

    def test_markers_and_scripts(self):
        self.assertEqual(escape_as("/g{delay:1.5}{tab}"), "/g{delay:1.5}{tab}")
        self.assertEqual(
            escape_as('{/AppleScript do shell script "sleep 1.5"}'),
            '{/AppleScript do shell script \\"sleep 1.5\\"}'
        )


if __name__ == '__main__':
    unittest.main()
