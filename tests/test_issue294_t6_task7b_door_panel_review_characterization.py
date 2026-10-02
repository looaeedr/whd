from __future__ import annotations

from types import SimpleNamespace

import gui


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.destroyed = False
        self.packs = []
        self.bindings = {}

    def destroy(self):
        self.destroyed = True

    def pack(self, *args, **kwargs):
        self.packs.append((args, kwargs))

    def bind(self, event, callback):
        self.bindings[event] = callback


class FakeContainer(FakeWidget):
    def __init__(self, children=()):
        super().__init__()
        self.children = list(children)

    def winfo_children(self):
        return list(self.children)


def test_task7b_indicator_state_normalization_contract():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)

    assert gui.Phase6ApplicationHost._normalize_door_indicator_state(host, None) == {
        "mode": "none",
        "enabled": False,
        "box_enabled": False,
        "layers": 1,
        "groups": [2, 2, 2, 2, 2, 2],
        "offset_x": 0.0,
        "offset_y": 0.0,
        "is_box_dist": False,
    }

    actual = gui.Phase6ApplicationHost._normalize_door_indicator_state(
        host,
        {
            "box_enabled": True,
            "layers": "9",
            "groups": ["3", "bad"],
            "offset_x": "1.5",
            "offset_y": "-2.5",
            "is_box_dist": 1,
        },
    )
    assert actual == {
        "mode": "indicator_box",
        "enabled": False,
        "box_enabled": True,
        "layers": 6,
        "groups": [3, 2, 2, 2, 2, 2],
        "offset_x": 1.5,
        "offset_y": -2.5,
        "is_box_dist": True,
    }


def test_task7b_destroy_door_layout_entry_widgets_resets_transient_ui():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    width = FakeWidget()
    height = FakeWidget()
    host.door_layout_width_entries = {0: width}
    host.door_layout_height_entries = {(0, 0): height}
    host.door_layout_entry_windows = [101, 102]

    gui.Phase6ApplicationHost._destroy_door_layout_entry_widgets(host)

    assert width.destroyed is True
    assert height.destroyed is True
    assert host.door_layout_width_entries == {}
    assert host.door_layout_height_entries == {}
    assert host.door_layout_entry_windows == []


def test_task7b_door_layout_entry_menu_preserves_delete_column_action(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.door_layout_columns = [{"width_auto": False, "height_auto": [False]}]
    removed = []
    host.remove_door_layout_column = lambda index: removed.append(index)
    host.remove_door_layout_height = lambda column, row: removed.append((column, row))

    menus = []

    class FakeMenu:
        def __init__(self, entry, tearoff=False):
            self.entry = entry
            self.tearoff = tearoff
            self.commands = []
            menus.append(self)

        def add_command(self, *, label, command):
            self.commands.append((label, command))

        def index(self, name):
            assert name == "end"
            return 0 if self.commands else None

        def tk_popup(self, x, y):
            return None

    monkeypatch.setattr(gui.tk, "Menu", FakeMenu)
    entry = FakeWidget()

    gui.Phase6ApplicationHost._door_layout_entry_menu(
        host, entry, column_index=0
    )

    assert len(menus) == 1
    assert [label for label, _command in menus[0].commands] == ["刪除此欄"]
    menus[0].commands[0][1]()
    assert removed == [0]
    assert "<Button-3>" in entry.bindings


def test_task7b_rebuild_door_layers_config_ui_preserves_layer_rows(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    existing = FakeWidget()
    host.door_layers_config_frame = FakeContainer([existing])
    host.door_indicator_l_var = Var("2")
    host.door_indicator_layer_g_vars = [object(), object()]
    host.COLOR_PANEL = "#panel"
    host.COLOR_TEXT = "#text"
    updates = []
    host._request_phase6_update = lambda kind: updates.append(kind)

    frames = []
    labels = []
    combos = []

    class FakeFrame(FakeWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            frames.append(self)

    class FakeLabel(FakeWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            labels.append(self)

    class FakeCombo(FakeWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            combos.append(self)

    monkeypatch.setattr(gui.tk, "Frame", FakeFrame)
    monkeypatch.setattr(gui.tk, "Label", FakeLabel)
    monkeypatch.setattr(gui.ttk, "Combobox", FakeCombo)

    gui.Phase6ApplicationHost.rebuild_door_layers_config_ui(host)

    assert existing.destroyed is True
    assert len(frames) == 2
    assert len(combos) == 2
    assert [item.kwargs["text"] for item in labels] == [
        "第 1 層 (底) 組數:",
        "第 2 層 (頂) 組數:",
    ]
    assert all("<<ComboboxSelected>>" in combo.bindings for combo in combos)
