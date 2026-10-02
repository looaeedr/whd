from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "visibility" / "controller.py"


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


class CacheOwner:
    def __init__(self):
        self.reasons = []
    def invalidate(self, reason):
        self.reasons.append(reason)


class Workspace:
    def __init__(self):
        self.calls = []
    def current_existing_parts(self, *, indicator_box_enabled):
        self.calls.append(("current", indicator_box_enabled))
        return {"box_body", "indicator_box"} if indicator_box_enabled else {"box_body"}
    def set_part_presence(self, key, present):
        self.calls.append(("set", key, present))
        return {"box_body", key} if present else {"box_body"}


def _host_methods():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _loc(node):
    return node.end_lineno - node.lineno + 1


def test_visibility_owner_exists_and_root_routes_are_thin():
    assert OWNER.is_file()
    funcs = {
        node.name: node
        for node in ast.parse(OWNER.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in (
        "phase6_current_existing_parts",
        "phase6_set_part_presence",
        "phase6_refresh_presence_ui",
    ):
        assert name in funcs
        assert _loc(funcs[name]) <= 40

    methods = _host_methods()
    for name in (
        "_phase6_current_existing_parts",
        "_phase6_set_part_presence",
        "_phase6_refresh_presence_ui",
    ):
        if name in methods:
            assert _loc(methods[name]) <= 5


def test_visibility_reads_presence_only_through_workspace_controller():
    if not OWNER.is_file():
        pytest.skip("RED: visibility owner not created yet")
    from gui_modules.visibility.controller import phase6_current_existing_parts

    host = type("Host", (), {})()
    host.workspace_controller = Workspace()
    host.is_indicator_box_var = Var(True)

    existing = phase6_current_existing_parts(host)
    assert existing == {"box_body", "indicator_box"}
    assert host.workspace_controller.calls == [("current", True)]


def test_visibility_presence_mutation_routes_workspace_then_ui_and_cache():
    if not OWNER.is_file():
        pytest.skip("RED: visibility owner not created yet")
    from gui_modules.visibility.controller import phase6_set_part_presence

    host = type("Host", (), {})()
    host.workspace_controller = Workspace()
    host._derived_cache_owner = CacheOwner()
    host.refreshed = []
    host._phase6_refresh_presence_ui = lambda existing: host.refreshed.append(existing)

    existing = phase6_set_part_presence(host, "door", True)
    assert existing == {"box_body", "door"}
    assert host.workspace_controller.calls == [("set", "door", True)]
    assert host.refreshed == [{"box_body", "door"}]
    assert host._derived_cache_owner.reasons == ["geometry"]


def test_visibility_module_has_no_shadow_identity_or_project_authority():
    if not OWNER.is_file():
        pytest.skip("RED: visibility owner not created yet")
    text = OWNER.read_text(encoding="utf-8")
    assert "self.existing_parts =" not in text
    assert "host.existing_parts =" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "Phase6ProjectController(" not in text
    assert "PROJECT_SCHEMA =" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
