# -*- coding: utf-8 -*-
"""#2517: Receiving source-current physical NFB BasePlate via headless Engine API."""
import inspect
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_base_partial_export as engine
from gui_modules.application import receiving_nfb_base_partial_export_action as gui_base
from gui_modules.application import receiving_nfb_partial_export_action as gui_door
from tests.test_issue1502_live_nfb_base_partial_export import _live


def test_base_plate_manufacture_identity_and_geometry_owner_is_engine_only():
    assert gui_base.prepare_verified_receiving_nfb_base_plate is api.prepare_verified_receiving_nfb_base_plate
    assert gui_base.export_verified_receiving_nfb_base_plate is api.export_verified_receiving_nfb_base_plate
    assert api.prepare_verified_receiving_nfb_base_plate is engine.prepare_verified_receiving_nfb_base_plate
    assert api.export_verified_receiving_nfb_base_plate is engine.export_verified_receiving_nfb_base_plate
    assert gui_door.nfb_verification_geometry_changed is engine.nfb_verification_geometry_changed
    engine_source = inspect.getsource(engine)
    assert "gui_modules" not in engine_source
    assert "phase6_" not in engine_source
    gui_source = inspect.getsource(gui_base)
    assert "BasePlatePartSpec" not in gui_source
    assert "def prepare_verified_receiving_nfb_base_plate" not in gui_source
    assert "def export_verified_receiving_nfb_base_plate" not in gui_source


@pytest.mark.parametrize("pattern", ("LEFT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD", "RIGHT_FLAT_SIDE"))
def test_headless_engine_api_revalidates_and_exports_actual_base_dxf(tmp_path, pattern):
    sample = _live(tmp_path, pattern)
    composed, receipt, panel, profile = api.prepare_verified_receiving_nfb_base_plate(
        sample.bundle, layout=sample.layout, current_snapshot=sample.snapshot,
        base_spec=sample.plate, index_path=sample.index, profile_path=sample.profile,
    )
    assert receipt.approval_scope == "PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2"
    assert composed.manufacturing_ready is False
    assert panel.stable_id == sample.bundle.scope.inner_door_part_id
    assert profile.source_sha256 == sample.bundle.source_inventory.source_sha256
    root = tmp_path / "headless"
    root.mkdir()
    path, actual = api.export_verified_receiving_nfb_base_plate(
        sample.bundle, layout=sample.layout, current_snapshot=sample.snapshot,
        base_spec=sample.plate, output_directory=root,
        index_path=sample.index, profile_path=sample.profile,
    )
    assert Path(path).is_file()
    assert actual.manufacturing_ready is False
    assert len(ezdxf.readfile(path).modelspace().query("CIRCLE[layer=='CUTTING']")) == 16


def test_headless_engine_api_rejects_stale_source_without_output(tmp_path):
    sample = _live(tmp_path)
    sample.original.write_bytes(sample.original.read_bytes() + b"new source")
    root = tmp_path / "blocked"
    root.mkdir()
    with pytest.raises(ValueError, match="source bytes changed"):
        api.export_verified_receiving_nfb_base_plate(
            sample.bundle, layout=sample.layout, current_snapshot=sample.snapshot,
            base_spec=sample.plate, output_directory=root,
            index_path=sample.index, profile_path=sample.profile,
        )
    assert list(root.iterdir()) == []
