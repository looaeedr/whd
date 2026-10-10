"""Regression: all operator-facing WHD time uses explicit Asia/Taipei."""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from tools.change_lane_gate import (
    ChangeLaneDenied,
    human_timestamp_taipei,
    require_new_code_taipei,
    require_taipei_timezone,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = "a" * 40
HEAD = "b" * 40


class TaiwanTimezoneHardGateTests(unittest.TestCase):
    def test_required_zone_and_explicit_offset(self):
        result = require_taipei_timezone({"TZ": "Asia/Taipei"})
        self.assertTrue(result.endswith("+08:00"), result)
        self.assertIn("T", result)

    def test_utc_host_or_missing_setting_is_denied(self):
        for env in ({}, {"TZ": "UTC"}, {"TZ": "Asia/Shanghai"}, {"TZ": ""}):
            with self.subTest(env=env):
                with self.assertRaisesRegex(ChangeLaneDenied, "TAIWAN_TIMEZONE_HARD_GATE_FAILED"):
                    require_taipei_timezone(env)

    def test_cross_midnight_utc_to_taipei_and_naive_denied(self):
        utc = datetime(2026, 10, 9, 17, 30, tzinfo=timezone.utc)
        self.assertEqual(
            human_timestamp_taipei(utc),
            "2026-10-10T01:30:00+08:00",
        )
        with self.assertRaisesRegex(ChangeLaneDenied, "NAIVE_TIMESTAMP"):
            human_timestamp_taipei(datetime(2026, 10, 9, 17, 30))

    def test_new_host_local_clock_calls_are_fail_closed(self):
        forbidden = (
            "from datetime import datetime\nvalue = datetime." + "now()\n",
            "from datetime import datetime\nvalue = datetime." + "today()\n",
            "from datetime import datetime\nvalue = datetime." + "utcnow()\n",
            "value = stamp." + "astimezone()\n",
            "value = time." + "localtime()\n",
        )
        for added in forbidden:
            patch_text = "diff --git a/owner.py b/owner.py\n+++ b/owner.py\n" + "".join(
                "+" + line + "\n" for line in added.splitlines()
            )
            with self.subTest(added=added), patch(
                "tools.change_lane_gate.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, patch_text.encode()),
            ):
                with self.assertRaisesRegex(ChangeLaneDenied, "HOST_LOCAL_CLOCK"):
                    require_new_code_taipei(ROOT, BASE, HEAD)

    def test_explicit_taipei_new_code_accepted(self):
        patch_text = (
            "diff --git a/owner.py b/owner.py\n+++ b/owner.py\n"
            "+from zoneinfo import ZoneInfo\n"
            "+value = datetime.now(ZoneInfo('Asia/Taipei'))\n"
            "+human = value.astimezone(ZoneInfo('Asia/Taipei'))\n"
        )
        with patch(
            "tools.change_lane_gate.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, patch_text.encode()),
        ):
            self.assertEqual(require_new_code_taipei(ROOT, BASE, HEAD), 3)

    def test_unreadable_diff_rejected(self):
        with patch("tools.change_lane_gate.subprocess.run", side_effect=OSError("offline")):
            with self.assertRaisesRegex(ChangeLaneDenied, "DIFF_UNREADABLE"):
                require_new_code_taipei(ROOT, BASE, HEAD)

    def test_governance_contract_and_ci_workflows_cannot_drift(self):
        contract = json.loads(
            (ROOT / ".agents/contracts/WHD_TAIPEI_TIMEZONE_HARD_GATE_V1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["timezone"], "Asia/Taipei")
        self.assertEqual(contract["utc_offset"], "+08:00")
        self.assertEqual(contract["status"], "ACTIVE")
        agent = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("TAIWAN_TIMEZONE_HARD_GATE_V1", agent)
        for path in (
            ".github/workflows/whd-change-lane-hard-gate.yml",
            ".github/workflows/whd-product-regression.yml",
            ".github/workflows/knowledge-governance-bootstrap.yml",
        ):
            with self.subTest(path=path):
                workflow = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("env:\n  TZ: Asia/Taipei\n", workflow)
        script = (ROOT / "tools/change_lane_gate.py").read_text(encoding="utf-8")
        self.assertIn("require_taipei_timezone()", script)
        self.assertIn("require_new_code_taipei(", script)


if __name__ == "__main__":
    unittest.main()
