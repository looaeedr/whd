# -*- coding: utf-8 -*-
"""Regression suite for the 14 deep-audit bugs (#1-#14)."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import tkinter as tk
from shapely.geometry import Polygon

from ae_engine.assembly_collision_basic import _scene_with_replaced_primary_cutting
from ae_engine.cutting_material import material_from_cutting_components
from ae_engine.drawing_annotation_layout import (
    _annotation_dimension_line_regions,
    _text_region,
    resolve_annotation_collisions,
)
from ae_engine.manufacturing_render_data import (
    _translated_scene,
    material_polygon_from_final_scene,
)
from ae_engine.receiving_layout import (
    new_receiving_layout,
    project_primary_bay_legacy_aliases,
    project_receiving_bay_legacy_aliases,
    resize_receiving_bays,
    update_receiving_bay,
)
from ae_engine.receiving_pairing_marking import _existing_conflict_geometry
from ae_engine.sheetmetal_drawing import (
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
    TextPrimitive,
)
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.fold_designer_snapshot_projection import (
    _snapshot_workspace_state,
)
from gui_modules.application.lifecycle import (
    _apply_fold_designer_live_settings,
    _apply_fold_designer_live_snapshot,
)
from gui_modules.application.state_sync import phase6_external_sync_envelope
from phase6_bending_ui import Phase6BendingUI
from phase6_registry_diagnostics_panel import (
    Phase6RegistryDiagnosticsPanel,
    _REGISTRY_PRESENTATION_FALLBACK,
    registry_source_display,
    registry_source_raw,
)
from phase6_settings_profile_projection import (
    SettingsProfileProjectionRequest,
    build_settings_profile_projection,
    is_derived_physical_part_key,
)
from phase6_workspace_controller import Phase6WorkspaceController


class _FakeSettingsSnapshot(dict):
    def as_dict(self):
        return dict(self)


class _FakeSettingsService:
    def __init__(self, initial):
        self._data = dict(initial)

    def snapshot(self):
        return _FakeSettingsSnapshot(self._data)

    def update(self, values):
        self._data.update(values)
        return self.snapshot()


class _FakeVar:
    def __init__(self, value=""):
        self._value = value
        self._traces = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for cb in list(self._traces):
            cb()

    def trace_add(self, _mode, callback):
        self._traces.append(callback)


def test_bug1_main_sync_fingerprint_updates_after_fold_designer_live_settings():
    """Bug #1: 3D live settings A->B must update _phase6_main_sync_fingerprint so 2D B->A syncs."""
    host = SimpleNamespace()
    host.settings_service = _FakeSettingsService({"w": 500.0, "h": 600.0})
    host._phase6_main_sync_revision = 0
    host._phase6_main_sync_fingerprint = None
    host._phase6_update_scheduler = None
    host._settings_sync_guard = False
    host._setting_var_map = lambda: {}
    host._fold_designer_number_text = lambda v: str(v)
    host.base_plate_all_same_var = _FakeVar(True)
    host.base_plate_shrink_same_var = _FakeVar("15")
    host._request_phase6_update = lambda *_a, **_kw: None

    # 1. Main GUI establishes initial fingerprint for w=500.0
    env1 = phase6_external_sync_envelope(host, {"settings": {"w": 500.0}})
    assert env1 is not None

    # 2. 3D Fold Designer changes w from 500.0 to 650.0
    _apply_fold_designer_live_settings(host, {"w": 650.0}, recalculate=False)
    assert host.settings_service.snapshot()["w"] == 650.0

    # 3. User changes w back from 650.0 to 500.0 in Main GUI
    host.settings_service.update({"w": 500.0})
    env2 = phase6_external_sync_envelope(host, {"settings": {"w": 500.0}})
    assert env2 is not None, "Reverting setting in 2D back to pre-3D value must emit sync envelope"
    assert env2["revision"] == 2


