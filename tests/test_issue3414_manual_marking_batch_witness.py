"""#3414 staged first batch: selected saved MARKING witness, physical identity, atomic DXF.

The original #3412/#3413 Receiving LEFT BasePlate Engine source is used:
other Family/Set/Bay targets are NOT implicitly certified by these tests.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.operator_manual_marking_batch import witness_selected_manual_marking_rows
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet
from tests.test_issue3413_manual_group_engine import _group


def _one(render):
    return ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("base_plate", render),
    ))


def _marked(actual_sheet, *, center=Vec2(100, 100), pattern="solid"):
    _, render, _ctx, _, _ = actual_sheet
    group = _group(actual_sheet, center=center, pattern=pattern, dash=2, gap=5)
    return api.with_physical_sheet_features("base_plate", render, (group,))


def test_selected_composed_marked_real_flats_preserve_distinct_variants(actual_sheet, tmp_path):
    a = _marked(actual_sheet)
    b = _marked(actual_sheet, center=Vec2(130, 100))
    # Identical CUTTING and finite BEND, distinct authorized MARKING:
    # compact quantity mode may not collapse them into one machining pattern.
    assert a.material.equals(b.material)
    assert tuple(p for p in a.scene.primitives if p.layer in ("CUTTING", "BEND")) == tuple(
        p for p in b.scene.primitives if p.layer in ("CUTTING", "BEND"))
    output = tmp_path / "composed.dxf"
    result = api.save_composed_panel_dxf(
        (("Bay-A", _one(a)), ("Bay-B", _one(b))), output,
        pre_commit_guard=lambda: None, quantity_summary=True,
        compact_quantity_total=True, overwrite=True,
    )
    assert len(result.sheets) == 2
    doc = ezdxf.readfile(output)
    assert doc.header["$INSUNITS"] == 4
    assert len([e for e in doc.modelspace() if e.dxf.layer == "MARKING"]) == (
        len([p for p in a.scene.primitives if p.layer == "MARKING"])
        + len([p for p in b.scene.primitives if p.layer == "MARKING"])
    )


def test_selected_marking_mutated_during_composed_stage_keeps_prior_dxf(actual_sheet, tmp_path):
    real = _marked(actual_sheet, pattern="dashed")
    unselected = _marked(actual_sheet, center=Vec2(135, 100))
    # Only Bay-A is selected. An unrelated different Bay is not validated.
    witness = witness_selected_manual_marking_rows((("Bay-A:base_plate", real),))
    witness.assert_current()
    unselected.metadata["manual_marking_v1_features"] = ("invalid_unselected",)
    witness.assert_current()

    target = tmp_path / "existing.dxf"
    target.write_bytes(b"prior-cutting-data")
    calls = []
    def live_guard():
        calls.append("source-check")
        if len(calls) == 2:
            real.metadata["manual_marking_v1_features"] = (
                replace(real.metadata["manual_marking_v1_features"][0], offset=Vec2(130, 120)),
            )

    with pytest.raises(ValueError, match="MANUAL_MARKING|MANUAL_BATCH"):
        api.save_composed_panel_dxf(
            (("Bay-A", _one(real)),), target,
            pre_commit_guard=live_guard, overwrite=True,
        )
    assert len(calls) == 2
    assert target.read_bytes() == b"prior-cutting-data"


def test_marked_selected_source_wrong_physical_owner_is_rejected(actual_sheet, tmp_path):
    rendered = _marked(actual_sheet)
    with pytest.raises(ValueError, match="MANUAL_BATCH_SELECTED_PHYSICAL_ID_MISMATCH"):
        witness_selected_manual_marking_rows(
            (("foreign_bay:another_part", rendered),)
        )
    target = tmp_path / "existing.dxf"
    target.write_bytes(b"old")
    # A lookalike output key cannot retag the original base_plate source.
    with pytest.raises(ValueError, match="MANUAL_BATCH_SELECTED_PHYSICAL_ID_MISMATCH"):
        api.save_resolved_manufacturing_geometry_dxf(
            ResolvedManufacturingGeometry(parts=(
                ResolvedManufacturingPart("door", rendered),
            )), tmp_path, overwrite=True,
        )
    assert target.read_bytes() == b"old"


def test_unselected_other_bay_with_invalid_marking_does_not_block_selected(actual_sheet, tmp_path):
    selected = _marked(actual_sheet)
    other = _marked(actual_sheet, center=Vec2(135, 100))
    other.metadata["manual_marking_v1_features"] = ("untrusted",)
    destination = tmp_path / "selected.dxf"
    api.save_composed_panel_dxf(
        (("Bay-A", _one(selected)),), destination,
        pre_commit_guard=lambda: None,
    )
    assert destination.exists()
    assert ezdxf.readfile(destination).header["$INSUNITS"] == 4
