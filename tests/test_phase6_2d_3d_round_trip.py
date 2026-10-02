# -*- coding: utf-8 -*-
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest

from ae_engine.assembly_placement import AssemblyPlacement, resolve_assembly_placement
from ae_engine.door_dividers import derive_box_body_dividers
from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
from phase6_fold_profiles import build_box_body_profile
import fold_designer_bridge as bridge
import gui
from phase6_designer_workspace import Phase6DesignerWorkspace
import phase6_project_file as project
from phase6_workspace_controller import Phase6WorkspaceController


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class DummyScheduler:
    def __init__(self):
        self.marked = []
    def mark_dirty(self, reason):
        self.marked.append(reason)


def make_dummy_gui(workspace_data=None):
    app = object.__new__(gui.BoxCalculatorGUI)
    app.workspace_controller = Phase6WorkspaceController()
    app.settings_service = SimpleNamespace(
        snapshot=lambda: {},
        update=lambda d: None,
    )
    app._apply_fold_designer_live_settings = lambda s, **kw: None
    app._reset_manual_corner_parameter_locks = lambda: None
    app.baseline_var = DummyVar('受電箱')
    app.w_var = DummyVar(800.0)
    app.h_var = DummyVar(1600.0)
    app.d_var = DummyVar(350.0)
    app.t_var = DummyVar(2.0)
    app.fw_z_var = DummyVar(25.0)
    app.zl1_var = DummyVar(15.0)
    app.zl2_var = DummyVar(15.0)
    app.zr2_var = DummyVar(15.0)
    app.zr1_var = DummyVar(15.0)
    app.yl1_var = DummyVar(15.0)
    app.yr1_var = DummyVar(15.0)
    app.ytop1_var = DummyVar(16.0)
    app.ybottom1_var = DummyVar(15.0)
    app.door_gap_w_var = DummyVar(1.5)
    app.door_gap_h_var = DummyVar(1.5)
    app.door_fold_l_var = DummyVar(12.0)
    app.door_fold_r_var = DummyVar(12.0)
    app.door_fold_t_var = DummyVar(12.0)
    app.door_fold_b_var = DummyVar(12.0)
    app.base_plate_shrink_top_var = DummyVar(0.0)
    app.base_plate_shrink_bottom_var = DummyVar(0.0)
    app.base_plate_shrink_left_var = DummyVar(0.0)
    app.base_plate_shrink_right_var = DummyVar(0.0)
    app.base_plate_bend_var = DummyVar(20.0)
    app.is_box_dist_var = DummyVar(False)
    app.box_assembly_type_var = DummyVar('貼外')
    app.multi_door_enabled_var = DummyVar(True)
    app.door_layout_columns = [[800.0, [1100.0, 500.0]]]
    app.door_layout_scope = 'receiving-main'
    app.door_layout_handle_edges = {'0:0': 'BOTTOM', '0:1': 'TOP'}
    app.receiving_inner_doors = []
    app.surface_features = {}
    app.box_body_face_features = {}
    app.head_holes = []
    app.tail_holes = []
    app.endcap_fw_state = {'fw': 25.0, 'endcap_fw': {}}
    app.manual_corner_pair_same = {}
    app.manual_corner_state = {}
    app.corner_parameter_locks = {}
    app.door_indicator_offset_x = 0.0
    app.door_indicator_offset_y = 0.0
    app.is_indicator_box_var = DummyVar(False)
    app.is_door_indicator_var = DummyVar(False)
    app.indicator_l_var = DummyVar('1')
    app.indicator_layer_g_vars = [DummyVar('1') for _ in range(6)]
    app.door_indicator_l_var = DummyVar('1')
    app.door_indicator_layer_g_vars = [DummyVar('1') for _ in range(6)]
    app._baseline_model_choices = lambda: ['受電箱', '金庫型', '自訂']
    app.project_controller = SimpleNamespace(
        project_path=None,
        capture_committed=lambda s: s,
        set_project_path=lambda p: None,
    )
    app._phase6_update_scheduler = DummyScheduler()
    app.refresh_corner_type_panel = lambda: None
    app._sync_fold_designer_manual_corner_context = lambda p: None
    app._reload_current_baseline_features = lambda: None
    app._apply_manual_corner_snapshot = lambda cs, cp: None
    app._set_box_assembly_type = lambda t, **kw: t
    app._apply_endcap_fw_snapshot = lambda s: None
    app._current_box_assembly_type = lambda: 'WRAP_OVERLAY'
    app._phase6_current_existing_parts = lambda: set(app.workspace_controller.raw_existing_parts())
    app._apply_existing_parts_from_fold_workspace = lambda parts: set(parts)
    app._collect_main_setting_values = lambda: {'fw': 25.0}

    def _dummy_new_column(width, heights, *, width_auto=False, height_auto=None):
        height_values = list(heights)
        if height_auto is None:
            height_auto = [False] * len(height_values)
        return {
            'width_var': DummyVar(str(width)),
            'width_auto': bool(width_auto),
            'width_committed': float(width),
            'height_vars': [DummyVar(str(v)) for v in height_values],
            'height_auto': [bool(v) for v in height_auto],
            'height_committed': [float(v) for v in height_values],
            'height_completion': None,
        }
    app._new_door_layout_column = _dummy_new_column
    app.door_layout_selected_var = DummyVar('0:0')
    app._door_layout_number_text = lambda v: str(int(v)) if float(v).is_integer() else str(v)
    app._parse_layout_value = lambda var, name: float(var.get() if hasattr(var, 'get') else var)
    app._recompute_door_layout_remainders = lambda **kw: None

    if workspace_data:
        app.workspace_controller.commit_workspace(workspace_data)
    return app


