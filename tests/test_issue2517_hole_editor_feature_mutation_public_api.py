# -*- coding: utf-8 -*-
"""#2517 Hole Editor physical draft operators supplied only by public Engine."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, feature_finished_point
from ae_engine.sheetmetal_feature_reference import (
    ReferenceAnchor,
    feature_with_reference_anchor,
    feature_with_process,
    move_feature_by_reference_distance,
)
from ae_engine.sheetmetal_feature_surface import (
    feature_is_within_surface,
    move_feature_within_surface,
    feature_surface_from_rect,
)
from ae_engine.sheetmetal_geometry import Vec2

ROOT = Path(__file__).resolve().parents[1]

OPERATORS = {
    "operator_hole_feature_with_reference_anchor": feature_with_reference_anchor,
    "operator_hole_feature_with_process": feature_with_process,
    "operator_hole_move_feature_by_reference_distance": move_feature_by_reference_distance,
    "operator_hole_feature_is_within_surface": feature_is_within_surface,
    "operator_hole_move_feature_within_surface": move_feature_within_surface,
}


def hole(x=40., y=40.):
    return CircleFeature(
        diameter=20., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y), layer="CUTTING",
    )


def surface():
    return feature_surface_from_rect("door", Vec2(0., 0.), Vec2(100., 100.))


def test_public_api_reexports_identical_canonical_feature_operators():
    for name, owner in OPERATORS.items():
        assert getattr(api, name) is owner
        assert getattr(ae_engine, name) is owner
        assert name in ae_engine.__all__


def test_process_and_reference_anchor_change_detached_features_only():
    original = hole()
    before = deepcopy(original)
    blind = api.operator_hole_feature_with_process(original, "BLIND_HOLE")
    assert blind == feature_with_process(original, "BLIND_HOLE")
    assert blind.layer == "BLIND_HOLE"
    cutting = api.operator_hole_feature_with_process(blind, "CUTTING")
    assert cutting.layer == "CUTTING"
    anchored = api.operator_hole_feature_with_reference_anchor(
        original, ReferenceAnchor.TOP_CENTER,
    )
    assert anchored == feature_with_reference_anchor(
        original, ReferenceAnchor.TOP_CENTER,
    )
    assert anchored != original
    with pytest.raises(ValueError, match="process must be"):
        api.operator_hole_feature_with_process(original, "FROM_DXF")
    assert original == before


def test_surface_drag_inside_and_outside_preserves_original_and_validity():
    original = hole()
    old = deepcopy(original)
    face = surface()
    assert api.operator_hole_feature_is_within_surface(face, original, 100, 100)
    moved = api.operator_hole_move_feature_within_surface(
        original, Vec2(65., 65.), 100., 100., face,
    )
    assert moved == move_feature_within_surface(original, Vec2(65., 65.), 100., 100., face)
    point = feature_finished_point(moved, 100., 100.)
    assert (point.x, point.y) == (65., 65.)
    out = api.operator_hole_move_feature_within_surface(
        original, Vec2(200., 65.), 100., 100., face,
    )
    assert out == original
    assert original == old


def test_reference_position_parity_and_invalid_values_do_not_mutate_source():
    face = surface()
    source = [hole()]
    original = deepcopy(source)
    kwargs = dict(
        axis="x", mode="edge", value=25.0,
    )
    moved = api.operator_hole_move_feature_by_reference_distance(
        face, source, 0, ReferenceAnchor.CENTER, 100., 100., **kwargs,
    )
    expected = move_feature_by_reference_distance(
        face, source, 0, ReferenceAnchor.CENTER, 100., 100., **kwargs,
    )
    assert moved == expected
    assert api.operator_hole_feature_is_within_surface(face, moved, 100., 100.)
    for kwargs in (dict(axis="x", mode="edge", value=float("nan")),
                   dict(axis="x", mode="edge", value=float("inf"))):
        with pytest.raises(ValueError, match="finite"):
            api.operator_hole_move_feature_by_reference_distance(
                face, source, 0, ReferenceAnchor.CENTER, 100., 100., **kwargs,
            )
    with pytest.raises(ValueError, match="out of range"):
        api.operator_hole_move_feature_by_reference_distance(
            face, source, -1, ReferenceAnchor.CENTER, 100., 100.,
            axis="x", mode="edge", value=10.,
        )
    assert source == original


def test_gui_composition_dependency_injects_only_public_engine_operators():
    gui = ast.parse((ROOT / "gui.py").read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(gui) if isinstance(n, ast.ImportFrom)]
    assert not [
        item.name for node in imports if node.module == "ae_engine.sheetmetal_features"
        for item in node.names if item.name in {
            "feature_with_reference_anchor", "feature_with_process",
            "move_feature_by_reference_distance",
            "feature_is_within_surface", "move_feature_within_surface",
        }
    ]
    assignments = {
        n.targets[0].id: n.value.attr
        for n in gui.body if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and isinstance(n.value, ast.Attribute)
        and isinstance(n.value.value, ast.Name)
        and n.value.value.id == "manufacturing_api"
    }
    for name, public_name in (
        ("feature_with_reference_anchor", "operator_hole_feature_with_reference_anchor"),
        ("feature_with_process", "operator_hole_feature_with_process"),
        ("move_feature_by_reference_distance", "operator_hole_move_feature_by_reference_distance"),
        ("feature_is_within_surface", "operator_hole_feature_is_within_surface"),
        ("move_feature_within_surface", "operator_hole_move_feature_within_surface"),
    ):
        assert assignments.get(name) == public_name

    from gui_modules.editors.hole_editor_composition import HoleEditorCompositionDependencies
    for name in (
        "feature_with_reference_anchor", "feature_with_process",
        "move_feature_by_reference_distance", "feature_is_within_surface",
        "move_feature_within_surface",
    ):
        assert name in HoleEditorCompositionDependencies.REQUIRED
