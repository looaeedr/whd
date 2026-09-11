import inspect
from types import SimpleNamespace

import fold_designer_bridge as bridge
import phase6_final_scene_view as view


def _formatter():
    fn = getattr(view, 'format_operator_info_text', None)
    assert callable(fn), 'T3 requires shared operator-info formatter'
    return fn


def _request(key, dims, *, pieces=(), x_profile=(), y_profile=()):
    return view.FinalSceneViewRequest(
        render_data=SimpleNamespace(pieces=tuple(pieces)),
        x_profile=tuple(x_profile),
        y_profile=tuple(y_profile),
        part_key=key,
        finished_dimensions=tuple(dims),
        thickness=2.0,
        corner_dimension_text='截角尺寸：CROSS',
        unfolded_blank_text='展開料：100 × 200 mm',
    )


def test_parent_shared_text_contains_complete_boxbody_and_current_piece_summaries_only():
    pieces = (
        SimpleNamespace(role='left_side', formed_outer_dimensions=(120, 700), material_dimensions=(140, 720)),
        SimpleNamespace(role='back', formed_outer_dimensions=(760, 700), material_dimensions=(780, 720)),
        SimpleNamespace(role='right_side', formed_outer_dimensions=(120, 700), material_dimensions=(140, 720)),
    )
    text = _formatter()(_request('box_body', (800, 1600, 600), pieces=pieces))
    assert '折後包外：W 800 × H 1600 × D 600 mm' in text
    assert '左側板：成形 120 × 700 mm；展開 140 × 720 mm' in text
    assert '後面板：成形 760 × 700 mm；展開 780 × 720 mm' in text
    assert '右側板：成形 120 × 700 mm；展開 140 × 720 mm' in text
    contracted = _formatter()(_request('box_body', (800, 1600, 600), pieces=pieces[:1]))
    assert '左側板：' in contracted
    assert '後面板：' not in contracted
    assert '右側板：' not in contracted


def test_child_shared_text_is_exact_scope_and_never_leaks_parent_depth_or_piece_summary():
    text = _formatter()(_request(
        'box_body:back', (760, 700),
        x_profile=({'len': 20.0, 'angle': 90.0}, {'len': 760.0}),
        y_profile=({'len': 700.0},),
    ))
    assert '折後包外：W 760 × H 700 mm' in text
    assert ' × D ' not in text
    assert '左側板：' not in text and '後面板：' not in text and '右側板：' not in text


def test_3d_draw_operator_dimensions_consumes_shared_formatter():
    src = inspect.getsource(view.Phase6FinalSceneView._draw_operator_dimensions)
    assert 'format_operator_info_text(' in src
    assert 'info = f"{finished}' not in src


def test_corner_data_request_uses_selected_stable_key_without_mutating_manufacturing_selection(monkeypatch):
    builder = getattr(bridge, '_phase6_corner_data_info_request_for_key', None)
    assert callable(builder), 'T3 requires selected-key Corner Data info request builder'
    workspace = SimpleNamespace(active_part='door_c1_r1', selected_part='door_c1_r1')
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot={'t': 2.0},
        _settings_values={'t': 2.0},
        state=SimpleNamespace(alpha_bend=0.85),
    )
    render_data = SimpleNamespace(material=SimpleNamespace(bounds=(0.0, 0.0, 760.0, 700.0)), pieces=())
    calls = []
    monkeypatch.setattr(bridge, '_phase6_mesh_profiles_for_part', lambda _owner, key, _mat: (calls.append(('profiles', key)) or ([{'len': 760.0}], [{'len': 700.0}])))
    monkeypatch.setattr(bridge, '_phase6_operator_finished_dimensions', lambda _owner, key: calls.append(('dims', key)) or (760.0, 700.0))
    monkeypatch.setattr(bridge, '_phase6_render_data_corner_dimension_text', lambda _data: '截角尺寸：CROSS')
    monkeypatch.setattr(bridge, '_phase6_format_unfolded_blank_text', lambda _data, *, part_key='': f'展開料：{part_key}')
    before = (workspace.active_part, workspace.selected_part)
    request = builder(app, 'box_body:back', render_data)
    assert request.part_key == 'box_body:back'
    assert request.finished_dimensions == (760.0, 700.0)
    assert ('profiles', 'box_body:back') in calls and ('dims', 'box_body:back') in calls
    assert (workspace.active_part, workspace.selected_part) == before


def test_corner_data_refresh_publishes_shared_info_text_above_canvas():
    src = inspect.getsource(bridge._phase6_refresh_corner_data_unfold_view)
    assert '_phase6_corner_data_info_text_for_key' in src
    assert 'corner_data_info_var' in src
    prep = inspect.getsource(bridge._phase6_prepare_corner_data_canvas)
    assert 'corner_data_info_label' in prep
    assert 'textvariable=self.corner_data_info_var' in prep
