"""#2517: operator legacy defaults only in Engine; never GUI AE manufacturing."""
from __future__ import annotations

from copy import deepcopy
import inspect
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import ae, manufacturing_api as api
from gui_modules.application import fold_designer_manufacturing_projection as gui


_DEFAULTS = {
    "door": {"door_gap_w": ae.door_gap_w_def, "door_gap_h": ae.door_gap_h_def,
             "door_fold_l": ae.door_fold_left_def, "door_fold_r": ae.door_fold_right_def,
             "door_fold_t": ae.door_fold_top_def, "door_fold_b": ae.door_fold_bottom_def},
    "box_body": {"zl1": ae.zl1_def, "zl2": ae.zl2_def,
                 "zr1": ae.zr1_def, "zr2": ae.zr2_def,
                 "z_comp": getattr(ae, "z_comp_def", 0.0),
                 "head_ybottom1": ae.ybottom1_def, "tail_ybottom1": ae.ybottom1_def},
    "head": {"yl1": ae.yl1_def, "yr1": ae.yr1_def, "ytop1": ae.ytop1_def,
             "ybottom1": ae.ybottom1_def, "zl1": ae.zl1_def, "zr1": ae.zr1_def},
    "tail": {"yl1": ae.yl1_def, "yr1": ae.yr1_def, "ytop1": ae.ytop1_def,
             "ybottom1": ae.ybottom1_def, "zl1": ae.zl1_def, "zr1": ae.zr1_def},
    "indicator_door": {"door_gap_w": ae.door_gap_w_def,
                       "door_gap_h": ae.door_gap_h_def,
                       "indicator_door_fold": getattr(ae, "indicator_small_door_fold_def", 19.0)},
}


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("part", tuple(_DEFAULTS))
def test_engine_legacy_absent_only_source_matches_original_part_defaults(family, part):
    raw = {"model": family, "w": 800, "h": 1500, "d": 380, "t": 2, "fw": 29}
    prior = deepcopy(raw)
    expected = {k: float(v) for k, v in _DEFAULTS[part].items()}
    assert api.resolve_fold_designer_legacy_numeric_settings(
        raw, part_name=part,
    ) == expected
    assert raw == prior


@pytest.mark.parametrize("part,key", [
    ("door", "door_fold_l"), ("door", "door_gap_w"),
    ("box_body", "z_comp"), ("box_body", "zl1"),
    ("head", "ybottom1"), ("tail", "yr1"),
    ("indicator_door", "indicator_door_fold"),
])
@pytest.mark.parametrize("bad", (True, False, None, "", "broken",
                                  float("nan"), float("inf"), "-Infinity", 10**400))
def test_explicit_corrupt_legacy_numeric_source_must_fail_closed(part, key, bad):
    with pytest.raises(ValueError, match="製造來源"):
        api.resolve_fold_designer_legacy_numeric_settings(
            {key: bad}, part_name=part,
        )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_real_fractional_saved_fold_settings_and_side_override_are_exact(family):
    raw = {"model": family, "yl1": "17.25", "ybottom1": "16.75",
           "head_ybottom1": "-12.5", "door_gap_w": "3.625",
           "indicator_door_fold": "19.25"}
    assert api.resolve_fold_designer_legacy_numeric_settings(
        raw, part_name="head",
    )["ybottom1"] == 16.75
    body = api.resolve_fold_designer_legacy_numeric_settings(raw, part_name="box_body")
    assert body["head_ybottom1"] == -12.5
    assert body["tail_ybottom1"] == 16.75
    assert api.resolve_fold_designer_legacy_numeric_settings(
        raw, part_name="door",
    )["door_gap_w"] == 3.625
    assert api.resolve_fold_designer_legacy_numeric_settings(
        raw, part_name="indicator_door",
    )["indicator_door_fold"] == 19.25


def test_gui_door_part_spec_passes_identical_engine_owned_legacy_values():
    source = {"door_gap_w": "3.625", "door_fold_l": "14.25",
              "door_indicator_box_enabled": False}
    host = SimpleNamespace(_door_part_spec_from_values=lambda values, **kw: (
        values, kw
    ))
    values, kwargs = gui._door_part_spec_from_payload_context(
        host, source, 800, 1400, 2, 29, "金庫型", False, (), None, None,
    )
    expected = api.resolve_fold_designer_legacy_numeric_settings(
        source, part_name="door",
    )
    assert {k: values[k] for k in expected} == expected
    assert (values["w"], values["h"], values["t"], values["fw"]) == (800, 1400, 2, 29)
    assert kwargs["model_name"] == "金庫型"


def test_gui_door_explicit_corrupt_gap_fails_before_part_spec():
    calls = []
    host = SimpleNamespace(_door_part_spec_from_values=lambda *args, **kw:
                           calls.append((args, kw)))
    with pytest.raises(ValueError, match="door_gap_w 製造來源"):
        gui._door_part_spec_from_payload_context(
            host, {"door_gap_w": True, "door_indicator_box_enabled": False},
            800, 1400, 2, 29, "受電箱", False, (), None, None,
        )
    assert not calls


@pytest.mark.parametrize("field", ("d", "t"))
def test_old_nonmanufacturing_divider_frame_compatibility_default_is_engine_owned(field):
    assert api.fold_designer_legacy_source_default(field) == getattr(ae, field.upper())


def test_invalid_part_and_unknown_physical_default_are_rejected():
    with pytest.raises(ValueError):
        api.resolve_fold_designer_legacy_numeric_settings({}, part_name="unverified")
    with pytest.raises(ValueError):
        api.fold_designer_legacy_source_default("fw")


def test_gui_does_not_import_ae_defaults_or_cast_saved_fold_manufacturing_values():
    root = Path(__file__).resolve().parents[1]
    content = (root / "gui_modules/application/fold_designer_manufacturing_projection.py"
               ).read_text(encoding="utf-8")
    assert "import ae_engine.ae" not in content
    assert "ae." not in content
    assert "resolve_fold_designer_legacy_numeric_settings(" in content
    assert "fold_designer_legacy_source_default(" in content
    main = (root / "gui.py").read_text(encoding="utf-8")
    start = main.index("    def _phase6_resolved_finished_dimensions(")
    end = main.index("    def _draw_phase6_finished_dimension_summary(", start)
    section = main[start:end]
    assert section.count("normalize_operator_source_dimension(") == 2
    assert "ae.FW" not in section and "ae.T" not in section


@pytest.mark.parametrize("field,bad", [
    ("fw", None), ("fw", True), ("fw", float("nan")),
    ("t", None), ("t", False), ("t", float("inf")),
])
def test_main_gui_physical_source_rejects_missing_or_corrupt_before_finished_scene(field, bad):
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_source_dimension(bad, field=field)
