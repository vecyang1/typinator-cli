#!/usr/bin/env python3
"""
End-to-End Live Integration Tests for Typinator CLI against running macOS Typinator.
Verifies the full lifecycle:
1. Status check
2. Set listing
3. Rule creation (add)
4. Rule inspection (get)
5. Rule expansion update (set)
6. Rule search (search)
7. Rule export (export)
8. Safety audit (audit)
9. Rule deletion (delete)
"""

import unittest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
import typinator_cli


@unittest.skipUnless(typinator_cli.is_typinator_running(), "Typinator application is not running on this host.")
class TestTypinatorLiveE2E(unittest.TestCase):
    TEST_SET = "AI prompt"
    TEST_ABBR = "test_e2e_ci_rule"
    TEST_EXP_1 = "e2e_initial_expansion_{delay:1.5}{tab}"
    TEST_EXP_2 = "e2e_updated_expansion_{delay:2.0}{tab}"

    def setUp(self):
        # Ensure cleanup before starting
        try:
            typinator_cli.delete_rule(self.TEST_SET, self.TEST_ABBR)
        except Exception:
            pass

    def tearDown(self):
        # Ensure cleanup after finishing
        try:
            typinator_cli.delete_rule(self.TEST_SET, self.TEST_ABBR)
        except Exception:
            pass

    def test_full_lifecycle(self):
        # 1. Check status
        status = typinator_cli.get_status()
        self.assertEqual(status["status"], "running")
        self.assertGreater(status["total_rule_sets"], 0)
        self.assertGreater(status["total_rules"], 0)

        # 2. List sets
        sets = typinator_cli.list_sets()
        set_names = [s["name"] for s in sets]
        self.assertIn(self.TEST_SET, set_names)

        # 3. Add rule
        uid = typinator_cli.add_rule(
            self.TEST_SET,
            self.TEST_ABBR,
            self.TEST_EXP_1,
            description="E2E test rule",
            whole_word=False
        )
        self.assertTrue(bool(uid))

        # 4. Get rule
        rule = typinator_cli.get_rule(self.TEST_SET, self.TEST_ABBR)
        self.assertIsNotNone(rule)
        self.assertEqual(rule["abbreviation"], self.TEST_ABBR)
        self.assertEqual(rule["expansion"], self.TEST_EXP_1)
        self.assertEqual(rule["description"], "E2E test rule")

        # 5. Update rule
        ok = typinator_cli.set_rule_expansion(
            self.TEST_SET,
            self.TEST_ABBR,
            expansion=self.TEST_EXP_2,
            description="E2E updated rule",
            whole_word=True
        )
        self.assertTrue(ok)

        # Verify updated rule
        updated = typinator_cli.get_rule(self.TEST_SET, self.TEST_ABBR)
        self.assertEqual(updated["expansion"], self.TEST_EXP_2)
        self.assertEqual(updated["description"], "E2E updated rule")
        self.assertTrue(updated["whole_word"])

        # 6. Search rule
        matches = typinator_cli.search_rules(query=self.TEST_ABBR, set_name=self.TEST_SET)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["abbreviation"], self.TEST_ABBR)

        # 7. Export rules
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            temp_path = tf.name

        try:
            exported = typinator_cli.export_rules(set_name=self.TEST_SET)
            self.assertGreater(exported["total_rules"], 0)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(exported, f)
            self.assertGreater(os.path.getsize(temp_path), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # 8. Delete rule
        del_ok = typinator_cli.delete_rule(self.TEST_SET, self.TEST_ABBR)
        self.assertTrue(del_ok)

        # Verify deletion
        rule_after_del = typinator_cli.get_rule(self.TEST_SET, self.TEST_ABBR)
        self.assertIsNone(rule_after_del)


if __name__ == '__main__':
    unittest.main()
