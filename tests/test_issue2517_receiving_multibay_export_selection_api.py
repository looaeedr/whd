"""#2517 Receiving multi-Bay export source plan (real persisted Bay topology)."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from tests.test_issue1502_current_csv_multi_bay_once import _multi


def _flags(**changes):
    result = dict.fromkeys(("box_body", "head", "tail", "door", "base_plate",
                            "indicator_box", "indicator_door"), False)
    result.update(changes)
    return result


def test_two_real_bays_plan_keeps_actual_nfb_and_source():
    snapshot = _multi()
    unchanged = deepcopy(snapshot)
    plan = manufacturing_api.plan_receiving_multibay_export_source(
        snapshot, _flags(box_body=True, door=True, base_plate=True),
    )
    assert isinstance(plan, manufacturing_api.ReceivingMultiBayExportPlan)
    assert plan.use_multibay and plan.bay_count == 2
    assert not plan.independent_only
    assert plan.preview_layout_for_bay(0, 1) is None
    assert plan.layout == snapshot["receiving_layout"]
    assert snapshot == unchanged


def test_independent_head_tail_masks_only_one_detached_preview_bay():
    snapshot = _multi()
    unchanged = deepcopy(snapshot)
    plan = manufacturing_api.plan_receiving_multibay_export_source(
        snapshot, _flags(head=True, tail=True), "END_VS_MIDDLE",
    )
    assert plan.use_multibay and plan.independent_only
    first = plan.preview_layout_for_bay(0, 0)
    second = plan.preview_layout_for_bay(0, 1)
    assert first["sets"][0]["bays"][0]["nfb_config_submitted"] is False
    assert first["sets"][0]["bays"][1]["nfb_config_submitted"] is True
    assert second["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert second["sets"][0]["bays"][1]["nfb_config_submitted"] is False
    first["sets"][0]["bays"][0]["nfb_config"]["holes"].clear()
    assert snapshot == unchanged


@pytest.mark.parametrize("flags", [
    _flags(head=True, base_plate=True),
    _flags(door=True, box_body=True),
    _flags(head=True, indicator_box=True),
])
def test_nfb_dependent_selection_never_masks_original_source(flags):
    plan = manufacturing_api.plan_receiving_multibay_export_source(_multi(), flags)
    assert plan.use_multibay and not plan.independent_only
    assert plan.preview_layout_for_bay(0, 1) is None


def test_legacy_one_bay_and_grouped_one_bay_eligibility():
    snapshot = _multi()
    snapshot["receiving_layout"] = new_receiving_layout(
        width=snapshot["w"], height=snapshot["h"], depth=snapshot["d"],
    )
    single = manufacturing_api.plan_receiving_multibay_export_source(
        snapshot, _flags(head=True),
    )
    assert not single.use_multibay
    with pytest.raises(ValueError, match="NOT_ACTIVE"):
        single.preview_layout_for_bay(0, 0)
    group = manufacturing_api.plan_receiving_multibay_export_source(
        snapshot, _flags(head=True), "ALL",
    )
    assert group.use_multibay and group.bay_count == 1
    dependent = manufacturing_api.plan_receiving_multibay_export_source(
        snapshot, _flags(head=True, base_plate=True), "ALL",
    )
    assert dependent.use_multibay and dependent.bay_count == 1
    assert not dependent.independent_only
    assert dependent.preview_layout_for_bay(0, 0) is None
    # A dependent selection must retain the saved original NFB configuration.
    assert snapshot["receiving_layout"]["sets"][0]["bays"][0].get("nfb_config_submitted") is not True
    with pytest.raises(ValueError, match="未知"):
        manufacturing_api.plan_receiving_multibay_export_source(
            snapshot, _flags(head=True), "BAD",
        )


def test_family_mode_and_invalid_topology_do_not_enter_multibay():
    snapshot = _multi()
    for other in ({**snapshot, "model": "金庫型"},
                  {**snapshot, "active_mode": "quantity"}):
        assert not manufacturing_api.plan_receiving_multibay_export_source(
            other, _flags(head=True),
        ).use_multibay
    assert manufacturing_api.plan_receiving_multibay_export_source(
        {**snapshot, "model": "RECEIVING"}, _flags(head=True),
    ).use_multibay
    snapshot["receiving_layout"]["sets"][0]["bays"][1]["width"] = -1
    with pytest.raises(ValueError):
        manufacturing_api.plan_receiving_multibay_export_source(
            snapshot, _flags(head=True),
        )


def test_gui_no_longer_duplicates_multibay_policy():
    code = (Path(__file__).resolve().parents[1]
            / "gui_modules/project/export_actions.py").read_text(encoding="utf-8")
    assert "manufacturing_api.plan_receiving_multibay_export_source(" in code
    assert "source_plan.preview_layout_for_bay(" in code
    assert 'preview_bay["nfb_config_submitted"]' not in code
    assert "safe_single_bay_group" not in code
    assert "physical_count = sum(" not in code
    preview = (Path(__file__).resolve().parents[1]
               / "gui_modules/layout/left_panel.py").read_text(encoding="utf-8")
    assert "manufacturing_api.resolve_live_cabinet_family(snapshot)" in preview
    assert 'snapshot.get("model") not in {"受電箱", "RECEIVING"}' not in preview