def _canonical_round_trip_workspace():
    return {
        'existing_parts': ['box_body', 'head', 'tail', 'door', 'base_plate'],
        'active_part': 'head',
        'part_profiles': {'head': {'X': [{'len': 25.0}], 'Y': []}, 'door': {'X': [{'len': 20.0}], 'Y': []}},
        'box_body_profile': build_box_body_profile({'w': 800.0, 'd': 350.0, 'zl1': 15.0, 'zl2': 15.0, 'zr1': 15.0, 'zr2': 15.0}),
        'box_body_structure': normalize_box_body_structure_state({'active_type': 'integral', 'locked': False}),
        'part_features': {'head': [{'type': 'round_hole', 'x': 50.0, 'y': 50.0, 'diameter': 10.0}]},
        'part_face_features': {'box_body': {'top': [{'type': 'square_hole', 'x': 20.0, 'y': 20.0}]}},
        'assembly_placements': {
            'box_body:divider:receiving-main:HORIZONTAL:C0:R0|R1': {
                'stable_id': 'box_body:divider:receiving-main:HORIZONTAL:C0:R0|R1',
                'parent_assembly_node': 'box_body',
                'placement_kind': 'divider_horizontal',
                'world_offset': [-150.0, 50.0, 0.0],
            }
        },
    }


def test_2d_to_3d_confirm_to_2d_round_trip_preserves_state():
    canonical = _canonical_round_trip_workspace()
    app = make_dummy_gui(canonical)

    # 1. 2D state -> compose snapshot for 3D
    snapshot = app._compose_phase6_project_snapshot_from_main_gui()
    assert snapshot['workspace']['assembly_placements'] == canonical['assembly_placements']

    # 2. 3D load from snapshot
    ws3d = Phase6DesignerWorkspace.from_snapshot(snapshot)
    assert ws3d.assembly_placements_snapshot() == canonical['assembly_placements']

    # 3. 3D confirm payload
    payload = {
        'workspace': ws3d.export_shared_snapshot(),
        'active_part': 'head',
        'assembly_placements': ws3d.assembly_placements_snapshot(),
        'part_features': ws3d.part_features_snapshot(),
        'part_face_features': ws3d.part_face_features_snapshot(),
    }
    payload['workspace']['assembly_placements'] = ws3d.assembly_placements_snapshot()
    payload['workspace']['part_features'] = ws3d.part_features_snapshot()
    payload['workspace']['part_face_features'] = ws3d.part_face_features_snapshot()
    payload['workspace']['box_body_profile'] = canonical['box_body_profile']

    # 4. 2D apply
    applied = app._apply_fold_designer_live_snapshot(payload)
    assert applied is True

    # 5. Verify authoritative 2D state matches
    after_ws = app.workspace_controller.workspace_snapshot()
    for key in ('existing_parts', 'part_features', 'part_face_features', 'assembly_placements', 'box_body_structure'):
        assert after_ws[key] == canonical[key], f'{key} mismatch after round-trip'


