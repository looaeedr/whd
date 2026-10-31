"""#2517: Engine is sole EndCap X/Y material -> outside W/D/FW authority."""
from __future__ import annotations
import inspect
import pytest

from ae_engine import manufacturing_api, resolve_endcap_xy_outside_dimensions, fold_material_segment_outside_length
from phase6_fold_profiles import build_endcap_xy_profiles, read_endcap_xy_profiles, engine_segment_length_to_ui


@pytest.mark.parametrize("family,depth_t", [("受電箱", 2.0), ("金庫型", 3.0)])
@pytest.mark.parametrize("part_key", ["head", "tail"])
def test_headless_family_endcap_xy_roundtrip_no_depth_growth(family, depth_t, part_key):
    source = {"model": family, "w": 800, "h": 1600, "d": 350, "t": 2,
              "fw": 29, "yl1": 15, "yr1": 15, "ytop1": 16, "ybottom1": 15}
    rows = build_endcap_xy_profiles(source, part_key=part_key)
    core = next(r for r in rows["Y"] if r.get("phase6_key") == "endcap_d_core")
    assert core["len"] == 350 - depth_t * 2
    physical = resolve_endcap_xy_outside_dimensions(rows, source)
    assert physical == read_endcap_xy_profiles(rows, source)
    assert (physical["w"], physical["d"], physical["fw"]) == (800, 350, 29)
    assert resolve_endcap_xy_outside_dimensions is manufacturing_api.resolve_endcap_xy_outside_dimensions
    assert fold_material_segment_outside_length is manufacturing_api.fold_material_segment_outside_length
    assert fold_material_segment_outside_length(next(r for r in rows["Y"] if r.get("phase6_key") == "fw")) == engine_segment_length_to_ui(next(r for r in rows["Y"] if r.get("phase6_key") == "fw"))


def test_endcap_xy_missing_source_roles_rejected():
    with pytest.raises(ValueError, match="X/Y 折彎資料不完整"):
        resolve_endcap_xy_outside_dimensions({"X": [], "Y": []}, {"model": "受電箱", "t": 2})


def test_phase6_does_not_infer_endcap_outer_dimensions_or_compensation():
    source = inspect.getsource(read_endcap_xy_profiles)
    assert "manufacturing_api.resolve_endcap_xy_outside_dimensions(" in source
    assert "endcap_depth_comp_t(" not in source
    assert "4.0 * t" not in source
    assert "engine_segment_length_to_ui(" not in source
    assert "manufacturing_api.fold_material_segment_outside_length(" in inspect.getsource(engine_segment_length_to_ui)
