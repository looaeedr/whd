from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "phase6_bridge_anti_regrowth_guard.py"
BASELINE = ROOT / "docs" / "architecture" / "phase6_bridge_anti_regrowth_baseline.json"
C0 = ROOT / "docs" / "superpowers" / "checkpoints" / "issue532-c0-final-classification.json"


def test_c1_permanent_guard_assets_exist():
    assert GUARD.is_file(), "C1 RED: permanent anti-regrowth executable guard is missing"
    assert BASELINE.is_file(), "C1 RED: accepted architecture baseline manifest is missing"
    assert C0.is_file()


@pytest.mark.skipif(not GUARD.is_file() or not BASELINE.is_file(), reason="C1 RED assets not implemented yet")
def test_c1_guard_uses_c0_record_and_current_repository():
    proc = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--root",
            str(ROOT),
            "--baseline",
            str(BASELINE),
            "--c0-record",
            str(C0),
            "--json-out",
            str(ROOT / ".scratch" / "issue533-c1-guard.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PHASE6_BRIDGE_ANTI_REGROWTH_GREEN" in proc.stdout

    payload = json.loads(
        (ROOT / ".scratch" / "issue533-c1-guard.json").read_text(encoding="utf-8")
    )
    c0 = json.loads(C0.read_text(encoding="utf-8"))
    assert payload["accepted_final_loc"] == c0["quantitative_gate"]["final_bridge_loc"]
    assert payload["accepted_facade_count"] == c0["quantitative_gate"]["facade_count"]
    assert payload["bridge_loc_limit"] == min(
        c0["quantitative_gate"]["final_bridge_loc"] + 25,
        c0["quantitative_gate"]["effective_final_ceiling"],
    )
    assert payload["violations"] == []
