"""#2517 saved Feature/Vec2 geometry must not invent or coerce physical holes."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
import ae_engine.project_feature_codec as owner
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingIntegrationRequest, ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity, dispatch_manufacturing_integration,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_features import (
    CircleFeature, ProfileFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_geometry import Vec2
import phase6_project_file as project


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((800.0, (1100.0, 500.0)),)
UPPER = "door_c1_r1"


def _hole():
    return CircleFeature(
        diameter=13.75, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(101.5, 125.25), layer="CUTTING",
        source_type="saved-door-source",
    )


@pytest.mark.parametrize("bad", [
    True, False, None, "", "broken", "nan", "inf", "-inf",
    float("nan"), float("inf"), float("-inf"), [], {}, 10 ** 400,
])
@pytest.mark.parametrize("axis", ("x", "y"))
def test_typed_vec2_saved_coordinate_never_invents_manufacturing_position(
    axis, bad,
):
    raw = {"__phase6_type__": "Vec2", "x": 10.0, "y": 20.0}
    raw[axis] = bad
    copy = deepcopy(raw)
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.decode_project_value(raw)
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.project_vec2_from_raw({"x": raw["x"], "y": raw["y"]})
    assert str(raw[axis]) == str(copy[axis])


@pytest.mark.parametrize("raw", [
    {"x": 101.5}, {"y": 125.25}, {},
    {"x": "nan", "y": 10.0}, {"x": True, "y": 10.0},
    {"x": 10.0, "y": float("inf")},
])
def test_explicit_partial_or_corrupt_feature_offset_does_not_get_defaulted_to_zero(raw):
    saved = {"diameter": 13.75, "anchor": "absolute_finished_face",
             "offset": raw, "layer": "CUTTING"}
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.decode_project_feature("CircleFeature", saved)


@pytest.mark.parametrize("raw,expected", [
    ({"x": "101.5", "y": "-125.25"}, Vec2(101.5, -125.25)),
    ((101.5, -125.25), Vec2(101.5, -125.25)),
    ([101.5, -125.25], Vec2(101.5, -125.25)),
    (Vec2(101.5, -125.25), Vec2(101.5, -125.25)),
])
def test_existing_complete_source_encodings_keep_coordinate_precision(raw, expected):
    assert api.project_vec2_from_raw(raw) == expected
    assert api.project_vec2_from_raw(api.encode_project_value(expected)) == expected
    # Historically omitted Feature.offset is an explicit zero-offset default,
    # not a partially supplied physical coordinate.
    old = api.decode_project_feature(
        "CircleFeature", {"diameter": 12.0, "anchor": "panel_center"},
    )
    assert old.offset == Vec2(0.0, 0.0)


def test_nested_profile_vertices_and_layered_cutting_source_reject_bad_coordinates():
    sample = ProfileFeature(
        points=(Vec2(0, 0), Vec2(20, 0), Vec2(20, 10)),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(10, 20),
        layered_profiles=(("CUTTING", (Vec2(0, 0), Vec2(20, 0),
                                          Vec2(20, 10)), True),),
    )
    payload = api.encode_project_value(sample)
    assert api.decode_project_value(payload) == sample
    wrong = deepcopy(payload)
    wrong["points"][1]["x"] = True
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.decode_project_value(wrong)
    wrong = deepcopy(payload)
    wrong["layered_profiles"][0][1][0]["y"] = "nan"
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.decode_project_value(wrong)


def test_real_p6fold_project_saved_feature_roundtrip_to_verified_door_cutting(tmp_path):
    physical = _hole()
    saved = {"model": "受電箱", "w": SOURCE["w"], "h": SOURCE["h"],
             "d": SOURCE["d"], "t": SOURCE["t"],
             "part_features": {UPPER: [physical]}}
    original = deepcopy(saved)
    file = project.write_project(
        tmp_path / "receiving-door-features.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    restored = project.read_project(file)["snapshot"]
    hole = restored["part_features"][UPPER][0]
    assert hole == physical
    assert hole is not physical
    assert saved == original

    identity = ManufacturingSourceIdentity(
        "P1", "saved-feature-coordinate-revision", "SetA", "Bay1",
    )
    bay = ManufacturingResolvedBayInput(
        family="受電箱", source=identity,
        source_dimensions_mm=SOURCE,
        operator_confirmation="fresh_family_confirmed",
        door_layout_columns=COLUMNS,
        confirmed_door_features={UPPER: (hole,)},
    )
    guarded = []
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: guarded.append("source-stable"),
    )
    assert guarded == ["source-stable", "source-stable"]
    assert result.physical_dxf_roundtrip_verified
    assert len(result.output_files) == 7
    upper = next(
        Path(v) for v in result.output_files.values()
        if Path(v).name.endswith(f"{UPPER}.dxf")
    )
    circles = [
        entity for entity in ezdxf.readfile(upper).modelspace()
        if entity.dxftype() == "CIRCLE" and entity.dxf.layer == "CUTTING"
    ]
    assert any(abs(float(item.dxf.radius) - 6.875) < 1e-6 for item in circles)
    denied = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("export", "受電箱", identity),
    )
    assert denied.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"


def test_corrupt_real_p6fold_physical_position_read_fails_before_any_export(tmp_path):
    saved = {
        "model": "受電箱", "part_features": {UPPER: [_hole()]},
    }
    path = project.write_project(
        tmp_path / "broken-feature.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    wire = json.loads(path.read_text(encoding="utf-8"))
    offset = wire["snapshot"]["part_features"][UPPER][0]["offset"]
    assert offset["__phase6_type__"] == "Vec2"
    offset["x"] = True
    path.write_text(json.dumps(wire, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Vec2"):
        project.read_project(path)
    assert not (tmp_path / "verified").exists()


def test_gui_codec_routes_real_coordinates_through_one_engine_owner():
    assert project._decode is api.decode_project_value is owner._decode
    assert project._as_vec2 is api.project_vec2_from_raw is owner._as_vec2
    src = inspect.getsource(owner._decode)
    assert 'return _as_vec2(value)' in src
    assert 'float(value["x"])' not in src