def test_bug2_multi_door_hole_edits_in_2d_override_stale_surface_features():
    """Bug #2: 2D door_layout_features updates must not be ignored by setdefault in _snapshot_workspace_state."""
    old_hole = CircleFeature(
        diameter=10.0,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(50.0, 50.0),
    )
    new_hole = CircleFeature(
        diameter=22.0,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(80.0, 90.0),
    )

    host = SimpleNamespace()
    host.workspace_controller = Phase6WorkspaceController()
    host._phase6_current_existing_parts = lambda: ("box_body", "head", "tail", "door")
    host.endcap_fw_state = {"head": {"follow_box": True, "value": 25.0}, "tail": {"follow_box": True, "value": 25.0}}
    host.endcap_bottom_wrap_state = {"head": False, "tail": False}
    host.assembly_relief_state = {}
    host._current_box_assembly_type = lambda: "INSERT_OVERLAY"
    host._serialize_manual_corner_state = lambda: {}
    host.manual_corner_pair_same = {}
    host.assembly_joint_state = {}
    host.surface_features = {
        "box_body": [],
        "door": [],
        "door_c1_r1": [old_hole],
    }
    host.door_layout_features = {
        "0:0": [new_hole],
    }
    host.box_body_face_features = {}

    snapshot = {
        "fw": 25.0,
        "assembly_type": "INSERT_OVERLAY",
        "multi_door_enabled": True,
        "door_layout_columns": [(500.0, (600.0,))],
    }
    _snapshot_workspace_state(host, snapshot)
    assert snapshot["part_features"]["door_c1_r1"] == [new_hole]

    # Also verify emptying the cell in 2D clears the stale surface_features entry in snapshot
    host.door_layout_features["0:0"] = []
    snapshot2 = {
        "fw": 25.0,
        "assembly_type": "INSERT_OVERLAY",
        "multi_door_enabled": True,
        "door_layout_columns": [(500.0, (600.0,))],
    }
    _snapshot_workspace_state(host, snapshot2)
    assert snapshot2["part_features"]["door_c1_r1"] == []


def test_bug3_custom_part_only_change_syncs_surface_features():
    """Bug #3: custom_part_only_change fast path in _apply_fold_designer_live_snapshot must update surface_features."""
    hole = CircleFeature(
        diameter=16.0,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(40.0, 40.0),
    )
    custom_parts_catalog = {
        "items": {
            "custom:1": {
                "display_name": "自訂1",
                "per_box_count": 1,
                "fold_axis": "X",
                "transverse_length": 100.0,
            }
        }
    }
    prev_payload = {
        "origin": "fold_designer",
        "revision": 1,
        "fingerprint": "fp1",
        "model": "金庫型",
        "active_part": "custom:1",
        "custom_parts": custom_parts_catalog,
        "part_features": {"custom:1": []},
        "workspace": {
            "existing_parts": ["box_body", "custom:1"],
            "active_part": "custom:1",
            "part_profiles": {},
            "box_body_structure": {},
            "custom_parts": custom_parts_catalog,
            "part_features": {"custom:1": []},
        },
    }
    next_payload = {
        **prev_payload,
        "revision": 2,
        "fingerprint": "fp2",
        "part_features": {"custom:1": [hole]},
        "workspace": {
            **prev_payload["workspace"],
            "part_features": {"custom:1": [hole]},
        },
    }

    captured = []
    host = SimpleNamespace()
    host._fold_designer_live_sync_guard = False
    host._phase6_last_fold_designer_revision = 1
    host._phase6_last_fold_designer_fingerprint = "fp1"
    host._phase6_last_fold_designer_live_payload = prev_payload
    host.workspace_controller = Phase6WorkspaceController()
    host.surface_features = {"box_body": [], "custom:1": []}
    host._compose_phase6_project_snapshot_from_main_gui = lambda: {
        "part_features": dict(host.surface_features),
    }
    host.project_controller = SimpleNamespace(
        capture_committed=lambda snap: captured.append(snap)
    )

    applied = _apply_fold_designer_live_snapshot(host, next_payload)
    assert applied is True
    assert host.surface_features["custom:1"] == [hole]
    assert captured[-1]["part_features"]["custom:1"] == [hole]


