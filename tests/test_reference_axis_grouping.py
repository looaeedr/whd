from pathlib import Path

import gui
from phase6_hole_editor_canvas_view import _layout_axis_reference_overlay_rects


def test_axis_group_layout_returns_x_y_and_panel_without_feature_overlap():
    rects = _layout_axis_reference_overlay_rects(
        1000, 700,
        crosshair=(500, 350),
        feature_rect=(430, 300, 570, 400),
        sizes={'x_group': (190, 84), 'y_group': (190, 84), 'panel': (140, 92)},
        x_side='left', y_side='bottom',
    )
    assert set(rects) == {'x_group', 'y_group', 'panel'}
    feature = (430, 300, 570, 400)
    for rect in rects.values():
        assert rect[2] <= feature[0] or rect[0] >= feature[2] or rect[3] <= feature[1] or rect[1] >= feature[3]


def test_axis_group_layout_follows_crosshair():
    common = dict(
        canvas_w=1000, canvas_h=700,
        feature_rect=(430, 300, 570, 400),
        sizes={'x_group': (190, 84), 'y_group': (190, 84), 'panel': (140, 92)},
        x_side='left', y_side='bottom',
    )
    a = _layout_axis_reference_overlay_rects(crosshair=(470, 330), **common)
    b = _layout_axis_reference_overlay_rects(crosshair=(530, 370), **common)
    assert a != b


def test_gui_source_groups_x_with_x_and_y_with_y():
    source = (Path(__file__).resolve().parents[1] / 'gui.py').read_text(encoding='utf-8')
    assert 'x_group = tk.Frame(canvas' in source
    assert 'add_group_entry(x_group, lbl_x_edge, var_x_edge, "x", "edge")' in source
    assert 'add_group_entry(x_group, lbl_x_neighbor, var_x_neighbor, "x", "neighbor")' in source
    assert 'y_group = tk.Frame(canvas' in source
    assert 'add_group_entry(y_group, lbl_y_edge, var_y_edge, "y", "edge")' in source
    assert 'add_group_entry(y_group, lbl_y_neighbor, var_y_neighbor, "y", "neighbor")' in source
    assert 'edge_group = tk.Frame(canvas' not in source
    assert 'neighbor_group = tk.Frame(canvas' not in source
