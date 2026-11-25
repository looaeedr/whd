"""#2517 original Receiving GUI: real per-Bay 3D skins and amber crossings.

Headless Matplotlib executes the same original GUI draw function that the
operator's on-demand Set/Bay diagnostic popup calls. Every 3D triangle comes
from the *same* Engine collision audit as its physical-pair matrix, never from
a second GUI Joint transform or manufactured preview cube.
"""
from copy import deepcopy
from dataclasses import replace
import inspect

import ezdxf
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.receiving_cross_bay_diagnostic_3d import (
    paint_receiving_cross_bay_3d_figure,
)
from gui_modules.application.receiving_set_bay_controls import (
    receiving_cross_bay_collision_display_status,
)
import phase6_project_file as project
from tests.test_issue2517_saved_multiset_original_gui_cross_bay_collision_status import (
    _actual_original_preview_requests,
)
from tests.test_issue2517_saved_multiset_original_gui_grouped_dxf import (
    _saved_with_real_inner_door_state, _run_gui_group, PREFIX, BAYS,
)
from tests.test_issue2517_saved_cross_bay_world_collision_engine_api import (
    _simple_two_bay, _synthetic_provider,
)


def _shown(audit, status):
    fig = Figure(figsize=(7, 5), dpi=75)
    receipt = paint_receiving_cross_bay_3d_figure(
        fig, audit, status=status,
    )
    assert len(fig.axes) == 1
    assert fig.axes[0].name == "3d"
    assert len(fig.axes[0].collections) == (
        len(receipt.sheet_keys) + int(bool(receipt.unresolved_segments))
    )
    return fig, receipt


def test_persisted_two_sets_four_bays_actual_original_gui_3d_meshes_and_dxf(
    tmp_path, monkeypatch,
):
    saved, original_bytes, source = _saved_with_real_inner_door_state(tmp_path)
    loaded = project.read_project(saved)["snapshot"]
    untouched = deepcopy(loaded)
    for set_index in (0, 1):
        previews = _actual_original_preview_requests(loaded, set_index)
        audit, message = receiving_cross_bay_collision_display_status(
            loaded["receiving_layout"], previews, set_index=set_index,
        )
        _figure, receipt = _shown(audit, message)
        expected = tuple(
            key for bay in audit.physical_keys_by_bay for key in bay
        )
        assert receipt.sheet_keys == expected
        assert not receipt.missing_world_keys
        assert all("::" in key for key in receipt.sheet_keys)
        assert all(
            any(key.endswith("::inner_door:upper:panel") for key in bay)
            for bay in audit.physical_keys_by_bay
        )
        assert receipt.unresolved_segments == tuple(
            segment for row in audit.unresolved for segment in row.segments
        )
        assert audit.evaluated_pair_count == (
            len(audit.physical_keys_by_bay[0]) *
            len(audit.physical_keys_by_bay[1])
        )
        if receipt.unresolved_segments:
            assert isinstance(_figure.axes[0].collections[-1], Line3DCollection)
            assert "不可判定零碰撞" in message
        assert "非實體體積穿透或製造放行證明" in message
        # No mesh may be a cosmetic preview derived from a single Bay's
        # 2D rectangle; the exact Engine world triangles are retained here.
        assert tuple(key for group in audit.world_triangles_by_bay
                     for key, _triangles in group) == receipt.sheet_keys
        assert all(triangles for group in audit.world_triangles_by_bay
                   for _key, triangles in group)

    # The *same saved source* remains valid at the existing original GUI
    # Door/Base + independent Head grouped DXF output entrance.
    monkeypatch.setattr(
        "ae_engine.receiving_dxf_groups._taipei_output_stamp",
        lambda: PREFIX.split("_", 1)[0],
    )
    output = tmp_path / "actual-4-bay-overlay-plus-dxf"
    calls, errors, infos = _run_gui_group(
        monkeypatch, loaded, output, mode="ALL", with_nfb=True,
    )
    assert not errors, errors
    assert len(infos) == 1 and calls == list(BAYS)
    assert {p.name for p in output.glob("*.dxf")} == {
        PREFIX + "全部.dxf", PREFIX + "總計.dxf",
    }
    for path in output.glob("*.dxf"):
        doc = ezdxf.readfile(path)
        assert not doc.audit().errors, path.name
        assert any(e.dxf.layer == "CUTTING" for e in doc.modelspace())
    assert saved.read_bytes() == original_bytes
    assert loaded == untouched