def test_2d_to_3d_modify_divider_confirm_to_2d():
    canonical = _canonical_round_trip_workspace()
    app = make_dummy_gui(canonical)

    snapshot = app._compose_phase6_project_snapshot_from_main_gui()
    ws3d = Phase6DesignerWorkspace.from_snapshot(snapshot)

    # Modify divider placement in 3D
    modified_placement = {
        'stable_id': 'box_body:divider:receiving-main:HORIZONTAL:C0:R0|R1',
        'parent_assembly_node': 'box_body',
        'placement_kind': 'divider_horizontal',
        'world_offset': [-150.0, 80.0, 0.0],
    }
    ws3d.replace_assembly_placements({modified_placement['stable_id']: modified_placement})

    # Modify door_layout_columns in 3D
    new_columns = [(800.0, [1000.0, 600.0])]
    payload = {
        'workspace': ws3d.export_shared_snapshot(),
        'door_layout_columns': new_columns,
        'assembly_placements': ws3d.assembly_placements_snapshot(),
        'part_features': ws3d.part_features_snapshot(),
        'part_face_features': ws3d.part_face_features_snapshot(),
    }
    payload['workspace']['assembly_placements'] = ws3d.assembly_placements_snapshot()
    payload['workspace']['box_body_profile'] = canonical['box_body_profile']

    app._apply_fold_designer_live_snapshot(payload)

    # Verify 2D received modified divider state
    assert app.get_door_layout_columns() == new_columns
    after_ws = app.workspace_controller.workspace_snapshot()
    assert after_ws['assembly_placements'][modified_placement['stable_id']]['world_offset'] == [-150.0, 80.0, 0.0]

    # Second 3D resolve yields the same modified state
    re_snap = app._compose_phase6_project_snapshot_from_main_gui()
    re_ws3d = Phase6DesignerWorkspace.from_snapshot(re_snap)
    assert re_ws3d.assembly_placements_snapshot()[modified_placement['stable_id']]['world_offset'] == [-150.0, 80.0, 0.0]


def test_2d_to_3d_modify_door_profile_and_tail_features_confirm_to_2d():
    canonical = _canonical_round_trip_workspace()
    app = make_dummy_gui(canonical)

    snapshot = app._compose_phase6_project_snapshot_from_main_gui()
    ws3d = Phase6DesignerWorkspace.from_snapshot(snapshot)

    # Modify non-derived part profile (door) & add tail feature
    ws3d.stash_profiles('door', {'X': [{'len': 35.0}], 'Y': []})
    tail_feature = [{'type': 'center_hole', 'diameter': 20.0}]
    ws3d.replace_part_features({'tail': tail_feature})

    payload = {
        'workspace': ws3d.export_shared_snapshot(),
        'part_features': ws3d.part_features_snapshot(),
    }
    payload['workspace']['part_features'] = ws3d.part_features_snapshot()
    payload['workspace']['box_body_profile'] = canonical['box_body_profile']

    app._apply_fold_designer_live_snapshot(payload)

    assert app.workspace_controller.profile_for('door')['X'][0]['len'] == 35.0
    assert 'tail' in app.surface_features
    assert app.workspace_controller.part_features_snapshot()['tail'] == tail_feature