def test_bug4_receiving_multi_bay_projection_does_not_leak_bay0_door_state():
    """Bug #4: Bay 0 door_state mirrored to root must not leak into Bay 1 when Bay 1 has no door_state."""
    layout = new_receiving_layout(width=600.0, height=1800.0, depth=500.0)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=2)
    # Bay 0 gets a custom 600mm multi-door layout; Bay 1 is resized to width 800mm without door_state
    layout = update_receiving_bay(
        layout,
        set_index=0,
        bay_index=0,
        door_state={
            "multi_door_enabled": True,
            "door_layout_columns": [(600.0, (1800.0,))],
        },
    )
    layout = update_receiving_bay(
        layout,
        set_index=0,
        bay_index=1,
        width=800.0,
    )
    # Remove door_state from Bay 1 if cloned so we test a bay without door_state
    layout["sets"][0]["bays"][1].pop("door_state", None)

    snapshot = {
        "model": "受電箱",
        "w": 600.0,
        "h": 1800.0,
        "d": 500.0,
        "receiving_layout": layout,
    }
    snapshot = project_primary_bay_legacy_aliases(snapshot)
    assert snapshot.get("multi_door_enabled") is True

    # Projecting Bay 1 (width 800) must not inherit Bay 0's 600mm door_layout_columns and crash validation
    projected_bay1 = project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=1, validate_common=True
    )
    assert projected_bay1["w"] == 800.0
    # A Bay with no persisted door_state receives this Bay's family default,
    # not Bay 0's edited 600-mm door layout.
    # This fixture has no saved inner-door authority: Bay 1 stays
    # unconfigured, without borrowing Bay 0's operator door layout.
    assert not projected_bay1.get("multi_door_enabled", False)
    assert "door_layout_columns" not in projected_bay1
    assert "door_state" not in projected_bay1["receiving_layout"]["sets"][0]["bays"][1]


def test_bug5_translated_scene_preserves_text_primitive_semantic_id():
    """Bug #5: _translated_scene must preserve TextPrimitive.semantic_id."""
    scene = DrawingScene()
    scene.add(
        TextPrimitive(
            text="數量: 2",
            insert=Vec2(10.0, 20.0),
            layer="TEXT",
            char_height=18.0,
            attachment_point=7,
            color="#ffffff",
            semantic_id="manufacturing_quantity",
        )
    )
    translated = _translated_scene(scene, 100.0, 50.0)
    text_prim = translated.primitives[0]
    assert isinstance(text_prim, TextPrimitive)
    assert text_prim.insert == Vec2(110.0, 70.0)
    assert text_prim.semantic_id == "manufacturing_quantity"


def test_bug6_material_from_cutting_components_promotes_outer_linework_over_inner_polyline():
    """Bug #6: Closed polyline interior hole before segmented CUTTING outer contour must not invert material."""
    scene = DrawingScene()
    # Interior rectangular cutout added as a closed PolylinePrimitive
    scene.add(
        PolylinePrimitive(
            points=(Vec2(40.0, 40.0), Vec2(60.0, 40.0), Vec2(60.0, 60.0), Vec2(40.0, 60.0)),
            layer="CUTTING",
            closed=True,
        )
    )
    # Outer 200x100 sheet added as segmented LinePrimitives
    scene.add(LinePrimitive(Vec2(0.0, 0.0), Vec2(200.0, 0.0), layer="CUTTING"))
    scene.add(LinePrimitive(Vec2(200.0, 0.0), Vec2(200.0, 100.0), layer="CUTTING"))
    scene.add(LinePrimitive(Vec2(200.0, 100.0), Vec2(0.0, 100.0), layer="CUTTING"))
    scene.add(LinePrimitive(Vec2(0.0, 100.0), Vec2(0.0, 0.0), layer="CUTTING"))

    material = material_polygon_from_final_scene(scene)
    assert abs(float(material.area) - (200.0 * 100.0 - 20.0 * 20.0)) < 1e-3
    assert len(material.interiors) == 1


