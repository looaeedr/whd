# -*- coding: utf-8 -*-
"""Common PAD 2D operator PartReadOnlyData follows same committed V5 source."""
from copy import deepcopy
import pytest
from ae_engine.receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from ae_engine.receiving_nfb_numeric_catalog import model_spec
from ae_engine.receiving_nfb_pad_generator import read_pad_tooling_rule


def test_current_one_tier_csv_selection_generates_single_real_pad_2d_sheet():
    snap=_current()
    parts=committed_nfb_pad_draft_parts(snap)
    assert len(parts)==1
    pad=parts[0]
    assert pad.parent_base_id=="base_plate"
    selected=tuple(model_spec("士林",row["model_filename"].rsplit(":",1)[-1])
                   for row in snap["nfb_config"]["holes"])
    assert pad.pattern.rise_mm==pytest.approx(
        max(s.depth_mm for s in selected)-min(s.depth_mm for s in selected))
    assert pad.render_data.unfolded_topology.width==pytest.approx(
        pad.pattern.blank_width_mm+2*read_pad_tooling_rule().tab_projection_mm)
    assert pad.render_data.unfolded_topology.height==pytest.approx(
        pad.pattern.formed_height_mm)
    assert pad.part_id.startswith("nfb_pad:")
    assert pad.part_id.endswith(snap["nfb_config"]["holes"][1]["physical_hole_id"])
    assert pad.manufacturing_ready is False
    assert pad.render_data.metadata["manufacturing_ready"] is False
    assert pad.render_data.metadata["nfb_deferred_manufacturing_role"]=="PAD"
    assert len(pad.render_data.fold_guides)==2


def test_existing_explicit_center_has_no_spurious_pad_navigation_or_double_compensation():
    snap=_current()
    snap["receiving_base_plate"]={"pattern":"CENTER_DOUBLE_SIDE_FOLD"}
    assert committed_nfb_pad_draft_parts(snap)==()


def test_uncommitted_and_no_source_bay_may_not_fabricate_pad_entries():
    snap=_current()
    snap["nfb_config_submitted"]=False
    assert committed_nfb_pad_draft_parts(snap)==()
    snap["nfb_config_submitted"]=True
    snap["nfb_config"]["holes"][1]["model_filename"]="nfbv5:士林:UNKNOWN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError):
        committed_nfb_pad_draft_parts(snap)



def test_native_part_renderer_reads_true_pad_2d_without_mfg_claim():
    from types import SimpleNamespace
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _query_fold_designer_render_data,
    )
    from phase6_part_navigation import operator_part_label
    from phase6_manufacturing_adapter import _canonical_part_keys
    snap=_current()
    selected,=committed_nfb_pad_draft_parts(snap)
    owner=SimpleNamespace(_phase6_input_snapshot=snap)
    host=SimpleNamespace(fold_designer_app=owner)
    rendered=_query_fold_designer_render_data(host,selected.part_id,{"features":()})
    assert rendered.material.equals(selected.render_data.material)
    assert rendered.unfolded_topology == selected.render_data.unfolded_topology
    assert rendered.metadata["nfb_deferred_manufacturing_role"]=="PAD"
    assert rendered.metadata["manufacturing_ready"] is False
    assert "墊高片" in operator_part_label(selected.part_id,snapshot=snap)
    app=SimpleNamespace(designer_workspace=SimpleNamespace(available_parts=(
        "box_body","base_plate",selected.part_id)),
        _phase6_input_snapshot=snap)
    canonical=_canonical_part_keys(app)
    assert "base_plate" in canonical
    assert selected.part_id not in canonical


def test_old_pad_2d_navigation_key_rejected_after_center_change():
    from types import SimpleNamespace
    from gui_modules.application.fold_designer_manufacturing_projection import (
        _query_fold_designer_render_data,
    )
    snap=_current()
    part,=committed_nfb_pad_draft_parts(snap)
    snap["receiving_base_plate"]={
        "pattern":"CENTER_DOUBLE_SIDE_FOLD","height":280.,"shrink_top":20.,
        "shrink_bottom":20.,"shrink_left":85.,"shrink_right":85.,"bend":20.,
    }
    with pytest.raises(ValueError,match="PAD_OPERATOR_2D_STALE"):
        _query_fold_designer_render_data(
            SimpleNamespace(fold_designer_app=SimpleNamespace(
                _phase6_input_snapshot=snap)),
            part.part_id,{"features":()},
        )
