"""#2517: BoxBody finished-face 2D preview consumes canonical public Engine drawing."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import (
    DrawingScene, resolved_features_to_primitives as owner,
)
from ae_engine.sheetmetal_features import (
    ResolvedCircle, ResolvedRect, ResolvedProfile,
)
from ae_engine.sheetmetal_geometry import Vec2
import gui


def _physical_resolved_features():
    return (
        ResolvedCircle(
            center=Vec2(40.0, 55.0), radius=6.0, layer="BLIND_HOLE",
            add_centerline=True, source_type="管孔",
        ),
        ResolvedRect(
            center=Vec2(65.0, 90.0), width=18.0, height=24.0,
            layer="CUTTING", source_type="方形",
        ),
        ResolvedProfile(
            points=(Vec2(10.0, 10.0), Vec2(32.0, 10.0), Vec2(32.0, 28.0)),
            layer="CUTTING",
            layered_profiles=((
                "MARKING",
                (Vec2(12.0, 12.0), Vec2(26.0, 12.0), Vec2(26.0, 25.0)),
                True,
            ),),
        ),
    )


def test_public_facade_and_root_export_original_physical_drawing_owner():
    assert api.project_operator_resolved_feature_drawing_primitives is owner
    assert ae_engine.project_operator_resolved_feature_drawing_primitives is owner
    assert "project_operator_resolved_feature_drawing_primitives" in ae_engine.__all__


def test_public_resolved_feature_primitives_match_existing_cut_bend_process_layers():
    source = _physical_resolved_features()
    before = deepcopy(source)
    public = api.project_operator_resolved_feature_drawing_primitives(source)
    assert public == owner(source)
    # One physical circle, one centerline, one rectangular cutting contour,
    # one primary Profile CUTTING and one independent MARKING process layer.
    assert [row.layer for row in public] == [
        "BLIND_HOLE", "DATUM", "CUTTING", "CUTTING", "MARKING",
    ]
    assert source == before
    assert type(public) is tuple


def test_from_dxf_profile_does_not_invent_a_primary_cutting_contour():
    profile = ResolvedProfile(
        points=(Vec2(0, 0), Vec2(25, 0), Vec2(25, 20)),
        layer="FROM_DXF",
        layered_profiles=(("MARKING", (Vec2(1, 1), Vec2(10, 1)), False),),
    )
    before = deepcopy(profile)
    actual = api.project_operator_resolved_feature_drawing_primitives((profile,))
    assert actual == owner((profile,))
    assert len(actual) == 1 and actual[0].layer == "MARKING"
    assert profile == before


def test_gui_box_body_real_2d_face_scene_calls_public_engine_once(monkeypatch):
    source = _physical_resolved_features()
    before = deepcopy(source)
    calls = []

    def public(features):
        calls.append(features)
        return owner(features)

    monkeypatch.setattr(api, "project_operator_resolved_feature_drawing_primitives", public)
    host = SimpleNamespace(_box_body_baseline_faces=lambda _val: {"back": source})
    scene = gui.Phase6ApplicationHost._box_body_face_baseline_scene(
        host, "back", {"w": 800.0, "h": 1200.0, "d": 350.0},
    )
    assert isinstance(scene, DrawingScene)
    assert scene.primitives == list(owner(source))
    assert calls == [source]
    assert source == before


def test_gui_box_body_unknown_or_empty_face_does_not_invent_geometry(monkeypatch):
    calls = []

    def forbidden(_features):
        calls.append(True)
        raise AssertionError("absent face must not ask Engine to invent a part")

    monkeypatch.setattr(api, "project_operator_resolved_feature_drawing_primitives", forbidden)
    host = SimpleNamespace(_box_body_baseline_faces=lambda _val: {"back": ()})
    assert gui.Phase6ApplicationHost._box_body_face_baseline_scene(host, "back", {}) is None
    assert gui.Phase6ApplicationHost._box_body_face_baseline_scene(host, "left", {}) is None
    assert calls == []


def test_invalid_resolved_source_does_not_mutate_other_physical_features():
    source = _physical_resolved_features()
    original = deepcopy(source)
    with pytest.raises(TypeError, match="Unsupported resolved feature"):
        api.project_operator_resolved_feature_drawing_primitives((*source, object()))
    assert source == original


def test_main_gui_has_no_direct_internal_feature_primitive_projection():
    source = Path(gui.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.sheetmetal_drawing"
        and any(alias.name == "resolved_features_to_primitives" for alias in node.names)
        for node in ast.walk(tree)
    )
    actual_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
        and node.func.attr == "project_operator_resolved_feature_drawing_primitives"
    ]
    assert len(actual_calls) == 1
