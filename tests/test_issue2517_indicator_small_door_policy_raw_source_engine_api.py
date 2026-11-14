"""#2517: the original SmallDoor policy API must validate raw FW, Gap and Fold."""
from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_door_indicator as owner
from gui_modules.application import manufacturing_adapter as gui


def _data():
    return {
        "model": "金庫型", "w": 800.0, "h": 1100.0, "d": 350.0,
        "t": 2.125, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "indicator_door_fold": 19.0,
    }


def _engine(row):
    return api.indicator_small_door_operator_spec(
        [2, 3], thickness=row["t"], frame_width=row["fw"],
        door_gap_w=row["door_gap_w"], door_gap_h=row["door_gap_h"],
        indicator_door_fold=row.get("indicator_door_fold"),
        features=(),
    )


@pytest.mark.parametrize("field,bad", [
    ("fw", True), ("fw", False), ("fw", 0), ("fw", -2),
    ("fw", None), ("fw", "nan"), ("fw", "inf"), ("fw", "bad"),
    ("door_gap_w", True), ("door_gap_w", False),
    ("door_gap_w", "nan"), ("door_gap_w", "-inf"), ("door_gap_w", None),
    ("door_gap_h", True), ("door_gap_h", "inf"), ("door_gap_h", "bad"),
    ("indicator_door_fold", True), ("indicator_door_fold", False),
    ("indicator_door_fold", "nan"), ("indicator_door_fold", "inf"),
    ("indicator_door_fold", "bad"),
])
@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_gui_and_headless_refuse_invalid_small_door_policy_source(
    field, bad, family, tmp_path,
):
    row = _data()
    row["model"] = family
    row[field] = bad
    original = deepcopy(row)
    with pytest.raises((TypeError, ValueError)):
        _engine(row)
    with pytest.raises((TypeError, ValueError)):
        gui._indicator_door_part_spec_from_values(
            None, row, [2, 3], features=(),
        )
    assert row == original
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_signed_finite_gaps_and_fold_are_preserved_in_canonical_engine_spec(model):
    row = _data()
    row.update(model=model, fw="29", door_gap_w="-0.5",
               door_gap_h=0.0, indicator_door_fold="-2.125")
    prior = deepcopy(row)
    spec, context = _engine(row)
    via_gui = gui._indicator_door_part_spec_from_values(
        None, row, [2, 3], features=(),
    )
    assert (spec, context) == via_gui
    assert spec.thickness == pytest.approx(2.125)
    assert context.policy.frame_width == pytest.approx(29)
    assert context.policy.door_gap_w == pytest.approx(-0.5)
    assert context.policy.door_gap_h == pytest.approx(0)
    assert spec.fold_top == pytest.approx(-2.125)
    assert spec.gap_w == pytest.approx(-0.5)
    assert row == prior


def test_project_reopen_keeps_original_physical_small_door_policy_and_real_dxf(tmp_path):
    import phase6_project_file as project

    row = _data()
    saved_file = project.write_project(
        tmp_path / "small-door-policy.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": row},
    )
    reopened = project.read_project(saved_file)["snapshot"]
    for key in ("t", "fw", "door_gap_w", "door_gap_h"):
        assert reopened[key] == row[key]

    spec, context = _engine(row)
    via_gui = gui._indicator_door_part_spec_from_values(
        None, reopened, [2, 3], features=(),
    )
    assert via_gui == (spec, context)
    assert spec.indicator_window_groups == (2, 3)
    assert spec.thickness == pytest.approx(2.125)

    # The existing Engine exporter uses the committed Indicator '小門.dxf'
    # as the qualified shared baseline; real DXF is independently reopened.
    root = Path(__file__).resolve().parents[1]
    assert (root / "基準檔" / "指示燈" / "小門.dxf").is_file()
    from dataclasses import replace
    from ae_engine.contracts import ManufacturingContext
    actual_context = replace(context, resource_root=root)
    dest = tmp_path / "indicator-small-door.dxf"
    api.generate_part(spec, dest, actual_context)
    reopened_dxf = ezdxf.readfile(dest)
    layers = {e.dxf.layer for e in reopened_dxf.modelspace()}
    assert "CUTTING" in layers
    assert "BEND" in layers


def test_one_original_engine_contract_owns_full_small_door_policy_projection():
    code = inspect.getsource(owner.indicator_small_door_operator_spec)
    assert 'normalize_operator_source_dimension(frame_width, field="fw")' in code
    assert '_finite_operator_number(door_gap_w, "door_gap_w")' in code
    assert '_finite_operator_number(door_gap_h, "door_gap_h")' in code
    assert '_finite_operator_number(fold_source, "indicator_door_fold")' in code
    assert "frame_width=float(frame_width)" not in code
    assert "door_gap_w=float(door_gap_w)" not in code
    assert "door_gap_h=float(door_gap_h)" not in code
    gui_code = inspect.getsource(gui._indicator_door_part_spec_from_values)
    assert "manufacturing_api.indicator_small_door_operator_spec(" in gui_code
    assert "float(" not in gui_code
