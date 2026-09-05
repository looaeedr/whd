# -*- coding: utf-8 -*-
import json
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge
from ae_engine import manufacturing_api
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext




def _segment(length, angle=-90, *, core=None, key=None):
    row = {'len': float(length)}
    if angle is not None:
        row['angle'] = float(angle)
    if core:
        row['core'] = core
    if key:
        row['phase6_key'] = key
    return row


def _box_profile(extra_left=(), extra_right=()):
    # User-custom topology: all extra folds are outside the fixed D-W-D core.
    left = list(extra_left) + [_segment(25, -90, key='fw_left')]
    core = [
        _segment(246, -90, core='D', key='d_left'),
        _segment(396, -90, core='W', key='w'),
        _segment(246, -90, core='D', key='d_right'),
    ]
    right = [_segment(25, None, key='fw_right')] + list(extra_right)
    # Last row owns no bend angle.
    rows = left + core + right
    for row in rows[:-1]:
        row.setdefault('angle', -90.0)
    rows[-1].pop('angle', None)
    return rows


def _spec(profile):
    return BoxBodyPartSpec(
        width=400, height=600, depth=250, thickness=2, frame_width=25,
        model_name=None, zl1=15, zl2=20, zr1=15, zr2=20, z_comp=0,
        fold_profile=bridge.profile_to_fold_segments(profile),
    )


@pytest.mark.parametrize('count', [5, 20])
def test_box_body_final_scene_uses_authoritative_arbitrary_fold_chain(count):
    extras = max(0, count - 5)
    left_extra = [_segment(7 + i, -45 if i % 2 else 90) for i in range(extras)]
    profile = _box_profile(extra_left=left_extra)
    assert len(profile) == count

    data = manufacturing_api.build_part_render_data(_spec(profile), ManufacturingContext())
    bends = [p for p in data.scene.primitives if getattr(p, 'layer', '') == 'BEND']

    assert len(bends) == count - 1
    expected = []
    cursor = 0.0
    for row in profile[:-1]:
        cursor += float(row['len'])
        expected.append(cursor)
    actual = [float(p.p1.x) for p in bends]
    assert actual == pytest.approx(expected)
    assert data.material.bounds[2] == pytest.approx(sum(float(row['len']) for row in profile))


def test_custom_box_topology_derives_head_and_native_tail_from_same_mating_chain():
    profile = _box_profile()
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    linked = bridge.build_linked_endcap_xy_profiles(snapshot, profile)
    head_y = linked['head']['Y']
    tail_y = linked['tail']['Y']

    assert [r.get('phase6_key') for r in head_y] == ['fw', 'endcap_d_core', 'ybottom1']
    assert [r.get('phase6_key') for r in tail_y] == ['ybottom1', 'endcap_d_core', 'fw']
    assert [r['len'] for r in head_y] == pytest.approx([25, 244, 15])
    assert [r['len'] for r in tail_y] == pytest.approx([15, 244, 25])
    assert [r.get('angle') for r in head_y[:-1]] == pytest.approx([-90, -90])
    assert 'angle' not in head_y[-1]
    assert [r.get('angle') for r in tail_y[:-1]] == pytest.approx([-90, -90])
    assert 'angle' not in tail_y[-1]


def test_linked_endcaps_accept_practical_twenty_segment_box_chain_without_count_branches():
    # 15 extra outer folds + D-W-D + the two FW segments = 20 segments.
    extras = [_segment(6 + i, 45 if i % 2 else -90) for i in range(15)]
    profile = _box_profile(extra_left=extras)
    assert len(profile) == 20
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }

    linked = bridge.build_linked_endcap_xy_profiles(snapshot, profile)
    # Every fold before the left D becomes one ordered mating fold; the only
    # extra segment is the opposite end-cap flap after the D core.
    assert len(linked['head']['Y']) == 15 + 3
    assert len(linked['tail']['Y']) == 15 + 3
    assert linked['head']['Y'][-2]['core'] == 'D-T'
    assert linked['tail']['Y'][1]['core'] == 'D-T'


