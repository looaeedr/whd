# -*- coding: utf-8 -*-
"""#1504 AC-09/24: link live V5 diagnosis to ORIGINAL manufacturing hard gate.

Use the existing tested CENTER Base Plate fixture and real PART_ONLY DXF
writer. These are source/part gate checks only, not an entire Windows GUI UAT
or whole-cabinet manufacturing release.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_v5_diagnostics import current_v5_nfb_diagnostics
from tests.test_issue1502_csv_v5_part_only_manufacturing import (
    _current, _export,
)


def _status(snapshot):
    layout=snapshot["receiving_layout"]
    bay=layout["sets"][0]["bays"][0]
    return current_v5_nfb_diagnostics(
        bay,
        set_id=layout["sets"][0]["stable_id"],
        bay_id=bay["stable_id"],
        version_id="inner-door-v1",
        dependent_part_ids=("base_plate",),
        unaffected_part_ids=("side_panel:left",),
    )


def test_ac09_ac24_real_current_source_is_not_green_until_original_part_writer_verifies(tmp_path):
    snap=_current()
    snap["receiving_base_plate"]={"pattern":"CENTER_DOUBLE_SIDE_FOLD"}
    prior=_status(snap)
    assert prior["derived_state"]=="CONFIGURED"
    assert not prior["manufacturing_ready"] and prior["actual_export_count"] is None
    assert prior["part_rows"][0]["status"]=="RECHECK_ONLY"
    # This is the same source-backed original NFB Base Plate writer exercised
    # by #1502; it rechecks physical blank / NFB source / CHECK-Q and DXF.
    exported=_export(snap,tmp_path/"accepted")
    assert Path(exported.path).is_file()
    assert exported.source_hole_ids==("nfb:0","nfb:1")
    assert prior["manufacturing_ready"] is False
    assert prior["part_rows"][1]["status"]=="NFB_UNAFFECTED"


def test_ac09_invalid_saved_model_blocks_original_part_export_with_no_dxf(tmp_path):
    snap=_current()
    snap["receiving_base_plate"]={"pattern":"CENTER_DOUBLE_SIDE_FOLD"}
    snap["nfb_config"]["holes"][1]["model_filename"]="nfbv5:士林:NO-SUCH-MODEL"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"]
    )
    state=_status(snap)
    assert state["derived_state"]=="DRAFT"
    assert "NFB_CSV_MODEL_MISSING" in state["unit_rows"][1]["reasons"]
    assert state["part_rows"][0]["status"]=="BLOCKED"
    assert state["part_rows"][1]["status"]=="NFB_UNAFFECTED"
    dest=tmp_path/"unverified"
    with pytest.raises((ValueError,KeyError,OSError)):
        _export(snap,dest)
    assert not list(dest.glob("*.dxf"))


def test_ac24_unconfirmed_world_x_blocks_original_dxf_not_unrelated_scope(tmp_path):
    snap=_current()
    snap["receiving_base_plate"]={"pattern":"CENTER_DOUBLE_SIDE_FOLD"}
    snap["nfb_config"]["holes"][0]["manual_x_state"]="RECONFIRM_REQUIRED"
    snap["nfb_config"]["holes"][0]["manual_x_mm"]=None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snap["nfb_config"]
    )
    state=_status(snap)
    assert state["derived_state"]=="DRAFT"
    assert state["unit_rows"][0]["reasons"]==("NFB_WORLD_X_RECONFIRM_REQUIRED",)
    assert state["part_rows"][0]["status"]=="BLOCKED"
    assert state["part_rows"][1]["status"]=="NFB_UNAFFECTED"
    dest=tmp_path/"not-approved"
    with pytest.raises(ValueError):
        _export(snap,dest)
    assert not list(dest.glob("*.dxf"))
