from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATOR = ROOT / "tools/knowledge_metadata_migrator.py"
MATRIX = ROOT / "docs/superpowers/verification/knowledge_authority_classification_v1.json"


def _load_migrator():
    assert MIGRATOR.is_file(), "#251 requires tools/knowledge_metadata_migrator.py"
    spec = importlib.util.spec_from_file_location("knowledge_metadata_migrator_issue251", MIGRATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_matrix(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"schema": "WHD_KNOWLEDGE_CLASSIFICATION_V1", "rows": rows}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_plan_fails_closed_before_mutation_on_unresolved_or_blocked_mapping(tmp_path: Path) -> None:
    migrator = _load_migrator()
    doc = tmp_path / "doc.md"
    original = "# untouched\n"
    doc.write_text(original, encoding="utf-8")
    matrix = tmp_path / "matrix.json"
    _write_matrix(
        matrix,
        [{"path": "doc.md", "target_role": "UNRESOLVED", "contract": None, "blocker": "ROLE_REQUIRES_AUTHORITY_REVIEW"}],
    )

    with pytest.raises(migrator.MigrationPlanError, match="UNRESOLVED|ROLE_REQUIRES_AUTHORITY_REVIEW"):
        migrator.build_plan(tmp_path, matrix)
    assert doc.read_text(encoding="utf-8") == original


def test_plan_fails_closed_when_current_scope_is_missing_from_matrix(tmp_path: Path) -> None:
    migrator = _load_migrator()
    (tmp_path / "doc.md").write_text("# governed\n", encoding="utf-8")
    matrix = tmp_path / "matrix.json"
    _write_matrix(matrix, [])

    with pytest.raises(migrator.MigrationPlanError, match="missing mapping"):
        migrator.build_plan(tmp_path, matrix)


def test_plan_fails_closed_on_duplicate_path_mapping(tmp_path: Path) -> None:
    migrator = _load_migrator()
    (tmp_path / "doc.md").write_text("# governed\n", encoding="utf-8")
    matrix = tmp_path / "matrix.json"
    row = {"path": "doc.md", "target_role": "REFERENCE", "contract": "doc-reference", "blocker": None}
    _write_matrix(matrix, [row, dict(row)])

    with pytest.raises(migrator.MigrationPlanError, match="duplicate mapping"):
        migrator.build_plan(tmp_path, matrix)


def test_repository_matrix_is_not_silently_migratable_while_authority_is_incomplete() -> None:
    migrator = _load_migrator()
    with pytest.raises(migrator.MigrationPlanError) as excinfo:
        migrator.build_plan(ROOT, MATRIX)
    message = str(excinfo.value)
    assert "UNRESOLVED" in message or "missing mapping" in message or "MISSING_STABLE_CONTRACT" in message