def test_remove_optional_part_is_transactional_and_box_body_cannot_be_removed():
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ['box_body', 'head', 'tail', 'door'],
        "active_part": 'tail',
        "part_profiles": {'head': {}, 'tail': {}, 'door': {}},
        "part_features": {'head': [], 'tail': [], 'door': []},
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        show_home=lambda: workspace.show_home(),
        _refresh_part_buttons=lambda: None,
        _refresh_add_part_menu=lambda: None,
    )

    bridge._fix11_remove_part(holder, 'tail')
    assert list(workspace.available_parts) == ['box_body', 'head', 'door']
    assert workspace.dirty is True

    with pytest.raises(ValueError, match='箱身'):
        bridge._fix11_remove_part(holder, 'box_body')


def test_main_gui_part_spec_carries_committed_box_profile_back_to_2d():
    import gui
    from phase6_workspace_controller import Phase6WorkspaceController
    profile = _box_profile()
    workspace_controller = Phase6WorkspaceController()
    workspace_controller.set_box_body_profile(profile)
    dummy = SimpleNamespace(workspace_controller=workspace_controller)
    val = {'w': 400, 'h': 600, 'd': 250, 't': 2, 'fw': 25, 'zl1': 15, 'zl2': 20, 'zr1': 15, 'zr2': 20, 'z_comp': 0}

    spec = gui.BoxCalculatorGUI._box_body_part_spec_from_values(
        dummy, val, model_name=None, features=(), face_features={},
    )
    assert len(spec.fold_profile) == 5


def test_confirm_existing_parts_updates_main_2d_export_presence_flags():
    class Var:
        def __init__(self, value=True): self.value = value
        def set(self, value): self.value = bool(value)
        def get(self): return self.value

    from phase6_workspace_controller import Phase6WorkspaceController
    dummy = SimpleNamespace(
        workspace_controller=Phase6WorkspaceController(),
        export_z_var=Var(True), export_head_var=Var(True), export_tail_var=Var(True),
        export_door_var=Var(True), export_base_plate_var=Var(True),
        is_indicator_box_var=Var(True), is_door_indicator_var=Var(False),
    )
    # This helper is intentionally GUI-light so commit/project-load share it.
    import gui
    gui.BoxCalculatorGUI._apply_existing_parts_from_fold_workspace(
        dummy, ['box_body', 'head', 'door']
    )
    assert dummy.export_z_var.get() is True
    assert dummy.export_head_var.get() is True
    assert dummy.export_tail_var.get() is False
    assert dummy.export_door_var.get() is True
    assert dummy.export_base_plate_var.get() is False
    assert dummy.is_indicator_box_var.get() is False

from ae_engine.contracts import EndCapPartSpec


def _endcap_spec(profile, *, is_tail=False):
    y_rows = list(profile['Y'])
    fold_top = sum(
        float(row.get('len', 0.0))
        for row in y_rows
        if row.get('phase6_key') not in {'fw', 'endcap_d_core', 'ybottom1'}
    )
    return EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        model_name=None, is_tail=is_tail,
        fold_left=15, fold_right=15, fold_top=fold_top, fold_bottom=15,
        box_fold_left=15, box_fold_right=15,
        fold_profile_x=bridge.profile_to_fold_segments(profile['X']),
        fold_profile_y=bridge.profile_to_fold_segments(profile['Y']),
    )


def test_formula_endcap_structural_outline_is_authoritative_material_not_feature_hole():
    # Custom/no-baseline projects use the formula scene. The structural outline
    # must win material resolution even though a small closed CUTTING rectangle
    # is emitted later as a real cut-out feature.
    spec = EndCapPartSpec(
        width=400, depth=250, height=600, thickness=2, frame_width=25,
        model_name=None, is_tail=False,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        box_fold_left=15, box_fold_right=15,
    )
    data = manufacturing_api.build_part_render_data(spec, ManufacturingContext())
    minx, miny, maxx, maxy = data.material.bounds
    assert maxx - minx > 400
    assert maxy - miny == pytest.approx(300)
    assert data.material.area > 100_000


