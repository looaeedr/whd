"""#2517 BoxBody D-W-D source selection is an Engine transaction, not GUI."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_box_body_dwd_sync as owner
import fold_designer_bridge as bridge


def _source(model="金庫型", **changes):
    return {
        "model": model, "w": 400.0, "h": 600.0, "d": 250.0,
        "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 15.0, "zr1": 15.0, "zr2": 15.0,
        **changes,
    }


def _profile(source=None):
    return api.build_box_body_fold_profile(source or _source())


def _outside(row):
    return float(row["len"]) + float(row.get("ui_len_add", 0.0))


def _plan(source=None, profile=None, *, w=400, d=250, last_w=400, last_d=250):
    return api.plan_operator_box_body_dwd_sync(
        source or _source(),
        _profile(source) if profile is None else profile,
        top_width=w, top_depth=d, previous_width=last_w,
        previous_depth=last_d,
    )


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw

    def set(self, value):
        self.raw = value


def test_engine_package_and_facade_expose_the_identical_transaction_owner():
    assert (api.plan_operator_box_body_dwd_sync
            is ae_engine.plan_operator_box_body_dwd_sync
            is owner.plan_operator_box_body_dwd_sync)
    assert (api.OperatorBoxBodyDwdSyncPlan
            is ae_engine.OperatorBoxBodyDwdSyncPlan
            is owner.OperatorBoxBodyDwdSyncPlan)
    assert "fold_designer_bridge" not in inspect.getsource(owner)


def test_top_whd_edit_has_priority_and_keeps_fractional_material_core():
    source = _source()
    original = _profile(source)
    before = deepcopy((source, original))
    plan = _plan(source, original, w="400.25", d="250.75")
    rows = list(plan.profile)
    assert plan.last_width == 400.25
    assert plan.last_depth == 250.75
    assert plan.display_width is None and plan.display_depth is None
    assert _outside(next(r for r in rows if r.get("core") == "W")) == pytest.approx(400.25)
    assert all(_outside(r) == pytest.approx(250.75)
               for r in rows if r.get("core") == "D")
    assert (source, original) == before
    rows[0]["len"] = 999
    assert original[0]["len"] != 999


def test_unchanged_fractional_top_is_not_replaced_by_rounded_fold_editor_row():
    source = _source(w=400.25, d=250.75)
    original = _profile(source)
    plan = _plan(source, original, w=400.25, d=250.75,
                 last_w=400.25, last_d=250.75)
    assert plan.last_width == pytest.approx(400.25)
    assert plan.last_depth == pytest.approx(250.75)
    assert plan.display_width is None and plan.display_depth is None
    rows = list(plan.profile)
    assert _outside(next(r for r in rows if r.get("core") == "W")) == pytest.approx(400.25)
    assert all(_outside(r) == pytest.approx(250.75)
               for r in rows if r.get("core") == "D")


def test_edited_one_depth_fold_core_is_mirrored_by_engine():
    source = _source()
    rows = _profile(source)
    next(r for r in rows if r.get("phase6_key") == "d_left")["len"] += 3.0
    original = deepcopy(rows)
    plan = _plan(source, rows)
    assert plan.last_depth == pytest.approx(253.0)
    assert plan.display_depth == pytest.approx(253.0)
    assert all(_outside(r) == pytest.approx(253.0)
               for r in plan.profile if r.get("core") == "D")
    assert rows == original


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING", "receiving"))
def test_receiving_set_bay_refresh_uses_saved_committed_dimensions(family):
    source = _source(family, w=820.25, d=360.75,
                     receiving_layout={"sets": [{"bays": []}]})
    rows = _profile(source)
    previous = deepcopy(rows)
    plan = _plan(source, rows, w="bad", d="bad", last_w=800, last_d=350)
    assert plan.replace_profile
    assert (plan.last_width, plan.last_depth) == (820.25, 360.75)
    assert plan.display_width is None and plan.display_depth is None
    assert rows == previous


def test_quantity_saved_common_box_has_priority_over_stale_snapshot_dimensions():
    source = _source(
        "受電箱", active_mode="quantity",
        receiving_quantity_box={"w": 830.125, "h": 1600, "d": 370.625},
    )
    before = deepcopy(source)
    plan = _plan(source, _profile(_source("受電箱")), w="bad", d="bad",
                 last_w=800, last_d=350)
    assert plan.replace_profile
    assert plan.last_width == 830.125 and plan.last_depth == 370.625
    assert all(_outside(r) == pytest.approx(370.625)
               for r in plan.profile if r.get("core") == "D")
    assert source == before


@pytest.mark.parametrize("bad", (True, False, None, 0, -1, "", "nan", "inf", "bad"))
def test_invalid_top_box_dimensions_reject_without_touching_fold_source(bad):
    rows = _profile()
    before = deepcopy(rows)
    with pytest.raises((ValueError, TypeError)):
        _plan(profile=rows, w=bad)
    assert rows == before


def test_late_invalid_second_d_core_fail_closed_without_partial_mutation():
    rows = _profile()
    d_rows = [r for r in rows if r.get("core") == "D"]
    d_rows[-1]["len"] = float("nan")
    before = deepcopy(rows)
    with pytest.raises((ValueError, TypeError)):
        _plan(profile=rows, w=410.25, d=255.5)
    assert repr(rows) == repr(before)


def test_legacy_manual_fold_conversion_keeps_its_default_whole_mm_contract():
    seg = {"len": 246, "ui_len_add": 4}
    assert api.box_body_ui_segment_length_to_material(seg, 250.75) == 247
    assert api.box_body_ui_segment_length_to_material(
        seg, 250.75, preserve_precision=True, field="d",
    ) == pytest.approx(246.75)


def test_live_gui_dwd_sync_calls_public_engine_only_and_preserves_list_identity():
    source = _source()
    rows = _profile(source)
    saved_list = rows
    app = SimpleNamespace(
        _phase6_input_snapshot=source,
        _phase6_last_w=400, _phase6_last_d=250,
        state=SimpleNamespace(profiles_vault={"箱身": rows}),
        v_w=Var("400.25"), v_d=Var("250.75"),
    )
    bridge.Phase6FoldDesignerApp._sync_dwd_with_top_whd(app)
    assert app.state.profiles_vault["箱身"] is saved_list
    assert app._phase6_last_w == 400.25
    assert app._phase6_last_d == 250.75
    assert _outside(next(r for r in rows if r.get("core") == "W")) == pytest.approx(400.25)
    source_text = inspect.getsource(bridge.Phase6FoldDesignerApp._sync_dwd_with_top_whd)
    assert "manufacturing_api.plan_operator_box_body_dwd_sync(" in source_text
    assert "original.get_int(" not in source_text
    assert "ui_segment_length_to_engine(" not in source_text


def test_invalid_live_gui_dwd_input_never_mutates_original_profiles():
    source = _source()
    rows = _profile(source)
    before = deepcopy(rows)
    app = SimpleNamespace(
        _phase6_input_snapshot=source, _phase6_last_w=400,
        _phase6_last_d=250,
        state=SimpleNamespace(profiles_vault={"箱身": rows}),
        v_w=Var(True), v_d=Var("250"),
    )
    with pytest.raises((ValueError, TypeError)):
        bridge.Phase6FoldDesignerApp._sync_dwd_with_top_whd(app)
    assert rows == before
    assert app._phase6_last_w == 400 and app._phase6_last_d == 250
