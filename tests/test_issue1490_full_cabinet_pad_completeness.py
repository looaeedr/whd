# -*- coding: utf-8 -*-
"""#1490: a valid PAD+Base pair cannot silently vanish from whole-cabinet DXF."""
from pathlib import Path

import pytest

from ae_engine.receiving_whole_cabinet_pad_preflight import (
    missing_required_pad_sheets,
)
from tests.test_receiving_nfb_pad_delivery import installed_pair
from tests.test_issue1502_single_button_full_csv_receiving_export import (
    _prepare, _run,
)


def test_committed_csv_actual_parent_requires_exact_pad_physical_owner():
    snap, installed = installed_pair()
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    demand, = resolve_committed_pad_physical_delivery(snap, installed)
    assert demand.full_thickness_contact_certified is True
    missing = missing_required_pad_sheets(snap, installed, ("base_plate",))
    assert missing == (demand.physical_id,)
    assert missing_required_pad_sheets(
        snap, installed, ("base_plate", demand.physical_id),
    ) == ()


def _strict_bundle(snapshot, geometry, folder):
    from ae_engine.receiving_ear_side_manufacturing_marking import (
        with_verified_receiving_ear_side_markings,
    )
    from ae_engine.receiving_fixed_plate_formed_manufacturing import (
        save_verified_receiving_formed_fixing_plate_bundle,
    )
    dimensions = tuple(float(snapshot[key]) for key in ("w", "h", "d"))
    marked = with_verified_receiving_ear_side_markings(
        snapshot, geometry, dimensions=dimensions,
        sheet_thickness=float(snapshot["t"]),
    )
    return save_verified_receiving_formed_fixing_plate_bundle(
        snapshot, geometry, marked, folder,
        dimensions=dimensions, sheet_thickness=float(snapshot["t"]),
        require_complete_cabinet_inventory=True,
    )


def test_explicit_complete_inventory_includes_real_pad_and_roundtrips(tmp_path):
    """Positive: existing GUI scene + verified PAD + EAR+SIDE all in one set."""
    import ezdxf
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    snap, geom = _prepare(False)
    pads = resolve_committed_pad_physical_delivery(snap, geom.parts)
    assert len(pads) == 1
    target = tmp_path / "certified_current_source_cabinet_sheets"
    result = _strict_bundle(snap, geom, target)
    outputs = dict(result.output_paths)
    assert pads[0].physical_id in outputs
    assert "base_plate" in outputs
    assert len(result.formed_part_ids) == 2
    assert result.side_marked_piece_ids == ("box_body:left_side", "box_body:right_side")
    assert len(outputs) == len(list(target.glob("*.dxf")))
    for path in outputs.values():
        assert Path(path).is_file()
        assert len(ezdxf.readfile(path).modelspace()) > 0
    pad_dx = ezdxf.readfile(outputs[pads[0].physical_id])
    assert sum(1 for row in pad_dx.modelspace() if row.dxf.layer=="BEND") == 2
    assert len(pads[0].source_csv_sha256) == 64


def test_incomplete_source_geometry_never_writes_partial_cabinet(tmp_path):
    """A stale source PAD/BASE FinalScene cannot turn into a partial success."""
    from dataclasses import replace
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    snap, geom = _prepare(False)
    assert resolve_committed_pad_physical_delivery(snap, geom.parts)
    # Move the real mounted base out of its source Z while leaving the
    # entire unchanged committed CSV and all other physical sheets intact.
    broken = replace(geom, parts=tuple(
        replace(part, offset=(part.offset[0], part.offset[1],
                              part.offset[2] + 2.))
        if part.part_key == "base_plate" else part
        for part in geom.parts
    ))
    folder = tmp_path / "stale_real_parent"
    with pytest.raises(ValueError):
        _strict_bundle(snap, broken, folder)
    assert not folder.exists()