def test_linked_endcap_final_2d_bends_follow_derived_fold_chain_and_keep_blank_size():
    profile = _box_profile()
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    linked = bridge.build_linked_endcap_xy_profiles(snapshot, profile)

    for part_key, is_tail, expected_y in (
        ('head', False, [25.0, 269.0]),
        ('tail', True, [15.0, 259.0]),
    ):
        data = manufacturing_api.build_part_render_data(
            _endcap_spec(linked[part_key], is_tail=is_tail), ManufacturingContext()
        )
        bends = [p for p in data.scene.primitives if getattr(p, 'layer', '') == 'BEND']
        vertical = sorted({round(float(p.p1.x), 7) for p in bends if abs(float(p.p1.x) - float(p.p2.x)) < 1e-7})
        horizontal = sorted({round(float(p.p1.y), 7) for p in bends if abs(float(p.p1.y) - float(p.p2.y)) < 1e-7})
        assert vertical == pytest.approx([15.0, 407.0])
        assert horizontal == pytest.approx(expected_y)
        minx, miny, maxx, maxy = data.material.bounds
        assert maxx - minx == pytest.approx(422.0)
        assert maxy - miny == pytest.approx(284.0)


def test_authoritative_endcap_bends_skip_nonterminal_segment_without_fold_angle():
    # Regression for the uploaded broken Tail shape: a segment boundary is not
    # a manufacturing BEND unless the owning segment has a real angle.
    profile = {
        'X': [
            {'len': 15, 'angle': -90, 'phase6_key': 'yl1'},
            {'len': 392, 'angle': -90, 'core': 'W-2T', 'phase6_key': 'endcap_w_core'},
            {'len': 15, 'phase6_key': 'yr1'},
        ],
        'Y': [
            {'len': 15, 'angle': -90, 'phase6_key': 'ybottom1'},
            {'len': 244, 'angle': -90, 'core': 'D-T', 'phase6_key': 'endcap_d_core'},
            {'len': 25, 'phase6_key': 'fw'},
            {'len': 16, 'phase6_key': 'ytop1'},
        ],
    }
    data = manufacturing_api.build_part_render_data(
        _endcap_spec(profile, is_tail=True), ManufacturingContext()
    )
    bends = [p for p in data.scene.primitives if getattr(p, 'layer', '') == 'BEND']
    horizontal = sorted({
        round(float(p.p1.y), 7) for p in bends
        if abs(float(p.p1.y) - float(p.p2.y)) < 1e-7
    })
    assert horizontal == pytest.approx([15.0, 259.0])


def test_linked_endcap_dxf_export_uses_same_authoritative_bends_as_2d(tmp_path):
    import ezdxf
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    linked = bridge.build_linked_endcap_xy_profiles(snapshot, _box_profile())
    spec = _endcap_spec(linked['head'], is_tail=False)
    expected_scene = manufacturing_api.build_part_scene(spec, ManufacturingContext())
    expected_bends = [p for p in expected_scene.primitives if getattr(p, 'layer', '') == 'BEND']

    output = tmp_path / 'head-linked.dxf'
    manufacturing_api.generate_part(spec, output, ManufacturingContext(overwrite=True))
    doc = ezdxf.readfile(output)
    actual_bends = [e for e in doc.modelspace() if str(e.dxf.layer).upper() == 'BEND']

    assert len(expected_bends) == 4
    assert len(actual_bends) == len(expected_bends)


def test_asymmetric_fold_edit_still_saves_and_updates_authoritative_chain():
    ui = object.__new__(bridge.Phase6BendingUI)
    ui._phase6_refreshing_controls = False
    ui.state = SimpleNamespace(symmetric=False)
    ui.controls = []
    calls = []
    ui.save = lambda: calls.append('save')
    ui.update_cb = lambda: calls.append('update')

    ui.apply_mirror(0, 'len')

    assert calls == ['save', 'update']


