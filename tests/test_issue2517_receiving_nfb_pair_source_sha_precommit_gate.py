# -*- coding: utf-8 -*-
"""#2517 real Receiving V5 paired DXF must not commit after CSV byte drift.

Uses the existing physical one-/two-tier FinalScene and genuinely reopened
DXFs. Mutation is only of a disposable byte-for-byte CSV copy: the actual
brand sources and any real input DXF are never edited.
"""
import os
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api, manufacturing_export
from ae_engine import receiving_nfb_numeric_catalog as catalog
from ae_engine import receiving_nfb_pair_export as owner
from ae_engine import manufacturing_verification as verification
from tests.test_issue1502_current_csv_original_pair_dxf import _current, _scene
from tests.test_issue1502_current_csv_original_two_tier_dxf import (
    _current_two_tiers, _actual_scene,
)


def _current_parts(tiers):
    snap = _current() if tiers == 1 else _current_two_tiers()
    return snap, (_scene(snap) if tiers == 1 else _actual_scene(snap))


@pytest.mark.parametrize("tiers", (1, 2))
def test_original_real_pair_source_still_reopens_every_dxf(tiers, tmp_path):
    snapshot, parts = _current_parts(tiers)
    receipt = manufacturing_api.export_current_csv_nfb_door_base_pair(
        snapshot, assembly_parts=parts, base_spec=None,
        output_directory=tmp_path,
    )
    paths = ((receipt.inner_door_path, receipt.base_plate_path)
             if tiers == 1 else
             (receipt.inner_door_path, *receipt.base_plate_paths))
    assert len(set(paths)) == len(paths) == tiers + 1
    assert set(Path(path) for path in paths) == set(tmp_path.glob("*.dxf"))
    assert all(ezdxf.readfile(path).audit().errors == [] for path in paths)


