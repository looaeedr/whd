from __future__ import annotations

from types import SimpleNamespace
import pytest
from shapely.geometry import GeometryCollection, LineString, Point

from ae_engine.cabinet_types.receiving import (
    derive_inner_door_frame_sets,
    resolve_back_panel_contract,
    resolve_box_body_structure_state,
)
from ae_engine.receiving_layout import (
    RECEIVING_RUNTIME_SELECTION_KEY,
    append_receiving_set,
    new_receiving_layout,
    project_receiving_bay_legacy_aliases,
    resize_receiving_bays,
    resize_receiving_sets,
)
from ae_engine.receiving_quantity_box import quantity_feature_errors
from ae_engine.receiving_shared_settings import normalize_set_settings, validate_setting
from ae_engine.receiving_switch_layout import resize_switch_layers
from ae_engine.sheetmetal_drawing import (
    DrawingScene,
    TextPrimitive,
    Vec2,
    mirror_drawing_scene_x,
)
from ae_engine.sheetmetal_feature_reference import generate_round_refill
from ae_engine.sheetmetal_features import (
    CircleFeature,
    FeatureAnchor,
    feature_finished_point,
    feature_surface_from_outline,
)
from ae_engine.sheetmetal_geometry_shared import _clip_axis_bend
import fold_designer_bridge
from gui_modules.application import door_layout_host_adapter, render_snapshots
from gui_modules.application.fold_designer_part_session import Phase6PartSessionOwner
from gui_modules.project import export_actions
from phase6_box_body_structure import BackPanelMode, set_side_back_back_panel_mode
from phase6_custom_parts import custom_part_only_change
from phase6_project_controller import Phase6ProjectController
from phase6_workspace_controller import Phase6WorkspaceController


def _circle(x: float, y: float, d: float = 10.0) -> CircleFeature:
    return CircleFeature(
        diameter=d,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y),
    )


def test_r2_1_and_r2_6_derived_keys_and_custom_parts_preserved_on_bootstrap_and_refresh(monkeypatch):
    assert fold_designer_bridge._phase6_is_derived_physical_part_key("base_plate:nfb_layer:1")
    assert fold_designer_bridge._phase6_is_derived_physical_part_key("nfb_pad:1")
    assert not fold_designer_bridge._phase6_is_derived_physical_part_key("door")

    monkeypatch.setattr(fold_designer_bridge, "_phase6_rebuild_linked_endcaps", lambda self: None)
    custom_profile = {"X": [{"len": 25.0, "angle": 90.0}], "Y": []}
    derived_profile = {"X": [{"len": 15.0, "angle": 90.0}], "Y": []}

    class DummyWorkspace:
        available_parts = ("door", "custom:bracket", "base_plate:nfb_layer:1")

        def __init__(self):
            self.stashed = {"custom:bracket": custom_profile, "base_plate:nfb_layer:1": derived_profile}

        def custom_part(self, key):
            return SimpleNamespace(key=key) if str(key).startswith("custom:") else None

        def stash_profiles(self, key, profiles):
            self.stashed[key] = profiles

        def profiles_for(self, key):
            return self.stashed.get(key, {"X": [], "Y": []})

    dummy = SimpleNamespace(
        designer_workspace=DummyWorkspace(),
        _phase6_input_snapshot={"t": 0.0},
        _settings_values={"t": 2.5},
        state=SimpleNamespace(profiles_vault={"門板": [{"len": 19.0, "angle": 90.0}], "基板": []}),
    )
    fold_designer_bridge._phase6_bootstrap_workspace_profiles(
        dummy,
        {
            "t": 2.5,
            "part_profiles": {
                "custom:bracket": {"X": [{"len": 999.0}], "Y": []},
                "base_plate:nfb_layer:1": {"X": [{"len": 999.0}], "Y": []},
            },
        },
    )
    assert dummy.designer_workspace.stashed["custom:bracket"] == custom_profile
    assert dummy.designer_workspace.stashed["base_plate:nfb_layer:1"] == derived_profile


def test_r2_1_commit_box_body_right_side_syncs_zr1_and_uses_settings_thickness(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        fold_designer_bridge,
        "apply_outside_dimension_compensation",
        lambda segs, t_val: captured.__setitem__("t_val", t_val) or segs,
    )
    monkeypatch.setattr(
        fold_designer_bridge,
        "read_box_body_profile",
        lambda agg, snap: {"zr1": next(r["len"] for r in agg if r.get("phase6_key") == "zr1")},
    )
    monkeypatch.setattr(
        fold_designer_bridge,
        "_phase6_store_editor_values",
        lambda self, vals, notify=True: captured.__setitem__("values", vals),
    )
    monkeypatch.setattr(
        fold_designer_bridge,
        "_phase6_commit_box_structure_state",
        lambda self, st, rebuild=False: None,
    )
    monkeypatch.setattr(
        fold_designer_bridge,
        "_phase6_sync_authoritative_derived_parts",
        lambda self: None,
    )

    bridge = SimpleNamespace(
        _phase6_input_snapshot={},
        _settings_values={"t": 3.0},
        _phase6_box_whd={"w": 600.0, "h": 800.0, "d": 300.0},
        designer_workspace=SimpleNamespace(box_body_structure_state=lambda: {}),
        state=SimpleNamespace(
            profiles_vault={
                "箱身": [
                    {"phase6_key": "zl1", "len": 20.0},
                    {"phase6_key": "zr1", "len": 20.0},
                ]
            }
        ),
    )
    fold_designer_bridge._phase6_commit_box_body_physical_piece_profile(
        bridge,
        "box_body:right_side",
        {"X": [{"phase6_key": "zr1", "len": 35.0}], "Y": []},
    )
    assert captured["t_val"] == 3.0
    assert captured["values"]["zr1"] == 35.0


