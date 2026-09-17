"""Fail-closed helpers for deciding whether a test scope may use pytest-xdist.

This module does not declare repository lanes safe by itself. Static audit can only
identify risk or produce an xdist candidate; promotion to XDIST_SAFE additionally
requires repeat-run evidence with stable nodes/results and clean protected state.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Set

SERIAL_ONLY = "SERIAL_ONLY"
XDIST_CANDIDATE = "XDIST_CANDIDATE"
XDIST_SAFE = "XDIST_SAFE"

_RISK_FLAGS = {
    "CONFIG_INI_WRITE",
    "DXF_WRITE",
    "FIXED_PATH",
    "GLOBAL_MUTATION",
    "ENV_MUTATION",
    "TK_ROOT",
}


def audit_source_text(text: str) -> Set[str]:
    """Return conservative shared-state risk markers found in Python source text."""
    source = str(text)
    risks: set[str] = set()

    # Direct writes to protected config or DXF inputs are never worker-safe.
    if re.search(
        r"open\s*\([^\n)]*config\.ini[^\n)]*,\s*['\"][^'\"]*[wax+][^'\"]*['\"]",
        source,
        re.IGNORECASE,
    ) or re.search(
        r"(?:Path\s*\([^\n)]*config\.ini[^\n)]*\)|[^\s]+config\.ini[^\s]*)\s*\.\s*write_(?:text|bytes)\s*\(",
        source,
        re.IGNORECASE,
    ):
        risks.add("CONFIG_INI_WRITE")

    if re.search(
        r"open\s*\([^\n)]*\.dxf[^\n)]*,\s*['\"][^'\"]*[wax+][^'\"]*['\"]",
        source,
        re.IGNORECASE,
    ) or re.search(
        r"(?:Path\s*\([^\n)]*\.dxf[^\n)]*\)|[^\s]+\.dxf[^\s]*)\s*\.\s*write_(?:text|bytes)\s*\(",
        source,
        re.IGNORECASE,
    ):
        risks.add("DXF_WRITE")

    # A literal absolute temp/work path is shared across workers unless rewritten
    # under a worker-local root. Detect POSIX and drive-letter forms conservatively.
    if re.search(r"['\"]/(?:tmp|var/tmp|private/tmp)/[^'\"]+['\"]", source) or re.search(
        r"['\"][A-Za-z]:[\\/][^'\"]+['\"]", source
    ):
        risks.add("FIXED_PATH")

    # monkeypatch.setenv is fixture-scoped and intentionally excluded.
    if re.search(r"\bos\.environ\s*\[[^\]]+\]\s*=", source) or re.search(
        r"\bos\.putenv\s*\(", source
    ):
        risks.add("ENV_MUTATION")

    if re.search(r"\b(?:tkinter|tk)\.Tk\s*\(", source) or re.search(r"\bTk\s*\(", source):
        risks.add("TK_ROOT")

    # Explicit global mutation is a fail-closed signal for in-process workers.
    if re.search(r"(?m)^\s*global\s+[A-Za-z_]\w*", source):
        risks.add("GLOBAL_MUTATION")

    return risks


def classify_scope(
    *,
    lane: str,
    risk_flags: set[str] | frozenset[str],
    proof: Mapping[str, object],
    gui: bool = False,
) -> str:
    """Classify a scope without ever inferring safety from static cleanliness alone."""
    risks = set(risk_flags)
    unknown = risks - _RISK_FLAGS
    if unknown:
        # Unknown risk evidence is not something the optimizer may ignore.
        return SERIAL_ONLY

    lane_name = str(lane).lower()
    if gui or lane_name in {"xvfb", "xvfb_ui", "gui", "tk", "ui_xvfb"}:
        return SERIAL_ONLY
    if risks:
        return SERIAL_ONLY
    if bool(proof.get("cross_worker_leakage")):
        return SERIAL_ONLY

    repeat_runs = int(proof.get("repeat_runs", 0) or 0)
    repeat_proven = (
        repeat_runs >= 2
        and proof.get("stable_nodes") is True
        and proof.get("stable_results") is True
        and proof.get("protected_invariants") is True
        and proof.get("cross_worker_leakage") is False
    )
    return XDIST_SAFE if repeat_proven else XDIST_CANDIDATE


def worker_count_for(classification: str, requested: int | str) -> int:
    """Return an explicit conservative worker count; global/implicit auto is forbidden."""
    if isinstance(requested, str):
        if requested.strip().lower() == "auto":
            raise ValueError("xdist worker count 'auto' is forbidden")
        try:
            requested = int(requested)
        except ValueError as exc:
            raise ValueError("xdist worker count must be an explicit integer, not auto") from exc

    if classification != XDIST_SAFE:
        return 1
    value = int(requested)
    if value < 1:
        raise ValueError("xdist worker count must be >= 1")
    return min(value, 2)


def worker_local_root(base: str | Path, worker_id: str) -> Path:
    """Return a worker-specific child path while rejecting traversal/absolute ids."""
    base_path = Path(base)
    worker = str(worker_id)
    if not re.fullmatch(r"(?:gw\d+|master)", worker):
        raise ValueError(f"invalid xdist worker id: {worker!r}")
    return base_path / worker
