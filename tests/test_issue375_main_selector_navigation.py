from types import SimpleNamespace

import fold_designer_bridge as bridge


class _FakeMenu:
    def __init__(self):
        self.entries = []

    def delete(self, *_args):
        self.entries.clear()

    def add_radiobutton(self, **kwargs):
        self.entries.append(dict(kwargs))


class _FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _owner(monkeypatch):
    owner = SimpleNamespace(
        part_buttons={},
        part_choice_menu=_FakeMenu(),
        part_var=_FakeVar("箱身"),
        available_parts=("box_body", "head", "tail"),
        active_part_key="box_body",
        selected_part_key="box_body",
        assembly_parts_panel=None,
        remove_part_button=None,
    )
    owner._refresh_part_button_states = lambda: None
    monkeypatch.setattr(
        bridge,
        "_phase6_operator_part_selector_keys",
        lambda _parts: ("box_body", "head", "tail"),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_part_label",
        lambda key, snapshot=None: {
            "box_body": "箱身",
            "head": "封頭",
            "tail": "封尾",
        }.get(str(key), str(key)),
    )
    monkeypatch.setattr(bridge, "_phase6_refresh_box_body_piece_selector", lambda _self: ())
    monkeypatch.setattr(bridge, "_phase6_refresh_assembly_parts_panel", lambda _self: None)
    monkeypatch.setattr(bridge, "_phase6_refresh_structure_tree", lambda _self: None)
    monkeypatch.setattr(bridge, "_phase6_refresh_content_switch", lambda _self: None)
    monkeypatch.setattr(bridge, "_phase6_refresh_status_bar", lambda _self: None)
    return owner


def test_main_selector_wraps_existing_part_projection_with_assembly_and_corner_data(monkeypatch):
    owner = _owner(monkeypatch)
    bridge._fix11_refresh_part_buttons(owner)

    values = [str(row.get("value", "")) for row in owner.part_choice_menu.entries]
    assert values == ["組合體", "箱身", "封頭", "封尾", "截角資料"]


def test_main_selector_mode_entries_delegate_to_existing_mode_callbacks(monkeypatch):
    owner = _owner(monkeypatch)
    calls = []

    monkeypatch.setattr(
        bridge, "_phase6_show_assembly", lambda _self: calls.append("assembly")
    )
    monkeypatch.setattr(
        bridge, "_phase6_show_corner_data", lambda _self: calls.append("corner_data")
    )

    bridge._fix11_refresh_part_buttons(owner)
    entries = {
        str(row.get("value", "")): row
        for row in owner.part_choice_menu.entries
    }

    assert "組合體" in entries
    assert "截角資料" in entries

    entries["組合體"]["command"]()
    entries["截角資料"]["command"]()

    assert calls == ["assembly", "corner_data"]


def test_mode_views_keep_main_selector_label_coherent(monkeypatch):
    owner = SimpleNamespace(part_var=_FakeVar("箱身"))
    monkeypatch.setattr(bridge, "_phase6_clear_navigation_residue", lambda _self: None)
    monkeypatch.setattr(bridge, "_phase6_hide_corner_data_canvas", lambda _self: None)

    # This contract is intentionally source-local: mode routing must own the
    # visible projection label without introducing a new domain state owner.
    assembly_source = bridge._phase6_show_assembly.__code__.co_consts
    corner_source = bridge._phase6_show_corner_data.__code__.co_consts

    assert "組合體" in assembly_source
    assert "截角資料" in corner_source
