# -*- coding: utf-8 -*-
"""#2517 actual single-tier Receiving V5 pair DXF enforces installed Base XYZ.

Uses the existing current CSV physical Set/Bay + authoritative real scene
fixture and writes/reopens genuine DXF, never a mock manufacturing result.
"""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.assembly_placement import resolve_assembly_placement
from tests.test_issue1502_current_csv_original_pair_dxf import _current, _scene


def _change_base(parts, offset):
    return tuple(
        replace(part, offset=offset) if part.part_key == "base_plate" else part
        for part in parts
    )


def _actual_base(parts):
    return next(part for part in parts if part.part_key == "base_plate")


def test_current_installed_base_is_preserved_and_both_real_dxfs_reopen(tmp_path):
    snapshot = _current()
    parts = _scene(snapshot)
    expected = resolve_assembly_placement(snapshot, "base_plate").world_offset
    assert _actual_base(parts).offset == pytest.approx(expected)
    proof = manufacturing_api.export_current_csv_nfb_door_base_pair(
        snapshot, assembly_parts=parts, base_spec=None,
        output_directory=tmp_path,
    )
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    for filename in (proof.inner_door_path, proof.base_plate_path):
        path = Path(filename)
        assert path.is_file()
        assert ezdxf.readfile(path).audit().errors == []


@pytest.mark.parametrize("axis", (0, 1, 2))
def test_stale_single_tier_base_installation_cannot_export_two_good_local_scenes(
    axis, tmp_path,
):
    snapshot = _current()
    parts = _scene(snapshot)
    original_offset = _actual_base(parts).offset
    wrong = list(original_offset)
    wrong[axis] += 11.5
    wrong_parts = _change_base(parts, tuple(wrong))
    # The two local render-data/FinalScenes did NOT change. Only installed
    # XYZ drifted. Old export permitted them and wrote apparently valid DXF.
    assert _actual_base(wrong_parts).render_data is _actual_base(parts).render_data
    with pytest.raises(ValueError, match="CSV_PAIR_REAL_BASE_INSTALL_XYZ_MISMATCH"):
        manufacturing_api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=wrong_parts, base_spec=None,
            output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []
    assert _actual_base(parts).offset == original_offset


@pytest.mark.parametrize("corrupted", ((0.0, 0.0), (True, 0.0, 0.0),
                                       (float("nan"), 0.0, 0.0),
                                       ("0", 0.0, 0.0)))
def test_invalid_single_tier_base_xyz_fails_before_writing_any_dxf(
    corrupted, tmp_path,
):
    snapshot = _current()
    parts = _change_base(_scene(snapshot), corrupted)
    with pytest.raises(ValueError, match="CSV_PAIR_REAL_BASE_INSTALL_XYZ_MISMATCH"):
        manufacturing_api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=parts, base_spec=None,
            output_directory=tmp_path,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("axis", (0, 1, 2))
def test_oversized_integer_single_tier_xyz_fails_with_engine_source_error(
    axis, tmp_path,
):
    snapshot = _current()
    parts = _scene(snapshot)
    wrong = list(_actual_base(parts).offset)
    wrong[axis] = 10 ** 1000
    with pytest.raises(ValueError, match="CSV_PAIR_REAL_BASE_INSTALL_XYZ_MISMATCH"):
        manufacturing_api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=_change_base(parts, tuple(wrong)),
            base_spec=None, output_directory=tmp_path,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("invalid_offset", (
    None,
    (0.0, 0.0),
    (False, 0.0, 0.0),
    ("0", 0.0, 0.0),
    (float("nan"), 0.0, 0.0),
    (float("inf"), 0.0, 0.0),
    (10 ** 1000, 0.0, 0.0),
))
def test_invalid_real_inner_door_xyz_rejects_csv_pair_before_any_dxf(
    invalid_offset, tmp_path,
):
    """Same real CSV, CUTTING and Base; only the installed 3D Door is invalid."""
    snapshot = _current()
    parts = _scene(snapshot)
    physical_door = next(p for p in parts if p.part_key.startswith("inner_door:"))
    tampered = tuple(
        replace(part, offset=invalid_offset) if part is physical_door else part
        for part in parts
    )
    assert physical_door.render_data is next(
        p.render_data for p in tampered if p.part_key == physical_door.part_key
    )
    with pytest.raises(ValueError, match="CSV_PAIR_REAL_DOOR_INSTALL_XYZ_INVALID"):
        manufacturing_api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=tampered, base_spec=None,
            output_directory=tmp_path,
        )
    assert not list(tmp_path.iterdir())