def test_bug7_scene_with_replaced_primary_cutting_preserves_inner_closed_polyline_holes():
    """Bug #7: _scene_with_replaced_primary_cutting must replace outer boundary, not first inner closed hole."""
    scene = DrawingScene()
    # Inner hole appears first (or alongside segmented outer lines)
    hole_poly = PolylinePrimitive(
        points=(Vec2(40.0, 40.0), Vec2(60.0, 40.0), Vec2(60.0, 60.0), Vec2(40.0, 60.0)),
        layer="CUTTING",
        closed=True,
    )
    outer_poly = PolylinePrimitive(
        points=(Vec2(0.0, 0.0), Vec2(200.0, 0.0), Vec2(200.0, 100.0), Vec2(0.0, 100.0)),
        layer="CUTTING",
        closed=True,
    )
    scene.add(hole_poly)
    scene.add(outer_poly)

    notched_material = Polygon(
        [(0.0, 0.0), (190.0, 0.0), (190.0, 10.0), (200.0, 10.0), (200.0, 100.0), (0.0, 100.0)],
        holes=[[(40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0)]],
    )
    updated = _scene_with_replaced_primary_cutting(scene, notched_material)
    cutting_polys = [
        Polygon([(p.x, p.y) for p in prim.points])
        for prim in updated.primitives
        if isinstance(prim, PolylinePrimitive) and prim.closed and prim.layer == "CUTTING"
    ]
    areas = sorted(round(float(p.area), 2) for p in cutting_polys)
    assert areas == [400.0, 19900.0]


def test_bug8_text_region_respects_mtext_attachment_points():
    """Bug #8: _text_region must center attachment_point 8 (Bottom-Center) horizontally."""
    text_bc = TextPrimitive(
        text="100",
        insert=Vec2(50.0, 10.0),
        layer="TEXT",
        char_height=10.0,
        attachment_point=8,
    )
    region = _text_region(text_bc)
    width = 10.0 * 0.6 * 3
    assert abs(region.min_x - (50.0 - width / 2.0)) < 1e-6
    assert abs(region.max_x - (50.0 + width / 2.0)) < 1e-6
    assert abs(region.min_y - 10.0) < 1e-6
    assert abs(region.max_y - 20.0) < 1e-6


def test_bug9_displaced_callout_leader_is_included_in_obstacle_line_regions():
    """Bug #9: Displaced callout leader lines on layer TEXT must be treated as line obstacles."""
    @dataclass(frozen=True)
    class _Callout:
        semantic_id: str
        source_id: str
        anchor: Vec2

    plan = SimpleNamespace(
        feature_callouts=(_Callout("callout:1", "hole_1", Vec2(50.0, 50.0)),),
        corner_callouts=(),
        radius_callouts=(),
        overall_dimensions=(),
        primitives=(
            TextPrimitive("2-Ø10", Vec2(50.0, 50.0), "TEXT", 5.0, 5, semantic_id="callout:1"),
            TextPrimitive("FIXED", Vec2(50.0, 50.0), "TEXT", 5.0, 5, semantic_id=""),
        ),
    )
    result = resolve_annotation_collisions(plan, step=15.0, max_steps=5)
    leaders = [p for p in result.primitives if isinstance(p, LinePrimitive) and p.layer == "TEXT"]
    assert len(leaders) == 1
    line_regions = _annotation_dimension_line_regions(
        result.primitives, own_line_index=None, clearance=1.0
    )
    assert any(r.kind == "LEADER" for r in line_regions)


def test_bug10_existing_conflict_geometry_handles_short_polyline_and_material_epsilon():
    """Bug #10: _existing_conflict_geometry must not crash on 1-pt polyline and must tolerate 1e-15 drift."""
    short_poly = PolylinePrimitive(points=(Vec2(1.0, 2.0),), layer="CUTTING", closed=False)
    material = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])
    assert _existing_conflict_geometry(short_poly, material) is None

    # Outer cutting polyline with 1e-13 drift relative to material
    outer_poly = PolylinePrimitive(
        points=(Vec2(0.0, 0.0), Vec2(100.0, 0.0), Vec2(100.0, 100.0), Vec2(0.0, 100.0)),
        layer="CUTTING",
        closed=True,
    )
    drifted_material = Polygon(
        [(-1e-12, -1e-12), (100.0 + 1e-12, 0.0), (100.0, 100.0), (0.0, 100.0)]
    )
    conflict_geom = _existing_conflict_geometry(outer_poly, drifted_material)
    assert conflict_geom.geom_type in {"LineString", "LinearRing"}


