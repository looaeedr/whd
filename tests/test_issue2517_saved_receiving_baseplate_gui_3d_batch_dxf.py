"""#2517 configured Receiving BasePlate: saved GUI/Engine 2D, 3D, real DXFs.

One physical saved LEFT sheet, not a fabricated NFB tier base or full
cabinet certification. The GUI source adapter and the independent verified
Engine Bay sink both consume the same public typed physical PartSpec.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry import folded_mesh_from_polygon
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from gui_modules.application import manufacturing_adapter as gui_spec
from gui_modules.application import fold_designer_snapshot_projection as gui_2d
from gui_modules.application import fold_designer_manufacturing_projection as gui_dxf
import phase6_project_file as project

from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import (
    _configured, _part_spec, _controls,
)

ROOT = Path(__file__).resolve().parents[1]


def _readback(tmp_path, source):
    before = deepcopy(source)
    project_path = project.write_project(
        tmp_path / "configured-receiving-base.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    loaded = project.read_project(project_path)["snapshot"]
    assert project_path.is_file()
    assert loaded.get("receiving_base_plate") == before.get("receiving_base_plate")
    assert source == before
    return loaded


def _actual_gui_base_spec(values):
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            box_body_structure_state=lambda: None,
            box_body_profile=lambda: (),
        ),
        surface_features={"base_plate": []},
        _manual_corner_policy=lambda *_args: None,
    )
    host._base_plate_part_spec_from_values = lambda val, **kw: (
        gui_spec._base_plate_part_spec_from_values(host, val, **kw)
    )
    return gui_spec._base_plate_part_spec(host, values)


def _actual_gui_dxf(spec, scene, path, ctx):
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _require_verified_baseline_sources_for_manufacturing=lambda: None,
        _authoritative_render_data=lambda given_spec, given_ctx: (
            scene if given_spec is spec and given_ctx is ctx else None
        ),
    )
    return gui_dxf._export_authoritative_part(host, spec, path, ctx)


@pytest.mark.parametrize("model", ("受電箱", "receiving", "ReCeIvInG"))
def test_saved_configured_baseplate_gui_2d_3d_independent_engine_batch_dxf(
    tmp_path, model,
):
    authored = _configured(model)
    loaded = _readback(tmp_path, authored)
    ctx = ManufacturingContext(resource_root=ROOT, draw_stock=False)
    before_2d = api.project_fold_designer_snapshot_dimensions(
        authored, [2],
    ).part_dimensions["base_plate"]
    after_2d = api.project_fold_designer_snapshot_dimensions(
        loaded, [2],
    ).part_dimensions["base_plate"]
    assert before_2d == after_2d
    gui_copy = deepcopy(loaded)
    gui_2d._snapshot_part_dimensions(_controls([2]), gui_copy)
    assert gui_copy["part_dimensions"]["base_plate"] == before_2d

    values, headless = _part_spec(loaded)
    original_values, original_spec = _part_spec(authored)
    gui = _actual_gui_base_spec(values)
    assert gui.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
    assert gui.bend == headless.bend == original_spec.bend == 20.0
    assert gui.model_name == headless.model_name == model.strip()
    assert gui.physical_id == headless.physical_id == "base_plate"
    assert gui.receiving_nfb_depth_pair_mm is None
    assert original_values == values
    original_scene = api.build_operator_part_render_data(original_spec, ctx)
    canonical = api.build_operator_part_render_data(headless, ctx)
    gui_scene = api.build_operator_part_render_data(gui, ctx)
    assert canonical.material.is_valid and not canonical.material.is_empty
    assert canonical.scene == original_scene.scene == gui_scene.scene
    assert canonical.fold_guides == original_scene.fold_guides == gui_scene.fold_guides
    assert canonical.material.equals(original_scene.material)
    assert canonical.material.equals(gui_scene.material)
    assert {p.layer for p in canonical.scene.primitives} >= {"CUTTING", "BEND"}

    # Both input snapshots drive the real pre-existing Fold profile, then the
    # exact same Engine FinalScene material becomes formed 3D triangles.
    xy = api.build_standard_part_fold_profiles(loaded, "base_plate")
    assert xy == api.build_standard_part_fold_profiles(authored, "base_plate")
    def mesh(render):
        return folded_mesh_from_polygon(
            render.material, xy["X"], xy["Y"],
            fold_guides=render.fold_guides,
        )
    assert mesh(canonical)
    assert mesh(original_scene) == mesh(canonical) == mesh(gui_scene)
    assert any(
        abs(float(vertex[2])) > 1e-7
        for tri in mesh(gui_scene) for vertex in tri
    )

    ui_path = tmp_path / "gui-base-actual.dxf"
    exported = _actual_gui_dxf(gui, gui_scene, ui_path, ctx)
    assert Path(exported) == ui_path
    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "confirmed-source", "Set-physical", "Bay-physical",
        ),
        confirmed_parts=(("base_plate", gui),),
    )
    checked = []
    batch = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "independent-engine-batch",
        context=ctx,
        pre_commit_guard=lambda: checked.append("original-source-current"),
    )
    assert checked == ["original-source-current", "original-source-current"]
    assert batch.physical_dxf_roundtrip_verified
    assert not batch.complete_assembly_certified
    assert len(batch.output_files) == 1
    engine_path = Path(next(iter(batch.output_files.values())))
    for path in (ui_path, engine_path):
        assert path.is_file()
        reopened = ezdxf.readfile(path)
        assert reopened.audit().errors == []
        layers = {entity.dxf.layer for entity in reopened.modelspace()}
        assert {"CUTTING", "BEND"} <= layers
        assert api.verify_saved_part_render_data_dxf(
            canonical, path,
        ).ok
        assert api.verify_saved_part_render_data_dxf(
            gui_scene, path,
        ).ok
    assert loaded["receiving_base_plate"] == authored["receiving_base_plate"]


def test_saved_unconfigured_receiving_baseplate_gui_cannot_replace_previous_dxf(
    tmp_path,
):
    configured = _configured("受電箱")
    source = deepcopy(configured)
    source.pop("receiving_base_plate")
    loaded = _readback(tmp_path, source)
    values, _ = _part_spec(loaded)
    spec = _actual_gui_base_spec(values)
    assert spec.receiving_bend_pattern is None
    ctx = ManufacturingContext(resource_root=ROOT, overwrite=True)
    render = api.build_operator_part_render_data(spec, ctx)
    assert render.metadata["receiving_base_plate_unconfigured"] is True
    existing = tmp_path / "old-physical-base.dxf"
    good_values, good_spec = _part_spec(configured)
    previous = api.build_operator_part_render_data(good_spec, ctx)
    api.save_part_render_data_dxf(
        previous, existing, verify_reopen=True,
    )
    old_bytes = existing.read_bytes()
    with pytest.raises(
        ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING",
    ):
        _actual_gui_dxf(spec, render, existing, ctx)
    assert existing.read_bytes() == old_bytes
    assert api.verify_saved_part_render_data_dxf(previous, existing).ok