def test_r2_2_save_current_part_custom_part_saves_bend_ui_and_outside_compensation(monkeypatch):
    order = []

    class DummyWorkspace:
        switching = False
        active_part = "custom:plate_1"

        def custom_part(self, key):
            if key == "custom:plate_1":
                return SimpleNamespace(
                    key="custom:plate_1",
                    display_name="Plate 1",
                    finished_width=100.0,
                    finished_height=80.0,
                    fold_axis="X",
                )
            return None

        def stash_profiles(self, key, profiles):
            order.append(("stash", key, profiles))

    monkeypatch.setattr(
        fold_designer_bridge,
        "apply_outside_dimension_compensation",
        lambda segs, t: [s.__setitem__("compensated_t", t) for s in segs],
    )
    app = SimpleNamespace(
        designer_workspace=DummyWorkspace(),
        bend_ui=SimpleNamespace(save=lambda: order.append(("bend_ui_save",))),
        state=SimpleNamespace(
            profiles={
                "X": [{"len": 20.0, "angle": 90.0}],
                "Y": [{"len": 80.0}],
            }
        ),
        _settings_values={"t": 2.5},
        _phase6_input_snapshot={"t": 2.0},
    )
    owner = Phase6PartSessionOwner().bind_application(app)
    owner.save_current_part()
    assert order[0] == ("bend_ui_save",)
    assert order[1][0] == "stash"
    assert order[1][2]["X"][0]["compensated_t"] == 2.5


def test_r2_3_workspace_controller_quantity_mode_feature_sync_and_snapshot():
    ctrl = Phase6WorkspaceController()
    feat = _circle(30.0, 30.0, 10.0)
    ctrl.commit_workspace(
        {
            "active_mode": "quantity",
            "quantity": {
                "schema": "phase6-quantity-v1",
                "selected_version_id": "quantity-v1",
                "next_version_number": 2,
                "versions": [
                    {
                        "version_id": "quantity-v1",
                        "piece_count": 1,
                        "head_features": [],
                        "tail_features": [],
                    }
                ],
            },
        }
    )
    ctrl.commit_workspace({"part_features": {"head": [feat], "tail": []}})
    snap = ctrl.workspace_snapshot()
    assert "part_features" in snap
    assert len(snap["part_features"]["head"]) == 1
    assert snap["quantity"]["versions"][0]["head_features"][0] == feat


def test_r2_4_custom_part_only_change_first_feature_on_custom_part():
    spec = {
        "physical_id": "custom:1",
        "display_name": "C1",
        "finished_width": 100,
        "finished_height": 50,
        "fold_axis": "X",
        "fold_preset": "OUTSIDE_17_100",
    }
    previous = {
        "model": "標準型",
        "workspace": {
            "active_part": "custom:1",
            "custom_parts": {"items": {"custom:1": spec}, "next_id": 2},
        },
    }
    current = {
        "model": "標準型",
        "workspace": {
            "active_part": "custom:1",
            "custom_parts": {"items": {"custom:1": spec}, "next_id": 2},
            "part_features": {"custom:1": [{"kind": "circle", "x": 10.0, "y": 10.0, "diameter": 5.0}]},
        },
    }
    assert custom_part_only_change(previous, current) is True


def test_r2_5_project_controller_quantity_mode_and_workspace_export():
    payload = Phase6ProjectController.build_designer_payload(
        schema="whd-project-v1",
        model="受電箱",
        base_snapshot={
            "model": "受電箱",
            "receiving_layout": new_receiving_layout(width=600.0, height=800.0, depth=300.0),
        },
        settings={"t": 2.0},
        box_whd={"w": 600.0, "h": 800.0, "d": 300.0},
        assembly_type="standard",
        endcap_fw={},
        corner_state={},
        corner_pair_same={},
        owner_workspace={
            "active_part": "head",
            "active_mode": "quantity",
            "part_features": {"head": [{"x": 10.0}]},
            "part_face_features": {"box_body": {"back": [{"x": 20.0}]}},
            "assembly_placements": {"door": {"world_offset": [0.0, 0.0, 0.0]}},
            "quantity": {"schema": "phase6-quantity-v1", "selected_version_id": "quantity-v1", "next_version_number": 2, "versions": []},
            "receiving_layout": new_receiving_layout(width=600.0, height=800.0, depth=300.0),
        },
        workspace={"active_part": "head"},
        box_body_profile=[],
        assembly_relief={},
        final_geometry={},
    )
    snap = payload["snapshot"]
    assert snap.get("active_mode") == "quantity"
    assert "receiving_layout" not in snap

    exported = Phase6ProjectController.build_workspace_export(
        owner_workspace={
            "active_part": "head",
            "active_mode": "quantity",
            "part_features": {"head": [{"x": 10.0}]},
            "part_face_features": {"box_body": {"back": [{"x": 20.0}]}},
            "assembly_placements": {"door": {"world_offset": [0.0, 0.0, 0.0]}},
        },
        box_body_profile=[],
        structure_state={},
    )
    assert exported["part_features"] == {"head": [{"x": 10.0}]}
    assert exported["part_face_features"] == {"box_body": {"back": [{"x": 20.0}]}}
    assert exported["assembly_placements"] == {"door": {"world_offset": [0.0, 0.0, 0.0]}}
    assert exported["active_mode"] == "quantity"


