"""#2517: one configured Receiving BasePlate source for GUI 2D, 3D and real DXF."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

import phase6_project_file as project
from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry import folded_mesh_from_polygon
from ae_engine.contracts import ManufacturingContext
from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from gui_modules.application import fold_designer_snapshot_projection as gui
from tests.test_issue2517_fold_designer_snapshot_dimensions_engine_api import (
    _controls, snapshot as _root_source,
)


_ALIASES = ("受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  ")


def _configured(model="受電箱"):
    source = _root_source(model)
    source["base_plate_bend"] = 29.0  # deliberately contradict the real BEND20
    source["receiving_base_plate"] = {
        "pattern": RECEIVING_BASE_PATTERN_LEFT,
        "height": 340.0,
        "shrink_top": 20.0, "shrink_bottom": 20.0,
        "shrink_left": 45.0, "shrink_right": 45.0,
        "bend": 20.0,
    }
    return source


def _part_spec(source):
    values, policy = api.resolve_fold_designer_base_plate_source(
        "base_plate", source,
        width=source["w"], height=source["h"],
        thickness=source["t"], frame_width=source["fw"],
        model_name=source["model"], corner_policy=None,
    )
    assert policy is None
    return values, api.build_base_plate_operator_part_spec(
        values, features=(), corner_policy=policy,
    )


@pytest.mark.parametrize("model", _ALIASES)
def test_real_configured_base_plate_gui_and_public_engine_use_same_2d_source(model):
    original = _configured(model)
    before = deepcopy(original)
    expected = receiving_base_plate_blank_dimensions(original)
    assert expected is not None
    assert expected != (690.0, 1490.0)  # stale generic shrink fallback

    projection = api.project_fold_designer_snapshot_dimensions(original, [2])
    assert tuple(projection.part_dimensions["base_plate"].values()) == pytest.approx(expected)
    values, spec = _part_spec(original)
    assert values["h"] == 340.0
    assert values["base_plate_bend"] == 20.0
    assert values["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_LEFT
    assert spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
    assert spec.bend == 20.0
    assert spec.model_name == model.strip()

    gui_source = deepcopy(original)
    gui._snapshot_part_dimensions(_controls([2]), gui_source)
    assert gui_source["part_dimensions"] == projection.part_dimensions
    assert original == before


@pytest.mark.parametrize("model", _ALIASES)
def test_actual_p6fold_save_reload_preserves_root_2d_and_headless_part_spec(model, tmp_path):
    raw = _configured(model)
    first = api.project_fold_designer_snapshot_dimensions(raw, [2]).part_dimensions
    original = deepcopy(raw)
    output = project.write_project(
        tmp_path / "physical-base-alias.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": raw},
    )
    loaded = project.read_project(output)["snapshot"]
    assert loaded["receiving_base_plate"] == original["receiving_base_plate"]
    restored = api.project_fold_designer_snapshot_dimensions(loaded, [2]).part_dimensions
    assert restored["base_plate"] == first["base_plate"]
    values, spec = _part_spec(loaded)
    assert values["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_LEFT
    assert spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
    assert raw == original


@pytest.mark.parametrize("model", _ALIASES)
def test_same_real_flat_fold_3d_and_independently_reopened_dxf_for_family_alias(model, tmp_path):
    raw = _configured(model)
    values, spec = _part_spec(raw)
    assert values["h"] == 340.0
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    rendered = api.build_part_render_data(spec, context)
    assert not rendered.material.is_empty
    assert any(p.layer == "CUTTING" for p in rendered.scene.primitives)
    assert any(p.layer == "BEND" for p in rendered.scene.primitives)

    physical_profiles = api.build_standard_part_fold_profiles(raw, "base_plate")
    triangles = folded_mesh_from_polygon(
        rendered.material, physical_profiles["X"], physical_profiles["Y"],
        fold_guides=rendered.fold_guides,
    )
    assert triangles  # Actual shared 2D material and physical Fold form a real 3D mesh
    assert any(abs(float(vertex[2])) > 1e-7 for tri in triangles for vertex in tri)
    path = tmp_path / "real-configured-base.dxf"
    saved = api.save_part_render_data_dxf(
        rendered, path, overwrite=False, verify_reopen=True,
    )
    assert api.verify_saved_part_render_data_dxf(rendered, saved).ok
    reopened = ezdxf.readfile(path)
    layers = {entity.dxf.layer for entity in reopened.modelspace()}
    assert {"CUTTING", "BEND"} <= layers
    assert path.stat().st_size > 0


@pytest.mark.parametrize("model", ("receiving", "ReCeIvInG", "  receiving  "))
def test_missing_confirmed_receiving_pattern_never_writes_generic_base_dxf(model, tmp_path):
    raw = _configured(model)
    raw.pop("receiving_base_plate")
    _values, spec = _part_spec(raw)
    assert spec.receiving_bend_pattern is None
    target = tmp_path / "must-not-exist.dxf"
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING"):
        api.generate_part(
            spec, target,
            ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        )
    assert not target.exists()


def test_vault_source_never_borrows_configured_receiving_plate():
    data = _configured("金庫型")
    root = api.project_fold_designer_snapshot_dimensions(data, [2])
    assert root.part_dimensions["base_plate"] == {"width": 690.0, "height": 1490.0}
    values, spec = _part_spec(data)
    assert values["h"] == 1600.0
    assert spec.receiving_bend_pattern is None
    assert spec.bend == 29.0
