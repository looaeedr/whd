
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_workspace_controller import Phase6WorkspaceController

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EXPORT = ROOT / "gui_modules" / "project" / "export_actions.py"


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return ast.get_source_segment(source, node) or ""


def _compile_function(path: Path, name: str):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    mod = ast.Module(body=[node], type_ignores=[])
    ns = {}
    exec(compile(ast.fix_missing_locations(mod), str(path), "exec"), ns)
    return ns[name]


def test_indicator_box_and_small_door_share_single_workspace_presence_owner():
    owner = Phase6WorkspaceController()
    owner.set_part_presence("indicator_box", True)
    owner.set_part_presence("indicator_door", True)
    existing = owner.current_existing_parts()
    assert {"indicator_box", "indicator_door"} <= existing

    owner.set_part_presence("indicator_box", False)
    owner.set_part_presence("indicator_door", False)
    existing = owner.current_existing_parts()
    assert "indicator_box" not in existing
    assert "indicator_door" not in existing


def test_single_door_indicator_toggle_removes_box_presence_without_touching_cell_state():
    src = _function_source(GUI, "_disable_indicator_box_for_door_indicator")
    assert 'set_part_presence("indicator_box", False)' in src
    assert 'set_part_presence("indicator_door", False)' in src
    assert "door_layout_indicator_states" not in src


def test_indicator_box_toggle_routes_both_physical_parts_through_presence_owner():
    src = _function_source(GUI, "on_indicator_box_toggle")
    assert '_phase6_set_part_presence("indicator_box", enabled)' in src
    assert '_phase6_set_part_presence("indicator_door", enabled)' in src
    assert "add_workspace_part" not in src


def test_multi_door_indicator_commit_updates_only_target_cell_and_not_global_mode():
    fn = _compile_function(EXPORT, "_apply_multi_door_indicator_state")

    class Host:
        def __init__(self):
            self.door_layout_indicator_states = {
                "1:0": {"mode": "indicator_box", "enabled": False, "box_enabled": True}
            }
            self.is_indicator_box_var = SimpleNamespace(value=True)
            self.is_door_indicator_var = SimpleNamespace(value=False)

        def _normalize_door_indicator_state(self, state):
            mode = str(state.get("mode", "none"))
            return {
                "mode": mode,
                "enabled": mode == "indicator",
                "box_enabled": mode == "indicator_box",
                "layers": int(state.get("layers", 1)),
                "groups": list(state.get("groups", [2] * 6)),
                "offset_x": float(state.get("offset_x", 0.0)),
                "offset_y": float(state.get("offset_y", 0.0)),
                "is_box_dist": bool(state.get("is_box_dist", False)),
            }

    host = Host()
    before_globals = (host.is_indicator_box_var.value, host.is_door_indicator_var.value)
    before_other = dict(host.door_layout_indicator_states["1:0"])
    fn(host, "0:0", {"mode": "indicator", "groups": [1, 2, 2, 2, 2, 2]})

    assert host.door_layout_indicator_states["0:0"]["mode"] == "indicator"
    assert host.door_layout_indicator_states["1:0"] == before_other
    assert (host.is_indicator_box_var.value, host.is_door_indicator_var.value) == before_globals


def test_multi_door_component_export_reads_per_cell_indicator_state():
    src = _function_source(EXPORT, "export_multi_door_indicator_box_parts")
    assert "_door_layout_cell_key(cell)" in src
    assert "_door_layout_indicator_state_for_key(key)" in src
    assert 'state.get("mode") != "indicator_box"' in src
    assert "is_indicator_box_var" not in src


def test_retired_dynamic_workspace_api_does_not_return():
    gui = GUI.read_text(encoding="utf-8")
    assert "add_workspace_part" not in gui


def test_false_legacy_indicator_hint_cannot_erase_controller_owned_presence():
    owner = Phase6WorkspaceController()
    owner.set_part_presence("indicator_box", True)
    owner.set_part_presence("indicator_door", True)

    existing = owner.current_existing_parts(indicator_box_enabled=False)
    assert {"indicator_box", "indicator_door"} <= existing


def test_indicator_component_presence_round_trips_through_workspace_snapshot():
    owner = Phase6WorkspaceController()
    owner.set_part_presence("indicator_box", True)
    owner.set_part_presence("indicator_door", True)
    snapshot = owner.workspace_snapshot()

    restored = Phase6WorkspaceController()
    restored.commit_workspace(snapshot)

    assert {"indicator_box", "indicator_door"} <= restored.current_existing_parts()
    assert {"indicator_box", "indicator_door"} <= set(restored.workspace_snapshot()["existing_parts"])
