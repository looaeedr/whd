"""DM8-C2 — one immutable FinalScene owner used by Joint and Pairing."""
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
from shapely.geometry import box

from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.manufacturing_render_data import (
    BoxBodyPieceRenderData,
    BoxBodyStructureRenderData,
    PartRenderData,
    build_exploded_box_body_preview,
)
from ae_engine.manufacturing_scene_access import (
    owner_render_data,
    replace_owner_render_data,
)
from ae_engine.sheetmetal_drawing import DrawingScene
import ae_engine.receiving_joint_marking as joint
import ae_engine.receiving_pairing_marking as pairing


def _render(label, width=20.0):
    return PartRenderData(
        scene=DrawingScene(), material=box(0, 0, width, 20),
        metadata={"source_label": label, "derived_marking_coordinates": ()},
    )


def _fixture():
    left = BoxBodyPieceRenderData(
        key="left", role="Left_Side", formed_w_start=0.0,
        formed_w_end=20.0, fold_profile=(), render_data=_render("left"),
    )
    right = BoxBodyPieceRenderData(
        key="right", role="Right_Side", formed_w_start=20.0,
        formed_w_end=40.0, fold_profile=(), render_data=_render("right"),
    )
    pieces = (left, right)
    canonical = _render("canonical", 40)
    body = BoxBodyStructureRenderData(
        structure_type="test", pieces=pieces,
        preview_render_data=build_exploded_box_body_preview(pieces),
        canonical_strip_render_data=canonical, warnings=("keep-warning",),
    )
    return ResolvedManufacturingGeometry(
        parts=(ResolvedManufacturingPart("door", _render("door")),
               ResolvedManufacturingPart("box_body", body)),
        diagnostics=("keep-diagnostic",),
    )


def test_direct_scene_lookup_and_immutable_replacement():
    source = _fixture()
    new_render = _render("new-door")
    result = replace_owner_render_data(source, "door", new_render)
    assert owner_render_data(source, "door").metadata["source_label"] == "door"
    assert owner_render_data(result, "door") is new_render
    assert result.parts[0] is not source.parts[0]
    assert result.parts[1] is source.parts[1]
    assert result.diagnostics is source.diagnostics
    assert source.parts[0].render_data is not new_render


def test_composite_role_casefold_order_preview_and_metadata_parity():
    source = _fixture()
    before = source.parts[1].render_data
    replacement = replace(_render("new-left", 31), metadata={"source_label": "new-left", "other_data": "keep"})
    result = replace_owner_render_data(source, "box_body:left_SIDE", replacement)
    after = result.parts[1].render_data
    assert owner_render_data(result, "box_body:LEFT_SIDE") is replacement
    assert owner_render_data(source, "box_body:left_side") is before.pieces[0].render_data
    assert after.pieces[1] is before.pieces[1]
    assert [piece.key for piece in after.pieces] == ["left", "right"]
    assert after.canonical_strip_render_data is before.canonical_strip_render_data
    assert after.warnings == before.warnings
    assert after.preview_render_data is not before.preview_render_data
    assert after.preview_render_data.material.area != before.preview_render_data.material.area
    assert after.pieces[0].render_data.metadata["other_data"] == "keep"
    assert result.parts[0] is source.parts[0]
    assert result.diagnostics == source.diagnostics


@pytest.mark.parametrize("owner_key", ["missing", "box_body:unavailable", "box_body:"])
def test_missing_owner_is_none_for_read_and_keyerror_for_replace(owner_key):
    source = _fixture()
    assert owner_render_data(source, owner_key) is None
    with pytest.raises(KeyError, match=".*"):
        replace_owner_render_data(source, owner_key, _render("unused"))


def test_single_owner_required_by_both_policy_modules_no_fallback_oracle():
    assert joint.owner_render_data is owner_render_data
    assert pairing.owner_render_data is owner_render_data
    assert joint.replace_owner_render_data is replace_owner_render_data
    assert pairing.replace_owner_render_data is replace_owner_render_data
    base = Path(joint.__file__).parent
    for policy_file in ("receiving_joint_marking.py", "receiving_pairing_marking.py"):
        code = (base / policy_file).read_text(encoding="utf-8")
        tree = ast.parse(code)
        owner_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        assert "_owner_render_data" not in owner_names
        assert "_replace_owner_render_data" not in owner_names
        assert "owner_render_data" not in owner_names
        assert "replace_owner_render_data" not in owner_names
        imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
        shared_imports = [node for node in imports if node.module == "manufacturing_scene_access"]
        assert len(shared_imports) == 1, "deleting the public seam must break BOTH callers"
        assert {alias.name for alias in shared_imports[0].names} == {
            "owner_render_data", "replace_owner_render_data",
        }
        assert "from .receiving_joint_marking import _owner_render_data" not in code
    oracle = (base / "assembly_marking_geometry.py").read_text(encoding="utf-8")
    assert oracle.count("def backproject_mapped_skin_world_points(") == 1
    seam = (base / "manufacturing_scene_access.py").read_text(encoding="utf-8")
    assert "backproject" not in seam
    assert "PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES" not in seam