def test_r2_7_and_r2_8_hole_editor_sync_and_multi_door_indicator_state_trigger_update():
    updates = []
    host = SimpleNamespace(
        _normalize_door_indicator_state=lambda s: dict(s),
        door_layout_indicator_states={},
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot={}),
        _request_phase6_update=lambda intent: updates.append(intent),
    )
    export_actions._apply_multi_door_indicator_state(
        host,
        "0:0",
        {"mode": "indicator_box", "layers": 1, "groups": [1, 1, 1, 1, 1, 1]},
    )
    assert updates == ["geometry"]
    assert "0:0" in host.fold_designer_app._phase6_input_snapshot["door_layout_indicator_states"]


def test_r2_9_remap_door_layout_owned_data_remaps_handle_edges_inner_doors_and_surface_features():
    host = SimpleNamespace(
        door_layout_features={"0:0": ["f0"], "1:0": ["f1"]},
        door_layout_indicator_states={},
        door_layout_indicator_box_features={},
        door_layout_indicator_door_features={},
        door_layout_handle_edges={"0:0": "right", "1:0": "left"},
        surface_features={"door_c1_r1": ["f0"], "door_c2_r1": ["f1"], "head": ["h"]},
        receiving_inner_doors=[
            {"cell_key": "0:0", "stable_id": "inner_door:c1_r1"},
            {"cell_key": "1:0", "stable_id": "inner_door:c2_r1"},
        ],
        _receiving_inner_door_stable_id_for_cell=lambda key: f"inner_door:c{int(key.split(':')[0])+1}_r{int(key.split(':')[1])+1}",
    )
    # Remove column 0 so column 1 shifts to column 0
    door_layout_host_adapter._remap_door_layout_owned_data(
        host,
        lambda c, r: None if c == 0 else (c - 1, r),
    )
    assert host.door_layout_handle_edges == {"0:0": "left"}
    assert host.surface_features["door_c1_r1"] == ["f1"]
    assert "door_c2_r1" not in host.surface_features
    assert host.surface_features["head"] == ["h"]
    assert host.receiving_inner_doors == [{"cell_key": "0:0", "stable_id": "inner_door:c1_r1"}]


def test_r2_10_render_snapshots_passes_model_name_and_frame_width_to_derive_box_body_dividers(monkeypatch):
    called_kwargs = {}

    def fake_derive(columns, **kwargs):
        called_kwargs.update(kwargs)
        return ()

    monkeypatch.setattr(render_snapshots.door_dividers, "derive_box_body_dividers", fake_derive)
    host = SimpleNamespace(
        door_layout_scope="main",
        door_layout_handle_edges={},
        _baseline_source_model=lambda: "受電箱",
        _compose_phase6_project_snapshot_from_main_gui=lambda: {"w": 1000.0, "h": 1200.0},
    )
    render_snapshots.door_layout_divider_frame_snapshot(
        host,
        [(500.0, [1200.0]), (500.0, [1200.0])],
        {"t": 2.0, "d": 350.0, "fw": 42.0, "w": 1000.0, "h": 1200.0},
    )
    assert called_kwargs["model_name"] == "受電箱"
    assert called_kwargs["frame_width"] == 42.0


def test_r2_12_receiving_inner_door_frames_top_only_and_half_back_panel_requires_multi_door():
    snapshot = {
        "model": "受電箱",
        "w": 700.0,
        "h": 1800.0,
        "d": 400.0,
        "t": 2.0,
        "fw": 50.0,
        "multi_door_enabled": True,
        "door_layout_columns": [(700.0, [1800.0])],
        "inner_doors": [
            {
                "cell_key": "0:0",
                "stable_id": "inner_door:c1_r1",
                "included_frame_sides": ["top", "top"],
            }
        ],
    }
    sets = derive_inner_door_frame_sets(snapshot)
    assert len(sets) == 1
    assert sets[0].included_sides == ("top",)
    assert list(sets[0].spans.keys()) == ["top"]

    with pytest.raises(ValueError, match="unsupported inner-door frame side"):
        derive_inner_door_frame_sets(
            {
                **snapshot,
                "inner_doors": [
                    {
                        "cell_key": "0:0",
                        "stable_id": "inner_door:c1_r1",
                        "included_frame_sides": ["invalid_side"],
                    }
                ],
            }
        )

    half_state = set_side_back_back_panel_mode(
        resolve_box_body_structure_state(None), BackPanelMode.HALF
    )
    with pytest.raises(ValueError, match="requires authoritative Door topology"):
        resolve_back_panel_contract(
            {**snapshot, "multi_door_enabled": False, "door_layout_columns": [(700.0, [1200.0, 600.0])]},
            panel_width=700.0,
            full_panel_height=1800.0,
            structure_state=half_state,
        )


