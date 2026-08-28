#!/usr/bin/env python3
"""Unit tests for Typinator CLI helper functions and escaping."""

import unittest
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from typinator_cli import escape_as

class TestTypinatorCli(unittest.TestCase):
    def test_escape_as_quotes_and_backslashes(self):
        self.assertEqual(escape_as('test "quoted" text'), 'test \\"quoted\\" text')
        self.assertEqual(escape_as('path\\to\\file'), 'path\\\\to\\\\file')

    def test_escape_as_newlines(self):
        self.assertEqual(escape_as("line1\nline2\rline3"), "line1\\nline2\\rline3")

    def test_escape_as_markers(self):
        raw = '/g{delay:1.5}{tab}'
        self.assertEqual(escape_as(raw), '/g{delay:1.5}{tab}')

if __name__ == '__main__':
    unittest.main()
