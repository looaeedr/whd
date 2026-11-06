# -*- coding: utf-8 -*-
"""#2517: double-tier CSV NFB real DXF refuses invalid physical installed XYZ.

The original current Receiving two-tier/Set-Bay source and actual canonical
FinalScene, including three independent staged DXF reopen checks, are used.
No fake geometry, manufacturing-ready shortcut, or GUI-side positioning.
"""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from tests.test_issue1502_current_csv_original_two_tier_dxf import (
    _actual_scene,
    _current_two_tiers,
)


def _invalid_tier_offset(parts, *, tier, offset):
    key = f"base_plate:nfb_layer:{tier}"
    return tuple(
        replace(part, offset=offset) if part.part_key == key else part
        for part in parts
    )


def _tier_offset(parts, tier):
    return next(
        p.offset for p in parts
        if p.part_key == f"base_plate:nfb_layer:{tier}"
    )


def _export(snapshot, parts, tmp_path):
    return manufacturing_api.export_current_csv_nfb_door_base_pair(
        snapshot, assembly_parts=parts,
        base_spec=None, output_directory=tmp_path,
    )


def test_real_two_tier_source_still_writes_three_independently_reopened_dxfs(tmp_path):
    snapshot = _current_two_tiers()
    parts = _actual_scene(snapshot)
    proof = _export(snapshot, parts, tmp_path)
    paths = (proof.inner_door_path, *proof.base_plate_paths)
    assert len(set(paths)) == len(paths) == 3
    assert {Path(path) for path in paths} == set(tmp_path.glob("*.dxf"))
    assert proof.source_hole_ids == ("tier:0:switch", "tier:1:switch")
    for path in paths:
        assert Path(path).is_file()
        assert ezdxf.readfile(path).audit().errors == []


@pytest.mark.parametrize("tier", (0, 1))
@pytest.mark.parametrize("axis", (0, 1, 2))
def test_nan_in_any_installed_tier_xyz_cannot_pass_float_difference(
    tier, axis, tmp_path,
):
    snapshot = _current_two_tiers()
    parts = _actual_scene(snapshot)
    bad = list(_tier_offset(parts, tier))
    bad[axis] = float("nan")
    tampered = _invalid_tier_offset(parts, tier=tier, offset=tuple(bad))
    with pytest.raises(
        ValueError, match="CSV_TWO_TIER_REAL_BASE_INSTALL_XYZ_MISMATCH",
    ):
        _export(snapshot, tampered, tmp_path)
    assert not list(tmp_path.iterdir())
    assert all(a.render_data is b.render_data for a, b in zip(parts, tampered))


@pytest.mark.parametrize("invalid_offset", (
    None,
    (0.0, 0.0),
    (True, 0.0, 0.0),
    ("0", 0.0, 0.0),
    (float("inf"), 0.0, 0.0),
    (float("-inf"), 0.0, 0.0),
))
@pytest.mark.parametrize("tier", (0, 1))
def test_invalid_tier_offset_type_or_infinity_fails_before_any_dxf(
    tier, invalid_offset, tmp_path,
):
    snapshot = _current_two_tiers()
    parts = _actual_scene(snapshot)
    tampered = _invalid_tier_offset(parts, tier=tier, offset=invalid_offset)
    with pytest.raises(
        ValueError, match="CSV_TWO_TIER_REAL_BASE_INSTALL_XYZ_MISMATCH",
    ):
        _export(snapshot, tampered, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("tier", (0, 1))
@pytest.mark.parametrize("axis", (0, 1, 2))
def test_oversized_integer_xyz_fails_as_source_error_not_uncaught_overflow(
    tier, axis, tmp_path,
):
    snapshot = _current_two_tiers()
    parts = _actual_scene(snapshot)
    bad = list(_tier_offset(parts, tier))
    bad[axis] = 10 ** 1000  # math.isfinite(int) overflows before float diff.
    tampered = _invalid_tier_offset(parts, tier=tier, offset=tuple(bad))
    with pytest.raises(
        ValueError, match="CSV_TWO_TIER_REAL_BASE_INSTALL_XYZ_MISMATCH",
    ):
        _export(snapshot, tampered, tmp_path)
    assert not list(tmp_path.iterdir())
    assert all(a.render_data is b.render_data for a, b in zip(parts, tampered))