def test_r2_13_and_r2_14_receiving_layout_and_switch_layout_validation_and_projection():
    layout = new_receiving_layout(width=700.0, height=1800.0, depth=400.0)
    with pytest.raises(ValueError, match="must be an integer"):
        resize_receiving_bays(layout, set_index=0, bay_count=True)
    with pytest.raises(ValueError, match="must be an integer"):
        resize_receiving_bays(layout, set_index=0, bay_count=1.5)
    with pytest.raises(ValueError, match="must be an integer"):
        resize_receiving_sets(layout, set_count=False)
    with pytest.raises(ValueError, match="must be an integer"):
        resize_switch_layers(None, True)

    # Set1 has settings, Set2 does not have settings yet: projecting Set2 should not leak Set1's settings
    layout2 = append_receiving_set(layout)
    layout2["sets"][0]["settings"] = normalize_set_settings(
        {
            "inner_door_layers": {
                "refs": {"receiving:set:1:bay:1": "r1"},
                "values": {"r1": 2},
            }
        },
        layout2["sets"][0]["bays"],
    )
    snap_set1 = project_receiving_bay_legacy_aliases(
        {"model": "受電箱", "receiving_layout": layout2},
        set_index=0,
        bay_index=0,
    )
    assert snap_set1["receiving_inner_door_layers"] == 2
    snap_set2 = project_receiving_bay_legacy_aliases(
        snap_set1,
        set_index=1,
        bay_index=0,
    )
    assert snap_set2["receiving_inner_door_layers"] == 1
    assert "settings" not in snap_set2["receiving_layout"]["sets"][1]

    # Quantity mode with out-of-range set_index/bay_index should clamp and not leave runtime selection key
    qty_snap = project_receiving_bay_legacy_aliases(
        {
            "model": "受電箱",
            "active_mode": "quantity",
            "receiving_layout": layout,
            "quantity": {
                "schema": "phase6-quantity-v1",
                "selected_version_id": "quantity-v1",
                "next_version_number": 2,
                "versions": [{"version_id": "quantity-v1", "piece_count": 1, "head_features": [], "tail_features": []}],
            },
        },
        set_index=5,
        bay_index=5,
    )
    assert RECEIVING_RUNTIME_SELECTION_KEY not in qty_snap


def test_r2_15_and_r2_16_quantity_feature_errors_and_validate_setting_tuple_normalization():
    feat = _circle(50.0, 50.0, 10.0)
    normalized = validate_setting("head_features", (feat,))
    assert isinstance(normalized, list)
    assert len(normalized) == 1

    errors = quantity_feature_errors(
        {
            "model": "RECEIVING",
            "active_mode": "quantity",
            "t": None,
            "receiving_quantity_box": {"w": 600.0, "h": 800.0, "d": 300.0, "back_panel_mode": "FULL"},
            "quantity": {
                "schema": "phase6-quantity-v1",
                "selected_version_id": "quantity-v1",
                "next_version_number": 2,
                "versions": [
                    {
                        "version_id": "quantity-v1",
                        "piece_count": 1,
                        "head_features": [_circle(5000.0, 5000.0, 20.0)],
                        "tail_features": [],
                    }
                ],
            },
        }
    )
    assert len(errors) == 1
    assert "quantity-v1／封頭／特徵 1" in errors[0]


def test_r2_17_clip_axis_bend_geometry_collection_and_round_refill_local_span():
    class FakeMaterial:
        def intersection(self, line):
            return GeometryCollection([Point(0.0, 0.0), LineString([(10.0, 0.0), (90.0, 0.0)])])

    bend = _clip_axis_bend("top", LineString([(0.0, 0.0), (100.0, 0.0)]), FakeMaterial(), vertical=False)
    assert bend.p1 == Vec2(10.0, 0.0)
    assert bend.p2 == Vec2(90.0, 0.0)

    # L-shaped polygon where local horizontal span at y=80 is [0, 40], while global bounds are [0, 100]
    surface = feature_surface_from_outline(
        "test",
        [Vec2(0, 0), Vec2(100, 0), Vec2(100, 50), Vec2(40, 50), Vec2(40, 100), Vec2(0, 100)],
    )
    seed = _circle(20.0, 80.0, 10.0)
    refilled = generate_round_refill(
        seed,
        surface,
        width=100.0,
        height=100.0,
        direction="both_horizontal",
        driver="center",
        value=10.0,
    )
    assert len(refilled) > 0
    assert all(feature_finished_point(f, 100.0, 100.0).x <= 35.0 + 1e-6 for f in refilled)


