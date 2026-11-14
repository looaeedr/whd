"""#2517: genuine persisted Receiving Corner policy -> same Engine 2D / 3D / DXF."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2, FourCornerTypePolicy
from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
import phase6_project_file as project
from tests.test_issue2517_receiving_factory_confirmed_saved_door_indicators_failclosed import (
    SOURCE, COLUMNS, _saved,
)
from tests.test_issue2517_receiving_gui_factory_real_dxf_parity import (
    _gui_door_part_spec,
)


def _authored_hole():
    return CircleFeature(
        diameter=13.75, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 100.0), layer="CUTTING",
    )


def _manufactured_parts(snapshot, features):
    return api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=snapshot,
        confirmed_door_layout_columns=COLUMNS,
        confirmed_door_features=features,
    )


def test_real_receiving_saved_head_tail_policy_and_door_holes_remain_identical_in_2d_3d_dxf(
    tmp_path,
):
    original = _saved()
    hole = _authored_hole()
    original["part_features"] = {"door_c1_r1": [hole]}
    features = {"door_c1_r1": (hole,)}
    before = deepcopy(original)
    original_parts = _manufactured_parts(original, features)
    assert isinstance(original["endcap_corner_policies"]["head"], FourCornerTypePolicy)

    target = project.write_project(
        tmp_path / "receiving-physical-corners-and-holes.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    loaded = project.read_project(target)["snapshot"]
    # The documented project codec encodes ordinary policy dataclasses as JSON
    # maps; the original Engine Factory must restore their complete physical
    # corner identities, not treat a valid persisted snapshot as incomplete.
    assert isinstance(loaded["endcap_corner_policies"]["head"], dict)
    assert isinstance(loaded["endcap_corner_policies"]["tail"], dict)
    assert loaded["part_features"]["door_c1_r1"] == [hole]
    restored_parts = _manufactured_parts(loaded, features)
    assert tuple(key for key, _ in restored_parts) == (
        "box_body", "head", "tail", "door_c1_r1", "door_c1_r2",
        "door_c2_r1", "door_c2_r2",
    )

    context = ManufacturingContext(
        resource_root=Path(__file__).resolve().parents[1],
    )
    original_renders = {
        role: api.build_operator_part_render_data(spec, context)
        for role, spec in original_parts
    }
    restored_renders = {
        role: api.build_operator_part_render_data(spec, context)
        for role, spec in restored_parts
    }
    for role in original_renders:
        before_render = original_renders[role]
        after_render = restored_renders[role]
        assert before_render.scene == after_render.scene
        assert before_render.material.equals(after_render.material)
        assert before_render.fold_guides == after_render.fold_guides

    # Actual formed 3D from the SAME saved X/Y profile and Engine 2D material.
    for role in ("head", "tail"):
        before_profile = original["endcap_fold_profiles"][role]
        after_profile = loaded["endcap_fold_profiles"][role]
        original_mesh = api.project_independent_part_view_mesh(
            role, original_renders[role],
            x_profile=before_profile["X"], y_profile=before_profile["Y"],
            thickness=SOURCE["t"],
        )
        reloaded_mesh = api.project_independent_part_view_mesh(
            role, restored_renders[role],
            x_profile=after_profile["X"], y_profile=after_profile["Y"],
            thickness=SOURCE["t"],
        )
        assert original_mesh.triangles
        assert original_mesh.triangles == reloaded_mesh.triangles
        assert original_mesh.fold_guides == reloaded_mesh.fold_guides

    # A saved 2x2 Door grid is four independent physical plates, not two
    # representative rows. Compare every GUI operator source with the same
    # Engine PartSpec, flat FinalScene and genuinely folded 3D after reload.
    restored_specs = dict(restored_parts)
    door_keys = tuple(key for key in restored_specs if key.startswith("door_c"))
    cells = derive_door_layout_cells(COLUMNS)
    assert door_keys == ("door_c1_r1", "door_c1_r2", "door_c2_r1", "door_c2_r2")
    assert len(cells) == len(door_keys)
    gui_renders = {}
    for cell, role in zip(cells, door_keys):
        spec = restored_specs[role]
        gui_features = api.map_door_features_to_unfolded_material(spec, context)
        gui_spec = _gui_door_part_spec(cell, loaded, gui_features)
        gui_render = api.build_operator_part_render_data(gui_spec, context)
        assert gui_render.material.equals(restored_renders[role].material)
        gui_renders[role] = gui_render

        def profiles(snapshot):
            # Per-cell outside dimensions are from the actual Engine PartSpec,
            # never the full-cabinet GUI width or a copied flat preview.
            source = dict(snapshot)
            source["part_dimensions"] = {
                **dict(snapshot.get("part_dimensions") or {}),
                role: {"width": spec.width, "height": spec.height},
            }
            return api.build_standard_part_fold_profiles(source, role)

        before_xy, after_xy = profiles(original), profiles(loaded)
        assert before_xy == after_xy
        def mesh(render, xy):
            return api.project_independent_part_view_mesh(
                role, render, x_profile=xy["X"], y_profile=xy["Y"],
                thickness=SOURCE["t"],
            )
        original_mesh = mesh(original_renders[role], before_xy)
        restored_mesh = mesh(restored_renders[role], after_xy)
        gui_mesh = mesh(gui_render, after_xy)
        assert original_mesh.triangles
        assert restored_mesh.triangles == original_mesh.triangles
        assert gui_mesh.triangles == restored_mesh.triangles
        assert gui_mesh.fold_guides == restored_mesh.fold_guides

    batch = export_verified_resolved_integration_bays(
        (ManufacturingResolvedBayInput(
            family="receiving",
            source=ManufacturingSourceIdentity(
                "P1", "source-saved-and-reloaded", "set-1", "bay-1",
            ),
            confirmed_parts=restored_parts,
            door_layout_columns=COLUMNS,
        ),),
        tmp_path / "verified-dxf",
        context=context, pre_commit_guard=lambda: None,
    )
    assert batch.physical_dxf_roundtrip_verified
    assert not batch.complete_assembly_certified
    assert len(batch.output_files) == 9
    paths = [Path(path) for path in batch.output_files.values()]
    for filepath in paths:
        assert filepath.is_file()
        drawing = ezdxf.readfile(filepath)
        assert drawing.audit().errors == []
        assert any(item.dxf.layer == "CUTTING" for item in drawing.modelspace())
    for role in ("head", "tail", *door_keys):
        match = [path for path in paths if path.name.endswith(role + ".dxf")]
        assert len(match) == 1
        assert api.verify_saved_part_render_data_dxf(
            restored_renders[role], match[0],
        ).ok
        if role in gui_renders:
            assert api.verify_saved_part_render_data_dxf(
                gui_renders[role], match[0],
            ).ok
    assert original == before


@pytest.mark.parametrize("change", (
    lambda p: p["top_left"].update(type_id="UNKNOWN_CORNER"),
    lambda p: p.update(fw=True),
    lambda p: p["bottom_right"].update(rotation_quadrants=True),
    lambda p: p["top_right"].pop("type_id"),
    lambda p: p.update(bottom_fw=float("inf")),
))
def test_corrupt_saved_corner_policy_fails_before_any_dxf_or_factory_part(
    tmp_path, change,
):
    original = _saved()
    target = project.write_project(
        tmp_path / "valid-receiving-physical.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    reloaded = project.read_project(target)["snapshot"]
    altered = deepcopy(reloaded)
    change(altered["endcap_corner_policies"]["head"])
    before = deepcopy(altered)
    output = tmp_path / "invalid.dxf"
    with pytest.raises(ValueError, match="RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=altered,
        )
    assert not output.exists()
    assert altered == before
