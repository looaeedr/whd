"""#2517: exact physical EAR side MARKING readback is Engine-owned."""
from __future__ import annotations

from dataclasses import replace
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import LinePrimitive
from gui_modules.application import receiving_ear_side_2d as gui
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _real_source():
    snapshot, geometry = _actual(_assembled)
    source = next(
        piece for piece in geometry.part("box_body").render_data.pieces
        if piece.role == "left_side"
    )
    return snapshot, geometry, source


def _project(snapshot, geometry, source, **kw):
    return manufacturing_api.project_receiving_ear_side_piece_2d_preview(
        snapshot, source, piece_key="box_body:left_side", geometry=geometry,
        dimensions=(800., 1600., 350.), sheet_thickness=2.,
        display_only_marking_overlap=True, **kw,
    )


def test_public_engine_owns_real_side_material_and_read_only_marking_scene():
    snapshot, geometry, source = _real_source()
    original = source.render_data
    before = tuple(original.scene.primitives)
    result = _project(snapshot, geometry, source)
    assert result is not source
    assert result.render_data is not original
    assert result.render_data.scene is not original.scene
    assert result.render_data.metadata["ear_side_mark_preview_only"] is True
    assert result.render_data.metadata["ear_side_mark_preview_owner"] == "box_body:left_side"
    assert result.render_data.metadata["ear_side_mark_preview_count"] == 3
    assert result.render_data.material.equals(original.material)
    assert tuple(original.scene.primitives) == before
    assert sum(
        isinstance(row, LinePrimitive) and row.layer == "MARKING"
        for row in result.render_data.scene.primitives
    ) >= 3
    assert result.render_data.metadata.get("manufacturing_ready") == original.metadata.get("manufacturing_ready")


def test_real_source_side_guard_rejects_stale_material_and_identity():
    snapshot, geometry, source = _real_source()
    with pytest.raises(ValueError, match="EXPECTS_PHYSICAL_SIDE"):
        manufacturing_api.project_receiving_ear_side_piece_2d_preview(
            snapshot, source, piece_key="box_body:back",
            geometry=geometry, dimensions=(800., 1600., 350.), sheet_thickness=2.,
        )
    with pytest.raises(ValueError, match="REQUIRES_SUBMITTED_RECEIVING"):
        _project({**snapshot, "nfb_config_submitted": False}, geometry, source)
    with pytest.raises(ValueError, match="PIECE_ROLE_MISMATCH"):
        _project(snapshot, geometry, replace(source, role="right_side"))
    with pytest.raises(ValueError, match="SOURCE_AND_MANUFACTURING_SIDE_DRIFT"):
        from shapely.geometry import box
        tampered = replace(
            source, render_data=replace(
                source.render_data, material=box(0, 0, 3, 3),
            ),
        )
        _project(snapshot, geometry, tampered)
    with pytest.raises(ValueError, match="SIDE_BASELINE_SOURCE_DRIFT"):
        meta = dict(source.render_data.metadata or {})
        meta["baseline_source_sha256"] = "untrusted-other-source"
        bad = replace(source, render_data=replace(source.render_data, metadata=meta))
        _project(snapshot, geometry, bad)


def test_gui_2d_and_3d_compatibility_path_use_exact_public_engine_api():
    source = inspect.getsource(gui.project_receiving_ear_side_piece_2d_preview)
    assert "manufacturing_api.project_receiving_ear_side_piece_2d_preview(" in source
    assert "owner_render_data(" not in source
    assert "resolve_receiving_ear_side_uv_receipts(" not in source
    assert "build_receiving_ear_side_marking_previews(" not in source
    assert "_phase6_build_joint_world_geometry(" not in source
    # GUIs retain existing cache and in-case-of-conflict source fallback.
    assert "host._receiving_ear_side_2d_display_cache" in inspect.getsource(
        gui.present_receiving_ear_side_piece_2d
    )
    assert "host.last_receiving_ear_single_piece_blocker" in inspect.getsource(
        gui.present_receiving_ear_side_designer_piece_3d
    )