def test_r2_18_mirror_drawing_scene_x_reflects_check_text_attachment_point():
    scene = DrawingScene()
    scene.add(
        TextPrimitive(
            text="DIM",
            insert=Vec2(10.0, 20.0),
            layer="CHECK",
            char_height=3.5,
            attachment_point=1,
        )
    )
    mirrored = mirror_drawing_scene_x(scene, 0.0, 100.0)
    text_prim = next(p for p in mirrored.primitives if isinstance(p, TextPrimitive))
    assert text_prim.insert == Vec2(90.0, 20.0)
    assert text_prim.attachment_point == 3


def test_r2_3_partial_active_quantity_commit_keeps_existing_version_and_head_features():
    owner = Phase6WorkspaceController()
    common_box = {"w": 600., "h": 800., "d": 300., "back_panel_mode": "FULL"}
    owner.commit_workspace({
        "active_mode": "quantity",
        "receiving_quantity_box": common_box,
        "quantity": {
            "schema": "phase6-quantity-v1",
            "selected_version_id": "quantity-v1",
            "next_version_number": 2,
            "versions": [{
                "version_id": "quantity-v1", "piece_count": 2,
                "head_features": [], "tail_features": [],
            }],
        },
    })
    hole = _circle(35.0, 45.0)
    result = owner.commit_workspace({
        "active_mode": "quantity",
        "part_features": {"head": [hole], "tail": []},
    })
    assert result["receiving_quantity_box"] == common_box
    assert result["quantity"]["versions"][0]["piece_count"] == 2
    assert result["quantity"]["versions"][0]["head_features"] == [hole]
    assert result["part_features"]["head"] == [hole]


def test_r2_9_inner_door_panel_hole_ownership_migrates_with_cell_stable_id():
    class Owner:
        features = {
            "inner_door:c2r1:panel": ["inner_hole"],
            "door_c2_r1": ["outer_hole"],
            "head": ["head_hole"],
        }

        def part_features_snapshot(self):
            return {k: list(v) for k, v in self.features.items()}

        def replace_part_features(self, value):
            self.features = {k: list(v) for k, v in value.items()}

    owner = Owner()
    host = SimpleNamespace(
        workspace_controller=owner,
        door_layout_features={"1:0": ["outer_hole"]},
        door_layout_indicator_states={},
        door_layout_indicator_box_features={},
        door_layout_indicator_door_features={},
        door_layout_handle_edges={},
        surface_features=dict(owner.features),
        receiving_inner_doors=[{"cell_key": "1:0", "stable_id": "c2r1"}],
        _receiving_inner_door_stable_id_for_cell=lambda cell: "upper" if cell == "0:0" else "c2r1",
    )
    door_layout_host_adapter._remap_door_layout_owned_data(
        host, lambda column, row: (0, row) if column == 1 else None,
    )
    assert host.receiving_inner_doors[0]["stable_id"] == "upper"
    for source in (host.surface_features, owner.features):
        assert source["inner_door:upper:panel"] == ["inner_hole"]
        assert source["door_c1_r1"] == ["outer_hole"]
        assert source["head"] == ["head_hole"]
        assert "inner_door:c2r1:panel" not in source
        assert "door_c2_r1" not in source


def test_r2_17_nested_geometry_collection_selects_real_segment():
    class Material:
        def intersection(self, _line):
            return GeometryCollection([
                GeometryCollection([Point(0, 0), LineString([(15, 0), (85, 0)])]),
                Point(100, 0),
            ])
    bend = _clip_axis_bend(
        "top", LineString([(0, 0), (100, 0)]), Material(), vertical=False,
    )
    assert bend.p1 == Vec2(15.0, 0.0)
    assert bend.p2 == Vec2(85.0, 0.0)


def test_r2_15_missing_thickness_cannot_authorize_quantity_hole():
    source = {
        "model": "RECEIVING", "active_mode": "quantity", "t": None,
        "receiving_quantity_box": {
            "w": 600., "h": 800., "d": 300., "back_panel_mode": "FULL",
        },
        "quantity": {
            "schema": "phase6-quantity-v1",
            "selected_version_id": "quantity-v1", "next_version_number": 2,
            "versions": [{
                "version_id": "quantity-v1", "piece_count": 1,
                "head_features": [_circle(300., 100.)], "tail_features": [],
            }],
        },
    }
    assert len(quantity_feature_errors(source)) == 1


