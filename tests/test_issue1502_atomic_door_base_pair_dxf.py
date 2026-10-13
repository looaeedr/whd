# -*- coding: utf-8 -*-
"""#1502 one committed Bay -> two real, reopened, atomic PART_ONLY DXFs."""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from gui_modules.application.receiving_nfb_pair_partial_export_action import (
    export_verified_receiving_nfb_door_base_pair,
)
from tests.test_issue1502_live_nfb_base_partial_export import _live


def _ready(tmp_path, pattern="LEFT_FLAT_SIDE"):
    fixture = _live(tmp_path, pattern=pattern)
    # The fixture's lightweight switch index must be a real operator-format
    # catalog for manufacturing's fresh MFG-1 door construction.
    fixture.index.write_text(
        "圖塊名稱,士林,深,東元,深,伍菱,深\n"
        "SH400,400_140X257_107.dxf,107,無對應檔案,,無對應檔案,\n",
        encoding="utf-8-sig",
    )
    return fixture


def _write(fixture, root):
    return export_verified_receiving_nfb_door_base_pair(
        fixture.bundle, layout=fixture.layout,
        current_snapshot=fixture.snapshot, base_spec=fixture.plate,
        output_directory=root, index_path=fixture.index,
        profile_path=fixture.profile,
    )


@pytest.mark.parametrize("pattern", (
    "LEFT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD", "RIGHT_FLAT_SIDE",
))
def test_same_submitted_nfb_produces_two_real_dxf_golden_atomically(tmp_path, pattern):
    fixture = _ready(tmp_path, pattern)
    target = tmp_path / "paired"
    target.mkdir()
    result = _write(fixture, target)
    assert result.scope == "PAIR_PART_ONLY_NOT_WHOLE_CABINET"
    assert result.receipt.physical_part_count == 2
    assert result.receipt.nfb_instance_count == 2
    assert result.receipt.native_screw_cut_count == 8
    assert result.receipt.approval_scope == "PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2"
    files = tuple(target.glob("*.dxf"))
    assert len(files) == 2
    assert {str(p) for p in files} == {result.inner_door_path, result.base_plate_path}
    assert all(p.name.startswith("setA__bayA__") for p in files)
    inner = ezdxf.readfile(result.inner_door_path).modelspace()
    base = ezdxf.readfile(result.base_plate_path).modelspace()
    # Each real door opening is a closed CUTTING contour, not a preview line.
    inner_cuts = tuple(x for x in inner if x.dxftype() == "LWPOLYLINE"
                       and x.dxf.layer == "CUTTING" and x.closed)
    assert len(inner_cuts) == 3  # physical door blank + 2 actual NFB cutouts
    base_screws = tuple(x for x in base if x.dxftype() == "CIRCLE"
                        and x.dxf.layer == "CUTTING")
    assert len(base_screws) == 16  # native source Color30 + 4 lower screws x 2
    # Both staged DXFs passed the canonical full geometry reopen before commit.
    assert not list(target.glob(".whd-*"))


def test_pair_atomic_existing_file_does_not_write_missing_second_dxf(tmp_path):
    fixture = _ready(tmp_path)
    root = tmp_path / "blocked"
    root.mkdir()
    from ae_engine.manufacturing_export import (
        resolved_physical_dxf_filename, receiving_instance_namespace,
    )
    name = resolved_physical_dxf_filename(
        "base_plate", box_body_physical_piece_roles=(),
        instance_namespace=receiving_instance_namespace(set_id="setA",bay_id="bayA"),
    )
    occupied = root / name
    occupied.write_bytes(b"ORIGINAL_USER_DXF")
    with pytest.raises(FileExistsError):
        _write(fixture, root)
    assert occupied.read_bytes() == b"ORIGINAL_USER_DXF"
    assert list(root.iterdir()) == [occupied]


@pytest.mark.parametrize("change", (
    "saved_rotation", "saved_x", "source_changed", "wrong_base_pattern",
))
def test_pair_source_config_or_part_change_fails_before_output(tmp_path, change):
    fixture = _ready(tmp_path)
    root = tmp_path / "no_output"
    root.mkdir()
    if change == "saved_rotation":
        fixture.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["rotation_deg"] = 180
    elif change == "saved_x":
        fixture.layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_mm"] = -85.
    elif change == "source_changed":
        document = ezdxf.readfile(fixture.original)
        document.modelspace().add_lwpolyline(
            ((100.,370.),(120.,370.),(120.,400.),(100.,400.)),
            close=True,dxfattribs={"color":150},
        )
        document.saveas(fixture.original)
    elif change == "wrong_base_pattern":
        fixture.plate = replace(fixture.plate, bend=fixture.plate.bend+3)
    with pytest.raises((ValueError, TypeError)):
        _write(fixture, root)
    assert list(root.iterdir()) == []


def test_pair_only_does_not_enable_whole_cabinet_dxf_or_add_bend_compensation(tmp_path):
    fixture = _ready(tmp_path)
    root = tmp_path / "paired"
    root.mkdir()
    receipt = _write(fixture, root)
    assert receipt.receipt.approval_scope != "WHOLE_MFG2_APPROVED"
    assert receipt.receipt.native_screw_cut_count == 8
    assert receipt.receipt.physical_part_count == 2