def test_bug11_derived_physical_part_key_includes_fixing_plate_nfb_layer_and_nfb_pad():
    """Bug #11: is_derived_physical_part_key must include fixing_plate, nfb_layer, and nfb_pad."""
    for key in (
        "base_plate:fixing_plate:1",
        "base_plate:nfb_layer:1",
        "nfb_pad:1:body",
    ):
        assert is_derived_physical_part_key(key) is True

    custom_profile = {"X": [{"len": 120.0}], "Y": [{"len": 80.0}]}
    request = SettingsProfileProjectionRequest(
        settings_values={"w": 600.0, "h": 1800.0, "d": 500.0, "t": 2.0, "fw": 29.0},
        input_snapshot={"model": "受電箱", "w": 600.0, "h": 1800.0, "d": 500.0, "t": 2.0, "fw": 29.0},
        available_parts=(
            "box_body",
            "head",
            "tail",
            "door",
            "base_plate",
            "base_plate:fixing_plate:1",
            "base_plate:nfb_layer:1",
            "nfb_pad:1:body",
        ),
        existing_profiles={
            "base_plate:fixing_plate:1": custom_profile,
            "base_plate:nfb_layer:1": custom_profile,
            "nfb_pad:1:body": custom_profile,
        },
        box_body_profile=(),
        active_part="base_plate:fixing_plate:1",
    )
    projection = build_settings_profile_projection(request)
    assert "base_plate:fixing_plate:1" not in projection.part_profiles
    assert "base_plate:nfb_layer:1" not in projection.part_profiles
    assert "nfb_pad:1:body" not in projection.part_profiles
    assert dict(projection.active_profiles) == {}