def test_r2_5_quantity_project_payload_strips_nested_set_bay_state():
    base = {"receiving_layout": {"legacy": True}}
    owner = {
        "active_mode": "quantity", "quantity": {"versions": []},
        "receiving_layout": {"legacy": True},
    }
    payload = Phase6ProjectController.build_designer_payload(
        schema="phase6-test", model="受電箱", base_snapshot=base,
        settings={}, box_whd={}, assembly_type=None, endcap_fw={},
        corner_state={}, corner_pair_same=False,
        owner_workspace=owner,
        workspace={"receiving_layout": {"legacy": True}, "part_profiles": {}},
        box_body_profile=[], assembly_relief={}, final_geometry={},
    )
    assert "receiving_layout" not in payload["snapshot"]
    assert "receiving_layout" not in payload["snapshot"]["workspace"]
    export = Phase6ProjectController.build_workspace_export(
        owner_workspace=owner, box_body_profile=[], structure_state={},
    )
    assert "receiving_layout" not in export


def test_r2_3_partial_set_bay_commit_does_not_drop_current_layout():
    owner = Phase6WorkspaceController()
    source_layout = {"schema": "source-layout", "sets": ["unchanged"]}
    owner.commit_workspace({
        "active_mode": "set_bay", "receiving_layout": source_layout,
    })
    result = owner.commit_workspace({
        "active_mode": "set_bay", "part_features": {"door": []},
    })
    assert result["receiving_layout"] == source_layout

@pytest.mark.parametrize("axis", ["width", "height", "depth"])
@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), float("-inf"), 0., -1., "nan"])
def test_r2_13_receiving_source_bay_dimensions_must_be_positive_finite_numbers(axis, bad):
    """A corrupt saved Bay W/H/D must not feed physical enclosure and lock geometry."""
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    valid = {"width": 800., "height": 1600., "depth": 350.}
    invalid = dict(valid, **{axis: bad})
    with pytest.raises(ValueError, match="Receiving Bay"):
        new_receiving_layout(**invalid)
    saved = new_receiving_layout(**valid)
    saved["sets"][0]["bays"][0][axis] = bad
    with pytest.raises(ValueError, match="Receiving Set1 Bay1"):
        normalize_receiving_layout(saved)


def test_r2_13_receiving_valid_bay_keeps_existing_w_h_d_authority():
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    saved = new_receiving_layout(width=800., height=1600., depth=350.)
    bay = normalize_receiving_layout(saved)["sets"][0]["bays"][0]
    assert (bay["width"], bay["height"], bay["depth"]) == (800., 1600., 350.)

@pytest.mark.parametrize("bad", [True, False, 1.5, "1", None, {}])
def test_r2_14_switch_connection_target_index_must_be_exact_integer(bad):
    """Layer selection is the same physical NFB layer owner, not Python coercion."""
    from ae_engine.receiving_switch_layout import (
        new_receiving_switch_layout, set_layer_connection_count,
    )
    layout = resize_switch_layers(new_receiving_switch_layout(), 2)
    with pytest.raises(ValueError, match="layer_index must be an integer"):
        set_layer_connection_count(layout, layer_index=bad, connection_count=3)


def test_r2_14_valid_second_layer_update_keeps_first_layer_unchanged():
    from ae_engine.receiving_switch_layout import (
        new_receiving_switch_layout, set_layer_connection_count,
    )
    source = resize_switch_layers(new_receiving_switch_layout(), 2)
    result = set_layer_connection_count(source, layer_index=1, connection_count=3)
    assert [x["connection_count"] for x in result["layers"]] == [1, 3]
    assert [x["connection_count"] for x in source["layers"]] == [1, 1]

@pytest.mark.parametrize("bad", [False, True, 0, 0., 1, "", "   "])
def test_r2_14_invalid_stored_nfb_brand_never_silently_defaults_to_shihlin(bad):
    from ae_engine.receiving_switch_layout import (
        new_receiving_switch_layout, normalize_receiving_switch_layout,
    )
    with pytest.raises(ValueError, match="unsupported Receiving switch brand"):
        new_receiving_switch_layout(brand=bad)
    stored = new_receiving_switch_layout()
    stored["switch_brand"] = bad
    with pytest.raises(ValueError, match="unsupported Receiving switch brand"):
        normalize_receiving_switch_layout(stored)
    assert new_receiving_switch_layout()["switch_brand"] == "士林"

@pytest.mark.parametrize("bad", [False, True, 0, "士林", [], ()])
def test_r2_14_corrupt_saved_switch_layout_cannot_reset_brand_and_tiers(bad):
    from ae_engine.receiving_switch_layout import normalize_receiving_switch_layout
    with pytest.raises(ValueError, match="Receiving switch layout must be a mapping"):
        normalize_receiving_switch_layout(bad)
    assert normalize_receiving_switch_layout(None)["switch_brand"] == "士林"


@pytest.mark.parametrize("owner", ["set", "bay"])
def test_r2_13_boolean_saved_set_bay_identity_cannot_become_physical_part_id(owner):
    """True is not a stored stable_id and must not become the string 'True'."""
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    saved = new_receiving_layout(width=800., height=1600., depth=350.)
    target = saved["sets"][0] if owner == "set" else saved["sets"][0]["bays"][0]
    target["stable_id"] = True
    with pytest.raises(ValueError, match="stable_id"):
        normalize_receiving_layout(saved)
    assert target["stable_id"] is True


