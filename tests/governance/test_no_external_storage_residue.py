from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".yml", ".yaml", ".py", ".toml",
    ".cfg", ".ini", ".csv", ".sh", ".ps1", ".bat",
}

# Keep the retired provider name out of CURRENT source while still detecting it.
PROVIDER_WORD = "Dri" + "ve"
PROHIBITED = (
    re.compile("Google" + r"\s+" + PROVIDER_WORD, re.IGNORECASE),
    re.compile("external" + "-g" + "drive", re.IGNORECASE),
    re.compile("1z-P-" + "VXPd1xjK-PS3Jj7RreT2BLEmDvf_"),
    re.compile("雲端" + "硬碟"),
    re.compile(
        r"\b" + PROVIDER_WORD
        + r"(?:/|-|\s+)(?:shared|first|snapshot|mount|skill|connector|id|root|payload|parity|search|v\d|退役)",
        re.IGNORECASE,
    ),
)


def _tracked_text_files() -> list[Path]:
    raw = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
    ).decode("utf-8")
    paths: list[Path] = []
    for rel in raw.split("\0"):
        if not rel:
            continue
        path = ROOT / rel
        if path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return paths


def test_current_tree_has_no_retired_external_storage_residue():
    hits: list[str] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in PROHIBITED):
                hits.append(f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}")
    assert not hits, "retired external-storage residue remains:\n" + "\n".join(hits)
