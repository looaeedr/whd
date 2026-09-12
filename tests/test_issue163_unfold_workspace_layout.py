import os
from pathlib import Path
import tkinter as tk

import pytest

import gui
from phase6_settings_center import UI_TEXT_SIZE_LABELS


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#163 layout contracts require real Tk/Xvfb"
)


@pytest.fixture(autouse=True)
def _restore_config_ini_after_ui_contract():
    """UI scale callbacks may persist preferences; regression tests must not leak them."""
    config_path = Path(__file__).resolve().parents[1] / "config.ini"
    original = config_path.read_bytes()
    try:
        yield
    finally:
        config_path.write_bytes(original)


def _open_designer():
    root = tk.Tk()
    root.geometry("1050x620+0+0")
    root.update_idletasks()
    app = gui.BoxCalculatorGUI(root)
    designer = app.open_original_fold_designer()
    root.update_idletasks()
    root.update()
    return root, app, designer


def _close(root):
    try:
        root.destroy()
    except Exception:
        pass


def _descendants(widget):
    rows = []
    for child in tuple(widget.winfo_children()):
        rows.append(child)
        rows.extend(_descendants(child))
    return rows


def _visible_texts(widget):
    texts = []
    for child in _descendants(widget):
        try:
            if not child.winfo_manager():
                continue
            text = str(child.cget("text") or "").strip()
        except Exception:
            continue
        if text:
            texts.append(text)
    return texts


def _is_descendant(widget, ancestor):
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, "master", None)
    return False


def test_red_163_top_surface_contains_only_file_and_corner_data_commands():
    root, _app, designer = _open_designer()
    try:
        top = designer.top_persistent_bar
        texts = _visible_texts(top)
        assert set(texts) == {"檔案 ▼", "截角資料庫"}, (
            f"#163 top must contain only File + Corner Data; found: {texts}"
        )
        managed_children = [child for child in top.winfo_children() if child.winfo_manager()]
        assert managed_children == [designer.top_command_row]
    finally:
        _close(root)


def test_red_163_non_file_controls_are_owned_by_right_control_region():
    root, _app, designer = _open_designer()
    try:
        host = designer.right_controls_host
        for name in (
            "transaction_buttons",
            "visual_controls",
            "fullscreen_button",
            "left_global_controls",
        ):
            widget = getattr(designer, name)
            assert _is_descendant(widget, host), f"{name} is not owned by right_controls_host"
    finally:
        _close(root)


def test_red_163_left_workspace_has_vertical_scroll_and_bottom_is_reachable_at_all_text_scales():
    root, _app, designer = _open_designer()
    try:
        canvas = designer.left_scroll_canvas
        scrollbar = designer.left_scrollbar
        assert str(scrollbar.cget("orient")) == "vertical"
        assert scrollbar.winfo_manager(), "left vertical scrollbar must be present"
        assert designer.left_scroll_window

        labels = tuple(UI_TEXT_SIZE_LABELS.values())
        assert len(labels) >= 3
        for label in labels:
            designer.settings_panel.ui_text_size_var.set(label)
            designer.on_ui_text_size_changed()
            root.update_idletasks()
            root.update()
            bbox = canvas.bbox("all")
            assert bbox is not None
            canvas.configure(scrollregion=bbox)
            canvas.yview_moveto(1.0)
            root.update_idletasks()
            root.update()
            _first, last = canvas.yview()
            assert last >= 0.999, f"bottom unreachable at text scale {label}: yview={canvas.yview()}"
    finally:
        _close(root)
