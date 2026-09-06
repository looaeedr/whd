from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFTEST = PROJECT_ROOT / "tests" / "conftest.py"


def _run_nested_pytest(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    target_dir = PROJECT_ROOT / "tmp" / "headless_policy" / tmp_path.name
    nested = target_dir / "nested"
    nested.mkdir(parents=True, exist_ok=True)
    try:
        # Execute the real project conftest as the nested pytest plugin so this
        # test verifies the actual repository policy rather than a copy.
        (nested / "conftest.py").write_text(
            "from pathlib import Path\n"
            f"_p = Path({str(PROJECT_CONFTEST)!r})\n"
            "exec(compile(_p.read_text(encoding='utf-8'), str(_p), 'exec'), globals())\n",
            encoding="utf-8",
        )
        (nested / "test_sample.py").write_text(source, encoding="utf-8")
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-rs", str(nested)],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
            check=False,
        )
    finally:
        shutil.rmtree(target_dir, ignore_errors=True)



def test_requires_tk_display_marker_skips_before_gui_body_without_display(tmp_path: Path) -> None:
    result = _run_nested_pytest(
        tmp_path,
        """
import pytest

@pytest.mark.requires_tk_display
def test_gui_body_must_not_run():
    raise RuntimeError('GUI body executed without DISPLAY')
""",
    )
    assert result.returncode == 0, result.stdout
    assert "1 skipped" in result.stdout
    assert "requires Tk display" in result.stdout or "需要 Tk 顯示環境" in result.stdout


def test_unmarked_legacy_tk_missing_display_error_is_reported_as_skip(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("Windows Tkinter does not use $DISPLAY environment variable")
    result = _run_nested_pytest(
        tmp_path,
        """
import tkinter as tk

def test_legacy_gui_without_marker():
    root = tk.Tk()
    root.destroy()
""",
    )
    assert result.returncode == 0, result.stdout
    assert "1 skipped" in result.stdout



def test_non_display_tcl_error_is_not_hidden_by_headless_policy(tmp_path: Path) -> None:
    result = _run_nested_pytest(
        tmp_path,
        """
import tkinter as tk

def test_real_tcl_bug():
    raise tk.TclError('bad option - this is not a DISPLAY problem')
""",
    )
    assert result.returncode != 0, result.stdout
    assert "1 failed" in result.stdout
    assert "bad option - this is not a DISPLAY problem" in result.stdout