def test_strict_request_rejects_incomplete_selection_even_without_pad(tmp_path):
    """Strict whole-cabinet means BODY+inner door+Base, not arbitrary subset."""
    from ae_engine.receiving_ear_side_manufacturing_marking import (
        with_verified_receiving_ear_side_markings,
    )
    from ae_engine.receiving_fixed_plate_formed_manufacturing import (
        save_verified_receiving_formed_fixing_plate_bundle,
    )
    from dataclasses import replace
    snap, geom = _prepare(False)
    dimensions = tuple(float(snap[k]) for k in ("w", "h", "d"))
    marked = with_verified_receiving_ear_side_markings(
        snap, geom, dimensions=dimensions, sheet_thickness=float(snap["t"]),
    )
    # Only body and sides are selected. The complete selection contract
    # refuses instead of pretending the NFB door/base were manufactured.
    selected = replace(marked, parts=tuple(p for p in marked.parts
                                           if p.part_key == "box_body"))
    folder = tmp_path / "missing_real_door_base"
    with pytest.raises(ValueError, match="RECEIVING_FULL_NFB_SELECTED_PHYSICAL_SHEETS_INCOMPLETE"):
        save_verified_receiving_formed_fixing_plate_bundle(
            snap, geom, selected, folder, dimensions=dimensions,
            sheet_thickness=float(snap["t"]),
            require_complete_cabinet_inventory=True,
        )
    assert not folder.exists()


def test_original_selected_parts_export_remains_legal_and_is_not_whole_release(tmp_path):
    """An operator's selected-sheet DXF has a distinct contract from WHOLE."""
    snapshot, geometry = _prepare(False)
    names, errors, calls = _run(snapshot, geometry, tmp_path)
    assert errors == [] and calls == ["resolve"]
    assert names and all((tmp_path / name).is_file() for name in names)


def test_pad_pair_manufacturing_reuses_same_current_source_physical_proof():
    from ae_engine.receiving_nfb_pad_pair_manufacturing import (
        verified_pad_base_physical_sheets,
    )
    snap, installed = installed_pair()
    rows, renders = verified_pad_base_physical_sheets(snap, installed)
    assert len(rows)==1
    assert set(renders)=={"base_plate",rows[0].physical_id}
    assert renders["base_plate"] is installed[0].render_data
    assert renders[rows[0].physical_id] is rows[0].render_data


def test_original_gui_full_nfb_sheet_selection_includes_real_pad_without_new_button(tmp_path):
    """Operator's existing selected DXF sends PAD alongside genuine NFB sheets."""
    import ezdxf
    from ae_engine.manufacturing_api import _resolved_physical_dxf_filename
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )

    snap, geom = _prepare(False)
    pads = resolve_committed_pad_physical_delivery(snap, geom.parts)
    assert len(pads) == 1
    outputs, errors, calls = _run(snap, geom, tmp_path)
    assert errors == [] and calls == ["resolve"]
    pad_filename = _resolved_physical_dxf_filename(pads[0].physical_id)
    assert pad_filename in outputs
    assert (tmp_path / pad_filename).is_file()
    pad_scene = ezdxf.readfile(tmp_path / pad_filename).modelspace()
    assert sum(1 for row in pad_scene if row.dxf.layer == "BEND") == 2
    # The positive path cannot hide a missing side, real base, or EAR.
    assert "base_plate.dxf" in outputs
    assert sum("fixing_plate" in name for name in outputs) == 2
    assert "box_body_box_body_left_side.dxf" in outputs
    assert "box_body_box_body_right_side.dxf" in outputs


def test_original_gui_door_base_only_does_not_require_full_cabinet(tmp_path):
    """Independent partial selection still works with source-required PAD."""
    snap, geom = _prepare(False)
    names, errors, calls = _run(
        snap, geom, tmp_path,
        flags={"box_body": False, "head": False},
    )
    assert errors == [] and calls == ["resolve"]
    assert any("base_plate" in name for name in names)
    assert not any("nfb_pad" in name for name in names)
