# -*- coding: utf-8 -*-
"""#2517 Receiving paired DXF manufacture is a public, GUI-free Engine operation."""
from pathlib import Path
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_pair_export as owner
from gui_modules.application import receiving_nfb_pair_partial_export_action as gui
from tests.test_issue1502_atomic_door_base_pair_dxf import _ready
from tests.test_issue1502_current_csv_original_pair_dxf import _current, _scene
from tests.test_issue1502_current_csv_original_two_tier_dxf import (
    _current_two_tiers, _actual_scene,
)


def test_all_real_pair_export_authority_is_engine_owned():
    assert api.export_verified_receiving_nfb_door_base_pair is owner.export_verified_receiving_nfb_door_base_pair
    assert api.export_current_csv_nfb_door_base_pair is owner.export_current_csv_nfb_door_base_pair
    assert gui.export_verified_receiving_nfb_door_base_pair is api.export_verified_receiving_nfb_door_base_pair
    assert gui.export_current_csv_nfb_door_base_pair is api.export_current_csv_nfb_door_base_pair
    assert gui.NfbPairedPartOnlyDxf is api.NfbPairedPartOnlyDxf
    assert gui.NfbCsvPairedPartOnlyDxf is api.NfbCsvPairedPartOnlyDxf
    assert gui.NfbCsvTwoTierPartOnlyDxf is api.NfbCsvTwoTierPartOnlyDxf
    source = inspect.getsource(owner)
    assert "gui_modules" not in source and "phase6_" not in source
    adapter = inspect.getsource(gui)
    for fragment in ("def export_", "def _export_", "save_scene_dxf(", "build_part_render_data(", "from ae_engine.receiving_nfb_"):
        assert fragment not in adapter


def test_native_indexed_pair_real_headless_output(tmp_path):
    fixture = _ready(tmp_path)
    root = tmp_path / "headless-native"
    root.mkdir()
    proof = api.export_verified_receiving_nfb_door_base_pair(
        fixture.bundle, layout=fixture.layout,
        current_snapshot=fixture.snapshot, base_spec=fixture.plate,
        output_directory=root, index_path=fixture.index,
        profile_path=fixture.profile,
    )
    assert type(proof) is api.NfbPairedPartOnlyDxf
    assert proof.receipt.physical_part_count == 2
    assert {Path(proof.inner_door_path), Path(proof.base_plate_path)} == set(root.glob("*.dxf"))
    assert proof.scope == "PAIR_PART_ONLY_NOT_WHOLE_CABINET"


@pytest.mark.parametrize("tiers", [1, 2])
def test_real_csv_v5_pair_headless_one_or_two_tiers(tmp_path, tiers):
    snapshot = _current() if tiers == 1 else _current_two_tiers()
    parts = _scene(snapshot) if tiers == 1 else _actual_scene(snapshot)
    proof = api.export_current_csv_nfb_door_base_pair(
        snapshot, assembly_parts=parts, base_spec=None, output_directory=tmp_path,
    )
    assert type(proof) is (
        api.NfbCsvPairedPartOnlyDxf if tiers == 1 else api.NfbCsvTwoTierPartOnlyDxf
    )
    saved = (proof.inner_door_path,) + (
        (proof.base_plate_path,) if tiers == 1 else proof.base_plate_paths
    )
    assert len(saved) == tiers + 1
    assert len(set(saved)) == tiers + 1
    assert all(Path(path).is_file() for path in saved)
    assert len(list(tmp_path.glob("*.dxf"))) == tiers + 1


def test_real_csv_v5_headless_rejects_missing_installed_base_without_files(tmp_path):
    snapshot = _current_two_tiers()
    parts = _actual_scene(snapshot)
    with pytest.raises(ValueError, match="MISSING_INSTALLED_PHYSICAL_PART"):
        api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=parts[:2],
            base_spec=None, output_directory=tmp_path,
        )
    assert not list(tmp_path.glob("*.dxf"))
