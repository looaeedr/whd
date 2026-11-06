# -*- coding: utf-8 -*-
"""#2517 current Receiving EAR side cache and source-trust inputs are Engine-owned."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_ear_side_display_context as owner
from gui_modules.application import receiving_ear_side_2d as gui
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _scene():
    snap, geometry = _actual(_assembled)
    source = geometry.part("box_body").render_data
    return snap, geometry, source


def test_real_physical_side_source_stamp_is_identical_for_2d_and_3d():
    snapshot, geometry, body = _scene()
    context = api.resolve_receiving_ear_side_display_context(
        snapshot, "box_body:left_side", body,
    )
    assert isinstance(context, api.ReceivingEarSideDisplayContext)
    assert context.should_project
    assert context.dimensions == (800., 1600., 350.)
    assert context.sheet_thickness == 2.
    owners = tuple(
        (p.role, (p.render_data.metadata or {}).get("baseline_source_sha256"),
         repr(tuple(p.render_data.scene.primitives or ())))
        for p in body.pieces
    )
    assert context.source_stamp == sha256(
        repr((snapshot, "box_body:left_side", owners)).encode("utf-8")
    ).hexdigest()
    assert api.resolve_receiving_ear_side_display_context(
        snapshot, "box_body:left_side",
    ).source_stamp is None
    with pytest.raises(FrozenInstanceError):
        context.should_project = False


def test_stale_primary_claim_fails_closed_but_real_submitted_source_projects():
    snapshot, geometry, body = _scene()
    unset = {**snapshot, "nfb_config_submitted": False}
    assert not api.resolve_receiving_ear_side_display_context(
        unset, "box_body:left_side", body,
    ).should_project
    with pytest.raises(ValueError, match="EAR_2D_PREVIEW_PRIMARY_SOURCE_DRIFT"):
        api.resolve_receiving_ear_side_display_context(
            unset, "box_body:left_side", body, main_mirror=snapshot,
        )
    assert not api.resolve_receiving_ear_side_display_context(
        {"model": "金庫型"}, "box_body:left_side", body,
    ).should_project
    assert not api.resolve_receiving_ear_side_display_context(
        snapshot, "box_body:back", body,
    ).should_project


def test_real_baseline_or_selected_side_invalidates_presentation_cache():
    snapshot, geometry, body = _scene()
    left = api.resolve_receiving_ear_side_display_context(
        snapshot, "box_body:left_side", body,
    )
    right = api.resolve_receiving_ear_side_display_context(
        snapshot, "box_body:right_side", body,
    )
    assert left.source_stamp != right.source_stamp
    first = body.pieces[0]
    changed_piece = replace(first, render_data=replace(
        first.render_data, metadata={
            **first.render_data.metadata,
            "baseline_source_sha256": "different-source-sha",
        },
    ))
    changed = replace(body, pieces=(changed_piece,) + tuple(body.pieces[1:]))
    after = api.resolve_receiving_ear_side_display_context(
        snapshot, "box_body:left_side", changed,
    )
    assert after.source_stamp != left.source_stamp


def test_both_gui_ear_side_paths_only_consume_public_engine_source_context():
    src = inspect.getsource(gui)
    assert src.count("manufacturing_api.resolve_receiving_ear_side_display_context(") >= 2
    assert "sha256(" not in src and "baseline_source_sha256" not in src
    assert "EAR_2D_PREVIEW_PRIMARY_SOURCE_DRIFT" not in src
    assert "manufacturing_api.project_receiving_ear_side_piece_2d_preview(" in src
    assert "gui_modules" not in inspect.getsource(owner)
    assert api.ReceivingEarSideDisplayContext is owner.ReceivingEarSideDisplayContext
