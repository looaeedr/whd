"""#2517: write and reload of authored physical Feature must use one Engine gate."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import project_feature_codec as codec
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_geometry import Vec2
import phase6_project_file as project


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
ROLE = "door_c1_r1"
COLUMNS = ((800.0, (1100.0, 500.0)),)


def _hole(*, diameter=13.75, offset=None):
    return CircleFeature(
        diameter=diameter,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 100.0) if offset is None else offset,
        layer="CUTTING",
    )


def _project(feature):
    return {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱", **SOURCE,
            "part_features": {ROLE: [feature]},
        },
    }


@pytest.mark.parametrize("bad", (
    True, False, None, "", "broken", "nan", "inf",
    float("nan"), float("inf"), float("-inf"), 10**400,
))
@pytest.mark.parametrize("axis", ("x", "y"))
def test_typed_vec2_invalid_physical_coordinate_refused_before_save(
    bad, axis, tmp_path,
):
    raw = Vec2(bad, 101.5) if axis == "x" else Vec2(101.5, bad)
    hole = _hole(offset=raw)
    source = _project(hole)
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.encode_project_value(source)
    target = tmp_path / "invalid-source.p6fold"
    with pytest.raises(ValueError, match="invalid Vec2"):
        project.write_project(target, source)
    assert not target.exists()


@pytest.mark.parametrize("field,type_name", (
    ("diameter", "circle"), ("width", "rect"), ("height", "rect"),
))
@pytest.mark.parametrize("bad", (
    True, False, None, "", "nan", "inf",
    float("nan"), float("inf"), 10**400,
))
def test_typed_feature_invalid_physical_size_fails_before_project_write(
    bad, field, type_name, tmp_path,
):
    if type_name == "circle":
        feature = _hole(diameter=bad)
    else:
        feature = RectFeature(
            width=bad if field == "width" else 20.0,
            height=bad if field == "height" else 20.0,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(100.0, 100.0), layer="CUTTING",
        )
    payload = _project(feature)
    with pytest.raises(ValueError, match=f"invalid saved Feature dimension: {field}"):
        api.encode_project_value(payload)
    path = tmp_path / "broken-size.p6fold"
    with pytest.raises(ValueError, match=f"invalid saved Feature dimension: {field}"):
        project.write_project(path, payload)
    assert not path.exists()


def _profile(*, closed=False, top=20.0, nested_top=20.0):
    points = (Vec2(0, 0), Vec2(top, 0), Vec2(top, 20))
    layer_points = (Vec2(0, 0), Vec2(nested_top, 0), Vec2(20, 20))
    return ProfileFeature(
        points=points, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(10, 10), layer="CUTTING",
        layered_profiles=(("CUTTING", layer_points, closed),),
    )


@pytest.mark.parametrize("closed", ("false", "true", "0", "1", None, -1, 2, float("nan")))
def test_typed_profile_layered_cutting_flag_cannot_change_truth_value_on_reload(
    closed, tmp_path,
):
    payload = _project(_profile(closed=closed))
    with pytest.raises(ValueError, match="invalid saved Profile closed flag"):
        api.encode_project_value(payload)
    target = tmp_path / "invalid-profile.p6fold"
    with pytest.raises(ValueError, match="invalid saved Profile closed flag"):
        project.write_project(target, payload)
    assert not target.exists()


@pytest.mark.parametrize("field", ("main", "nested"))
def test_typed_profile_vertex_cannot_be_serialized_as_boolean_mm(field):
    profile = (
        _profile(top=True) if field == "main"
        else _profile(nested_top=float("inf"))
    )
    with pytest.raises(ValueError, match="invalid Vec2 physical coordinate"):
        api.encode_project_value(profile)


def test_invalid_new_feature_does_not_overwrite_valid_saved_project(tmp_path):
    target = tmp_path / "existing.p6fold"
    original_feature = _hole()
    project.write_project(target, _project(original_feature))
    original_bytes = target.read_bytes()
    invalid_source = _project(_hole(offset=Vec2(True, 100.0)))
    with pytest.raises(ValueError, match="invalid Vec2"):
        project.write_project(target, invalid_source)
    assert target.read_bytes() == original_bytes
    assert project.read_project(target)["snapshot"]["part_features"][ROLE] == [
        original_feature,
    ]


def test_legitimate_physical_feature_writes_and_reads_without_numeric_coercion_loss():
    circular = _hole(diameter=13.75)
    rectangular = RectFeature(
        width=0.0, height=-2.5,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(-14.5, 11.25), layer="CUTTING",
    )
    profile = _profile(closed=False)
    for feature in (circular, rectangular, profile):
        encoded = api.encode_project_value(feature)
        json.dumps(encoded, allow_nan=False)
        decoded = api.decode_project_value(encoded)
        assert decoded == feature
    assert api.encode_project_value(Vec2("105.5", "-12.25")) == {
        "__phase6_type__": "Vec2", "x": 105.5, "y": -12.25,
    }
    assert api.decode_project_value(
        api.encode_project_value(Vec2("105.5", "-12.25"))
    ) == Vec2(105.5, -12.25)
    assert api.decode_project_value(
        api.encode_project_value(_profile(closed=0))
    ).layered_profiles[0][2] is False


def test_real_receiving_door_saved_feature_reloads_to_verified_physical_dxf(tmp_path):
    hole = _hole()
    authored = _project(hole)
    original = deepcopy(authored)
    saved = project.write_project(tmp_path / "valid-hole.p6fold", authored)
    reloaded = project.read_project(saved)["snapshot"]["part_features"][ROLE][0]
    assert reloaded == hole and reloaded is not hole
    assert authored == original
    verified = export_verified_resolved_integration_bays(
        (ManufacturingResolvedBayInput(
            family="受電箱",
            source=ManufacturingSourceIdentity(
                "P1", "write-read-source", "SetA", "Bay1",
            ),
            source_dimensions_mm=SOURCE,
            operator_confirmation="fresh_family_confirmed",
            door_layout_columns=COLUMNS,
            confirmed_door_features={ROLE: (reloaded,)},
        ),),
        tmp_path / "verified",
        context=ManufacturingContext(
            resource_root=Path(__file__).resolve().parents[1],
        ),
        pre_commit_guard=lambda: None,
    )
    assert verified.physical_dxf_roundtrip_verified
    assert len(verified.output_files) == 7
    upper = next(Path(p) for p in verified.output_files.values()
                 if Path(p).name.endswith(f"{ROLE}.dxf"))
    reopened = ezdxf.readfile(upper)
    circles = [
        item for item in reopened.modelspace()
        if item.dxftype() == "CIRCLE" and item.dxf.layer == "CUTTING"
    ]
    assert any(abs(float(circle.dxf.radius) - 6.875) < 1e-6
               for circle in circles)


def test_gui_file_api_remains_exact_engine_codec_and_has_no_parallel_geometry_gate():
    assert project._encode is api.encode_project_value is codec._encode
    assert project._decode is api.decode_project_value is codec._decode
    source = inspect.getsource(codec._encode)
    assert "_finite_saved_coordinate(" in source
    assert "_finite_saved_feature_dimension(" in source
    assert "_saved_profile_closed_flag(" in source
    assert "bool(closed)" not in source