def test_2d_to_3d_modify_structure_confirm_to_2d():
    canonical = _canonical_round_trip_workspace()
    app = make_dummy_gui(canonical)

    snapshot = app._compose_phase6_project_snapshot_from_main_gui()
    ws3d = Phase6DesignerWorkspace.from_snapshot(snapshot)

    # Modify box body structure
    new_structure = normalize_box_body_structure_state({
        'active_type': BoxBodyStructureType.THREE_PIECE_W_SPLIT.value,
        'locked': False,
        'configs': {BoxBodyStructureType.THREE_PIECE_W_SPLIT.value: {'seam_bend': 15.0}},
    })
    ws3d.set_box_body_structure_state(new_structure)

    payload = {
        'workspace': ws3d.export_shared_snapshot(),
    }
    payload['workspace']['box_body_structure'] = ws3d.box_body_structure_state()
    payload['workspace']['box_body_profile'] = canonical['box_body_profile']

    app._apply_fold_designer_live_snapshot(payload)

    after_struct = app.workspace_controller.box_body_structure_state()
    assert after_struct['active_type'] == BoxBodyStructureType.THREE_PIECE_W_SPLIT.value
    assert after_struct['configs'][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]['seam_bend'] == 15.0


def test_save_reload_to_3d_to_2d_round_trip(tmp_path):
    canonical = _canonical_round_trip_workspace()
    app = make_dummy_gui(canonical)

    # Compose snapshot and save to .p6fold
    snapshot = app._compose_phase6_project_snapshot_from_main_gui()
    file_path = tmp_path / 'round_trip_test.p6fold'
    project.write_project(file_path, {
        'schema': project.PROJECT_SCHEMA,
        'snapshot': snapshot,
        'final_geometry': {},
    })

    # Reload into a fresh 2D app
    fresh_app = make_dummy_gui()
    read_payload = project.read_project(file_path)['snapshot']
    fresh_app._apply_phase6_project_snapshot(read_payload)

    # Verify loaded state matches canonical
    loaded_ws = fresh_app.workspace_controller.workspace_snapshot()
    for key in ('part_features', 'part_face_features', 'assembly_placements', 'box_body_structure'):
        assert loaded_ws[key] == canonical[key], f'{key} mismatch after reload'

    # Re-compose to 3D and back to 2D
    snap_3d = fresh_app._compose_phase6_project_snapshot_from_main_gui()
    ws3d = Phase6DesignerWorkspace.from_snapshot(snap_3d)
    assert ws3d.assembly_placements_snapshot() == canonical['assembly_placements']


def test_second_3d_resolve_is_idempotent_no_drift():
    snapshot = {
        'w': 800.0,
        'h': 1600.0,
        'd': 350.0,
        't': 2.0,
        'door_layout_scope': 'receiving-main',
        'door_layout_columns': [[800.0, [1100.0, 500.0]]],
        'multi_door_enabled': True,
    }
    stable_id = 'box_body:divider:receiving-main:HORIZONTAL:C0:R0|R1'

    # First resolve
    p1 = resolve_assembly_placement(snapshot, stable_id)

    # Store into snapshot as authoritative
    snapshot['assembly_placements'] = {stable_id: p1.to_dict()}

    # Second resolve via placement lookup helper (consumes cached authoritative)
    kind, offset = bridge._phase6_assembly_placement_for_part(snapshot, stable_id)
    assert kind == p1.placement_kind
    assert offset == p1.world_offset


def test_2d_consumes_authoritative_placement_without_recalculating():
    canonical = _canonical_round_trip_workspace()
    app = make_dummy_gui(canonical)

    snap = app._compose_phase6_project_snapshot_from_main_gui()
    # Placement is present in both top-level and workspace subdict
    assert 'assembly_placements' in snap
    assert 'assembly_placements' in snap['workspace']
    assert snap['assembly_placements'] == snap['workspace']['assembly_placements']
