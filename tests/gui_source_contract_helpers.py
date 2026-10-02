from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI_PATH = ROOT / "gui.py"
LIFECYCLE_PATH = ROOT / "gui_modules" / "application" / "lifecycle.py"
COMMAND_ROUTER_PATH = ROOT / "gui_modules" / "application" / "command_router.py"


def _source_tree(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path))


def phase6_host_method_location(name: str) -> tuple[Path, str, ast.FunctionDef]:
    """Return the actual production implementation for a Phase6 host method.

    Phase-2 modularization intentionally moves implementations out of ``gui.py``.
    Source-contract tests must follow the implementation rather than pinning the
    legacy file location.  This helper never supplies production values; it only
    lets tests inspect the current source of truth.
    """
    gui_source, gui_tree = _source_tree(GUI_PATH)
    host = next(
        node
        for node in gui_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    for node in host.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return GUI_PATH, gui_source, node

    if not LIFECYCLE_PATH.is_file():
        raise LookupError(f"Phase6ApplicationHost method not found: {name}")
    lifecycle_source, lifecycle_tree = _source_tree(LIFECYCLE_PATH)
    implementation_name = "phase6_application_host_init" if name == "__init__" else name
    for node in lifecycle_tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == implementation_name:
            return LIFECYCLE_PATH, lifecycle_source, node

    raise LookupError(f"Phase6ApplicationHost method not found: {name}")


def phase6_host_method_source(name: str) -> str:
    _, source, node = phase6_host_method_location(name)
    segment = ast.get_source_segment(source, node)
    assert segment is not None
    return segment


def compile_phase6_host_method(name: str):
    path, _, method = phase6_host_method_location(name)
    standalone = ast.FunctionDef(
        name=name,
        args=method.args,
        body=method.body,
        decorator_list=[],
        returns=method.returns,
        type_comment=method.type_comment,
    )
    ast.fix_missing_locations(standalone)
    namespace: dict[str, object] = {}
    exec(
        compile(ast.Module(body=[standalone], type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace[name]


def application_source_bundle() -> str:
    """Source text for the root GUI plus focused application implementation.

    Use only when an assertion is deliberately about a cross-file application
    invariant (for example, uniqueness of SettingsService construction).
    """
    chunks = [GUI_PATH.read_text(encoding="utf-8")]
    if LIFECYCLE_PATH.is_file():
        chunks.append(LIFECYCLE_PATH.read_text(encoding="utf-8"))
    if COMMAND_ROUTER_PATH.is_file():
        chunks.append(COMMAND_ROUTER_PATH.read_text(encoding="utf-8"))
    return "\n".join(chunks)
