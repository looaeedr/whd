from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "gui.py").read_text(encoding="utf-8")
BRIDGE = (ROOT / "fold_designer_bridge.py").read_text(encoding="utf-8")


def test_3d_is_separate_entry_not_workspace_mode():
    assert '("fold", "3D 折彎")' not in GUI
    assert 'self.fold_designer_button.pack_forget()' not in GUI
    assert 'text="開啟折彎 / 3D 設計"' in GUI


def test_3d_workspace_uses_persistent_part_menubutton_row():
    assert 'self.part_selector = original.ttk.Frame(self.left)' in BRIDGE
    assert 'self.part_choice_button = original.ttk.Menubutton' in BRIDGE
    assert 'self.add_part_button = original.ttk.Menubutton' in BRIDGE
    assert 'text="刪除"' in BRIDGE
    assert 'workspace_part_buttons' not in GUI


def test_main_gui_no_longer_embeds_legacy_workspace_mode_frames():
    assert 'self.workspace_controller = Phase6WorkspaceController()' in GUI
    assert 'workspace_part_frame' not in GUI
    assert 'workspace_holes_frame' not in GUI
    assert 'workspace_fold_frame' not in GUI
