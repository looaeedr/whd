import ast
from pathlib import Path
from types import SimpleNamespace


def _load_class_method(path, class_name, method_name):
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    standalone = ast.FunctionDef(
        name=method.name,
        args=method.args,
        body=method.body,
        decorator_list=[],
        returns=method.returns,
        type_comment=method.type_comment,
    )
    ast.fix_missing_locations(standalone)
    ns = {}
    exec(compile(ast.Module(body=[standalone], type_ignores=[]), str(path), "exec"), ns)
    return ns[method_name]


def test_indicator_box_and_small_door_profiles_use_real_bend_span_but_show_outside_core_size():
    from fold_designer_bridge import build_standard_part_profiles, engine_segment_length_to_ui

    snapshot = {
        "t": 2.0,
        "indicator_box_fold": 49.0,
        "indicator_door_fold": 19.0,
        "part_dimensions": {
            "indicator_box": {"width": 326.0, "height": 445.0},
            "indicator_door": {"width": 254.0, "height": 374.0},
        },
    }

    box = build_standard_part_profiles(snapshot, "indicator_box")
    assert box["X"][1]["len"] == 228
    assert box["Y"][1]["len"] == 347
    assert engine_segment_length_to_ui(box["X"][1]) == 232
    assert engine_segment_length_to_ui(box["Y"][1]) == 351

    door = build_standard_part_profiles(snapshot, "indicator_door")
    assert door["X"][1]["len"] == 216
    assert door["Y"][1]["len"] == 336
    assert engine_segment_length_to_ui(door["X"][1]) == 220
    assert engine_segment_length_to_ui(door["Y"][1]) == 340


def test_hidden_indicator_part_returned_from_3d_becomes_manual_corner_context():
    sync = _load_class_method("gui.py", "BoxCalculatorGUI", "_sync_fold_designer_manual_corner_context")
    current = _load_class_method("gui.py", "BoxCalculatorGUI", "_current_manual_corner_part_key")

    refreshed = []
    app = SimpleNamespace(
        _manual_corner_part_override=None,
        manual_corner_state={"indicator_box": {}, "indicator_door": {}, "door": {}},
        refresh_corner_type_panel=lambda: refreshed.append(True),
    )

    sync(app, "indicator_box")
    assert app._manual_corner_part_override == "indicator_box"
    assert current(app) == "indicator_box"
    assert refreshed == [True]

    sync(app, "indicator_door")
    assert app._manual_corner_part_override == "indicator_door"
    assert current(app) == "indicator_door"


def test_apply_path_syncs_active_designer_part_back_to_manual_corner_context():
    source = Path("gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BoxCalculatorGUI")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_apply_original_fold_designer_snapshot")
    text = ast.get_source_segment(source, method)
    assert "_sync_fold_designer_manual_corner_context" in text
    assert 'snapshot.get("active_part")' in text
