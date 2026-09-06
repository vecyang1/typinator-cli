#!/usr/bin/env python3
"""Unit tests for Typinator CLI helper functions and escaping."""

import unittest
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from typinator_cli import escape_as, is_typinator_running
import typinator_cli

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
        self.assertIn(data["status"], ("running", "not_running"))
        if data["status"] == "running":
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

    def test_bin_wrapper_audit_json(self):
        if not is_typinator_running():
            self.skipTest("Typinator app is not running (headless or CI runner environment)")
        import subprocess, json
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        res = subprocess.run([bin_path, "audit", "--set", "AI prompt", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("total_rules_scanned", data)
        self.assertIn("issues_found", data)
        self.assertIn("details", data)

    def test_bin_wrapper_debug_json(self):
        if not is_typinator_running():
            self.skipTest("Typinator app is not running (headless or CI runner environment)")
        import subprocess, json
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        # 1. Inspection mode for live active rule
        res = subprocess.run([bin_path, "debug", "im⇧", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["mode"], "inspection")
        self.assertTrue(data["exists"])
        self.assertGreater(len(data["rules"]), 0)

        # 2. Preflight simulation mode for non-existent rule
        res_preflight = subprocess.run([bin_path, "debug", "test_simulated_abbr_xyz", "--json"], capture_output=True, text=True)
        self.assertEqual(res_preflight.returncode, 0)
        data_preflight = json.loads(res_preflight.stdout)
        self.assertEqual(data_preflight["mode"], "preflight_simulation")
        self.assertFalse(data_preflight["exists"])

        # 3. Inspection mode for slash command /boost
        res_boost = subprocess.run([bin_path, "debug", "/boost", "--json"], capture_output=True, text=True)
        self.assertEqual(res_boost.returncode, 0)
        data_boost = json.loads(res_boost.stdout)
        self.assertEqual(data_boost["mode"], "inspection")
        self.assertEqual(data_boost["matched_by"], "expansion")
        self.assertGreaterEqual(len(data_boost["rules"]), 1)

        # 4. Inspection mode for slash command /goal
        res_goal = subprocess.run([bin_path, "debug", "/goal", "--json"], capture_output=True, text=True)
        self.assertEqual(res_goal.returncode, 0)
        data_goal = json.loads(res_goal.stdout)
        self.assertEqual(data_goal["mode"], "inspection")
        self.assertEqual(data_goal["matched_by"], "expansion")
        self.assertGreaterEqual(len(data_goal["rules"]), 1)


if __name__ == '__main__':
    unittest.main()
