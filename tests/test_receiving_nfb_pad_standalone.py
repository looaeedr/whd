# -*- coding: utf-8 -*-
"""Independent PAD entry point must never promote a draft to MFG output."""
import json
import pytest

from ae_engine.receiving_nfb_pad_standalone import (
    PadSelection, build_pad_preview, export_draft_pad_dxf,
)


def test_current_numeric_v5_source_generates_real_39mm_pad_without_cabinet():
    plan = build_pad_preview(
        [PadSelection(1, "士林", "3P400SN"),
         PadSelection(1, "士林", "100HN-s")],
        plate_thickness_mm=2,
    )
    assert len(plan.jobs) == 1
    job, = plan.jobs
    assert (job.tier, job.selected_index) == (1, 1)
    assert (job.pattern.rise_mm, job.pattern.blank_width_mm) == (39, 145)
    assert job.pattern.manufacturing_ready is False


def test_each_tier_owns_its_own_deepest_reference_and_pad():
    plan = build_pad_preview(
        [PadSelection(1, "士林", "3P400SN"),
         PadSelection(1, "士林", "100HN-s"),
         PadSelection(2, "士林", "100HN-s"),
         PadSelection(2, "士林", "100HN-s")],
        plate_thickness_mm=2,
    )
    assert [(j.tier, j.selected_index, j.pattern.rise_mm)
            for j in plan.jobs] == [(1, 1, 39)]


def test_unknown_or_incomplete_or_invalid_tier_fail_closed():
    for rows in (
        [], [PadSelection(1, "士林", "MISSING-MODEL")],
        [PadSelection(True, "士林", "3P400SN")],
        [PadSelection(0, "士林", "3P400SN")],
    ):
        with pytest.raises(ValueError):
            build_pad_preview(rows, plate_thickness_mm=2)


def test_equal_depth_requires_no_pad():
    plan = build_pad_preview(
        [PadSelection(3, "士林", "100HN-s"),
         PadSelection(3, "士林", "100HN-s")],
        plate_thickness_mm=2,
    )
    assert plan.jobs == ()
    with pytest.raises(ValueError):
        export_draft_pad_dxf(plan, "/unused")


def test_draft_dxf_is_visibly_nonmanufacturing_and_cannot_overwrite(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    plan = build_pad_preview(
        [PadSelection(1, "士林", "3P400SN"),
         PadSelection(1, "士林", "100HN-s")],
        plate_thickness_mm=2,
    )
    folder = tmp_path / "new-draft-folder"
    result = export_draft_pad_dxf(plan, folder)
    assert len(result) == 1
    doc = ezdxf.readfile(result[0])
    entities = tuple(doc.modelspace())
    assert len([x for x in entities if x.dxftype() == "LWPOLYLINE"]) == 1
    assert len([x for x in entities if x.dxftype() == "LINE"]) == 2
    assert len([x for x in entities if x.dxftype() == "CIRCLE"]) == 4
    assert all(x.dxf.layer.startswith("DRAFT_") for x in entities)
    assert any("NOT FOR MANUFACTURING" in x.dxf.text
               for x in entities if x.dxftype() == "TEXT")
    receipt = json.loads(
        (folder / "DRAFT_NOT_FOR_MANUFACTURING.json").read_text(encoding="utf-8")
    )
    assert receipt["manufacturing_ready"] is False
    assert receipt["pads"][0]["rise_mm"] == 39
    with pytest.raises(FileExistsError):
        export_draft_pad_dxf(plan, folder)
