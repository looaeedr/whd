"""#2517 original Receiving set-settings GUI → exact Engine cross-Bay 3D evidence.

Original Bay preview must retain its canonical per-Bay identity and FinalScene.
On-demand GUI diagnostic must not silently reuse a stale/single-Bay/other-Set
scene, manufacture its own Joint offsets, or label surface crossings as solid
zero-penetration. The saved 2-Set × 2-Bay source is the same used for original
GUI grouped NFB/DXF validation.
"""
from copy import deepcopy
from dataclasses import replace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.receiving_set_bay_controls import (
    receiving_cross_bay_collision_display_status,
    receiving_live_cross_bay_collision_display_status,
)
from phase6_final_scene_contracts import (
    AssemblySceneRenderData, FinalSceneViewRequest,
)
import phase6_project_file as project
from tests.test_issue2517_saved_multiset_original_gui_grouped_dxf import (
    _saved_with_real_inner_door_state,
)
from tests.test_issue2517_saved_nfb_pair_real_inner_door_3d_profiles import (
    _fully_profiled_bay_source,
)


def _actual_original_preview_requests(snapshot, set_index):
    """Use independent Engine resolutions from each actual saved physical Bay.

    Only display DTO assembly parts are empty in this headless adapter test;
    the immutable collision source is the complete REAL resolved FinalScene.
    No fake triangle, synthetic material or GUI geometry calculation appears.
    """
    resolved, calls = _fully_profiled_bay_source(snapshot)
    selected = snapshot["receiving_layout"]["sets"][set_index]
    requests = []
    for bi, bay in enumerate(selected["bays"]):
        scene = resolved(set_index, bi)
        requests.append(FinalSceneViewRequest(
            render_data=AssemblySceneRenderData(assembly_parts=()),
            x_profile=(), y_profile=(), part_key="assembly",
            finished_dimensions=(
                bay["width"], bay["height"], bay["depth"]
            ),
            thickness=snapshot["t"],
            receiving_collision_geometry=scene,
            receiving_collision_identity=(
                selected["stable_id"], bay["stable_id"],
            ),
        ))
    assert calls == [(set_index, bi) for bi in range(len(selected["bays"]))]
    return tuple(requests)


def test_saved_four_bay_real_gui_source_cross_bay_diagnostics_match_engine(
    tmp_path,
):
    saved, original_bytes, authored = _saved_with_real_inner_door_state(tmp_path)
    loaded = project.read_project(saved)["snapshot"]
    original_snapshot = deepcopy(loaded)
    for si in (0, 1):
        old = _actual_original_preview_requests(authored, si)
        new = _actual_original_preview_requests(loaded, si)
        audit, text = receiving_live_cross_bay_collision_display_status(
            lambda: loaded["receiving_layout"], lambda: new, set_index=si,
        )
        expected = api.project_receiving_set_cross_bay_collision_display_audit(
            loaded["receiving_layout"],
            lambda s, b: new[b].receiving_collision_geometry,
            set_index=si, thickness_mm=loaded["t"],
        )
        before, original_text = receiving_cross_bay_collision_display_status(
            authored["receiving_layout"], old, set_index=si,
        )
        assert audit == expected == before
        assert text == original_text
        assert audit.set_id == loaded["receiving_layout"]["sets"][si]["stable_id"]
        assert audit.complete and not audit.missing_world_keys
        assert audit.require_complete()
        assert all(
            any(k.endswith("::inner_door:upper:panel") for k in bay)
            for bay in audit.physical_keys_by_bay
        )
        assert audit.evaluated_pair_count == (
            len(audit.physical_keys_by_bay[0]) * len(audit.physical_keys_by_bay[1])
        )
        assert "跨連 3D 表面診斷" in text
        assert "非實體體積穿透或製造放行證明" in text
        if audit.unresolved:
            assert "不可判定零碰撞" in text
        else:
            assert "未觀察到非共面交線" in text
    assert loaded == original_snapshot
    assert saved.read_bytes() == original_bytes


def test_original_gui_preview_set_and_bay_identity_must_not_be_borrowed(
    tmp_path,
):
    _saved, _bytes, saved = _saved_with_real_inner_door_state(tmp_path)
    requests = _actual_original_preview_requests(saved, 0)
    other = _actual_original_preview_requests(saved, 1)
    layout = saved["receiving_layout"]
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_PREVIEW_IDENTITY_DRIFT"):
        receiving_cross_bay_collision_display_status(
            layout, tuple(reversed(requests)), set_index=0,
        )
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_PREVIEW_IDENTITY_DRIFT"):
        receiving_cross_bay_collision_display_status(
            layout, other, set_index=0,
        )
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_PREVIEW_COUNT_DRIFT"):
        receiving_cross_bay_collision_display_status(
            layout, (requests[0],), set_index=0,
        )


def test_original_gui_preview_stale_and_missing_finalscene_fail_closed(
    tmp_path,
):
    _saved, _bytes, saved = _saved_with_real_inner_door_state(tmp_path)
    requests = _actual_original_preview_requests(saved, 0)
    layout = saved["receiving_layout"]
    for error, wrong in (
        ("RECEIVING_CROSS_BAY_PREVIEW_DIMENSION_DRIFT",
         replace(requests[1], finished_dimensions=(10, 20, 30))),
        ("RECEIVING_CROSS_BAY_PREVIEW_THICKNESS_DRIFT",
         replace(requests[1], thickness=3.0)),
        ("RECEIVING_CROSS_BAY_PREVIEW_FINALSCENE_REQUIRED",
         replace(requests[1], receiving_collision_geometry=None)),
        ("RECEIVING_CROSS_BAY_PREVIEW_ASSEMBLY_REQUIRED",
         replace(requests[1], part_key="head")),
    ):
        with pytest.raises(ValueError, match=error):
            receiving_cross_bay_collision_display_status(
                layout, (requests[0], wrong), set_index=0,
            )


def test_original_gui_modal_mutable_bay_source_drift_is_rejected(tmp_path):
    saved, before_bytes, source = _saved_with_real_inner_door_state(tmp_path)
    layout = deepcopy(source["receiving_layout"])
    requests = _actual_original_preview_requests(source, 0)
    def change_source_during_resolve():
        # Same object is retained by the original modal editor. A shallow
        # identity comparison would miss this nested mutation entirely.
        layout["sets"][0]["bays"][1]["width"] += 13.0
        return requests
    with pytest.raises(ValueError, match="RECEIVING_CROSS_BAY_SOURCE_DRIFT"):
        receiving_live_cross_bay_collision_display_status(
            lambda: layout, change_source_during_resolve, set_index=0,
        )
    assert saved.read_bytes() == before_bytes


def test_original_gui_widget_inserts_on_demand_engine_diagnostic_not_geometry():
    from gui_modules.application import receiving_set_bay_controls as controls
    from gui_modules.application import fold_designer_composition_receiving as composition

    widget = inspect.getsource(controls.open_receiving_layer_preview)
    assert 'text="跨連 3D 碰撞診斷"' in widget
    assert "receiving_live_cross_bay_collision_display_status" in widget
    assert "win._phase6_receiving_audit_cross_bay" in widget
    assert "manufacturing_api.project_receiving_set_cross_bay_collision_from_preview_requests" in inspect.getsource(
        controls.receiving_cross_bay_collision_display_status
    )
    composer = inspect.getsource(composition.receiving_bay_preview_request)
    assert "receiving_collision_geometry=resolved" in composer
    assert "receiving_collision_identity=" in composer
    assert "plan_receiving_bay_preview_offset_rebase" not in widget
