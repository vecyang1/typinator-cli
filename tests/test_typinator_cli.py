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

    def test_bin_wrapper_help(self):
        import subprocess
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        res = subprocess.run([bin_path, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Typinator CLI", res.stdout)
        self.assertIn("subcommands", res.stdout)

    def test_bin_wrapper_status_json(self):
        import subprocess, json
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        res = subprocess.run([bin_path, "status", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "running")
        self.assertGreater(data["total_rules"], 0)

    def test_bin_symlink_resolution(self):
        import subprocess, tempfile, shutil
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        tmp_dir = tempfile.mkdtemp()
        try:
            symlink_path = os.path.join(tmp_dir, "typinator-symlink-test")
            os.symlink(bin_path, symlink_path)
            res = subprocess.run([symlink_path, "--help"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Typinator CLI", res.stdout)
        finally:
            shutil.rmtree(tmp_dir)

if __name__ == '__main__':
    unittest.main()
