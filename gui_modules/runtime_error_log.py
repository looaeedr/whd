"""Best-effort durable runtime exception logging for the WHD desktop GUI.

The logger is deliberately off the normal render path. It performs file I/O only
when an exception is reported, so normal Tk/Matplotlib rendering stays unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import sys
import traceback
from typing import Mapping

SCHEMA = "WHD_RUNTIME_EXCEPTION_V1"
DEFAULT_FILENAME = "runtime_error.log"


def default_runtime_log_path() -> Path:
    if bool(getattr(sys, "frozen", False)):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parents[1]
    return root / "logs" / DEFAULT_FILENAME


def _safe_text(value: object) -> str:
    return str(value).replace("\r", "\\r").replace("\n", "\\n")


def write_runtime_exception(
    context: str,
    exc: BaseException,
    *,
    tb=None,
    log_path: str | os.PathLike[str] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> Path | None:
    """Append one traceback record and never raise while handling the exception."""
    prior = getattr(exc, "_whd_runtime_log_path", None)
    if prior:
        return Path(prior)

    path = Path(log_path) if log_path is not None else default_runtime_log_path()
    timestamp = datetime.now(timezone.utc).isoformat()
    trace = "".join(traceback.format_exception(type(exc), exc, tb or exc.__traceback__))
    lines = [
        f"[{timestamp}] {SCHEMA}",
        f"context={_safe_text(context)}",
        f"exception_type={type(exc).__name__}",
        f"exception_message={_safe_text(exc)}",
        f"python={_safe_text(sys.version.split()[0])}",
        f"executable={_safe_text(sys.executable)}",
        f"platform={_safe_text(platform.platform())}",
        f"cwd={_safe_text(os.getcwd())}",
    ]
    for key, value in sorted(dict(metadata or {}).items()):
        lines.append(f"{_safe_text(key)}={_safe_text(value)}")
    lines.extend(("traceback:", trace.rstrip(), f"END {SCHEMA}", ""))

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines))
        try:
            setattr(exc, "_whd_runtime_log_path", str(path))
        except Exception:
            pass
        return path
    except Exception:
        # Error reporting must never replace the original application exception.
        return None


def install_tk_exception_logging(
    root,
    *,
    log_path: str | os.PathLike[str] | None = None,
    metadata: Mapping[str, object] | None = None,
):
    """Install a Tk callback exception hook while preserving Tk's prior handler."""
    previous = getattr(root, "report_callback_exception", None)

    def report_callback_exception(exc_type, exc, tb):
        write_runtime_exception(
            "tk_callback",
            exc,
            tb=tb,
            log_path=log_path,
            metadata=metadata,
        )
        if callable(previous):
            try:
                previous(exc_type, exc, tb)
                return
            except Exception:
                pass
        traceback.print_exception(exc_type, exc, tb)

    root.report_callback_exception = report_callback_exception
    return Path(log_path) if log_path is not None else default_runtime_log_path()
