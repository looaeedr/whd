"""#2517: actual Vault Door .p6fold → canonical 2D → folded 3D → verified DXF."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
import phase6_project_file as project
from tests.test_issue2517_direct_door_partspec_original_source_engine_gate import (
    _row, _spec, _gui,
)


def _physical_outputs(source, context):
    direct = _spec(source)
    from_gui = _gui(source)
    render = api.build_part_render_data(direct, context)
    via_gui = api.build_part_render_data(from_gui, context)
    profiles = api.build_standard_part_fold_profiles(source, "door")
    mesh = api.project_independent_part_view_mesh(
        "door", render, x_profile=profiles["X"], y_profile=profiles["Y"],
        thickness=source["t"],
    )
    gui_mesh = api.project_independent_part_view_mesh(
        "door", via_gui, x_profile=profiles["X"], y_profile=profiles["Y"],
        thickness=source["t"],
    )
    assert render.scene == via_gui.scene
    assert render.material.equals(via_gui.material)
    assert render.fold_guides == via_gui.fold_guides
    assert mesh.triangles and mesh.triangles == gui_mesh.triangles
    assert mesh.x_profile == gui_mesh.x_profile
    assert mesh.y_profile == gui_mesh.y_profile
    assert all(len(face) == 3 for face in mesh.triangles)
    return render, mesh, from_gui


def test_real_vault_door_save_reload_2d_folded_3d_and_gui_headless_dxf_agree(
    tmp_path,
):
    original = _row()
    original["door_fold_l"] = 18.0
    original["door_fold_r"] = 17.0
    before = deepcopy(original)
    context = ManufacturingContext(
        resource_root=Path(__file__).resolve().parents[1],
        draw_stock=False,
    )

    # Prove the physical source BEFORE and AFTER a real project serialization.
    source_render, source_mesh, _ = _physical_outputs(original, context)
    destination = project.write_project(
        tmp_path / "vault-door-authoritative.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    saved = project.read_project(destination)["snapshot"]
    assert {key: saved[key] for key in (
        "model", "w", "h", "d", "t", "fw",
        "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b",
        "door_gap_w", "door_gap_h",
    )} == {key: original[key] for key in (
        "model", "w", "h", "d", "t", "fw",
        "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b",
        "door_gap_w", "door_gap_h",
    )}
    restored_render, restored_mesh, gui_spec = _physical_outputs(saved, context)
    assert restored_render.scene == source_render.scene
    assert restored_render.fold_guides == source_render.fold_guides
    assert restored_render.material.equals(source_render.material)
    assert restored_mesh.triangles == source_mesh.triangles

    # GUI and headless export the exact same physical FinalScene, not preview.
    actual_file = tmp_path / "door-gui-finalscene.dxf"
    saved_dxf = api.save_part_render_data_dxf(
        restored_render, actual_file, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(restored_render, saved_dxf).ok
    doc = ezdxf.readfile(actual_file)
    assert doc.audit().errors == []
    layers = Counter(entity.dxf.layer for entity in doc.modelspace())
    assert layers["CUTTING"] > 0
    assert layers["BEND"] > 0

    direct_file = tmp_path / "door-headless-generated.dxf"
    generated = api.generate_part(gui_spec, direct_file, context)
    assert generated.output_path == str(direct_file)
    assert ezdxf.readfile(direct_file).audit().errors == []
    assert api.verify_saved_part_render_data_dxf(restored_render, direct_file).ok
    assert original == before


@pytest.mark.parametrize("invalid", (True, 0, -2, "nan", float("inf")))
def test_invalid_real_project_thickness_cannot_publish_door_2d_3d_or_dxf(
    tmp_path, invalid,
):
    source = {**_row(), "t": invalid}
    target = tmp_path / "invalid-door.p6fold"
    with pytest.raises(ValueError):
        project.write_project(
            target, {"schema": project.PROJECT_SCHEMA, "snapshot": source},
        )
    assert not target.exists()
    render_dxf = tmp_path / "invalid-door.dxf"
    ctx = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    with pytest.raises((ValueError, TypeError)):
        api.build_part_render_data(_spec(source), ctx)
    assert not render_dxf.exists()
