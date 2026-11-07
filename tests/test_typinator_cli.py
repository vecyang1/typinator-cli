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

    def test_bin_wrapper_restart_help(self):
        import subprocess
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        res = subprocess.run([bin_path, "restart", "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Restart Typinator application", res.stdout)
        self.assertIn("--force", res.stdout)
        self.assertIn("--json", res.stdout)

    def test_bin_wrapper_snapshots_and_restore_dry_run(self):
        import subprocess, json
        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))
        res_help = subprocess.run([bin_path, "restore-snapshot", "--help"], capture_output=True, text=True)
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("--dry-run", res_help.stdout)

        if not os.path.isdir(os.path.join(typinator_cli.DEFAULT_SYNC_REPO, ".git")):
            self.skipTest("typinator-sync repository not present on this runner")

        res_snaps = subprocess.run([bin_path, "snapshots", "--set", "AI prompt", "-n", "3", "--json"], capture_output=True, text=True)
        self.assertEqual(res_snaps.returncode, 0)
        snaps = json.loads(res_snaps.stdout)
        self.assertGreaterEqual(len(snaps), 1)
        self.assertIn("commit", snaps[0])

        res_dry = subprocess.run(
            [bin_path, "restore-snapshot", snaps[0]["commit"], "--set", "AI prompt", "--dry-run", "--json"],
            capture_output=True, text=True
        )
        self.assertEqual(res_dry.returncode, 0)
        dry_data = json.loads(res_dry.stdout)
        self.assertEqual(dry_data["status"], "dry_run")
        self.assertEqual(dry_data["set"], "AI prompt")

    def test_decode_typinator_archive_involutory(self):
        sample = b"bplist00\x01\x02\x03Hello Typinator Time Machine"
        encoded = typinator_cli.decode_typinator_archive(sample)
        self.assertNotEqual(encoded, sample)
        decoded = typinator_cli.decode_typinator_archive(encoded)
        self.assertEqual(decoded, sample)

    def test_decode_x_payload_bplist_and_streamtyped(self):
        import plistlib
        # 1. Modern NSKeyedArchiver (bplist00) payload
        fake_bplist = plistlib.dumps({
            "$objects": [
                "$null",
                {"NS.keys": [plistlib.UID(2)], "NS.objects": [plistlib.UID(3)]},
                "Expansion",
                "/wheel-check test payload",
            ]
        }, fmt=plistlib.FMT_BINARY)
        enc_bplist = typinator_cli.decode_typinator_archive(fake_bplist)
        self.assertEqual(typinator_cli.decode_x_payload(enc_bplist), "/wheel-check test payload")

        # 2. Legacy NSArchiver (streamtyped) payload with 1-byte length
        msg = b"Legacy expansion string"
        stream_raw = b"\x04\x0bstreamtyped\x00\x00Expansion\x86\x92\x84\x97\x98" + bytes([len(msg)]) + msg
        enc_stream = typinator_cli.decode_typinator_archive(stream_raw)
        self.assertEqual(typinator_cli.decode_x_payload(enc_stream), "Legacy expansion string")

    def test_time_machine_trace_diff_and_restore_rule_dry_run(self):
        import subprocess, json
        if not os.path.isdir(os.path.join(typinator_cli.DEFAULT_SYNC_REPO, ".git")):
            self.skipTest("typinator-sync repository not present on this runner")

        bin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "typinator"))

        # 1. Trace wc⇧ in AI prompt
        res_trace = subprocess.run(
            [bin_path, "trace", "wc⇧", "--set", "AI prompt", "-n", "3", "--json"],
            capture_output=True, text=True
        )
        self.assertEqual(res_trace.returncode, 0)
        trace_data = json.loads(res_trace.stdout)
        self.assertEqual(trace_data["abbreviation"], "wc⇧")
        self.assertIn("AI prompt", trace_data["sets"])
        self.assertGreaterEqual(len(trace_data["sets"]["AI prompt"]), 1)

        # 2. Diff 7532d3f vs 21ae618 for AI prompt
        res_diff = subprocess.run(
            [bin_path, "diff", "7532d3f", "21ae618", "--set", "AI prompt", "--json"],
            capture_output=True, text=True
        )
        self.assertEqual(res_diff.returncode, 0)
        diff_data = json.loads(res_diff.stdout)
        self.assertEqual(diff_data["total_changes"], 1)
        self.assertEqual(diff_data["changes"][0]["abbreviation"], "wc⇧")
        self.assertEqual(diff_data["changes"][0]["change"], "modified")

        # 3. Single-rule surgical restore dry-run
        res_rr = subprocess.run(
            [bin_path, "restore-rule", "7532d3f", "AI prompt", "wc⇧", "--dry-run", "--json"],
            capture_output=True, text=True
        )
        self.assertEqual(res_rr.returncode, 0)
        rr_data = json.loads(res_rr.stdout)
        self.assertEqual(rr_data["status"], "dry_run")
        self.assertEqual(rr_data["abbreviation"], "wc⇧")
        self.assertIn("/wheel-check", rr_data["restored_expansion"])


if __name__ == '__main__':
    unittest.main()