def test_readding_optional_nonlinked_part_restores_stashed_profile_instead_of_factory_reset():
    custom_door = {
        'X': [_segment(23, -45, key='custom_left'), _segment(301, None, key='custom_face')],
        'Y': [_segment(17, -90, key='custom_bottom'), _segment(500, None, key='custom_height')],
    }
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ['box_body'],
        "part_profiles": {'door': json.loads(json.dumps(custom_door))},
        "part_features": {'door': []},
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot={'w': 400, 'h': 600, 'd': 250, 't': 2, 'fw': 25},
        state=SimpleNamespace(profiles_vault={'箱身': _box_profile()}),
        _refresh_part_buttons=lambda: None,
        _refresh_add_part_menu=lambda: None,
        activate_part=lambda key: None,
    )

    bridge._fix11_add_part(holder, 'door')

    assert workspace.profiles_for('door') == custom_door


def test_main_workspace_store_rederives_head_tail_profiles_from_authoritative_box_chain():
    import gui
    old_head = bridge.build_endcap_xy_profiles({
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }, part_key='head')
    workspace = {
        'box_body_profile': _box_profile(),
        'existing_parts': ['box_body', 'head', 'tail'],
        'active_part': 'box_body',
        'part_profiles': {'head': old_head, 'tail': old_head},
    }
    from phase6_workspace_controller import Phase6WorkspaceController
    holder = SimpleNamespace(
        workspace_controller=Phase6WorkspaceController(),
        _collect_main_setting_values=lambda: {
            'w': 400, 'd': 250, 't': 2, 'fw': 25,
            'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
        },
    )

    gui.BoxCalculatorGUI._store_fold_designer_workspace(holder, workspace)

    profiles = holder.workspace_controller.part_profiles_snapshot()
    assert [row['phase6_key'] for row in profiles['head']['Y']] == ['fw', 'endcap_d_core', 'ybottom1']
    assert [row['phase6_key'] for row in profiles['tail']['Y']] == ['ybottom1', 'endcap_d_core', 'fw']


def test_known_box_baseline_face_features_survive_authoritative_custom_fold_chain(monkeypatch):
    from ae_engine import ae
    from ae_engine.sheetmetal_features import ResolvedCircle
    from ae_engine.sheetmetal_geometry import Vec2

    calls = []
    def fake_baseline_faces(model_name, **kwargs):
        calls.append(model_name)
        return {
            'left': [ResolvedCircle(center=Vec2(30, 40), radius=4, layer='CUTTING', source_type='baseline')],
            'back': [],
            'right': [],
        }
    monkeypatch.setattr(ae, 'get_box_body_baseline_face_features', fake_baseline_faces)

    scene = ae._build_box_body_scene(
        w=400, h=600, d=250, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=0,
        model_name='金庫型', fold_profile=bridge.profile_to_fold_segments(_box_profile()),
    )
    baseline_circles = [
        p for p in scene.primitives
        if type(p).__name__ == 'CirclePrimitive' and getattr(p, 'layer', '') == 'CUTTING'
    ]
    assert calls == ['金庫型']
    assert len(baseline_circles) == 1
    assert baseline_circles[0].radius == pytest.approx(4.0)


def test_real_main_2d_tabs_follow_existing_parts_delete_and_add_back():
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app._apply_existing_parts_from_fold_workspace(['box_body', 'head', 'door'])
        assert app.notebook.tab(app.tab_z, 'state') != 'hidden'
        assert app.notebook.tab(app.tab_head, 'state') != 'hidden'
        assert app.notebook.tab(app.tab_door, 'state') != 'hidden'
        assert app.notebook.tab(app.tab_tail, 'state') == 'hidden'
        assert app.notebook.tab(app.tab_base_plate, 'state') == 'hidden'

        app._apply_existing_parts_from_fold_workspace([
            'box_body', 'head', 'tail', 'door', 'base_plate', 'indicator_box', 'indicator_door'
        ])
        assert app.notebook.tab(app.tab_tail, 'state') != 'hidden'
        assert app.notebook.tab(app.tab_base_plate, 'state') != 'hidden'
    finally:
        root.destroy()

