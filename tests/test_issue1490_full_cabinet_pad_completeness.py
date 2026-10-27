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


def test_complete_original_gui_selected_inventory_must_not_drop_source_pad(tmp_path):
    """The original operator button must not report a whole box missing its PAD."""
    snapshot, geometry = _prepare(False)
    from ae_engine.receiving_nfb_pad_delivery import (
        resolve_committed_pad_physical_delivery,
    )
    pads = resolve_committed_pad_physical_delivery(snapshot, geometry.parts)
    assert pads, "this current Shihlin mixed-depth fixture really requires PAD"
    output = tmp_path / "must-not-falsely-report-complete"
    with pytest.raises(
        ValueError, match="RECEIVING_FULL_NFB_PAD_REQUIRED_IN_COMPLETE_EXPORT",
    ):
        _run(snapshot, geometry, output)
    assert not output.exists() or not list(Path(output).glob("*.dxf"))
