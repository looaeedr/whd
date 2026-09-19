from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge


class _FakeMenu:
    def __init__(self):
        self.values = []

    def delete(self, *_args):
        self.values.clear()

    def add_radiobutton(self, **kwargs):
        self.values.append(str(kwargs.get("value", "")))


class _FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeCanvas:
    def __init__(self):
        self.calls = []

    def yview_scroll(self, steps, units):
        self.calls.append((steps, units))


@pytest.fixture
def selector_owner(monkeypatch):
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
    monkeypatch.setattr(bridge, "_phase6_refresh_structure_tree", lambda _self: ())
    monkeypatch.setattr(bridge, "_phase6_refresh_content_switch", lambda _self: None)
    monkeypatch.setattr(bridge, "_phase6_refresh_status_bar", lambda _self: None)
    return owner


def test_issue374_target_main_selector_is_single_combined_projection(selector_owner):
    bridge._fix11_refresh_part_buttons(selector_owner)

    assert selector_owner.part_choice_menu.values == [
        "組合體",
        "箱身",
        "封頭",
        "封尾",
        "截角資料",
    ], (
        "RED: #373 main selector does not yet contain assembly + existing parts + "
        "corner data"
    )


def test_issue374_assembly_mousewheel_accepts_windows_nonnumeric_num():
    canvas = _FakeCanvas()
    owner = SimpleNamespace(assembly_parts_canvas=canvas)
    event = SimpleNamespace(delta=120, num="??")

    try:
        result = bridge._phase6_scroll_assembly_parts(owner, event)
    except (TypeError, ValueError) as exc:
        pytest.fail(
            "RED: assembly MouseWheel still crashes on nonnumeric event.num: "
            f"{exc}"
        )

    assert result == "break"
    assert canvas.calls == [(-1, "units")]