@pytest.mark.parametrize('count', [3, 5, 9, 12, 20])
def test_linked_endcap_topology_is_count_agnostic_through_practical_twenty_segments(count):
    if count == 3:
        profile = [
            _segment(246, -90, core='D', key='d_left'),
            _segment(396, -90, core='W', key='w'),
            _segment(246, None, core='D', key='d_right'),
        ]
    else:
        profile = _box_profile(extra_left=[
            _segment(7 + i, 45 if i % 2 else -90, key=f'extra_{i}')
            for i in range(count - 5)
        ])
    assert len(profile) == count
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    linked = bridge.build_linked_endcap_xy_profiles(snapshot, profile)
    for key in ('head', 'tail'):
        y = linked[key]['Y']
        expected_total = 284.0 if count in (3, 5) else 300.0
        assert sum(float(row['len']) for row in y) == pytest.approx(expected_total)
        assert sum(1 for row in y if row.get('core') == 'D-T') == 1


def test_project_workspace_presence_excludes_deleted_part_but_keeps_stashed_profile_for_add_back():
    from phase6_designer_workspace import Phase6DesignerWorkspace
    owner = Phase6DesignerWorkspace.from_snapshot({
        'existing_parts': ['box_body', 'head', 'door'],
        'active_part': 'head',
        'part_profiles': {
            'head': {'X': [], 'Y': []},
            'tail': {'X': [{'len': 99}], 'Y': [{'len': 88}]},
            'door': {'X': [], 'Y': []},
        },
    })
    holder = SimpleNamespace(
        designer_workspace=owner,
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        _phase6_endcap_fw_state={},
        _phase6_input_snapshot={'fw': 25},
        state=SimpleNamespace(profiles_vault={'箱身': _box_profile()}),
    )
    workspace = bridge._phase6_collect_workspace_state(holder)
    assert workspace['existing_parts'] == ['box_body', 'head', 'door']
    assert 'tail' in workspace['part_profiles']  # stash survives, presence does not


def test_linked_tail_native_profile_preserves_every_real_mating_turn_for_uploaded_five_segment_shape():
    profile = _box_profile()
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    tail_y = bridge.build_linked_endcap_xy_profiles(snapshot, profile)['tail']['Y']

    assert [r.get('phase6_key') for r in tail_y] == [
        'ybottom1', 'endcap_d_core', 'fw'
    ]
    # With the box-side outer fold removed, native tail owns only the two
    # remaining physical bends: bottom->core and core->FW.
    assert [r.get('angle') for r in tail_y] == [-90, -90, None]


def test_authoritative_endcap_2d_draws_bend_only_when_profile_boundary_has_real_angle():
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    linked = bridge.build_linked_endcap_xy_profiles(snapshot, _box_profile())
    tail = linked['tail']
    # Deliberately remove the FW->ytop1 bend. The FinalScene must not invent
    # a BEND merely because another segment boundary exists at the same cursor.
    tail['Y'][2].pop('angle', None)

    data = manufacturing_api.build_part_render_data(
        _endcap_spec(tail, is_tail=True), ManufacturingContext()
    )
    horizontal = sorted({
        round(float(p.p1.y), 7)
        for p in data.scene.primitives
        if getattr(p, 'layer', '') == 'BEND'
        and abs(float(p.p1.y) - float(p.p2.y)) < 1e-7
    })
    assert horizontal == pytest.approx([15.0, 259.0])


def test_linked_endcap_bends_use_the_exact_input_angles_from_box_fold_chain():
    """輸入幾度就折幾度；derived EndCap 不得固定成 90 或另行換算。"""
    profile = _box_profile()
    profile[0]['angle'] = bridge.ui_angle_to_engine(45.0)       # FW -> D
    profile[1]['angle'] = bridge.ui_angle_to_engine(-60.0)      # D -> next face
    snapshot = {
        'w': 400, 'd': 250, 't': 2, 'fw': 25,
        'yl1': 15, 'yr1': 15, 'ytop1': 16, 'ybottom1': 15,
    }
    linked = bridge.build_linked_endcap_xy_profiles(snapshot, profile)

    head_ui = [bridge.engine_angle_to_ui(row['angle']) for row in linked['head']['Y'] if 'angle' in row]
    tail_ui = [bridge.engine_angle_to_ui(row['angle']) for row in linked['tail']['Y'] if 'angle' in row]
    assert head_ui == pytest.approx([45.0, -60.0])
    # Tail is native reverse order: bend ownership reverses; operator angle values stay unchanged.
    assert tail_ui == pytest.approx([-60.0, 45.0])


