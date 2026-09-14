from __future__ import annotations

import ast
import copy
from pathlib import Path

GUI = Path("gui.py")
MODULE = Path("gui_modules/render_2d.py")
NAMES = (
    "_draw_layout_resolved_features",
    "_draw_layout_baseline_secondary",
    "draw_grid",
)

source = GUI.read_text(encoding="utf-8")
lines = source.splitlines()
tree = ast.parse(source)
host = next(
    node for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
)
methods = {
    node.name: node
    for node in host.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in NAMES
}
if set(methods) != set(NAMES):
    raise SystemExit(f"expected exact pre-move methods {NAMES}, got {sorted(methods)}")


def function_source(node: ast.FunctionDef) -> str:
    # Preserve the original AST (including docstring value) while only removing
    # the class-level decorator. Text dedent can mutate triple-quoted docstrings.
    clone = copy.deepcopy(node)
    clone.decorator_list = []
    ast.fix_missing_locations(clone)
    return ast.unparse(clone).rstrip() + "\n"


module_text = '''"""Stateless 2D Canvas presentation helpers.

This module consumes already-resolved drawing/feature data. It does not own
manufacturing geometry, physical-part identity, visibility, persistence, or
application state.
"""

from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect, ResolvedProfile
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive


'''
module_text += "\n\n".join(function_source(method).rstrip() for method in (methods[name] for name in NAMES)) + "\n"

module_tree = ast.parse(module_text)
module_methods = {
    node.name: node
    for node in module_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in NAMES
}
for name in NAMES:
    before = ast.dump(ast.Module(body=methods[name].body, type_ignores=[]), include_attributes=False)
    after = ast.dump(ast.Module(body=module_methods[name].body, type_ignores=[]), include_attributes=False)
    if before != after:
        raise SystemExit(f"Move-Only body mismatch while constructing module: {name}")

# Insert the one-way gui -> gui_modules import after the existing part_panels import.
import_node = next(
    node for node in tree.body
    if isinstance(node, ast.ImportFrom) and node.module == "gui_modules.part_panels"
)
insert_at = import_node.end_lineno
import_block = [
    "",
    "from gui_modules.render_2d import (",
    "    _draw_layout_resolved_features as _draw_layout_resolved_features_impl,",
    "    _draw_layout_baseline_secondary as _draw_layout_baseline_secondary_impl,",
    "    draw_grid as _draw_grid_impl,",
    ")",
]
new_lines = list(lines)
new_lines[insert_at:insert_at] = import_block
import_delta = len(import_block)

# Account for the import insertion when replacing class methods.
def shifted(line_no: int) -> int:
    return line_no + (import_delta if line_no > insert_at else 0)

replacements = []
for name in NAMES:
    node = methods[name]
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    end = node.end_lineno
    if name == "_draw_layout_resolved_features":
        replacement = ["    _draw_layout_resolved_features = staticmethod(_draw_layout_resolved_features_impl)", ""]
    elif name == "_draw_layout_baseline_secondary":
        replacement = ["    _draw_layout_baseline_secondary = staticmethod(_draw_layout_baseline_secondary_impl)", ""]
    else:
        # Keep the historical bound-method call contract: module function still
        # has its original `self` parameter and remains a normal descriptor.
        replacement = ["    draw_grid = _draw_grid_impl", ""]
    replacements.append((shifted(start) - 1, shifted(end), replacement))

for start, end, replacement in sorted(replacements, reverse=True):
    new_lines[start:end] = replacement

new_source = "\n".join(new_lines).rstrip() + "\n"
new_tree = ast.parse(new_source)
new_host = next(
    node for node in new_tree.body
    if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
)
remaining = {
    node.name
    for node in new_host.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
if set(NAMES) & remaining:
    raise SystemExit(f"moved method bodies still present: {sorted(set(NAMES) & remaining)}")

if "from gui_modules.render_2d import" not in new_source:
    raise SystemExit("render_2d import not inserted")
if "import gui" in module_text or "from gui import" in module_text:
    raise SystemExit("reverse gui dependency detected")

MODULE.write_text(module_text, encoding="utf-8")
GUI.write_text(new_source, encoding="utf-8")
print("T7_RENDER2D_MOVE_APPLIED")
for name in NAMES:
    print(f"MOVED={name}")
