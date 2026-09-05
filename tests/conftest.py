"""Phase6 pytest bootstrap and display-policy guardrails."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tkinter as tk

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
root = str(PROJECT_ROOT)
if root not in sys.path:
    sys.path.insert(0, root)

_TK_DISPLAY_ERROR_FRAGMENTS = (
    "no display name and no $DISPLAY environment variable",
    "couldn't connect to display",
)
_TK_DISPLAY_SKIP_REASON = "requires Tk display (DISPLAY is unset)"


def _is_missing_display_tcl_error(exc: BaseException) -> bool:
    """Return True only for Tcl errors caused by an unavailable GUI display."""
    if not isinstance(exc, tk.TclError):
        return False
    message = str(exc).lower()
    return any(fragment.lower() in message for fragment in _TK_DISPLAY_ERROR_FRAGMENTS)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_tk_display: test requires a real Tk display; skipped only when DISPLAY is absent",
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Explicit GUI tests skip before their body in a truly headless process."""
    if os.environ.get("DISPLAY"):
        return
    if item.get_closest_marker("requires_tk_display") is not None:
        pytest.skip(_TK_DISPLAY_SKIP_REASON)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    """Convert only missing-DISPLAY Tk failures from legacy unmarked tests into skips.

    This is a compatibility net while old GUI tests are migrated to
    ``@pytest.mark.requires_tk_display``.  It intentionally does not hide other
    TclError failures, and it is inactive whenever DISPLAY is present (including
    Xvfb), so GUI regressions still fail in the release gate.
    """
    outcome = yield
    report = outcome.get_result()
    if os.environ.get("DISPLAY") or call.excinfo is None:
        return
    if not _is_missing_display_tcl_error(call.excinfo.value):
        return

    report.outcome = "skipped"
    report.longrepr = (
        str(getattr(item, "path", getattr(item, "fspath", ""))),
        report.location[1],
        f"Skipped: {_TK_DISPLAY_SKIP_REASON}",
    )
