from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATOR = ROOT / "tools/knowledge_metadata_migrator.py"
MATRIX = ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json"
OVERLAY = ROOT / "docs/superpowers/verification/knowledge_authority_resolution_overlay_v1.json"


def _load_migrator():
    assert MIGRATOR.is_file(), "#251 requires tools/knowledge_metadata_migrator.py"
    spec = importlib.util.spec_from_file_location("knowledge_metadata_migrator_issue251", MIGRATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_effective_authority_builds_total_plan(tmp_path: Path) -> None:
    """The frozen T6 migration must stay total for its accepted 398-path snapshot.

    Post-T6 governed documents are validated by current strict/permanent governance and
    must not be backfilled into the frozen T1 matrix or #255 resolution overlay.
    """
    migrator = _load_migrator()
    from tools.knowledge_authority_overlay import merge_effective_authority

    effective = tuple(merge_effective_authority(MATRIX, OVERLAY))
    frozen_paths = tuple(sorted(str(row["path"]) for row in effective))
    assert len(frozen_paths) == 398

    snapshot = tmp_path / "frozen-t6-snapshot"
    for rel in frozen_paths:
        source = ROOT / rel
        assert source.is_file(), f"frozen T6 governed path disappeared: {rel}"
        target = snapshot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    plan = migrator.build_plan(snapshot, MATRIX, OVERLAY)
    assert len(plan) == 398
    assert len({operation.path for operation in plan}) == 398
    assert all(operation.role in {"CURRENT", "REFERENCE", "MIRROR", "HISTORICAL"} for operation in plan)
    assert all(operation.contract for operation in plan)


def test_apply_adds_v1_metadata_without_changing_non_mirror_body(tmp_path: Path) -> None:
    migrator = _load_migrator()
    source = tmp_path / "doc.md"
    body = "# Title\n\nbody stays byte-for-byte\n"
    source.write_text(body, encoding="utf-8")
    plan = (
        migrator.MigrationOperation(
            path="doc.md",
            role="REFERENCE",
            contract="doc-reference",
            canonical=None,
        ),
    )

    changed = migrator.apply_plan(tmp_path, plan)
    assert changed == ("doc.md",)
    text = source.read_text(encoding="utf-8")
    assert text.endswith(body)
    assert "whd_doc_role: REFERENCE" in text
    assert "whd_contract: doc-reference" in text
    assert "whd_canonical: null" in text
    assert "whd_schema: WHD_DOC_META_V1" in text


def test_apply_is_idempotent_on_second_execution(tmp_path: Path) -> None:
    migrator = _load_migrator()
    source = tmp_path / "doc.md"
    source.write_text("# Title\n", encoding="utf-8")
    plan = (
        migrator.MigrationOperation(
            path="doc.md",
            role="HISTORICAL",
            contract="history-provenance",
            canonical=None,
        ),
    )

    assert migrator.apply_plan(tmp_path, plan) == ("doc.md",)
    first = source.read_bytes()
    assert migrator.apply_plan(tmp_path, plan) == ()
    assert source.read_bytes() == first


def test_mirror_apply_writes_pointer_only_body(tmp_path: Path) -> None:
    migrator = _load_migrator()
    canonical = tmp_path / "canonical.md"
    canonical.write_text("# Canonical\n", encoding="utf-8")
    mirror = tmp_path / "mirror.md"
    mirror.write_text("# stale copied normative prose\n\nMUST NOT SURVIVE\n", encoding="utf-8")
    plan = (
        migrator.MigrationOperation(
            path="mirror.md",
            role="MIRROR",
            contract="mirror-contract",
            canonical="canonical.md",
        ),
    )

    assert migrator.apply_plan(tmp_path, plan) == ("mirror.md",)
    text = mirror.read_text(encoding="utf-8")
    assert "whd_doc_role: MIRROR" in text
    assert "whd_canonical: canonical.md" in text
    assert "MUST NOT SURVIVE" not in text
    body = text.split("\n---\n", 1)[1]
    nonempty = [line for line in body.splitlines() if line.strip()]
    assert 3 <= len(nonempty) <= 5
    assert "canonical.md" in body
    assert "不得新增或複製 normative 規則" in body
