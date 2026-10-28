# -*- coding: utf-8 -*-
"""#1702 — single Receiving cabinet acceptance at an exact GitHub localX candidate.

This is validation only. It does not change product geometry or install any
second manufacturing source of truth. Single cabinet means ONE Set/Bay; it is
not synonymous with one inner-door tier.
"""
from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.manufacturing_api import resolved_quantity_physical_demands
from ae_engine.manufacturing_quantity import ResolvedQuantityVersion
from ae_engine.receiving_mfg2_software_receipt import RECEIPT_FILENAME
from phase6_project_file import PROJECT_SCHEMA_V2, read_project, write_project
from tests.test_issue1502_single_button_full_csv_receiving_export import (
    _prepare,
    _run,
)


def _one_cabinet_source():
    source, geometry = _prepare(False)
    layout = source["receiving_layout"]
    assert len(layout["sets"]) == 1, "Single-cabinet acceptance cannot silently use multiple Sets"
    assert len(layout["sets"][0]["bays"]) == 1, "Single-cabinet acceptance cannot silently use multiple Bays"
    assert source["model"] == "受電箱"
    return source, geometry


def test_single_receiving_true_panel_dimensions_physical_bom_and_project_reload(tmp_path: Path):
    source, geometry = _one_cabinet_source()
    panels = derive_inner_door_panels(source)
    assert [p.stable_id for p in panels] == ["inner_door:upper:panel"]
    panel = panels[0]
    # Independently approved W800/T2, 1100-mm upper cell dimensional datum.
    assert panel.width == pytest.approx(689.0)
    assert panel.height == pytest.approx(1041.0)
    assert panel.unfolded_width == pytest.approx(723.0)
    assert panel.unfolded_height == pytest.approx(1075.0)
    rendered = geometry.part(panel.stable_id).render_data
    assert rendered.material.area > 0
    assert tuple(rendered.fold_guides)
    assert any(p.layer == "CUTTING" for p in rendered.scene.primitives)
    assert any(p.layer == "BEND" for p in rendered.scene.primitives)

    demands = resolved_quantity_physical_demands(
        (ResolvedQuantityVersion("single-cabinet", 1, geometry),)
    )
    demand = [row for row in demands if row.physical_id == panel.stable_id]
    assert len(demand) == 1 and demand[0].quantity == 1
    assert not any(row.physical_id == "inner_door:lower:panel" for row in demands)
    assert any(row.physical_id.endswith("left_side") for row in demands)
    assert any(row.physical_id.endswith("right_side") for row in demands)

    project = write_project(
        tmp_path / "single-cabinet.p6fold",
        {"schema": PROJECT_SCHEMA_V2, "snapshot": source},
    )
    persisted = read_project(project)
    assert persisted["final_geometry"] == {}
    restored_panels = derive_inner_door_panels(persisted["snapshot"])
    assert [p.stable_id for p in restored_panels] == [panel.stable_id]
    reloaded = restored_panels[0]
    assert (reloaded.width, reloaded.height, reloaded.unfolded_width, reloaded.unfolded_height) == pytest.approx(
        (689.0, 1041.0, 723.0, 1075.0)
    )


def test_single_receiving_actual_full_export_reopens_all_dxfs_and_side_markings(tmp_path: Path):
    source, geometry = _one_cabinet_source()
    target = tmp_path / "single-cabinet-export"
    names, errors, calls = _run(source, geometry, target)
    assert errors == [] and calls == ["resolve"]
    assert RECEIPT_FILENAME in names
    receipt = json.loads((target / RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert receipt["status"] == "SOFTWARE_WHOLE_CABINET_DXF_SOURCE_CERTIFIED"
    physical = tuple(name for name in names if name.lower().endswith(".dxf"))
    assert len(physical) == receipt["output_dxf_count"]
    assert len(physical) == len(set(physical)) == len(list(target.glob("*.dxf")))
    assert any("inner_door" in name and "panel" in name for name in physical)

    for name in physical:
        doc = ezdxf.readfile(target / name)
        assert doc.modelspace() is not None, name
    for side in ("left_side", "right_side"):
        doc = ezdxf.readfile(target / f"box_body_box_body_{side}.dxf")
        marks = tuple(entity for entity in doc.modelspace()
                      if entity.dxftype() == "LINE"
                      and str(entity.dxf.layer).upper() == "MARKING")
        # A valid single cabinet must retain the physical divider-to-side
        # contact and inner-door-frame-to-side contact, never merely an EAR.
        assert len(marks) >= 2, (side, len(marks))
    originals = set(receipt["original_cabinet_physical_ids"])
    assert "inner_door:upper:panel" in originals
    assert not any(k.startswith("inner_door:lower:") for k in originals)
    assert receipt["nc_machine_format_certified"] is False
    assert receipt["factory_welding_workmanship_certified"] is False
