"""#2517 No fallback to AE factory size when operator physical fields are invalid."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_snapshot_projection as gui


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
@pytest.mark.parametrize("bad", ("", "invalid", 0, -1, True, None, float("inf"), float("nan")))
def test_bad_physical_source_never_uses_factory_dimension(field, bad):
    var = SimpleNamespace(get=lambda: bad)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_source_dimension(bad, field=field)
    with pytest.raises(ValueError, match="包外尺寸"):
        gui._read_snapshot_numeric_control(var, 999., physical_field=field)


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
def test_broken_tk_read_rejected_for_physical_fields_and_unrelated_ui_keeps_fallback(field):
    def broken():
        raise ValueError("unavailable")
    var = SimpleNamespace(get=broken)
    with pytest.raises(ValueError, match="禁止使用預設值"):
        gui._read_snapshot_numeric_control(var, 999., physical_field=field)
    assert gui._read_snapshot_numeric_control(var, 999.) == 999.0


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_engine_normalizes_physical_save_reload_snapshot_without_rounding(model):
    source = {"model": model, "w": "800.25", "h": 1600.125,
              "d": "350.5", "t": "2.25", "fw": "28.75"}
    old = deepcopy(source)
    normalized = api.normalize_operator_source_dimensions(source)
    assert normalized == {
        "w": 800.25, "h": 1600.125, "d": 350.5, "t": 2.25, "fw": 28.75
    }
    assert source == old
    for key, value in normalized.items():
        assert gui._read_snapshot_numeric_control(
            SimpleNamespace(get=lambda v=value: str(v)),
            -1, physical_field=key
        ) == value


def test_settings_overlay_must_be_revalidated_at_last_snapshot_readback():
    original = {"w": 800., "h": 1600., "d": 350., "t": 2., "fw": 25.}
    for field in original:
        altered = dict(original, **{field: "invalid"})
        with pytest.raises(ValueError, match="包外尺寸"):
            api.normalize_operator_source_dimensions(altered)


def test_gui_delegates_both_control_read_and_settings_overlay_to_public_engine():
    src = Path("gui_modules/application/fold_designer_snapshot_projection.py").read_text(encoding="utf-8")
    base = src.split("def _snapshot_base_state(", 1)[1].split(
        "def _snapshot_workspace_state(", 1
    )[0]
    helper = src.split("def _read_snapshot_numeric_control(", 1)[1].split(
        "def _snapshot_base_state(", 1
    )[0]
    assert "manufacturing_api.normalize_operator_source_dimension(" in helper
    assert "manufacturing_api.normalize_operator_source_dimensions(" in base
    for field in ("w", "h", "d", "t", "fw"):
        assert 'physical_field="' + field + '"' in base
    assert "settings.update({" in base
    engine = Path("ae_engine/operator_settings_transactions.py").read_text(encoding="utf-8")
    assert "from phase6_" not in engine and "from gui_modules" not in engine


def test_snapshot_default_projection_matches_current_engine_runtime_without_physical_size():
    from ae_engine import ae, project_operator_fold_designer_snapshot_numeric_defaults
    expected = {
        "zl1": ae.zl1_def, "zl2": ae.zl2_def,
        "zr2": ae.zr2_def, "zr1": ae.zr1_def,
        "yl1": ae.yl1_def, "yr1": ae.yr1_def,
        "ytop1": ae.ytop1_def, "ybottom1": ae.ybottom1_def,
        "door_gap_w": ae.door_gap_w_def, "door_gap_h": ae.door_gap_h_def,
        "door_fold_l": ae.door_fold_left_def,
        "door_fold_r": ae.door_fold_right_def,
        "door_fold_t": ae.door_fold_top_def,
        "door_fold_b": ae.door_fold_bottom_def,
        "base_plate_shrink_top": 0.0,
        "base_plate_shrink_bottom": 0.0,
        "base_plate_shrink_left": 0.0,
        "base_plate_shrink_right": 0.0,
        "base_plate_bend": 20.0,
        "indicator_box_fold": getattr(ae, "indicator_box_fold_def", 49.0),
        "indicator_door_fold": getattr(ae, "indicator_small_door_fold_def", 19.0),
    }
    got = api.project_operator_fold_designer_snapshot_numeric_defaults()
    assert got == {key: float(value) for key, value in expected.items()}
    assert project_operator_fold_designer_snapshot_numeric_defaults is (
        api.project_operator_fold_designer_snapshot_numeric_defaults)
    assert not any(key in got for key in ("w", "h", "d", "t", "fw"))
    got["zl1"] = -9876.0
    assert api.project_operator_fold_designer_snapshot_numeric_defaults()["zl1"] == float(ae.zl1_def)


def test_snapshot_default_projection_uses_dynamic_current_engine_values(monkeypatch):
    from ae_engine import ae
    old = ae.zl1_def
    monkeypatch.setattr(ae, "zl1_def", 19.375)
    assert api.project_operator_fold_designer_snapshot_numeric_defaults()["zl1"] == 19.375
    monkeypatch.setattr(ae, "zl1_def", float("nan"))
    with pytest.raises(ValueError, match="zl1 製造來源"):
        api.project_operator_fold_designer_snapshot_numeric_defaults()
    assert old != float("nan")


def test_gui_snapshot_has_no_private_engine_numeric_fallbacks():
    source = Path("gui_modules/application/fold_designer_snapshot_projection.py").read_text(encoding="utf-8")
    function = source.split("def _snapshot_base_state(", 1)[1].split(
        "def _snapshot_workspace_state(", 1,
    )[0]
    assert "manufacturing_api.project_operator_fold_designer_snapshot_numeric_defaults()" in function
    for attribute in (
        "ae.W", "ae.H", "ae.D", "ae.T", "ae.FW", "ae.zl1_def",
        "ae.zl2_def", "ae.zr1_def", "ae.zr2_def", "ae.yl1_def",
        "ae.ybottom1_def", "ae.door_gap_w_def", "ae.door_fold_left_def",
        "ae.indicator_box_fold_def", "ae.indicator_small_door_fold_def",
    ):
        assert attribute not in function
    assert 'defaults["indicator_box_fold"]' in function
    assert 'defaults["indicator_door_fold"]' in function
    assert 'number(self.w_var, physical_field="w")' in function
