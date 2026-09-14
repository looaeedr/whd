from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/knowledge_authority_overlay.py"
GOVERNANCE = ROOT / "tools/knowledge_governance.py"
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


def _load_governance():
    spec = importlib.util.spec_from_file_location("knowledge_governance_issue255", GOVERNANCE)
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
    governance = _load_governance()
    assert OVERLAY.is_file(), "#255 requires a reviewed T6 resolution overlay"
    rows = tool.merge_effective_authority(FROZEN, OVERLAY)
    effective = {row["path"]: row for row in rows}
    governed = set(tool.governed_paths(ROOT))

    # #255 completed a frozen 398-path T6 authority snapshot. Current repository
    # growth must not mutate that reviewed authority; post-T6 documents are owned
    # by current strict/permanent governance instead.
    assert len(effective) == len(rows) == 398
    assert set(effective) <= governed
    post_t6_paths = governed - set(effective)
    assert "個人AI檔案庫/踩坑庫/execution_claim_hard_gate_pitfall.md" in post_t6_paths
    assert governance.validate_strict(ROOT) == ()

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
