"""#2517 GUI baseline-model and AssemblyJoint source routes use public Engine APIs."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.corner_type_ui import is_unknown_model, normalize_custom_model_name
from gui_modules.application import cabinet_controller as gui

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("model", (
    "未知類型", " 自訂 ", "金庫型", "受電箱", "", None, "未識別模型",
))
def test_public_engine_baseline_model_routes_equal_existing_owner_without_mutation(model):
    source = {"model": model, "unchanged": {"part_features": [1, 2]}}
    before = deepcopy(source)
    assert api.operator_normalize_custom_model_name(model) == normalize_custom_model_name(model)
    assert api.is_unknown_operator_model(model) == is_unknown_model(model)
    assert source == before


@pytest.mark.parametrize("model,custom", (
    ("未知類型", True), (" 自訂 ", True), ("金庫型", False),
))
def test_real_main_gui_family_change_reads_public_model_classification(model, custom):
    host = SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: model),
        _current_cabinet_type_name=lambda: "金庫型",
        _active_cabinet_type="金庫型",
        _fold_designer_baseline_commit_guard=False,
        _derived_cache_owner=None,
        _cabinet_family_defaults={},
    )
    assert gui._apply_cabinet_family_for_current_model(host) is False
    assert host._active_cabinet_type == "金庫型"
    assert api.is_unknown_operator_model(api.operator_normalize_custom_model_name(model)) is custom


def test_public_joint_migration_matches_engine_owner_and_preserves_saved_input():
    source = {
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    }
    before = deepcopy(source)
    assert api.migrate_operator_assembly_joint_snapshot is migrate_legacy_snapshot_joints
    assert api.migrate_operator_assembly_joint_snapshot(source) == migrate_legacy_snapshot_joints(source)
    assert source == before
    invalid = {
        "assembly_joint_schema_version": 999,
        "assembly_type": "INSERT",
        "assembly_joints": [],
    }
    invalid_before = deepcopy(invalid)
    with pytest.raises(ValueError):
        api.migrate_operator_assembly_joint_snapshot(invalid)
    assert invalid == invalid_before


def test_cabinet_and_fold_designer_gui_use_public_seams_not_private_model_or_joint():
    cabinet_tree = ast.parse(
        (ROOT / "gui_modules/application/cabinet_controller.py").read_text(encoding="utf-8")
    )
    fold_tree = ast.parse(
        (ROOT / "gui_modules/application/fold_designer_adapter.py").read_text(encoding="utf-8")
    )
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.corner_type_ui"
        and any(alias.name in {"is_unknown_model", "normalize_custom_model_name"} for alias in node.names)
        for node in ast.walk(cabinet_tree)
    )
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.assembly_joint"
        and any(alias.name == "migrate_legacy_snapshot_joints" for alias in node.names)
        for node in ast.walk(fold_tree)
    )
    def calls(tree):
        return [
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "manufacturing_api"
        ]
    assert calls(cabinet_tree).count("operator_normalize_custom_model_name") == 1
    # Also checks the known-Vault baseline T preflight via the public Engine selector.
    assert calls(cabinet_tree).count("is_unknown_operator_model") == 7
    # Eligibility and migration now live together in the public Joint Engine owner.
    assert calls(fold_tree).count("migrate_operator_assembly_joint_snapshot") == 0
    assert calls(fold_tree).count("project_operator_user_assembly_joint_parts") == 1
