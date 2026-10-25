# -*- coding: utf-8 -*-
"""Receiving: standalone FoldDesigner SIDE view must match authentic EAR contact.

Source panel/assembly stays untouched; only the independently selected 3D
piece gets the same display-only UV MARKING as the established primary 2D.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
from ae_engine.sheetmetal_drawing import LinePrimitive
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


@pytest.mark.parametrize("role", ("left_side", "right_side"))
def test_fold_designer_physical_side_displays_real_ear_marks_and_caches(
    monkeypatch, role,
):
    snapshot, geometry = _actual(_assembled)
    original = next(p for p in geometry.part("box_body").render_data.pieces
                    if p.role == role)
    before = tuple(original.render_data.scene.primitives)
    monkeypatch.setattr(
        bridge, "_phase6_resolve_manufacturing_geometry", lambda _: geometry,
    )
    host = SimpleNamespace(_phase6_input_snapshot=snapshot)
    key = f"box_body:{role}"
    display = bridge._phase6_box_body_piece_render_data(host, key)
    assert display is not original.render_data
    assert display.metadata["ear_side_mark_preview_only"] is True
    assert display.metadata["ear_side_mark_preview_owner"] == key
    assert display.metadata["ear_side_mark_preview_count"] == 3
    marks = tuple(p for p in display.scene.primitives
                  if isinstance(p, LinePrimitive) and p.layer == "MARKING")
    assert len(marks) >= 3
    assert display.material.equals(original.render_data.material)
    assert tuple(original.render_data.scene.primitives) == before
    assert host.last_receiving_ear_single_piece_blocker is None
    again = bridge._phase6_box_body_piece_render_data(host, key)
    assert again is display, "same source must not recompute 3D/world-UV repeatedly"
    assert tuple(original.render_data.scene.primitives) == before


def test_unsubmitted_designer_never_borrows_assembly_marks(monkeypatch):
    snapshot, geometry = _actual(_assembled)
    monkeypatch.setattr(
        bridge, "_phase6_resolve_manufacturing_geometry", lambda _: geometry,
    )
    host = SimpleNamespace(
        _phase6_input_snapshot={**snapshot, "nfb_config_submitted": False},
    )
    shown = bridge._phase6_box_body_piece_render_data(host, "box_body:left_side")
    source = next(p for p in geometry.part("box_body").render_data.pieces
                  if p.role == "left_side")
    assert shown is source.render_data
    assert host.last_receiving_ear_single_piece_blocker is None


def test_actual_source_conflict_does_not_create_false_single_piece_marks(
    monkeypatch,
):
    snapshot, geometry = _actual(_assembled)
    monkeypatch.setattr(
        bridge, "_phase6_resolve_manufacturing_geometry", lambda _: geometry,
    )
    import gui_modules.application.receiving_ear_side_2d as projection
    def fail_true_source(*args, **kwargs):
        raise ValueError("EAR_SIDE_UV_CUTTING_OR_MATERIAL_CONFLICT")
    monkeypatch.setattr(
        projection, "project_receiving_ear_side_piece_2d_preview",
        fail_true_source,
    )
    host = SimpleNamespace(_phase6_input_snapshot=deepcopy(snapshot))
    source = next(p for p in geometry.part("box_body").render_data.pieces
                  if p.role == "left_side")
    shown = bridge._phase6_box_body_piece_render_data(host, "box_body:left_side")
    assert shown is source.render_data
    assert host.last_receiving_ear_single_piece_blocker == (
        "EAR_SIDE_UV_CUTTING_OR_MATERIAL_CONFLICT"
    )
