from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "application" / "calculation_controller.py"


class Var:
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


RESULT_ATTRS = (
    "result_z_var",
    "result_z_h_var",
    "result_y_w_var",
    "result_y_d_var",
    "result_door_w_var",
    "result_door_h_var",
    "result_base_plate_w_var",
    "result_base_plate_h_var",
    "result_ib_w_var",
    "result_ib_h_var",
    "result_ib_door_w_var",
    "result_ib_door_h_var",
)


def _update_method():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return next(
        (
            node for node in host.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "update_calculations"
        ),
        None,
    )


def test_calculation_controller_owner_exists_and_root_is_thin():
    assert OWNER.is_file()
    text = OWNER.read_text(encoding="utf-8")
    assert "def update_calculations(" in text
    node = _update_method()
    if node is not None:
        assert node.end_lineno - node.lineno + 1 <= 5
    else:
        assert "update_calculations = _phase6_calculation_controller.update_calculations" in GUI.read_text(encoding="utf-8")


def test_incomplete_numeric_input_clears_all_result_values_without_escape():
    import gui

    host = object.__new__(gui.Phase6ApplicationHost)
    for attr in RESULT_ATTRS:
        setattr(host, attr, Var("stale"))

    def fail_values():
        raise ValueError("incomplete")
    host.get_float_values = fail_values

    host.update_calculations()
    assert {attr: getattr(host, attr).get() for attr in RESULT_ATTRS} == {
        attr: "-" for attr in RESULT_ATTRS
    }


def test_scheduler_still_routes_full_dirty_work_to_owner_update():
    from gui_modules.application.command_router import _Phase6UpdateScheduler

    class Owner:
        root = None
        def __init__(self):
            self.calls = 0
        def update_calculations(self):
            self.calls += 1

    owner = Owner()
    scheduler = _Phase6UpdateScheduler(owner)
    scheduler.dirty.add("geometry")
    assert scheduler.flush_now() is True
    assert owner.calls == 1


def test_calculation_controller_has_no_authority_construction():
    if not OWNER.is_file():
        pytest.skip("RED: calculation controller owner not created yet")
    text = OWNER.read_text(encoding="utf-8")
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
    assert "PROJECT_SCHEMA =" not in text
