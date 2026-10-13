# -*- coding: utf-8 -*-
"""#1502: actual paired part geometry, not filenames/SHA, controls CHECK Q."""
from dataclasses import replace
from pathlib import Path
import re

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from gui_modules.application.receiving_nfb_pair_quantity_check_action import (
    NfbPairedQuantityInput, group_reopened_nfb_pair_check_q,
)
from tests.test_issue1502_atomic_door_base_pair_dxf import _ready, _write


PARAM = ManufacturingParameters("SPCC", 2., {"process": "laser"})


def _paired(tmp_path, instance, *, pattern="LEFT_FLAT_SIDE"):
    root = tmp_path / instance
    root.mkdir()
    fixture = _ready(root, pattern=pattern)
    if instance != "A":
        scope = replace(fixture.bundle.scope,
                        set_id="set" + instance, bay_id="bay" + instance,
                        version_id="v" + instance)
        fixture.bundle = replace(
            fixture.bundle, scope=scope, version_id=scope.version_id,
        )
        fixture.layout["sets"][0]["stable_id"] = scope.set_id
        fixture.layout["sets"][0]["bays"][0]["stable_id"] = scope.bay_id
    target = root / "output"
    target.mkdir()
    result = _write(fixture, target)
    return fixture, result


def _input(pair, count):
    return NfbPairedQuantityInput(pair, count, PARAM, PARAM)


def test_real_pair_same_geometry_different_source_sha_groups_exact_q(tmp_path):
    _, first = _paired(tmp_path, "A")
    _, second = _paired(tmp_path, "B")
    checked = group_reopened_nfb_pair_check_q((
        _input(first, 2), _input(second, 3),
    ))
    assert checked.scope == "PAIR_PART_ONLY_CHECK_Q_NOT_WHOLE_MFG2"
    assert checked.gate.partial_only
    assert not checked.gate.held
    assert checked.actual_piece_count == 10
    assert sorted(g.quantity for g in checked.groups) == [5, 5]
    assert all(len(g.members) == 2 for g in checked.groups)
    output = tmp_path / "check"
    output.mkdir()
    paths = api.save_quantity_manufacturing_groups_dxf(checked.groups, output)
    assert len(paths) == 2
    labels = []
    for path in paths.values():
        dxf = ezdxf.readfile(path)
        labels.extend(e.plain_text() for e in dxf.modelspace().query("MTEXT")
                      if re.fullmatch(r"Q[0-9]+", e.plain_text()))
    assert sorted(labels) == ["Q5", "Q5"]


def test_real_pair_different_base_machining_does_not_merge_unequal_shapes(tmp_path):
    _, first = _paired(tmp_path, "A", pattern="LEFT_FLAT_SIDE")
    _, second = _paired(tmp_path, "B", pattern="CENTER_DOUBLE_SIDE_FOLD")
    checked = group_reopened_nfb_pair_check_q((
        _input(first, 1), _input(second, 1),
    ))
    assert checked.actual_piece_count == 4
    assert sorted(g.quantity for g in checked.groups) == [1, 1, 2]
    assert len(checked.groups) == 3


def test_changed_exported_dxf_blocks_check_before_quantity_output(tmp_path):
    _, first = _paired(tmp_path, "A")
    dxf = ezdxf.readfile(first.base_plate_path)
    dxf.modelspace().add_circle((200., 100.), 7.,
                                dxfattribs={"layer": "CUTTING"})
    dxf.saveas(first.base_plate_path)
    with pytest.raises(ValueError, match="DXF_CHANGED"):
        group_reopened_nfb_pair_check_q((_input(first, 3),))
    assert not list(tmp_path.glob("part_*.dxf"))


def test_edited_source_requires_pair_reverify_not_old_sha_lock(tmp_path):
    fixture, first = _paired(tmp_path, "A")
    source = Path(first.source_path)
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="REVERIFY_PAIR"):
        group_reopened_nfb_pair_check_q((_input(first, 2),))
    # The file is not permanently locked; re-exporting/validating the
    # edited current DXF is the correct next manufacturing action.


@pytest.mark.parametrize("count", (0, -1, True, 1.5))
def test_quantity_invalid_counts_fail_before_grouping(tmp_path, count):
    _, first = _paired(tmp_path, "A")
    with pytest.raises(ValueError, match="QUANTITY"):
        group_reopened_nfb_pair_check_q((_input(first, count),))


def test_duplicate_real_scope_and_reused_dxf_cannot_double_count(tmp_path):
    _, first = _paired(tmp_path, "A")
    with pytest.raises(ValueError, match="DUPLICATE"):
        group_reopened_nfb_pair_check_q((_input(first, 1), _input(first, 1)))


def test_check_cannot_grant_whole_mfg2_or_ear_pad(tmp_path):
    _, first = _paired(tmp_path, "A")
    verified = group_reopened_nfb_pair_check_q((_input(first, 1),))
    assert verified.gate.partial_only
    assert verified.scope != "WHOLE_CABINET"
    from ae_engine.receiving_nfb_quantity_gate import gate_nfb_quantity_physical_demands
    with pytest.raises(ValueError, match="partial only|whole CHECK"):
        gate_nfb_quantity_physical_demands(
            verified.gate.permitted,
            manifests=(), partial=False,
        )
