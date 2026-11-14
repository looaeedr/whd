"""#2517: an explicit headless DoorPartSpec must not bypass GUI's Engine source gate."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from gui_modules.application import manufacturing_adapter as gui


def _row():
    return {
        "model": "金庫型", "w": 800.0, "h": 1100.0,
        "d": 350.0, "t": 2.125, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 15.0, "door_fold_r": 15.0,
        "door_fold_t": 15.0, "door_fold_b": 15.0,
    }


def _spec(row):
    return DoorPartSpec(
        width=row["w"], height=row["h"], thickness=row["t"],
        frame_width=row["fw"], model_name=row["model"],
        gap_w=row["door_gap_w"], gap_h=row["door_gap_h"],
        fold_left=row["door_fold_l"], fold_right=row["door_fold_r"],
        fold_top=row["door_fold_t"], fold_bottom=row["door_fold_b"],
    )


def _gui(row):
    return gui._door_part_spec_from_values(
        SimpleNamespace(door_nameplate_center_datum_top=None),
        row, model_name=row["model"], features=(),
    )


_BAD = [
    ("w", True), ("w", False), ("w", 0), ("w", -10),
    ("h", True), ("h", "nan"), ("h", None),
    ("t", True), ("t", 0), ("t", "inf"), ("t", -2),
    ("fw", True), ("fw", False), ("fw", 0), ("fw", "nan"),
    ("door_gap_w", True), ("door_gap_w", "nan"),
    ("door_gap_h", False), ("door_gap_h", "inf"),
    ("door_fold_l", True), ("door_fold_l", "-inf"),
    ("door_fold_r", False), ("door_fold_r", "bad"),
    ("door_fold_t", True), ("door_fold_t", "nan"),
    ("door_fold_b", False), ("door_fold_b", "inf"),
]


@pytest.mark.parametrize("field,bad", _BAD)
@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_invalid_direct_physical_spec_fails_before_finalscene_or_dxf(
    field, bad, model, tmp_path,
):
    row = _row()
    row.update(model=model)
    row[field] = bad
    original = deepcopy(row)
    direct = _spec(row)
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    with pytest.raises((ValueError, TypeError)):
        api.door_finished_face_size(direct, context)
    with pytest.raises((ValueError, TypeError)):
        api.build_part_render_data(direct, context)
    output = tmp_path / "rejected-manufacturing.dxf"
    with pytest.raises((ValueError, TypeError)):
        api.generate_part(direct, output, context)
    with pytest.raises((ValueError, TypeError)):
        _gui(row)
    assert not output.exists()
    assert row == original


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_valid_signed_door_gap_fold_preserves_original_engine_physical_values(model):
    row = _row()
    row.update(model=model, door_gap_w="-0.5", door_gap_h="0",
               door_fold_l="-2.125", door_fold_t="0")
    original = deepcopy(row)
    from ae_engine.manufacturing_door_indicator import _resolved_door_params
    params = _resolved_door_params(_spec(row))
    assert params["gap_w"] == pytest.approx(-0.5)
    assert params["gap_h"] == pytest.approx(0)
    assert params["fold_left"] == pytest.approx(-2.125)
    assert params["fold_top"] == pytest.approx(0)
    assert params["t"] == pytest.approx(2.125)
    assert row == original


def test_vault_door_direct_headless_and_original_gui_have_same_canonical_scene_dxf(tmp_path):
    import phase6_project_file as project

    row = _row()
    path = project.write_project(
        tmp_path / "direct-door-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": row},
    )
    reopened = project.read_project(path)["snapshot"]
    for field in ("w", "h", "t", "fw", "door_gap_w", "door_gap_h"):
        assert reopened[field] == row[field]
    direct = _spec(reopened)
    from_gui = _gui(reopened)
    # The GUI declares legacy feature-space, not new material geometry.
    assert replace(direct, feature_space=from_gui.feature_space) == from_gui

    root = Path(__file__).resolve().parents[1]
    assert (root / "基準檔" / "金庫型" / "門.dxf").is_file()
    context = ManufacturingContext(resource_root=root)
    a = api.build_part_render_data(direct, context)
    b = api.build_part_render_data(from_gui, context)
    assert a.material is not None and not a.material.is_empty
    assert a.scene == b.scene
    assert api.door_finished_face_size(direct, context) == (
        api.door_finished_face_size(from_gui, context)
    )
    output = tmp_path / "canonical-door.dxf"
    saved = api.save_part_render_data_dxf(a, output, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(a, saved).ok
    assert any(e.dxf.layer == "CUTTING" for e in ezdxf.readfile(output).modelspace())
    ordinary_dxf = tmp_path / "generated-door.dxf"
    result = api.generate_part(direct, ordinary_dxf, context)
    assert result.output_path == str(ordinary_dxf)
    assert ordinary_dxf.is_file()
    assert any(e.dxf.layer == "BEND" for e in ezdxf.readfile(ordinary_dxf).modelspace())


def test_direct_door_physical_source_gate_is_original_engine_not_a_gui_parser():
    from ae_engine.manufacturing_door_indicator import _resolved_door_params
    source = inspect.getsource(_resolved_door_params)
    for field in ("w", "h", "t", "fw"):
        assert f'normalize_operator_source_dimension(spec.{ {"w":"width", "h":"height", "t":"thickness", "fw":"frame_width"}[field]}, field="{field}")' in source
    for name in ("door_gap_w", "door_gap_h", "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b"):
        assert f'"{name}"' in source
    assert "float(spec.thickness)" not in source
    assert "w=float(spec.width)" not in source
    gui_code = inspect.getsource(gui._door_part_spec_from_values)
    assert "manufacturing_api.build_door_operator_part_spec(" in gui_code
    assert "DoorPartSpec(" not in gui_code
