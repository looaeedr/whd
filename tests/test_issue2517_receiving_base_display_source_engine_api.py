# -*- coding: utf-8 -*-
"""#2517 Receiving BasePlate display status owns no physical source rules in GUI."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_base_display_source import (
    ReceivingBasePlateDisplaySource,
)
from phase6_final_scene_view import receiving_base_source_display_warnings
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def test_legacy_vault_does_not_require_receiving_material():
    status = manufacturing_api.inspect_receiving_base_plate_display_source(
        {"model": "金庫型"}, "金庫型",
    )
    assert status == ReceivingBasePlateDisplaySource("NOT_APPLICABLE")
    assert not status.source_available
    assert receiving_base_source_display_warnings({"model": "金庫型"}, "金庫型") == ()


def test_unconfigured_receiving_keeps_warning_and_mfg_fail_closed():
    snapshot = {"model": "受電箱"}
    status = manufacturing_api.inspect_receiving_base_plate_display_source(
        snapshot, "受電箱",
    )
    assert status.status == "UNAVAILABLE"
    assert not status.source_available
    assert "尚未配置" in receiving_base_source_display_warnings(snapshot, "受電箱")[0]


def test_invalid_receiving_source_keeps_original_reason_and_no_material_guess():
    snapshot = {"model": "受電箱", "receiving_base_plate": {"pattern": "CENTER_DOUBLE_SIDE_FOLD"}}
    status = manufacturing_api.inspect_receiving_base_plate_display_source(
        snapshot, "受電箱",
    )
    assert status.status == "INVALID"
    assert status.reason.startswith("RECEIVING_BASE_PLATE_CONFIG_INCOMPLETE:")
    assert not status.source_available
    warning = receiving_base_source_display_warnings(snapshot, "受電箱")
    assert len(warning) == 1 and status.reason in warning[0]


def test_existing_committed_nfb_source_is_display_resolvable_without_mutation():
    snapshot = _assembled()
    before = deepcopy(snapshot)
    result = manufacturing_api.inspect_receiving_base_plate_display_source(snapshot, "受電箱")
    assert result == ReceivingBasePlateDisplaySource("RESOLVED_DISPLAY_ONLY")
    assert result.source_available
    assert receiving_base_source_display_warnings(snapshot, "受電箱") == ()
    assert snapshot == before


@pytest.mark.parametrize("state,expected", [
    ("INVALID", "來源驗證失敗"),
    ("UNAVAILABLE", "尚未配置"),
    ("RESOLVED_DISPLAY_ONLY", None),
    ("NOT_APPLICABLE", None),
])
def test_gui_warning_only_formats_engine_status(monkeypatch, state, expected):
    source = {"model": "受電箱"}
    calls = []
    def engine(snapshot, family):
        calls.append((snapshot, family))
        return ReceivingBasePlateDisplaySource(state, "SOURCE_ERROR")
    monkeypatch.setattr(manufacturing_api, "inspect_receiving_base_plate_display_source", engine)
    warnings = receiving_base_source_display_warnings(source, "受電箱")
    assert calls == [(source, "受電箱")]
    if expected is None:
        assert warnings == ()
    else:
        assert expected in warnings[0]
        if state == "INVALID":
            assert "SOURCE_ERROR" in warnings[0]