def test_r2_13_canonical_saved_set_bay_stable_ids_remain_identical():
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    saved = new_receiving_layout(width=800., height=1600., depth=350.)
    normalized = normalize_receiving_layout(saved)
    assert normalized["sets"][0]["stable_id"] == saved["sets"][0]["stable_id"]
    assert normalized["sets"][0]["bays"][0]["stable_id"] == saved["sets"][0]["bays"][0]["stable_id"]


@pytest.mark.parametrize("bad", [False, 0, "", True])
def test_r2_13_invalid_explicit_back_panel_mode_never_defaults_to_full(bad):
    """False and a saved blank are corrupt back-panel authority, not FULL."""
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    with pytest.raises(ValueError, match="back_panel_mode"):
        new_receiving_layout(width=800., height=1600., depth=350., back_panel_mode=bad)
    saved = new_receiving_layout(width=800., height=1600., depth=350.)
    saved["sets"][0]["bays"][0]["back_panel_mode"] = bad
    with pytest.raises(ValueError, match="back_panel_mode"):
        normalize_receiving_layout(saved)
    assert saved["sets"][0]["bays"][0]["back_panel_mode"] is bad


def test_r2_13_missing_or_real_back_panel_modes_preserve_authority():
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    for mode, expected in [(None, "FULL"), ("HALF", "HALF"), ("BACK_OPENING", "BACK_OPENING")]:
        saved = new_receiving_layout(
            width=800., height=1600., depth=350., back_panel_mode=mode,
        )
        assert normalize_receiving_layout(saved)["sets"][0]["bays"][0]["back_panel_mode"] == expected


@pytest.mark.parametrize("bad", [True, False])
def test_r2_14_saved_switch_layer_boolean_id_cannot_become_a_string_identity(bad):
    from ae_engine.receiving_switch_layout import (
        new_receiving_switch_layout, normalize_receiving_switch_layout,
    )
    saved = new_receiving_switch_layout()
    saved["layers"][0]["stable_id"] = bad
    with pytest.raises(ValueError, match="stable_id"):
        normalize_receiving_switch_layout(saved)
    assert saved["layers"][0]["stable_id"] is bad
    assert normalize_receiving_switch_layout(new_receiving_switch_layout())["layers"][0]["stable_id"] == "receiving:switch-layer:1"


@pytest.mark.parametrize("axis", ["panel_width", "full_panel_height"])
@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), float("-inf"), 10 ** 400])
def test_r2_12_rear_panel_manufacturing_contract_rejects_nonphysical_sizes(axis, bad):
    """Bad direct rear-panel sizes may not escape validation into DXF datums."""
    from ae_engine.cabinet_types.receiving import resolve_back_panel_contract
    from ae_engine.cabinet_types.receiving import resolve_box_body_structure_state
    saved = {"model": "受電箱", "w": 800., "h": 1600., "d": 350., "t": 2.}
    kwargs = {"panel_width": 700., "full_panel_height": 1600.}
    kwargs[axis] = bad
    with pytest.raises(ValueError, match="rear-panel dimensions"):
        resolve_back_panel_contract(
            saved, structure_state=resolve_box_body_structure_state(None), **kwargs
        )
    result = resolve_back_panel_contract(
        saved, structure_state=resolve_box_body_structure_state(None),
        panel_width=700., full_panel_height=1600.,
    )
    assert result["panel_width"] == 700.
    assert result["material_height"] == 1600.
    assert len(result["fixed_slot_datums"]) == 4


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), float("-inf"), 10 ** 400, 0, -1])
def test_r2_12_half_rear_panel_requires_finite_positive_upper_section(bad):
    """A corrupt Door section may not become certified HALF rear manufacturing."""
    from ae_engine.cabinet_types.receiving import resolve_back_panel_contract
    from ae_engine.cabinet_types.receiving import resolve_box_body_structure_state
    saved = {
        "model": "受電箱", "w": 800., "h": 1600., "d": 350., "t": 2.,
        "multi_door_enabled": True, "door_layout_columns": [(700., [bad, 500.])],
    }
    half = set_side_back_back_panel_mode(
        resolve_box_body_structure_state(None), BackPanelMode.HALF,
    )
    with pytest.raises(ValueError, match="rear-panel upper section"):
        resolve_back_panel_contract(
            saved, structure_state=half,
            panel_width=700., full_panel_height=1600.,
        )
    saved["door_layout_columns"] = [(700., [1100., 500.])]
    valid = resolve_back_panel_contract(
        saved, structure_state=half,
        panel_width=700., full_panel_height=1600.,
    )
    assert valid["mode"] == "HALF"
    assert valid["material_height"] > 0
    assert len(valid["fixed_slot_datums"]) == 4