def test_bug12_and_bug13_registry_diagnostics_panel_form_and_source_round_trip():
    """Bugs #12 & #13: populate_rule_form fields and registry_source_display/raw round-trip."""
    part_labels = {"base_plate": "底板", "box_body": "箱身"}
    raw_source = "REAR_PANEL + OUTER_SURFACE + base_plate + face + 2D"
    displayed = registry_source_display(raw_source, part_labels=part_labels)
    assert displayed != _REGISTRY_PRESENTATION_FALLBACK
    restored = registry_source_raw(displayed, part_labels=part_labels)
    assert restored == raw_source

    # Verify _bind_translated_var does not overwrite raw_var with fallback text
    raw_var = _FakeVar("custom_english_token_v1")
    display_var = _FakeVar("")
    Phase6RegistryDiagnosticsPanel._bind_translated_var(
        raw_var,
        display_var,
        lambda val: registry_source_display(val, part_labels=part_labels),
        lambda val: registry_source_raw(val, part_labels=part_labels),
    )
    assert display_var.get() == _REGISTRY_PRESENTATION_FALLBACK
    # Re-triggering display_var with the fallback must not corrupt raw_var
    display_var.set(_REGISTRY_PRESENTATION_FALLBACK)
    assert raw_var.get() == "custom_english_token_v1"

    # Verify populate_rule_form updates target_role, symmetry, and resets extra_target_role
    panel = Phase6RegistryDiagnosticsPanel(
        owner=SimpleNamespace(),
        present_token=lambda v, **_kw: str(v),
        formula_display=str,
        formula_raw=str,
        preconditions_display=str,
        preconditions_raw=str,
        source_display=str,
        source_raw=str,
        validate_formula=lambda: None,
        preview_payload=lambda: None,
        preview_assembly_3d=lambda: None,
        save_candidate=lambda: None,
        run_formula_matrix=lambda: None,
        promote_candidate=lambda: None,
        load_rule_rows=lambda: (),
        rule_record=lambda _id: {},
        joint_rows=lambda: (),
        add_joint=lambda: None,
        delete_joint=lambda: None,
        on_diagnostic_changed=lambda: None,
        create_promotion_candidates=lambda: None,
        diagnostic_ids=lambda _r: (),
    )
    for name in (
        "rule_id", "rule_name", "family", "part_role", "joint_face", "intent",
        "topology", "target_role", "extra_joint", "extra_target_role",
        "primary_u", "primary_v", "secondary_u", "secondary_depth",
        "preconditions", "symmetry", "source",
    ):
        setattr(panel, f"relief_registry_{name}_var", _FakeVar(""))

    # First populate a 2-joint rule with custom target_role, extra_target_role, and symmetry
    panel.populate_rule_form({
        "rule_id": "R1",
        "symmetry": "EXPLICIT_ONLY",
        "joint_signature": [
            {"relation": "INSERT", "target_role": "REAR_PANEL"},
            {"relation": "WRAP", "target_role": "BOX_SIDE"},
        ],
    })
    assert panel.relief_registry_target_role_var.get() == "REAR_PANEL"
    assert panel.relief_registry_extra_target_role_var.get() == "BOX_SIDE"
    assert panel.relief_registry_symmetry_var.get() == "EXPLICIT_ONLY"

    # Next populate a 1-joint rule: extra_target_role must reset to REAR_PANEL
    panel.populate_rule_form({
        "rule_id": "R2",
        "joint_signature": [
            {"relation": "OVERLAY", "target_role": "BOX_SIDE"},
        ],
    })
    assert panel.relief_registry_target_role_var.get() == "BOX_SIDE"
    assert panel.relief_registry_extra_target_role_var.get() == "REAR_PANEL"
    assert panel.relief_registry_symmetry_var.get() == "MIRROR_IF_GEOMETRY_SYMMETRIC"


def test_bug14_phase6_bending_ui_remove_pairs_by_phase6_key():
    """Bug #14: Symmetric box segment removal must pair by phase6_key, not raw index when asymmetric."""
    segs = [
        {"len": 50.0, "angle": 90},  # index 0: operator-added unkeyed segment on left
        {"len": 15.0, "angle": 90, "phase6_key": "zl2"},
        {"len": 15.0, "angle": 90, "phase6_key": "zl1"},
        {"len": 25.0, "angle": 90, "phase6_key": "fw_left", "core": "FW"},
        {"len": 500.0, "angle": 90, "phase6_key": "d_left", "core": "D"},
        {"len": 600.0, "angle": 90, "phase6_key": "w", "core": "W"},
        {"len": 500.0, "angle": 90, "phase6_key": "d_right", "core": "D"},
        {"len": 25.0, "angle": 90, "phase6_key": "fw_right", "core": "FW"},
        {"len": 15.0, "angle": 90, "phase6_key": "zr1"},
        {"len": 15.0, "phase6_key": "zr2"},
    ]
    ui = Phase6BendingUI.__new__(Phase6BendingUI)
    ui.state = SimpleNamespace(
        symmetric=True,
        phase6_fold_ui_vault_key="箱身",
        phase6_thickness=2.0,
        active_bend="X",
        phase6_fold_ui_profiles={"X": segs},
        profiles_vault={"箱身": segs},
    )
    ui. _mark_workspace_dirty = lambda: None
    ui.save = lambda: None
    ui.render = lambda: None
    ui.update_cb = lambda: None

    # Removing zl1 (index 2) must remove zr1 (index 8), NOT fw_right (index 7 = 10 - 1 - 2)!
    ui.remove(2)
    remaining_keys = [seg.get("phase6_key") for seg in ui.state.phase6_fold_ui_profiles["X"]]
    assert "zl1" not in remaining_keys
    assert "zr1" not in remaining_keys
    assert "zl2" in remaining_keys
    assert "zr2" in remaining_keys
