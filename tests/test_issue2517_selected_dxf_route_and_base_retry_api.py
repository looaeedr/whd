"""#2517: original GUI DXF export route and Base fallback owned by Engine."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from gui_modules.project import export_actions as gui


def _flags(**changes):
    result = {"box_body": False, "door": False, "base_plate": False,
              "head": False, "tail": False, "indicator_box": False}
    result.update(changes)
    return result


_MISSING = (
    "canonical resolved export: "
    "RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING: base_plate"
)


def test_vault_grouped_route_preserves_original_guard_and_unselected_route():
    plan = manufacturing_api.plan_selected_resolved_export_route(
        {"model": "金庫型"}, _flags(door=True), "ALL",
    )
    assert isinstance(plan, manufacturing_api.SelectedResolvedExportRoute)
    assert plan.vault_composed
    assert dict(plan.legacy_guard_flags)["door"]
    ordinary = manufacturing_api.plan_selected_resolved_export_route(
        {"model": "金庫型"}, _flags(door=True),
    )
    assert not ordinary.vault_composed
    assert ordinary.legacy_guard_flags is not None


@pytest.mark.parametrize("flags", [
    _flags(box_body=True, door=True, base_plate=True),
    _flags(box_body=True),
])
def test_receiving_old_nfb_scene_guards_unselected_body_only(flags):
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    plan = manufacturing_api.plan_selected_resolved_export_route(snapshot, flags)
    assert not plan.vault_composed
    guarded = dict(plan.legacy_guard_flags)
    assert not guarded["box_body"]
    assert guarded["door"] == flags["door"]
    assert guarded["base_plate"] == flags["base_plate"]


def test_current_csv_receiving_uses_source_verified_selected_export():
    from tests.test_issue1502_single_button_full_csv_receiving_export import _prepare
    snapshot, _ = _prepare(False)
    assert snapshot.get("nfb_config_submitted") is True
    flags = _flags(box_body=True, door=True, base_plate=True)
    plan = manufacturing_api.plan_selected_resolved_export_route(snapshot, flags)
    assert not plan.vault_composed
    assert plan.legacy_guard_flags is None
    with pytest.raises(ValueError, match="QUANTITY_NOT_VERIFIED"):
        manufacturing_api.plan_selected_resolved_export_route(
            {**snapshot, "active_mode": "quantity"}, flags,
        )


def test_non_csv_non_auto_side_and_unrelated_selection_keep_legacy_gate():
    snapshot = {"model": "受電箱", "nfb_config_submitted": False}
    flags = _flags(head=True)
    plan = manufacturing_api.plan_selected_resolved_export_route(snapshot, flags)
    assert dict(plan.legacy_guard_flags) == flags
    committed = {"model": "受電箱", "nfb_config_submitted": True}
    plan = manufacturing_api.plan_selected_resolved_export_route(
        committed, flags,
    )
    assert dict(plan.legacy_guard_flags) == flags


@pytest.mark.parametrize("errors", [
    ["canonical resolved export: UNVERIFIED_NFB_HOLE"],
    [_MISSING, "canonical resolved export: UNVERIFIED_NFB_HOLE"],
    ["RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING: base_plate"],
    [],
])
def test_partial_retry_rejects_unrelated_or_nonexclusive_failures(errors):
    flags = _flags(head=True, base_plate=True)
    assert manufacturing_api.plan_unconfigured_receiving_base_export_retry(
        errors, flags,
    ) is None


def test_retry_requires_selected_base_and_preserves_only_other_intents():
    flags = _flags(head=True, tail=True, base_plate=True)
    original = dict(flags)
    retry = manufacturing_api.plan_unconfigured_receiving_base_export_retry(
        [_MISSING], flags,
    )
    assert dict(retry) == {**flags, "base_plate": False}
    assert flags == original
    assert manufacturing_api.plan_unconfigured_receiving_base_export_retry(
        [_MISSING], _flags(head=True),
    ) is None
    single = manufacturing_api.plan_unconfigured_receiving_base_export_retry(
        [_MISSING], _flags(base_plate=True),
    )
    assert single is not None and not any(dict(single).values())


def test_engine_requires_operator_mapping():
    with pytest.raises(TypeError, match="SNAPSHOT_REQUIRED"):
        manufacturing_api.plan_selected_resolved_export_route(None, _flags())
    with pytest.raises(TypeError, match="FLAGS_REQUIRED"):
        manufacturing_api.plan_unconfigured_receiving_base_export_retry(
            [_MISSING], (),
        )


def test_original_gui_route_has_no_manufacturing_policy_branches():
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/project/export_actions.py").read_text(encoding="utf-8")
    assert "manufacturing_api.plan_selected_resolved_export_route(" in source
    assert "manufacturing_api.plan_unconfigured_receiving_base_export_retry(" in source
    assert 'mode_source.get("model") == "金庫型"' not in source
    assert "EAR_SIDE_NORMAL_EXPORT_QUANTITY_NOT_VERIFIED" not in source
    assert "RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING" not in source
    assert "manufacturing_api.selected_export_manufacturing_policy(" not in source
