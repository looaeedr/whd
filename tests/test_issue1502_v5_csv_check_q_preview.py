# -*- coding: utf-8 -*-
"""#1502: identical CSV physical geometry has exact CHECK Q, never auto-release."""
from dataclasses import replace

import pytest

from ae_engine.manufacturing_api import save_part_render_data_dxf
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.receiving_nfb_v5_check_q_preview import (
    CsvV5BaseCheckDemand, check_csv_v5_base_part_only_groups,
)
from tests.test_issue1502_v5_csv_tier_bases import _setup, _run

PARAMS = ManufacturingParameters(material="steel", thickness=2., process="laser")


def _row(part, *, version="V1", quantity=1, parameters=PARAMS):
    return CsvV5BaseCheckDemand(version, part, quantity, parameters)


def test_csv_two_tier_base_produces_separate_check_q_by_real_geometry():
    snap, door, holes, bases = _setup()
    first, second = _run(snap, door, holes, bases)
    result = check_csv_v5_base_part_only_groups((
        _row(first, quantity=3), _row(second, quantity=3),
    ))
    assert result.status == "NFB_V5_CSV_BASE_CHECK_Q_PREVIEW_ONLY"
    assert result.manufacturing_ready is False
    assert len(result.physical_part_ids) == 2
    assert len(result.groups) == 2
    assert sorted(group.quantity for group in result.groups) == [3, 3]
    assert all(len(group.key) == 64 for group in result.groups)


def test_check_q_merges_only_same_actual_material_and_cutting_across_versions():
    snap, door, holes, bases = _setup()
    first, second = _run(snap, door, holes, bases)
    result = check_csv_v5_base_part_only_groups((
        _row(first, version="V1", quantity=2),
        _row(first, version="V2", quantity=4),
        _row(second, version="V1", quantity=1),
    ))
    assert sorted(group.quantity for group in result.groups) == [1, 6]
    changed_process = check_csv_v5_base_part_only_groups((
        _row(first, version="V1", quantity=1),
        _row(first, version="V2", quantity=1,
             parameters=ManufacturingParameters("steel", 2., "punch")),
    ))
    assert len(changed_process.groups) == 2


def test_csv_check_q_never_authorizes_trial_manufacturing_dxf(tmp_path):
    snap, door, holes, bases = _setup()
    first, second = _run(snap, door, holes, bases)
    assert not check_csv_v5_base_part_only_groups(
        (_row(first), _row(second)),
    ).manufacturing_ready
    destination = tmp_path / "unsafe-base-plate.dxf"
    with pytest.raises(ValueError, match="未驗證試作"):
        save_part_render_data_dxf(first.render_data, destination)
    assert not destination.exists()


def test_reject_duplicate_tier_and_stale_csv_even_with_valid_geometry(monkeypatch, tmp_path):
    import ae_engine.receiving_nfb_v5_check_q_preview as check
    snap, door, holes, bases = _setup()
    first, second = _run(snap, door, holes, bases)
    with pytest.raises(ValueError, match="重複"):
        check_csv_v5_base_part_only_groups((_row(first), _row(first)))
    altered_csv = tmp_path / "NFB數值規格.csv"
    altered_csv.write_text("changed,CSV", encoding="utf-8")
    monkeypatch.setattr(check, "brand_csv_path", lambda _brand: altered_csv)
    with pytest.raises(ValueError, match="CSV 已變更"):
        check_csv_v5_base_part_only_groups((_row(first),))
