from dataclasses import dataclass

import pytest

from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


@dataclass(frozen=True)
class Feature:
    name: str
    layer: str = "CUTTING"


def names(features):
    return [feature.name for feature in features]


def test_insert_then_cancel_active_restores_original_features():
    features = [Feature("A"), Feature("B")]
    session = Phase6HoleEditorSession("door", features)

    session.execute(HoleEditorAction.insert(Feature("C")))
    assert names(features) == ["A", "B", "C"]
    assert session.snapshot().selected_index == 2
    assert session.snapshot().active_edit is True

    session.execute(HoleEditorAction.cancel_active())

    assert names(features) == ["A", "B"]
    assert session.snapshot().selected_index == -1
    assert session.snapshot().active_edit is False


def test_insert_commit_then_undo_restores_original_features():
    features = [Feature("A")]
    session = Phase6HoleEditorSession("door", features)

    session.execute(HoleEditorAction.insert(Feature("B")))
    session.execute(HoleEditorAction.commit_active())
    assert names(features) == ["A", "B"]
    assert session.snapshot().undo_depth == 1

    session.execute(HoleEditorAction.undo())

    assert names(features) == ["A"]
    assert session.snapshot().selected_index == -1


def test_replace_selected_is_transient_and_cancel_restores_before_snapshot():
    features = [Feature("A"), Feature("B")]
    session = Phase6HoleEditorSession("door", features)

    session.execute(HoleEditorAction.select(1))
    session.execute(HoleEditorAction.replace_selected(Feature("B-moved")))
    assert names(features) == ["A", "B-moved"]

    session.execute(HoleEditorAction.cancel_active())

    assert names(features) == ["A", "B"]


def test_committed_replacement_pushes_undo_without_leaving_active_edit():
    features = [Feature("A", "CUTTING")]
    session = Phase6HoleEditorSession("door", features)

    session.execute(HoleEditorAction.select(0))
    session.execute(HoleEditorAction.replace_selected_committed(Feature("A", "BLIND_HOLE")))

    assert features[0].layer == "BLIND_HOLE"
    assert session.snapshot().active_edit is False
    assert session.snapshot().undo_depth == 1

    session.execute(HoleEditorAction.undo())
    assert features[0].layer == "CUTTING"


def test_delete_selected_then_undo_restores_deleted_feature():
    features = [Feature("A"), Feature("B")]
    session = Phase6HoleEditorSession("door", features)

    session.execute(HoleEditorAction.select(0))
    session.execute(HoleEditorAction.delete_selected())
    assert names(features) == ["B"]

    session.execute(HoleEditorAction.undo())
    assert names(features) == ["A", "B"]


def test_context_switch_cancels_transient_edit_and_does_not_pollute_other_context():
    door = [Feature("door-A")]
    box = [Feature("box-A")]
    session = Phase6HoleEditorSession("door", door)

    session.execute(HoleEditorAction.select(0))
    session.execute(HoleEditorAction.replace_selected(Feature("door-temp")))
    assert names(door) == ["door-temp"]

    session.activate_context("indicator_box", box)

    assert names(door) == ["door-A"]
    assert names(box) == ["box-A"]
    snap = session.snapshot()
    assert snap.context_key == "indicator_box"
    assert snap.selected_index == -1
    assert snap.undo_depth == 0


def test_cancel_all_restores_every_registered_context():
    door = [Feature("door-A")]
    box = [Feature("box-A")]
    session = Phase6HoleEditorSession("door", door)

    session.execute(HoleEditorAction.insert(Feature("door-B")))
    session.execute(HoleEditorAction.commit_active())
    session.activate_context("indicator_box", box)
    session.execute(HoleEditorAction.insert(Feature("box-B")))
    session.execute(HoleEditorAction.commit_active())

    session.finish(commit=False)

    assert names(door) == ["door-A"]
    assert names(box) == ["box-A"]


def test_confirm_all_keeps_all_context_changes_even_with_active_transient_edit():
    door = [Feature("door-A")]
    box = [Feature("box-A")]
    session = Phase6HoleEditorSession("door", door)

    session.execute(HoleEditorAction.insert(Feature("door-B")))
    session.execute(HoleEditorAction.commit_active())
    session.activate_context("indicator_box", box)
    session.execute(HoleEditorAction.insert(Feature("box-B")))

    session.finish(commit=True)

    assert names(door) == ["door-A", "door-B"]
    assert names(box) == ["box-A", "box-B"]
    assert session.snapshot().active_edit is False


def test_preview_all_uses_same_active_transaction_for_cancel_and_commit_undo():
    features = [Feature("A"), Feature("B")]
    session = Phase6HoleEditorSession("door", features)

    session.execute(HoleEditorAction.preview_all([Feature("A2"), Feature("C")], selected_index=0))
    assert names(features) == ["A2", "C"]
    session.execute(HoleEditorAction.cancel_active())
    assert names(features) == ["A", "B"]

    session.execute(HoleEditorAction.preview_all([Feature("A2"), Feature("C")], selected_index=0))
    session.execute(HoleEditorAction.commit_active())
    assert names(features) == ["A2", "C"]
    session.execute(HoleEditorAction.undo())
    assert names(features) == ["A", "B"]


