# -*- coding: utf-8 -*-
"""#2517 real immutable NFB requests -> all-or-none multi-Bay DXF API.

All requests use original canonical physical render inputs and actual
committed numeric CSV V5 sources. No caller-owned 2D/3D NFB geometry.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_batch_pair_export import (
    NfbCsvMultiBayPartOnlyDxf,
)
from tests.test_issue2517_nfb_pair_request_to_finalscene_dxf_public_api import (
    _original_request,
)
from tests.test_issue1502_current_csv_original_pair_dxf import _current
from tests.test_issue1502_current_csv_original_two_tier_dxf import (
    _current_two_tiers,
)


def _request(*, set_id="S", bay_id="B", tiers=1):
    snapshot = _current() if tiers == 1 else _current_two_tiers()
    snapshot["receiving_layout"]["sets"][0]["stable_id"] = set_id
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["stable_id"] = bay_id
    snapshot["_receiving_runtime_selection"]["set_id"] = set_id
    snapshot["_receiving_runtime_selection"]["bay_id"] = bay_id
    return _original_request(snapshot, tiers=tiers)


@pytest.mark.parametrize("size", (2, 16))
def test_public_atomic_request_to_real_dxf_for_distinct_receiving_bays(
    size, tmp_path,
):
    requests = tuple(
        _request(set_id="S", bay_id=f"B{i:02d}") for i in range(size)
    )
    before = deepcopy(requests)
    result = manufacturing_api.export_receiving_committed_nfb_csv_bays(
        requests, output_directory=tmp_path,
    )
    assert result.__class__ is NfbCsvMultiBayPartOnlyDxf
    assert (ae_engine.export_receiving_committed_nfb_csv_bays
            is manufacturing_api.export_receiving_committed_nfb_csv_bays)
    assert len(result.bays) == size
    assert all(sid == "S" and bid == f"B{i:02d}"
               for i, (sid, bid, _receipt) in enumerate(result.bays))
    assert len(result.output_paths) == size * 2
    assert set(map(Path, result.output_paths)) == set(tmp_path.glob("*.dxf"))
    assert "PART_ONLY" in result.scope
    assert all(ezdxf.readfile(path).audit().errors == []
               for path in result.output_paths)
    assert requests == before


def test_one_and_two_tier_current_bays_share_exact_atomic_output_contract(tmp_path):
    requests = (
        _request(set_id="S", bay_id="B1", tiers=1),
        _request(set_id="S", bay_id="B2", tiers=2),
    )
    proof = manufacturing_api.export_receiving_committed_nfb_csv_bays(
        requests, output_directory=tmp_path,
    )
    assert [len((p.inner_door_path, p.base_plate_path))
            if hasattr(p, "base_plate_path") else
            len((p.inner_door_path,) + p.base_plate_paths)
            for _, _, p in proof.bays] == [2, 3]
    assert len(proof.output_paths) == 5
    assert len(list(tmp_path.glob("*.dxf"))) == 5


def test_second_bay_missing_real_original_base_rolls_back_first_staged_pair(tmp_path):
    first = _request(bay_id="B1")
    second = _request(bay_id="B2")
    second = replace(
        second, canonical_part_keys=(second.parts[0].part_key,),
        parts=(second.parts[0],),
    )
    with pytest.raises(ValueError, match="REAL_BASE_PART_MISSING|SOURCE_BASE_PLATE_MISSING"):
        manufacturing_api.export_receiving_committed_nfb_csv_bays(
            (first, second), output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_precommit_source_guard_rejection_discards_all_staged_files(tmp_path):
    requests = (_request(bay_id="B1"), _request(bay_id="B2"))
    calls = []
    def guard():
        calls.append("checked")
        if len(calls) == 2:
            raise ValueError("ORIGINAL_SOURCE_DXF_CHANGED")
    with pytest.raises(ValueError, match="ORIGINAL_SOURCE_DXF_CHANGED"):
        manufacturing_api.export_receiving_committed_nfb_csv_bays(
            requests, output_directory=tmp_path, pre_commit_guard=guard,
        )
    assert calls == ["checked", "checked"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("invalid", (
    (), (object(),), None,
))
def test_invalid_request_inventory_fails_before_any_dxf(invalid, tmp_path):
    with pytest.raises((TypeError, ValueError), match="CSV_MULTIBAY_MANUFACTURING_REQUEST"):
        manufacturing_api.export_receiving_committed_nfb_csv_bays(
            invalid, output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_duplicate_physical_bay_is_blocked_before_any_dxf(tmp_path):
    request = _request()
    with pytest.raises(ValueError, match="CSV_MULTIBAY_DUPLICATED_PHYSICAL_SET_BAY"):
        manufacturing_api.export_receiving_committed_nfb_csv_bays(
            (request, request), output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_unconfirmed_second_bay_source_rejects_entire_batch_before_stage(tmp_path):
    first = _request(bay_id="B1")
    # The original physical BasePlate can only be built from a committed
    # source. Start with a genuinely valid immutable manufacturing request,
    # THEN remove the selected Bay submission on its request snapshot.
    second = _request(bay_id="B2")
    from ae_engine.manufacturing_contracts import thaw_manufacturing_value
    snapshot = thaw_manufacturing_value(second.input_snapshot)
    snapshot["nfb_config_submitted"] = False
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config_submitted"] = False
    second = replace(second, input_snapshot=snapshot)
    with pytest.raises(ValueError, match="CSV_MULTIBAY_COMMITTED_SOURCE_REQUIRED"):
        manufacturing_api.export_receiving_committed_nfb_csv_bays(
            (first, second),
            output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_existing_dxf_not_overwritten_and_no_second_bay_partial_publication(tmp_path):
    dst = tmp_path / "already-saved.dxf"
    request = _request()
    result = manufacturing_api.export_receiving_committed_nfb_csv_bays(
        (request,), output_directory=tmp_path,
    )
    content = {p: Path(p).read_bytes() for p in result.output_paths}
    with pytest.raises(FileExistsError):
        manufacturing_api.export_receiving_committed_nfb_csv_bays(
            (request,), output_directory=tmp_path,
        )
    assert content == {p: Path(p).read_bytes() for p in result.output_paths}
    assert set(tmp_path.glob("*.dxf")) == {Path(p) for p in result.output_paths}
