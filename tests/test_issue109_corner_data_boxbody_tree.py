import inspect
from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Workspace:
    def __init__(self, parts):
        self.available_parts = tuple(parts)


def _app(parts):
    return SimpleNamespace(designer_workspace=_Workspace(parts))


def _rows(parts):
    fn = getattr(bridge, '_phase6_corner_data_navigation_rows', None)
    assert callable(fn), 'T2 requires a pure corner-data hierarchy projection'
    return fn(_app(parts))


def test_three_piece_box_body_is_one_parent_with_three_physical_children():
    parts = (
        'box_body',
        'box_body:left_side',
        'box_body:back',
        'box_body:right_side',
        'box_body:divider:1',
        'head',
    )
    assert _rows(parts) == (
        ('box_body', 0),
        ('box_body:left_side', 1),
        ('box_body:back', 1),
        ('box_body:right_side', 1),
        ('box_body:divider:1', 0),
        ('head', 0),
    )


def test_single_piece_box_body_has_parent_only_and_never_invents_fake_child():
    result = _rows(('box_body', 'head'))
    assert result == (('box_body', 0), ('head', 0))
    assert all(key != 'box_body:box_body' for key, _depth in result)


def test_view_projection_never_invents_parent_when_authority_does_not_have_one():
    parts = ('box_body:left_side', 'box_body:back', 'head')
    assert _rows(parts) == (
        ('box_body:left_side', 0),
        ('box_body:back', 0),
        ('head', 0),
    )


def test_child_identity_and_back_label_stay_exact():
    parts = ('box_body', 'box_body:left_side', 'box_body:back', 'box_body:right_side')
    rows = _rows(parts)
    assert [key for key, depth in rows if depth == 1] == [
        'box_body:left_side', 'box_body:back', 'box_body:right_side'
    ]
    assert bridge._phase6_part_label('box_body:back') == '後面板'
    assert bridge._phase6_part_label('box_body:left_side') == '左側板'
    assert bridge._phase6_part_label('box_body:right_side') == '右側板'


def test_corner_data_panel_consumes_hierarchy_projection_and_indents_children():
    src = inspect.getsource(bridge._phase6_refresh_corner_data_parts_panel)
    assert '_phase6_corner_data_navigation_rows(self)' in src
    assert 'for key, depth in navigation_rows' in src
    assert 'padx=(18, 0) if depth else 0' in src


def test_raw_authoritative_flat_projection_remains_unchanged():
    parts = (
        'box_body', 'box_body:left_side', 'box_body:back', 'box_body:right_side',
        'box_body:divider:7', 'door_c2_r1', 'base_plate_c1_r1'
    )
    app = _app(parts)
    assert bridge._phase6_corner_data_part_keys(app) == parts
