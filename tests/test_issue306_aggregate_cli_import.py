from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_aggregate_cli_can_start_as_direct_repo_script() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/test_shard_aggregate.py", "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout
    assert "Aggregate WHD non-Xvfb shard results" in proc.stdout