def test_undo_history_is_bounded_to_configured_max_steps():
    features = [Feature("0")]
    session = Phase6HoleEditorSession("door", features, max_undo_steps=3)

    for i in range(1, 6):
        session.execute(HoleEditorAction.select(0))
        session.execute(HoleEditorAction.replace_selected_committed(Feature(str(i))))

    assert session.snapshot().undo_depth == 3
    session.execute(HoleEditorAction.undo())
    session.execute(HoleEditorAction.undo())
    session.execute(HoleEditorAction.undo())
    assert names(features) == ["2"]
    session.execute(HoleEditorAction.undo())
    assert names(features) == ["2"]


def test_invalid_selection_is_rejected_without_mutating_features():
    features = [Feature("A")]
    session = Phase6HoleEditorSession("door", features)

    with pytest.raises(IndexError):
        session.execute(HoleEditorAction.select(4))

    assert names(features) == ["A"]


def test_gui_unified_hole_editor_does_not_recreate_session_owned_state():
    import ast
    from pathlib import Path

    tree = ast.parse(Path("gui.py").read_text(encoding="utf-8"))
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_open_unified_hole_editor"
    )
    assigned_names = set()
    for node in ast.walk(method):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
    assert not ({
        "selected",
        "active_snapshot",
        "undo_history_ref",
        "context_feature_lists",
        "context_original_features",
    } & assigned_names)


def test_hole_editor_session_module_has_no_tk_or_project_dependencies():
    import ast
    from pathlib import Path

    tree = ast.parse(Path("phase6_hole_editor_session.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden_prefixes = (
        "tkinter", "gui", "ae_engine", "phase6_project", "phase6_settings", "phase6_final_scene",
    )
    assert not [name for name in imported if name.startswith(forbidden_prefixes)]


def test_gui_no_longer_owns_legacy_editor_undo_history_class():
    import ast
    from pathlib import Path

    tree = ast.parse(Path("gui.py").read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert "EditorUndoHistory" not in names


def _walk_tk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk_tk_widgets(child)


def test_real_tk_unified_hole_editor_delete_undo_and_cancel_all_use_session():
    import tkinter as tk

    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, feature_surface_from_rect
    from ae_engine.sheetmetal_geometry import Vec2

    root = tk.Tk()
    try:
        app = gui.BoxCalculatorGUI(root)
        root.update()
        features = [
            CircleFeature(
                diameter=20.0,
                anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(50.0, 50.0),
            )
        ]
        surface = feature_surface_from_rect("test_face", Vec2(0.0, 0.0), Vec2(100.0, 100.0))

        app._open_unified_hole_editor(
            "door",
            "測試門板",
            surface,
            100.0,
            100.0,
            feature_list_override=features,
        )
        editor = app.last_unified_hole_editor
        root.update()

        widgets = list(_walk_tk_widgets(editor))
        created = next(
            widget for widget in widgets
            if isinstance(widget, tk.Listbox)
            and widget.size() == 1
            and str(widget.get(0)).startswith("01")
        )
        delete_btn = next(
            widget for widget in widgets
            if isinstance(widget, tk.Button) and widget.cget("text") == "刪除選中"
        )
        undo_btn = next(
            widget for widget in widgets
            if isinstance(widget, tk.Button) and widget.cget("text") == "↶ 回上一步"
        )
        cancel_all_btn = next(
            widget for widget in widgets
            if isinstance(widget, tk.Button) and widget.cget("text") == "取消全部"
        )

        created.selection_set(0)
        created.event_generate("<<ListboxSelect>>")
        root.update()
        delete_btn.invoke()
        root.update()
        assert features == []

        undo_btn.invoke()
        root.update()
        assert len(features) == 1
        assert features[0].diameter == 20.0

        # Make a committed mutation, then Cancel All must still restore the
        # original context snapshot captured when the editor opened.
        created.selection_clear(0, tk.END)
        created.selection_set(0)
        created.event_generate("<<ListboxSelect>>")
        root.update()
        delete_btn.invoke()
        root.update()
        assert features == []
        cancel_all_btn.invoke()
        root.update()
        assert len(features) == 1
        assert features[0].diameter == 20.0
        assert not editor.winfo_exists()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_gui_unified_hole_editor_does_not_mutate_feature_list_outside_session():
    import ast
    from pathlib import Path

    tree = ast.parse(Path("gui.py").read_text(encoding="utf-8"))
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_open_unified_hole_editor"
    )
    violations = []
    for node in ast.walk(method):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "feature_list":
                    violations.append((node.lineno, "item assignment"))
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "feature_list":
                    violations.append((node.lineno, "delete"))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "feature_list"
            and node.func.attr in {"append", "extend", "insert", "pop", "remove", "clear"}
        ):
            violations.append((node.lineno, node.func.attr))
    assert violations == []
