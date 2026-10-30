# -*- coding: utf-8 -*-
"""#1502: 2D FinalScene side BEND stations MUST become true 3D fold profiles."""
import pytest

from ae_engine.assembly_geometry_folded_mesh import _profile_geometry
from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions
from phase6_fold_profiles import apply_outside_dimension_compensation, engine_segment_length_to_ui
from phase6_settings_profile_projection import build_standard_part_profiles


def _snap(pattern="CENTER_DOUBLE_SIDE_FOLD"):
    return {
        "model":"受電箱", "w":800., "h":1600., "d":350., "t":2.,
        "receiving_base_plate":{
            "pattern":pattern, "height":350.,
            "shrink_top":55., "shrink_bottom":55.,
            "shrink_left":85. if pattern=="CENTER_DOUBLE_SIDE_FOLD" else 45.,
            "shrink_right":85. if pattern=="CENTER_DOUBLE_SIDE_FOLD" else 45.,
            "bend":20.,
        },
    }


def test_real_center_3d_fold_has_all_original_source_40_73_699_732_bend_stations():
    snap=_snap()
    assert receiving_base_plate_blank_dimensions(snap)==(772.,240.)
    profiles=build_standard_part_profiles(snap,"base_plate")
    x=profiles["X"]
    assert [row["len"] for row in x] == [40.,33.,626.,33.,40.]
    assert [row.get("angle") for row in x]==[90,-90,-90,90,None]
    assert [row.get("core") for row in x]==[None,None,"W",None,None]
    xbound, folded=_profile_geometry(x)
    assert xbound == pytest.approx((0,40,73,699,732,772))
    # User-mandated true second return 33, not the old fake 31.
    assert xbound[2]-xbound[1] == 33
    assert xbound[4]-xbound[3] == 33
    # 33 mm in the original DXF is only the UNFOLDED material segment.
    # After formation the two parallel front NFB physical mounting surfaces
    # are 35 mm apart (107-72), preserving the same T2 skin offset.
    assert x[1]["formed_length"] == pytest.approx(35)
    assert x[3]["formed_length"] == pytest.approx(35)
    assert abs(folded[2][1]-folded[1][1]) == pytest.approx(35)
    assert abs((folded[2][1]+1)-(folded[1][1]+1)) == pytest.approx(35)
    y=profiles["Y"]
    assert [row["len"] for row in y] == [35.,170.,35.]
    ybounds,_=_profile_geometry(y)
    assert ybounds == pytest.approx((0,35,205,240))
    # User-confirmed CENTER equality is in operator OUTSIDE dimension space.
    # X second 33 material+2T = Y upper/lower 35 material+1T = 37 outside.
    x_ui=apply_outside_dimension_compensation([dict(row) for row in x],2.)
    y_ui=apply_outside_dimension_compensation([dict(row) for row in y],2.)
    assert [engine_segment_length_to_ui(x_ui[i]) for i in (1,3)] == [37,37]
    assert [engine_segment_length_to_ui(y_ui[i]) for i in (0,2)] == [37,37]


@pytest.mark.parametrize("pattern",["LEFT_FLAT_SIDE","RIGHT_FLAT_SIDE"])
def test_real_flat_sided_3d_has_zero_x_folds_and_only_top_bottom_20(pattern):
    snap=_snap(pattern)
    profiles=build_standard_part_profiles(snap,"base_plate")
    assert len(profiles["X"]) == 1
    assert profiles["X"][0]["len"] == 710.
    assert profiles["X"][0].get("angle") is None
    assert [row["len"] for row in profiles["Y"]] == [20.,200.,20.]


def test_original_unconfigured_preview_or_other_family_does_not_take_receiving_profile():
    snap=_snap()
    snap.pop("receiving_base_plate")
    fallback=build_standard_part_profiles(snap,"base_plate")
    assert len(fallback["X"]) == 3
    snap=_snap()
    snap["model"]="金庫型"
    shared=build_standard_part_profiles(snap,"base_plate")
    assert len(shared["X"]) == 3


def test_rendered_3d_profile_tracks_a_nonhardcoded_nfb_second_return(monkeypatch):
    # The same snapshot authority controls BOTH actual base blank and live
    # profile; avoid an independent 3D 33-mm constant.
    import phase6_settings_profile_projection as projection
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    snap=_snap()
    real=receiving_base_plate_values
    def changed_current_nfb_pair(data):
        d=real(data)
        if d is None:
            return None
        return {**d,"receiving_nfb_depth_pair_mm":(105.,75.)}
    monkeypatch.setattr(
        __import__("ae_engine.receiving_base_plate_config",
                   fromlist=["receiving_base_plate_values"]),
        "receiving_base_plate_values", changed_current_nfb_pair
    )
    source=projection.build_standard_part_profiles(snap,"base_plate")
    assert [row["len"] for row in source["X"]] == [40.,28.,626.,28.,40.]
    b,_=_profile_geometry(source["X"])
    assert b==pytest.approx((0,40,68,694,722,762))
    # Another CSV pair: delta30 -> X material28/outside32,
    # CENTER Y material30/outside32; the rule is NOT a constant 35.
    assert [row["len"] for row in source["Y"]] == [30.,180.,30.]
    x_ui=apply_outside_dimension_compensation([dict(row) for row in source["X"]],2.)
    y_ui=apply_outside_dimension_compensation([dict(row) for row in source["Y"]],2.)
    assert engine_segment_length_to_ui(x_ui[1]) == 32
    assert engine_segment_length_to_ui(y_ui[0]) == 32