def test_real_engine_joint_crossing_is_visible_as_3d_amber_segments(monkeypatch):
    from ae_engine import receiving_cross_bay_collision_display as impl

    a = ((400., -1., -1.), (400., 1., -1.), (400., 0., 1.))
    b = ((-401., 0., -0.5), (-399., 0., -0.5), (-400., 0., 1.))
    remote = ((10000., 0., 0.), (10001., 0., 0.), (10000., 1., 0.))
    calls = []
    def actual_mesh_owner(parts, dimensions, thickness):
        calls.append((dimensions, thickness))
        if len(calls) == 1:
            return {"world_triangles_by_part": {
                "box_body": (a,), "box_body:left_side": (remote,),
                "box_body:back": (remote,), "box_body:right_side": (a,),
            }}
        return {"world_triangles_by_part": {
            "box_body": (b,), "box_body:left_side": (b,),
            "box_body:back": (remote,), "box_body:right_side": (remote,),
        }}

    monkeypatch.setattr(impl, "build_joint_world_geometry", actual_mesh_owner)
    layout = _simple_two_bay()
    old = deepcopy(layout)
    audit = api.project_receiving_set_cross_bay_collision_display_audit(
        layout, _synthetic_provider, set_index=0, thickness_mm=2.0,
    )
    assert len(calls) == 2
    assert audit.bay_offsets == ((0.0, 0.0, 0.0), (800.0, 0.0, 0.0))
    assert audit.unresolved and audit.complete
    fig, receipt = _shown(audit, "橘色交線不得推論零穿透")
    assert receipt.unresolved_segments
    assert isinstance(fig.axes[0].collections[-1], Line3DCollection)
    assert any(
        key.endswith("::box_body:right_side") for key in receipt.sheet_keys
    )
    assert any(
        key.endswith("::box_body:left_side") for key in receipt.sheet_keys
    )
    # This second Bay triangle was x=-400 *locally*; the Engine (not GUI)
    # has applied the physical Joint 800 mm offset to show it at x=400.
    assert any(
        tri[0][0] == pytest.approx(399.0)
        for group in audit.world_triangles_by_bay[1]
        for key, tris in (group,)
        if key.endswith("::box_body:left_side")
        for tri in tris
    )
    assert layout == old


def test_partial_world_receipt_and_physical_key_drift_never_draw_as_clean(
    tmp_path,
):
    _saved, _bytes, source = _saved_with_real_inner_door_state(tmp_path)
    requests = _actual_original_preview_requests(source, 0)
    audit, message = receiving_cross_bay_collision_display_status(
        source["receiving_layout"], requests, set_index=0,
    )
    with pytest.raises(
        ValueError, match="RECEIVING_CROSS_BAY_3D_SOURCE_MESH_RECEIPT_MISSING"
    ):
        paint_receiving_cross_bay_3d_figure(
            Figure(), replace(audit, world_triangles_by_bay=()), status=message,
        )
    incomplete = (
        audit.world_triangles_by_bay[0][:-1],
        audit.world_triangles_by_bay[1],
    )
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_3D_SOURCE_KEY_DRIFT"):
        paint_receiving_cross_bay_3d_figure(
            Figure(), replace(audit, world_triangles_by_bay=incomplete),
            status=message,
        )


def test_original_set_gui_3d_popup_is_on_demand_and_operator_edits_close_it():
    from gui_modules.application import receiving_set_bay_controls as controls
    from gui_modules.application import receiving_cross_bay_diagnostic_3d as display

    controls_source = inspect.getsource(controls.open_receiving_layer_preview)
    assert "open_receiving_cross_bay_3d_popup(" in controls_source
    assert "subscribe(clear_cross_bay_diagnostic)" in controls_source
    assert "popup.destroy()" in controls_source
    assert "win._phase6_receiving_audit_cross_bay" in controls_source
    assert "receiving_live_cross_bay_collision_display_status" in controls_source
    painter_source = inspect.getsource(display.paint_receiving_cross_bay_3d_figure)
    assert "gridless_mesh_collection(" in painter_source
    assert "Line3DCollection(" in painter_source
    assert "manufacturing_api" not in painter_source
