"""#2517: saved Receiving multipart BoxBody shares 2D, world 3D and real GUI/Engine DXF."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext, ResolvedManufacturingPart
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from gui_modules.application import fold_designer_manufacturing_projection as gui
import phase6_project_file as project
from tests.test_issue2517_receiving_factory_confirmed_saved_door_indicators_failclosed import (
    COLUMNS, SOURCE, _saved,
)

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("left_side", "back", "right_side")


def _parts(snapshot):
    return api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=snapshot, confirmed_door_layout_columns=COLUMNS,
    )


def _world_skins(render):
    part = ResolvedManufacturingPart(part_key="box_body", render_data=render)
    return api.resolve_box_body_true_world_piece_meshes(
        part,
        dimensions=(SOURCE["w"], SOURCE["h"], SOURCE["d"]),
        thickness=SOURCE["t"],
    )


def test_saved_three_sheet_boxbody_has_same_engine_world_mesh_and_gui_batch_dxf(
    tmp_path,
):
    original = _saved()
    untouched = deepcopy(original)
    source_specs = dict(_parts(original))
    filename = project.write_project(
        tmp_path / "real-receiving-boxbody.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    reloaded = project.read_project(filename)["snapshot"]
    restored_parts = _parts(reloaded)
    confirmed = dict(restored_parts)
    ctx = ManufacturingContext(resource_root=ROOT, draw_stock=False)
    source_render = api.build_operator_part_render_data(source_specs["box_body"], ctx)
    loaded_render = api.build_operator_part_render_data(confirmed["box_body"], ctx)

    assert tuple(piece.role for piece in loaded_render.pieces) == ROLES
    assert len(source_render.pieces) == 3
    for previous, current in zip(source_render.pieces, loaded_render.pieces):
        assert previous.role == current.role
        assert previous.key == current.key
        assert previous.render_data.scene == current.render_data.scene
        assert previous.render_data.material.equals(current.render_data.material)
        assert previous.render_data.fold_guides == current.render_data.fold_guides

    source_world = _world_skins(source_render)
    restored_world = _world_skins(loaded_render)
    assert tuple(piece.role for piece, _ in source_world) == ROLES
    assert all(mesh for _, mesh in source_world)
    assert tuple((piece.role, mesh) for piece, mesh in restored_world) == (
        tuple((piece.role, mesh) for piece, mesh in source_world)
    )

    # Invoke the real GUI export adapter. It must use the same cached Engine
    # physical FinalScenes, not synthesize a second BoxBody manufacturing path.
    gui_dir = tmp_path / "gui"
    gui_dir.mkdir()
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _require_verified_baseline_sources_for_manufacturing=lambda: None,
        _authoritative_render_data=lambda spec, context: (
            loaded_render if spec is confirmed["box_body"] and context is ctx else None
        ),
    )
    gui_files = gui._export_authoritative_part(
        host, confirmed["box_body"], gui_dir / "箱身.dxf", ctx,
    )
    assert len(gui_files) == 3
    assert tuple(result.part_kind for result in gui_files) == (
        tuple(piece.key for piece in loaded_render.pieces)
    )

    # The separate confirmed-source Engine client must verify all three
    # physical sheets in the same real nine-output saved 2x2 Bay batch.
    exported = export_verified_resolved_integration_bays(
        (ManufacturingResolvedBayInput(
            family="receiving",
            source=ManufacturingSourceIdentity("P1", "saved-physical", "Set1", "Bay1"),
            confirmed_parts=restored_parts,
            door_layout_columns=COLUMNS,
        ),),
        tmp_path / "engine-batch",
        context=ctx,
        pre_commit_guard=lambda: None,
    )
    assert exported.physical_dxf_roundtrip_verified
    assert not exported.complete_assembly_certified
    assert len(exported.output_files) == 9
    batch_files = tuple(Path(value) for value in exported.output_files.values())
    for piece, gui_result in zip(loaded_render.pieces, gui_files):
        matches = [f for f in batch_files if piece.role in f.name]
        assert len(matches) == 1
        for output in (Path(gui_result.output_path), matches[0]):
            drawing = ezdxf.readfile(output)
            assert drawing.audit().errors == []
            assert any(e.dxf.layer == "CUTTING" for e in drawing.modelspace())
            assert api.verify_saved_part_render_data_dxf(
                piece.render_data, output,
            ).ok
    assert original == untouched


def test_saved_boxbody_with_missing_physical_fold_cannot_export(tmp_path):
    original = _saved()
    filename = project.write_project(
        tmp_path / "invalid-body-fold.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    reloaded = project.read_project(filename)["snapshot"]
    reloaded["box_body_fold_profile"] = ()
    with pytest.raises((ValueError, TypeError)):
        _parts(reloaded)
    assert not (tmp_path / "invalid-export").exists()
