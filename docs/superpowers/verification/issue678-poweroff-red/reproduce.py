from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPROVED = HERE / "approved"
BASELINE = "87eb35b3f5ae5211673c941cb56c4c4343fa5405"

COPIES = {
    "test_requirement_red_v4.py": "test_whd_poweroff_requirement_red_v4.py",
    "run_requirement_red_v4.py": "run_whd_poweroff_red_matrix_v4.py",
    "test_behavioral_red_v5.py": "test_whd_poweroff_behavioral_red_v5.py",
    "run_behavioral_red_v5.py": "run_whd_poweroff_red_matrix_v5.py",
    "fake_always_safe_gate.py": "fake_token_only_poweroff_gate.py",
    "fake_always_not_safe_gate.py": "fake_always_not_safe_poweroff_gate.py",
}


def _repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    candidate = HERE.parents[3]
    if (candidate / ".git").exists() or (candidate / "tools").is_dir():
        return candidate
    p = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(p.stdout.strip()).resolve()


def _patch_test_root(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = 'ROOT = Path(r"Z:\\新WHD")'
    if old not in text:
        raise RuntimeError(f"approved probe root anchor missing in {path.name}")
    text = text.replace(old, 'ROOT = Path(os.environ["WHD_REPO_ROOT"])', 1)
    path.write_text(text, encoding="utf-8")


def _patch_runner_paths(path: Path, tmp: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = r"C:\Users\Public"
    if old not in text:
        raise RuntimeError(f"approved runner local path anchor missing in {path.name}")
    text = text.replace(old, str(tmp))
    path.write_text(text, encoding="utf-8")


def _run(path: Path, *, cwd: Path, env: dict[str, str]) -> None:
    p = subprocess.run(
        [sys.executable, str(path)],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    sys.stdout.write(p.stdout)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root")
    args = ap.parse_args()
    repo = _repo_root(args.repo_root)

    p = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{BASELINE}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        raise SystemExit(f"baseline commit unavailable: {BASELINE}")

    with tempfile.TemporaryDirectory(prefix="whd-issue678-red-") as td:
        tmp = Path(td)
        for source, target in COPIES.items():
            shutil.copy2(APPROVED / source, tmp / target)

        _patch_test_root(tmp / "test_whd_poweroff_requirement_red_v4.py")
        _patch_test_root(tmp / "test_whd_poweroff_behavioral_red_v5.py")
        _patch_runner_paths(tmp / "run_whd_poweroff_red_matrix_v4.py", tmp)
        _patch_runner_paths(tmp / "run_whd_poweroff_red_matrix_v5.py", tmp)

        env = dict(os.environ)
        env["WHD_REPO_ROOT"] = str(repo)
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

        _run(tmp / "run_whd_poweroff_red_matrix_v4.py", cwd=tmp, env=env)
        _run(tmp / "run_whd_poweroff_red_matrix_v5.py", cwd=tmp, env=env)

        v4 = json.loads((tmp / "whd_poweroff_requirement_red_v4_manifest.json").read_text(encoding="utf-8"))
        v5 = json.loads((tmp / "whd_poweroff_requirement_red_v5_manifest.json").read_text(encoding="utf-8"))

        checks = {
            "v4_all_current_cases_red": v4.get("all_current_cases_red") is True,
            "v4_all_current_expected_failures_observed": v4.get("all_current_expected_failures_observed") is True,
            "v4_anti_false_green_all_red": v4.get("anti_false_green_all_red") is True,
            "v4_anti_false_green_expected_failures_observed": v4.get("anti_false_green_expected_failures_observed") is True,
            "v5_all_current_behavioral_cases_red": v5.get("all_current_behavioral_cases_red") is True,
            "v5_all_current_expected_failures_observed": v5.get("all_current_expected_failures_observed") is True,
            "v5_all_adversarial_cases_red": v5.get("all_adversarial_cases_red") is True,
            "v5_all_adversarial_expected_failures_observed": v5.get("all_adversarial_expected_failures_observed") is True,
        }
        print(json.dumps({"baseline": BASELINE, "checks": checks}, indent=2))
        if not all(checks.values()):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
