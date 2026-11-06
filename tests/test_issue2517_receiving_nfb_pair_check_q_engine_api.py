# -*- coding: utf-8 -*-
"""#2517 real Receiving NFB pair CHECK/Q public Engine API parity."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_pair_quantity_check as engine
from gui_modules.application import receiving_nfb_pair_quantity_check_action as gui_check
from gui_modules.application import receiving_nfb_pair_partial_export_action as gui_export
from tests.test_issue1502_paired_real_dxf_check_q import _paired, _input


def test_engine_owns_typed_pair_and_check_q_without_reverse_gui_dependency():
    assert api.NfbPairedPartOnlyDxf is engine.NfbPairedPartOnlyDxf
    assert api.NfbPairedQuantityInput is engine.NfbPairedQuantityInput
    assert api.NfbPairedQuantityCheck is engine.NfbPairedQuantityCheck
    assert api.group_reopened_nfb_pair_check_q is engine.group_reopened_nfb_pair_check_q
    assert api.save_checked_reopened_nfb_pair_q_dxf is engine.save_checked_reopened_nfb_pair_q_dxf
    assert gui_export.NfbPairedPartOnlyDxf is engine.NfbPairedPartOnlyDxf
    assert gui_check.NfbPairedQuantityInput is engine.NfbPairedQuantityInput
    assert gui_check.group_reopened_nfb_pair_check_q is engine.group_reopened_nfb_pair_check_q
    src = inspect.getsource(engine)
    assert "gui_modules" not in src and "phase6_" not in src
    assert "receiving_nfb_pair_partial_export_action" not in src
    gui_src = inspect.getsource(gui_check)
    for forbidden in ("def group_reopened_nfb_pair_check_q", "def save_checked_reopened_nfb_pair_q_dxf",
                      "verify_saved_part_render_data_dxf", "PhysicalPartDemand("):
        assert forbidden not in gui_src


def test_real_headless_pair_check_q_and_save_roundtrip(tmp_path):
    _, first = _paired(tmp_path, "A")
    _, second = _paired(tmp_path, "B")
    checked = api.group_reopened_nfb_pair_check_q((_input(first, 2), _input(second, 3)))
    assert checked.scope == "PAIR_PART_ONLY_CHECK_Q_NOT_WHOLE_MFG2"
    assert checked.actual_piece_count == 10
    assert sorted(g.quantity for g in checked.groups) == [5, 5]
    output = tmp_path / "engine-q"
    output.mkdir()
    paths = api.save_checked_reopened_nfb_pair_q_dxf(checked, output)
    assert len(paths) == 2
    assert all(Path(path).is_file() for path in paths.values())


def test_real_headless_pair_refuses_source_or_count_drift(tmp_path):
    _, pair = _paired(tmp_path, "A")
    with pytest.raises(ValueError, match="QUANTITY"):
        api.group_reopened_nfb_pair_check_q((_input(pair, True),))
    source = Path(pair.source_path)
    source.write_bytes(source.read_bytes() + b"\\n")
    with pytest.raises(ValueError, match="REVERIFY_PAIR"):
        api.group_reopened_nfb_pair_check_q((_input(pair, 1),))
