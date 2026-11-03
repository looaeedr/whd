"""#2517: saved physical hole sizes and Profile closure are Engine-owned sources."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
import ae_engine.project_feature_codec as codec
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
COLUMNS = ((800.0, (1100.0, 500.0)),)
UPPER = "door_c1_r1"


def _shape_payload(type_name, **extra):
    return {"__phase6_type__": type_name,
            "anchor": "absolute_finished_face",
            "offset": {"__phase6_type__": "Vec2", "x": 100, "y": 100},
            "layer": "CUTTING", **extra}


@pytest.mark.parametrize("bad", (
    True, False, None, "broken", "", "nan", "inf", "-inf",
    float("nan"), float("inf"), float("-inf"), [], {},
    10 ** 400,
))
@pytest.mark.parametrize("type_name,field,rest", (
    ("CircleFeature", "diameter", {}),
    ("RectFeature", "width", {"height": 12.0}),
    ("RectFeature", "height", {"width": 20.0}),
))
def test_saved_hole_dimension_rejects_boolean_nonfinite_and_corrupt_sources(
    type_name, field, rest, bad,
):
    raw = _shape_payload(type_name, **rest, **{field: bad})
    frozen = deepcopy(raw)
    with pytest.raises(ValueError, match=f"invalid saved Feature dimension: {field}"):
        api.decode_project_value(raw)
    assert str(raw[field]) == str(frozen[field])


@pytest.mark.parametrize("size,expected", (
    ("13.75", 13.75), (12, 12.0), (1.5, 1.5), (0, 0.0), (-1, -1.0),
))
def test_legacy_valid_finite_numeric_dimensions_preserve_preexisting_material_values(
    size, expected,
):
    # A saved draft's zero or negative dimension stays present; the
    # existing separate manufacturing geometry validator owns fit/positivity.
    circle = api.decode_project_value(_shape_payload("CircleFeature", diameter=size))
    rect = api.decode_project_value(_shape_payload(
        "RectFeature", width=size, height="10.25",
    ))
    assert circle.diameter == expected
    assert rect.width == expected and rect.height == 10.25
    assert circle.offset == rect.offset == Vec2(100.0, 100.0)


@pytest.mark.parametrize("closed,expected", (
    (True, True), (False, False), (1, True), (0, False),
    (1.0, True), (0.0, False),
))
def test_legacy_profile_layer_flag_has_one_precise_boolean_meaning(closed, expected):
    raw = _shape_payload(
        "ProfileFeature",
        points=[{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 10}],
        layered_profiles=[["CUTTING", [
            {"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 10},
        ], closed]],
    )
    result = api.decode_project_value(raw)
    assert type(result) is ProfileFeature
    assert result.layered_profiles[0][2] is expected


@pytest.mark.parametrize("bad", (
    "false", "true", "0", "1", "yes", "", None,
    -1, 2, float("nan"), float("inf"), [], {},
))
def test_profile_closed_false_must_not_become_cutting_true_by_python_truthiness(bad):
    raw = _shape_payload(
        "ProfileFeature",
        points=[{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 10}],
        layered_profiles=[["CUTTING", [
            {"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 10},
        ], bad]],
    )
    with pytest.raises(ValueError, match="invalid saved Profile closed flag"):
        api.decode_project_value(raw)


def _hole(diameter=13.75):
    return CircleFeature(
        diameter=diameter, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(105.0, 121.0), layer="CUTTING",
    )


def test_valid_p6fold_saved_door_hole_dimensions_to_real_verified_cutting(tmp_path):
    physical = _hole()
    raw = {"model": "受電箱", **SOURCE, "part_features": {UPPER: [physical]}}
    original = deepcopy(raw)
    saved_file = project.write_project(tmp_path / "hole-sizes.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": raw,
    })
    loaded = project.read_project(saved_file)["snapshot"]
    hole = loaded["part_features"][UPPER][0]
    assert hole == physical and hole is not physical
    assert raw == original

    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "saved-size-confirmation", "Set1", "Bay1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="fresh_family_confirmed",
        door_layout_columns=COLUMNS,
        confirmed_door_features={UPPER: (hole,)},
    )
    guarded = []
    output = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "verified",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: guarded.append("source-attested"),
    )
    assert guarded == ["source-attested", "source-attested"]
    assert output.physical_dxf_roundtrip_verified
    assert len(output.output_files) == 7
    path = next(Path(v) for v in output.output_files.values()
                if Path(v).name.endswith(f"{UPPER}.dxf"))
    circles = [entity for entity in ezdxf.readfile(path).modelspace()
               if entity.dxftype() == "CIRCLE" and entity.dxf.layer == "CUTTING"]
    assert any(abs(float(c.dxf.radius) - 6.875) < 1e-6 for c in circles)


@pytest.mark.parametrize("corruption", ("diameter_bool", "diameter_nan"))
def test_corrupt_real_project_hole_size_fails_at_read_not_after_dxf(tmp_path, corruption):
    saved_file = project.write_project(tmp_path / "bad-size.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {"model": "受電箱", "part_features": {UPPER: [_hole()]}},
    })
    raw = json.loads(saved_file.read_text(encoding="utf-8"))
    feature = raw["snapshot"]["part_features"][UPPER][0]
    feature["diameter"] = True if corruption == "diameter_bool" else "NaN"
    saved_file.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid saved Feature dimension: diameter"):
        project.read_project(saved_file)
    assert not (tmp_path / "verified").exists()


def test_gui_save_reload_and_headless_feature_decode_stay_one_engine_function():
    assert api.decode_project_feature is project._decode_feature is codec._decode_feature
    assert api.decode_project_value is project._decode is codec._decode
    source = inspect.getsource(codec._decode_feature)
    assert "_finite_saved_feature_dimension" in source
    assert "_saved_profile_closed_flag(closed)" in source
    assert "bool(closed)" not in source
