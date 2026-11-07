#!/usr/bin/env python3
"""
Quiet-launch contract (T-008).

Typinator 9.x opens its main window on every launch while its
"Open Window at Start" preference is on, no matter who launches it.
`open -g -j` does not prevent that; only the per-launch NSUserDefaults
override does. These tests pin that every launch the CLI performs carries the
override, and that the CLI never lets osascript launch the app implicitly.

All subprocess calls go through a recording fake, so the suite runs on the
Ubuntu CI runner as well as on a Mac.
"""

import os
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
import typinator_cli  # noqa: E402

QUIET_OVERRIDE = ["--args", "-Open Window at Start", "NO"]
SOURCE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "typinator_cli.py")
)


class FakeMac:
    """Records every subprocess.run argv and simulates the Typinator process."""

    def __init__(self, running: bool, pid: int = 4242, open_is_trap: bool = False):
        self.running = running
        self.pid = pid
        self.open_is_trap = open_is_trap
        self.calls = []

    def run(self, argv, *args, **kwargs):
        self.calls.append(list(argv))
        text = kwargs.get("text", False)

        def out(s: str):
            return s if text else s.encode()

        cmd = argv[0]
        if cmd == "pgrep":
            return SimpleNamespace(
                returncode=0 if self.running else 1,
                stdout=out(f"{self.pid}\n" if self.running else ""),
                stderr=out(""),
            )
        if cmd == "open":
            if self.open_is_trap:
                raise AssertionError(f"open must not be called while Typinator runs: {argv}")
            self.running = True
            return SimpleNamespace(returncode=0, stdout=out(""), stderr=out(""))
        if cmd == "osascript":
            script = argv[-1]
            if "to quit" in script:
                self.running = False
                return SimpleNamespace(returncode=0, stdout=out(""), stderr=out(""))
            return SimpleNamespace(returncode=0, stdout=out("OK"), stderr=out(""))
        if cmd == "kill":
            self.running = False
            return SimpleNamespace(returncode=0, stdout=out(""), stderr=out(""))
        raise AssertionError(f"unexpected subprocess call: {argv}")

    def opens(self):
        return [c for c in self.calls if c and c[0] == "open"]

    def index_of(self, cmd: str) -> int:
        for i, c in enumerate(self.calls):
            if c and c[0] == cmd:
                return i
        return -1


class QuietLaunchTests(unittest.TestCase):
    def setUp(self):
        self.app_dir = tempfile.mkdtemp(suffix=".app")
        patches = [
            mock.patch.object(typinator_cli, "TYPINATOR_APP_PATH", self.app_dir),
            mock.patch.object(typinator_cli.time, "sleep", lambda *_: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(os.rmdir, self.app_dir)

    def assert_quiet_open(self, argv):
        self.assertEqual(argv[0], "open")
        self.assertIn("-g", argv, "launch must not bring Typinator to the front")
        self.assertIn("-j", argv, "launch must start Typinator hidden")
        self.assertIn(self.app_dir, argv)
        self.assertEqual(
            argv[-len(QUIET_OVERRIDE):], QUIET_OVERRIDE,
            "launch must override 'Open Window at Start' for this launch only",
        )

    def test_quiet_launch_uses_background_hidden_and_window_override(self):
        fake = FakeMac(running=False)
        with mock.patch.object(typinator_cli.subprocess, "run", fake.run):
            pid = typinator_cli.launch_typinator_quietly(timeout_sec=1)
        self.assertEqual(pid, fake.pid)
        self.assertEqual(len(fake.opens()), 1)
        self.assert_quiet_open(fake.opens()[0])

    def test_quiet_launch_refuses_when_already_running(self):
        # `open` against a running app sends a reopen event, which shows the window.
        fake = FakeMac(running=True, open_is_trap=True)
        with mock.patch.object(typinator_cli.subprocess, "run", fake.run):
            pid = typinator_cli.launch_typinator_quietly(timeout_sec=1)
        self.assertEqual(pid, fake.pid)
        self.assertEqual(fake.opens(), [])

    def test_run_applescript_launches_quietly_before_osascript_when_quit(self):
        fake = FakeMac(running=False)
        with mock.patch.object(typinator_cli.subprocess, "run", fake.run):
            out = typinator_cli.run_applescript('tell application "Typinator" to return "OK"')
        self.assertEqual(out, "OK")
        self.assertEqual(len(fake.opens()), 1)
        self.assert_quiet_open(fake.opens()[0])
        self.assertLess(fake.index_of("open"), fake.index_of("osascript"),
                        "osascript must never be the thing that launches Typinator")

    def test_run_applescript_never_opens_when_running(self):
        fake = FakeMac(running=True, open_is_trap=True)
        with mock.patch.object(typinator_cli.subprocess, "run", fake.run):
            out = typinator_cli.run_applescript('tell application "Typinator" to return "OK"')
        self.assertEqual(out, "OK")
        self.assertEqual(fake.opens(), [])

    def test_restart_relaunches_quietly(self):
        fake = FakeMac(running=True, pid=111)
        status = {"status": "running", "total_rules": 1, "enabled_rule_sets": 1}
        with mock.patch.object(typinator_cli.subprocess, "run", fake.run), \
                mock.patch.object(typinator_cli, "get_status", return_value=status):
            res = typinator_cli.restart_typinator(timeout_sec=1)
        self.assertEqual(res["status"], "restarted")
        self.assertEqual(len(fake.opens()), 1)
        self.assert_quiet_open(fake.opens()[0])


class LaunchChokepointGuard(unittest.TestCase):
    def test_module_has_exactly_one_open_launch_site(self):
        with open(SOURCE_PATH, encoding="utf-8") as f:
            src = f.read()
        sites = re.findall(r'\[\s*"open"\s*,', src)
        print(f"\n[quiet-launch guard] graded {len(sites)} `open` argv literal(s) in typinator_cli.py")
        self.assertEqual(
            len(sites), 1,
            "every Typinator launch must go through launch_typinator_quietly()",
        )
        fn = re.search(r"def launch_typinator_quietly\(.*?(?=\ndef )", src, re.S)
        self.assertIsNotNone(fn, "launch_typinator_quietly() must exist")
        self.assertRegex(fn.group(0), r'\[\s*"open"\s*,', "the one launch site must live in the chokepoint")


if __name__ == "__main__":
    unittest.main()
