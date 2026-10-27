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


def test_explicit_complete_inventory_fails_atomically_when_pad_is_missing(tmp_path):
    """A strict whole-cabinet request must account for the source-required PAD."""
    snapshot, geometry = _prepare(False)
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    from ae_engine.receiving_ear_side_manufacturing_marking import (
        with_verified_receiving_ear_side_markings,
    )
    from ae_engine.receiving_fixed_plate_formed_manufacturing import (
        save_verified_receiving_formed_fixing_plate_bundle,
    )
    pads = resolve_committed_pad_physical_delivery(snapshot, geometry.parts)
    assert pads, "this current Shihlin mixed-depth fixture really requires PAD"
    marked = with_verified_receiving_ear_side_markings(
        snapshot, geometry,
        dimensions=(float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
        sheet_thickness=float(snapshot["t"]),
    )
    output = tmp_path / "must-not-falsely-report-complete"
    with pytest.raises(
        ValueError, match="RECEIVING_FULL_NFB_PAD_REQUIRED_IN_COMPLETE_EXPORT",
    ):
        save_verified_receiving_formed_fixing_plate_bundle(
            snapshot, geometry, marked, output,
            dimensions=(float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
            sheet_thickness=float(snapshot["t"]),
            require_complete_cabinet_inventory=True,
        )
    assert not output.exists()


def test_original_selected_parts_export_remains_legal_and_is_not_whole_release(tmp_path):
    """An operator's selected-sheet DXF has a distinct contract from WHOLE."""
    snapshot, geometry = _prepare(False)
    names, errors, calls = _run(snapshot, geometry, tmp_path)
    assert errors == [] and calls == ["resolve"]
    assert names and all((tmp_path / name).is_file() for name in names)