@pytest.mark.parametrize('angle', [90, -90, 45, -60, 22.5])
def test_phase6_angle_editor_round_trip_keeps_exact_operator_input(angle):
    stored = bridge.ui_angle_to_engine(angle)
    assert bridge.engine_angle_to_ui(stored) == pytest.approx(angle)


def test_deleted_parts_hide_left_result_rows_and_output_rows_without_spacing():
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        root.update_idletasks(); root.update()
        app._apply_existing_parts_from_fold_workspace(['box_body', 'head'])
        root.update_idletasks(); root.update()

        # Shared Head/Tail size remains visible while Head still exists.
        assert all(row.winfo_manager() == 'pack' for row in app._phase6_result_part_rows['endcap'])

        # Deleted parts disappear completely: no blank row remains in the left panel.
        for group in ('door', 'base_plate', 'indicator_box', 'indicator_door'):
            assert all(row.winfo_manager() == '' for row in app._phase6_result_part_rows[group])

        # Output selectors follow the same physical presence set, not stale checkbox state.
        assert app._phase6_output_part_widgets['box_body'].winfo_manager() == 'pack'
        assert app._phase6_output_part_widgets['head'].winfo_manager() == 'pack'
        for key in ('tail', 'door', 'base_plate', 'indicator_box', 'indicator_door'):
            assert app._phase6_output_part_widgets[key].winfo_manager() == ''
    finally:
        root.destroy()


def test_deleted_part_cannot_export_even_if_checkbox_is_stale_true(monkeypatch, tmp_path):
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        # Exact physical presence says Tail is gone, but simulate a stale old checkbox.
        app.fold_designer_part_bundle = {'existing_parts': ['box_body', 'head']}
        app.export_z_var.set(False)
        app.export_head_var.set(False)
        app.export_tail_var.set(True)
        app.export_door_var.set(False)
        app.export_base_plate_var.set(False)
        app.export_ib_var.set(False)
        app.export_ib_door_var.set(False)

        exported = []
        monkeypatch.setattr(gui.filedialog, 'askdirectory', lambda **_kw: str(tmp_path))
        monkeypatch.setattr(gui.messagebox, 'showwarning', lambda *_a, **_kw: None)
        monkeypatch.setattr(gui.messagebox, 'showerror', lambda *_a, **_kw: None)
        monkeypatch.setattr(gui.messagebox, 'showinfo', lambda *_a, **_kw: None)
        monkeypatch.setattr(app, '_export_authoritative_part', lambda *args, **kwargs: exported.append(args))

        app.export_selected_dxf()
        assert exported == []
    finally:
        root.destroy()


def test_deleted_endcaps_do_not_build_final_scene_from_stashed_profiles(monkeypatch):
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set('自訂')
        app.fold_designer_box_body_profile = None
        # Deletion is presence-only, so stashed profile data intentionally survives.
        app.fold_designer_part_bundle = {
            'existing_parts': ['box_body', 'door'],
            'part_profiles': {'head': {'X': [{'len': 123.0}], 'Y': [{'len': 234.0}]}}
        }
        calls = []
        monkeypatch.setattr(app, '_end_cap_part_spec', lambda *a, **kw: calls.append('endcap') or object())
        app.update_calculations()
        assert calls == []
        assert app.result_y_w_var.get() == '-'
        assert app.result_y_d_var.get() == '-'
    finally:
        root.destroy()


def test_output_checkbox_does_not_delete_physical_part_from_designer_snapshot():
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.export_tail_var.set(False)
        snapshot = app._make_original_fold_designer_snapshot()
        assert 'tail' in snapshot['existing_parts']
        assert app.export_tail_var.get() is False
    finally:
        root.destroy()