@pytest.mark.parametrize("invalid_flag", ["false", "0", 1, {"enabled": True}])
def test_r2_12_half_back_panel_requires_explicit_boolean_multi_door_authority(invalid_flag):
    """A truthy corrupt project flag cannot enable the HALF manufacturing mode."""
    from ae_engine.cabinet_types.receiving import (
        resolve_back_panel_contract, resolve_box_body_structure_state,
    )
    saved = {
        "model": "受電箱",
        "multi_door_enabled": invalid_flag,
        "door_layout_columns": [(700., [1100., 500.])],
    }
    half = set_side_back_back_panel_mode(
        resolve_box_body_structure_state(None), BackPanelMode.HALF,
    )
    with pytest.raises(ValueError, match="requires authoritative Door topology"):
        resolve_back_panel_contract(
            saved, structure_state=half, panel_width=700., full_panel_height=1600.,
        )
    saved["multi_door_enabled"] = True
    assert resolve_back_panel_contract(
        saved, structure_state=half, panel_width=700., full_panel_height=1600.,
    )["mode"] == "HALF"


@pytest.mark.parametrize("owner", ["set", "bay", "joint"])
@pytest.mark.parametrize("invalid_id", [{"bad": 1}, ["bad"], ("bad",), float("nan"), float("inf")])
def test_r2_13_corrupt_saved_identity_source_must_not_mint_physical_id(owner, invalid_id):
    """Persisted structured/nonfinite IDs may not stringify into valid part keys."""
    from ae_engine.receiving_layout import (
        new_receiving_layout, normalize_receiving_layout, resize_receiving_bays,
    )
    saved = new_receiving_layout(width=800., height=1600., depth=350.)
    if owner == "joint":
        saved = resize_receiving_bays(saved, set_index=0, bay_count=2)
    target = (
        saved["sets"][0] if owner == "set" else
        saved["sets"][0]["bays"][0] if owner == "bay" else
        saved["sets"][0]["joints"][0]
    )
    target["stable_id"] = invalid_id
    with pytest.raises(ValueError, match="stable_id"):
        normalize_receiving_layout(saved)
    assert target["stable_id"] is invalid_id


def test_r2_13_legacy_finite_numeric_stable_id_is_not_unnecessarily_reassigned():
    from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
    saved = new_receiving_layout(width=800., height=1600., depth=350.)
    saved["sets"][0]["stable_id"] = 42
    assert normalize_receiving_layout(saved)["sets"][0]["stable_id"] == "42"


@pytest.mark.parametrize("bad", [None, False, True, 42, "door", [], [("door_layout_columns", [])]])
def test_r2_13_per_bay_editor_rejects_non_mapping_door_state_without_erasing_owner(bad):
    """The edit path must keep the same Door ownership rule as project reload."""
    from ae_engine.receiving_layout import (
        new_receiving_layout, normalize_receiving_layout, update_receiving_bay,
    )
    layout = new_receiving_layout(width=800., height=1600., depth=350.)
    layout["sets"][0]["bays"][0]["door_state"] = {
        "door_layout_columns": [[800., [800., 800.]]],
    }
    original = normalize_receiving_layout(layout)
    with pytest.raises(ValueError, match="每連門分割必須為物件"):
        update_receiving_bay(layout, set_index=0, bay_index=0, door_state=bad)
    assert normalize_receiving_layout(layout) == original


def test_r2_13_per_bay_editor_accepts_real_empty_or_populated_door_state():
    from ae_engine.receiving_layout import new_receiving_layout, update_receiving_bay
    layout = new_receiving_layout(width=800., height=1600., depth=350.)
    for saved in ({}, {"door_layout_columns": [[800., [800., 800.]]]}):
        revised = update_receiving_bay(layout, set_index=0, bay_index=0, door_state=saved)
        assert revised["sets"][0]["bays"][0]["door_state"] == saved


@pytest.mark.parametrize("bad", [True, False, 0.5, 1.5, "1.5", None, [], {}])
def test_r2_14_switch_ui_adapter_rejects_nonintegral_layer_index(bad):
    """GUI read/write must not alias True to tier 2 or truncate decimal input."""
    from gui_modules.application.receiving_switch_layout_adapter import ReceivingSwitchLayoutAdapter
    from ae_engine.receiving_switch_layout import new_receiving_switch_layout
    adapter = ReceivingSwitchLayoutAdapter(new_receiving_switch_layout())
    adapter.add_layer()
    before = adapter.layout
    with pytest.raises(ValueError, match="layer_index"):
        adapter.connection_count(bad)
    with pytest.raises(ValueError, match="layer_index"):
        adapter.resize_connections(bad, 1)
    assert adapter.layout == before
    assert adapter.connection_count("0") == 1
    assert adapter.connection_count("1") == 1


@pytest.mark.parametrize("bad_delta", [True, False, 0.5, 1.5, "1.5", None, [], {}])
def test_r2_14_switch_ui_adapter_rejects_fractional_or_boolean_connection_delta(bad_delta):
    from gui_modules.application.receiving_switch_layout_adapter import ReceivingSwitchLayoutAdapter
    from ae_engine.receiving_switch_layout import new_receiving_switch_layout
    adapter = ReceivingSwitchLayoutAdapter(new_receiving_switch_layout())
    before = adapter.layout
    with pytest.raises(ValueError, match="delta"):
        adapter.resize_connections("0", bad_delta)
    assert adapter.layout == before
    assert adapter.resize_connections("0", "1") is True
    assert adapter.connection_count(0) == 2
