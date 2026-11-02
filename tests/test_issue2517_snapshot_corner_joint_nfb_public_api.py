# -*- coding: utf-8 -*-
"""#2517 Fold Designer model/Joint and legacy NFB source preview public API."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.corner_type_ui import is_unknown_model
from ae_engine.sheetmetal_geometry import EDITABLE_CORNER_TYPE_IDS, CORNER_TYPE_LABELS
from ae_engine.receiving_nfb_2d_preview import (
    NfbDxfPreviewCache, Nfb2DViewport,
)
from gui_modules.application import fold_designer_snapshot_projection as projection
from gui_modules.application import receiving_nfb_source_preview as nfb_gui


@pytest.mark.parametrize("model", ("金庫型", "受電箱", "自訂", "未知類型"))
def test_engine_corner_catalog_matches_existing_model_and_corner_rules(model):
    models = ("金庫型", "受電箱", "自訂")
    catalog = api.project_operator_corner_selection_catalog(model, models)
    assert isinstance(catalog, api.OperatorCornerSelectionCatalog)
    assert catalog.editable is is_unknown_model(model)
    assert catalog.labels == tuple(
        (key.value, CORNER_TYPE_LABELS[key]) for key in EDITABLE_CORNER_TYPE_IDS
    )
    assert catalog.custom_model_name == "自訂"
    assert tuple(catalog.labels) == catalog.labels


def test_legacy_unknown_alias_is_preserved_as_existing_operator_label():
    result = api.project_operator_corner_selection_catalog(
        "未知類型", ("金庫型", "未知類型"),
    )
    assert result.editable and result.custom_model_name == "未知類型"
    assert api.project_operator_corner_selection_catalog("金庫型", ()).custom_model_name == "自訂"


@pytest.mark.parametrize("assembly_type", ("INSERT", "INSERT_OVERLAY"))
def test_engine_joint_migration_preserves_original_operator_inputs(assembly_type):
    prior = {"assembly_joint_schema_version": 0, "assembly_joints": []}
    before = deepcopy(prior)
    parts = ["box_body", "head", "tail", "door"]
    expected = migrate_legacy_snapshot_joints({
        **prior, "existing_parts": parts, "assembly_type": assembly_type,
    })
    result = api.project_operator_assembly_joint_snapshot(
        prior, existing_parts=parts, assembly_type=assembly_type,
    )
    assert result == expected
    assert prior == before
    assert result["assembly_joint_schema_version"] >= 1
    assert api.project_operator_assembly_joint_snapshot(
        result, existing_parts=parts, assembly_type=assembly_type,
    ) == result


def test_future_joint_schema_fails_closed_not_reinterpreted_by_gui():
    with pytest.raises(ValueError, match="unsupported assembly joint schema version"):
        api.project_operator_assembly_joint_snapshot(
            {"assembly_joint_schema_version": 999},
            existing_parts=("head", "tail"), assembly_type="INSERT",
        )


def test_fold_designer_snapshot_consumes_public_engine_catalog_and_joint_projection():
    base_source = inspect.getsource(projection._snapshot_base_state)
    workspace_source = inspect.getsource(projection._snapshot_workspace_state)
    assert "manufacturing_api.project_operator_corner_selection_catalog(" in base_source
    assert "manufacturing_api.project_operator_assembly_joint_snapshot(" in workspace_source
    assert "is_unknown_model(" not in base_source
    assert "EDITABLE_CORNER_TYPE_IDS" not in base_source
    assert "migrate_legacy_snapshot_joints(" not in workspace_source
    source = inspect.getsource(projection)
    assert "from ae_engine.corner_type_ui import" not in source
    assert "from ae_engine.assembly_joint import" not in source


def test_legacy_indexed_nfb_dxf_is_available_only_as_read_only_engine_preview():
    assert api.NfbDxfPreviewCache is NfbDxfPreviewCache
    assert api.Nfb2DViewport is Nfb2DViewport
    assert api.NfbDxfPreviewCache(max_entries=2).parse_count == 0
    assert api.Nfb2DViewport().preview is None
    source = inspect.getsource(nfb_gui)
    assert "from ae_engine.receiving_nfb_2d_preview import" not in source
    assert "manufacturing_api.NfbDxfPreviewCache()" in source
    assert "manufacturing_api.Nfb2DViewport()" in source