@pytest.mark.parametrize("tiers", (1, 2))
@pytest.mark.parametrize("change", ("bytes_same_size_mtime", "deleted"))
def test_csv_changed_during_actual_staged_dxf_reopen_refuses_atomic_pair(
    tiers, change, tmp_path, monkeypatch,
):
    snapshot, parts = _current_parts(tiers)
    # Keep the Engine geometry reader on its actual source. This staged
    # export-guard source is an independent, identical temporary byte copy.
    brand = "士林"
    original = catalog.brand_csv_path(brand)
    temporary_csv = tmp_path / "source-proof-copy.csv"
    temporary_csv.write_bytes(original.read_bytes())
    before = temporary_csv.stat()
    monkeypatch.setattr(
        owner, "brand_csv_path",
        lambda requested: temporary_csv if requested == brand
        else catalog.brand_csv_path(requested),
    )
    real_verify = verification.verify_saved_part_render_data_dxf
    calls = []

    def verify_and_change_source(render, staged_path):
        proof = real_verify(render, staged_path)
        assert proof.ok
        calls.append(staged_path)
        if len(calls) == 1:
            if change == "deleted":
                temporary_csv.unlink()
            else:
                original_bytes = temporary_csv.read_bytes()
                assert len(original_bytes) > 10
                replacement = (
                    original_bytes[:-1] + bytes((original_bytes[-1] ^ 1,))
                )
                temporary_csv.write_bytes(replacement)
                os.utime(temporary_csv, ns=(before.st_atime_ns, before.st_mtime_ns))
                after = temporary_csv.stat()
                assert after.st_size == before.st_size
                assert after.st_mtime_ns == before.st_mtime_ns
                assert temporary_csv.read_bytes() != original_bytes
        return proof

    monkeypatch.setattr(
        verification, "verify_saved_part_render_data_dxf",
        verify_and_change_source,
    )
    root = tmp_path / "output"
    root.mkdir()
    expected = (
        "CSV_PAIR_COMMITTED_BRAND_CSV_CHANGED_BEFORE_COMMIT"
        if change == "bytes_same_size_mtime"
        else "CSV_PAIR_COMMITTED_BRAND_CSV_SOURCE_UNAVAILABLE"
    )
    with pytest.raises(ValueError, match=expected):
        manufacturing_api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=parts, base_spec=None,
            output_directory=root,
        )
    assert len(calls) == tiers + 1
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("tiers", (1, 2))
def test_current_csv_pair_rolls_back_when_source_changes_after_first_publish_move(
    tiers, tmp_path, monkeypatch,
):
    snapshot, parts = _current_parts(tiers)
    brand = "士林"
    original = catalog.brand_csv_path(brand)
    original_bytes = original.read_bytes()
    proof = tmp_path / "source-proof-copy.csv"
    proof.write_bytes(original_bytes)
    monkeypatch.setattr(
        owner, "brand_csv_path",
        lambda requested: proof if requested == brand else catalog.brand_csv_path(requested),
    )
    root = tmp_path / "output"
    root.mkdir()

    def export():
        return manufacturing_api.export_current_csv_nfb_door_base_pair(
            snapshot, assembly_parts=parts, base_spec=None, output_directory=root,
        )

    def assert_reopened_dxf_count():
        paths = tuple(root.glob("*.dxf"))
        assert len(paths) == tiers + 1
        assert set(paths) == set(root.iterdir())
        assert all(not ezdxf.readfile(path).audit().errors for path in paths)
        return {path.name: path.read_bytes() for path in paths}

    real_move = manufacturing_export.os.replace
    moved = []

    def move_and_change_source(path, destination, *args, **kwargs):
        result = real_move(path, destination, *args, **kwargs)
        destination = Path(destination)
        if destination.parent == root and destination.suffix.lower() == ".dxf":
            assert not ezdxf.readfile(destination).audit().errors
            moved.append(destination)
            if len(moved) == 1:
                proof.write_bytes(original_bytes[:-1] + bytes((original_bytes[-1] ^ 1,)))
        return result

    # Empty folder: the race occurs during the actual shared publish moves,
    # after every staged DXF has passed the existing independent reopen check.
    with monkeypatch.context() as injected:
        injected.setattr(manufacturing_export.os, "replace", move_and_change_source)
        with pytest.raises(ValueError, match="CSV_PAIR_COMMITTED_BRAND_CSV_CHANGED_BEFORE_COMMIT"):
            export()
    assert len(moved) == tiers + 1
    assert list(root.iterdir()) == []

    # A restored source supports a clean retry, then existing output stays
    # byte-for-byte intact and never enters the move path on a second request.
    proof.write_bytes(original_bytes)
    export()
    expected = assert_reopened_dxf_count()
    moved.clear()
    with monkeypatch.context() as injected:
        injected.setattr(manufacturing_export.os, "replace", move_and_change_source)
        with pytest.raises(FileExistsError, match="CSV_(PAIR|TWO_TIER)_EXISTING_DXF_NOT_OVERWRITTEN"):
            export()
    assert not moved
    assert assert_reopened_dxf_count() == expected
    assert original.read_bytes() == original_bytes


def test_each_submitted_csv_brand_is_fingerprinted_independently(tmp_path, monkeypatch):
    brands = ("士林", "東元")
    files = {}
    for brand in brands:
        path = tmp_path / (brand + ".csv")
        path.write_bytes(catalog.brand_csv_path(brand).read_bytes())
        files[brand] = path
    monkeypatch.setattr(owner, "brand_csv_path", lambda brand: files[brand])
    source_holes = (
        SimpleNamespace(brand="士林", model_ref="nfbv5:士林:2P400"),
        SimpleNamespace(brand="東元", model_ref="nfbv5:東元:3P125SN"),
    )
    initial = owner._committed_csv_brand_source_hashes(source_holes)
    assert tuple(brand for brand, _ in initial) == tuple(sorted(brands))
    files["東元"].write_bytes(files["東元"].read_bytes() + b"x")
    with pytest.raises(
        ValueError, match="CSV_PAIR_COMMITTED_BRAND_CSV_CHANGED_BEFORE_COMMIT",
    ):
        owner._require_committed_csv_source_unchanged(source_holes, initial)


def test_wrong_submitted_brand_and_model_ref_cannot_mint_source_hashes():
    with pytest.raises(ValueError, match="MODEL_SOURCE_IDENTITY_INVALID"):
        owner._committed_csv_brand_source_hashes((
            SimpleNamespace(brand="東元", model_ref="nfbv5:士林:2P400"),
        ))
