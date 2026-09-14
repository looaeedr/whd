from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/knowledge_authority_overlay.py"
FROZEN = ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json"
OVERLAY = ROOT / "docs/superpowers/verification/knowledge_authority_resolution_overlay_v1.json"
CONTRACT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _load_tool():
    assert TOOL.is_file(), "#255 requires tools/knowledge_authority_overlay.py"
    spec = importlib.util.spec_from_file_location("knowledge_authority_overlay_issue255", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_overlay_cannot_override_an_unblocked_frozen_t1_row(tmp_path: Path) -> None:
    tool = _load_tool()
    matrix = tmp_path / "matrix.json"
    overlay = tmp_path / "overlay.json"
    _write_json(
        matrix,
        {
            "schema": "WHD_KNOWLEDGE_CLASSIFICATION_V1",
            "rows": [
                {
                    "path": "doc.md",
                    "target_role": "REFERENCE",
                    "contract": "stable-reference",
                    "blocker": None,
                    "replacement": None,
                }
            ],
        },
    )
    _write_json(
        overlay,
        {
            "schema": "WHD_KNOWLEDGE_AUTHORITY_OVERLAY_V1",
            "rows": [
                {
                    "path": "doc.md",
                    "target_role": "HISTORICAL",
                    "contract": "different-contract",
                    "canonical": None,
                    "evidence": ["authority:test"],
                    "resolves": "blocked-t1-row",
                }
            ],
        },
    )
    with pytest.raises(tool.AuthorityOverlayError, match="unblocked|override"):
        tool.merge_effective_authority(matrix, overlay)


def test_resolution_row_requires_explicit_evidence(tmp_path: Path) -> None:
    tool = _load_tool()
    matrix = tmp_path / "matrix.json"
    overlay = tmp_path / "overlay.json"
    _write_json(
        matrix,
        {
            "schema": "WHD_KNOWLEDGE_CLASSIFICATION_V1",
            "rows": [
                {
                    "path": "doc.md",
                    "target_role": "UNRESOLVED",
                    "contract": None,
                    "blocker": "ROLE_REQUIRES_AUTHORITY_REVIEW",
                    "replacement": None,
                }
            ],
        },
    )
    _write_json(
        overlay,
        {
            "schema": "WHD_KNOWLEDGE_AUTHORITY_OVERLAY_V1",
            "rows": [
                {
                    "path": "doc.md",
                    "target_role": "REFERENCE",
                    "contract": "doc-reference",
                    "canonical": None,
                    "evidence": [],
                    "resolves": "blocked-t1-row",
                }
            ],
        },
    )
    with pytest.raises(tool.AuthorityOverlayError, match="evidence"):
        tool.merge_effective_authority(matrix, overlay)


def test_repository_effective_authority_is_total_and_unblocked() -> None:
    tool = _load_tool()
    assert OVERLAY.is_file(), "#255 requires a reviewed T6 resolution overlay"
    rows = tool.merge_effective_authority(FROZEN, OVERLAY)
    effective = {row["path"]: row for row in rows}
    governed = set(tool.governed_paths(ROOT))
    assert set(effective) == governed
    assert len(effective) == len(rows)
    for path, row in effective.items():
        assert row["target_role"] in {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"}, path
        assert row.get("blocker") in {None, ""}, path
        contract = row.get("contract")
        assert isinstance(contract, str) and CONTRACT_RE.fullmatch(contract), path
        if row["target_role"] == "MIRROR":
            canonical = row.get("replacement") or row.get("canonical")
            assert isinstance(canonical, str) and canonical, path
            assert (ROOT / canonical).is_file(), (path, canonical)


def test_frozen_t1_matrix_identity_is_pinned() -> None:
    import hashlib

    assert hashlib.sha1((b"blob " + str(FROZEN.stat().st_size).encode() + b"\0" + FROZEN.read_bytes())).hexdigest() == "d1afe3013d74010ee23660659cd4692fade4a815"
