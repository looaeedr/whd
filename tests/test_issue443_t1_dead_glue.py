from __future__ import annotations

import ast
import subprocess
from pathlib import Path

BRIDGE = Path("fold_designer_bridge.py")
SETTINGS_PANEL = Path("phase6_settings_panel.py")
SELF = Path(__file__).resolve()
TARGETS = {
    "_phase6_build_box_symmetry_settings",
    "_phase6_build_assembly_settings",
}


def _tracked_python_paths() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z", "*.py"])
    paths = [
        Path(item.decode("utf-8", "surrogateescape"))
        for item in raw.split(b"\0")
        if item
    ]
    return [path for path in paths if not (path.parts and path.parts[0] == "BACKUP")]


def _inventory() -> dict[str, dict[str, list[tuple[str, int]]]]:
    result = {
        name: {
            "definitions": [],
            "calls": [],
            "getattr_refs": [],
            "facade_refs": [],
        }
        for name in TARGETS
    }
    for path in _tracked_python_paths():
        if path.resolve() == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in TARGETS:
                    result[node.name]["definitions"].append((str(path), node.lineno))

            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Name):
                callee = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee = node.func.attr
            else:
                callee = None
            if callee in TARGETS:
                result[callee]["calls"].append((str(path), getattr(node, "lineno", 0)))

            if callee == "getattr" and len(node.args) >= 2:
                key = node.args[1]
                if isinstance(key, ast.Constant) and key.value in TARGETS:
                    result[key.value]["getattr_refs"].append(
                        (str(path), getattr(node, "lineno", 0))
                    )

            if callee == "install_fold_designer_bridge_facade":
                for arg in node.args:
                    if not isinstance(arg, ast.Dict):
                        continue
                    for key in arg.keys:
                        if isinstance(key, ast.Constant) and key.value in TARGETS:
                            result[key.value]["facade_refs"].append(
                                (str(path), getattr(key, "lineno", 0))
                            )
    return result


def _bridge_top_level_names() -> set[str]:
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"), filename=str(BRIDGE))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def test_t0_proof_dead_builders_have_no_runtime_or_dynamic_dispatch():
    inventory = _inventory()
    for name in TARGETS:
        assert inventory[name]["calls"] == [], (name, inventory[name]["calls"])
        assert inventory[name]["getattr_refs"] == [], (name, inventory[name]["getattr_refs"])
        assert inventory[name]["facade_refs"] == [], (name, inventory[name]["facade_refs"])


def test_red_zero_caller_historical_builders_are_deleted():
    remaining = sorted(TARGETS & _bridge_top_level_names())
    assert remaining == [], (
        "RED[T1_DEAD_GLUE]: zero-caller historical builders still defined: "
        f"{remaining}"
    )


def test_settings_panel_does_not_gain_duplicate_symmetry_ui():
    source = SETTINGS_PANEL.read_text(encoding="utf-8")
    assert 'text="對稱折彎"' not in source
    assert "_phase6_build_box_symmetry_settings" not in source
    assert "_phase6_build_assembly_settings" not in source
