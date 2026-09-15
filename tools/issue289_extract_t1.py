#!/usr/bin/env python3
"""Issue #289 T1 move-only extraction for application lifecycle/command routing.

Temporary branch-only transformer.  It copies exact method/class bodies out of
``gui.py`` and replaces them with explicit delegation aliases.  It never imports
or executes gui.py.
"""
from __future__ import annotations

import ast
import builtins
import textwrap
from pathlib import Path

GUI = Path("gui.py")
APP_DIR = Path("gui_modules/application")
APP_DIR.mkdir(parents=True, exist_ok=True)

LIFECYCLE_METHODS = (
    "__init__",
    "_current_cabinet_type_name",
    "_apply_manual_corner_snapshot",
    "_apply_fold_designer_live_settings",
    "_save_fold_designer_defaults",
    "_apply_fold_designer_live_corner_state",
    "_notify_fold_designer_corner_state",
    "_fold_designer_number_text",
    "_apply_existing_parts_from_fold_workspace",
    "_apply_phase6_project_snapshot",
    "_compose_phase6_project_snapshot_from_main_gui",
    "_capture_phase6_committed_snapshot",
    "_apply_original_fold_designer_snapshot",
    "_store_fold_designer_workspace",
    "_apply_fold_designer_live_snapshot",
    "_apply_fold_designer_corner_transaction",
    "_reload_current_baseline_features",
    "open_original_fold_designer",
)
COMMAND_METHODS = (
    "_request_phase6_update",
    "_flush_phase6_authoritative_state",
    "bind_live_updates",
)
ALL_METHODS = LIFECYCLE_METHODS + COMMAND_METHODS
STATIC_METHODS = {"_fold_designer_number_text"}


def parse(text: str) -> ast.Module:
    return ast.parse(text, filename=str(GUI))


def source_lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def node_bounds(node: ast.AST) -> tuple[int, int]:
    start = int(node.lineno)
    decorators = getattr(node, "decorator_list", ())
    if decorators:
        start = min(start, *(int(d.lineno) for d in decorators))
    return start, int(node.end_lineno)


def exact_segment(lines: list[str], node: ast.AST) -> str:
    start, end = node_bounds(node)
    return "".join(lines[start - 1:end])


def dedented_function(lines: list[str], node: ast.FunctionDef) -> str:
    # Start at ``def`` rather than decorators.  Class-level @staticmethod must
    # become an ordinary module function and is re-applied at the alias seam.
    raw = "".join(lines[node.lineno - 1:int(node.end_lineno)])
    return textwrap.dedent(raw).rstrip() + "\n"


def imported_preamble(tree: ast.Module, lines: list[str]) -> str:
    chunks: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            chunks.append(exact_segment(lines, node).rstrip())
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "PHASE6_BUILD_ID" in targets:
                chunks.append(exact_segment(lines, node).rstrip())
    # Application modules must never back-import gui.  The source preamble has
    # no such import, and this assertion protects future reruns.
    text = "\n".join(chunks)
    if "import gui" in text or "from gui import" in text:
        raise RuntimeError("forbidden gui back-import in generated preamble")
    return text + "\n"


def direct_host_methods(tree: ast.Module) -> tuple[ast.ClassDef, dict[str, ast.FunctionDef]]:
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    methods: dict[str, ast.FunctionDef] = {}
    for node in host.body:
        if isinstance(node, ast.FunctionDef):
            if node.name in methods:
                raise RuntimeError(f"duplicate direct host method: {node.name}")
            methods[node.name] = node
    return host, methods


def make_lifecycle_module(preamble: str, lines: list[str], methods: dict[str, ast.FunctionDef]) -> str:
    pieces = [
        '"""Application/session lifecycle seams extracted from the legacy GUI host.\n\n'
        'Authoritative settings, workspace, project and manufacturing ownership remains\n'
        'with the existing services/controllers/engine.  This module only coordinates them.\n'
        '"""\n',
        preamble,
        "from gui_modules.application.command_router import _Phase6UpdateScheduler\n\n",
    ]
    for name in LIFECYCLE_METHODS:
        fn = dedented_function(lines, methods[name])
        if name == "__init__":
            fn = fn.replace("def __init__(", "def phase6_application_host_init(", 1)
        # These two bodies intentionally named the old class to pin the base
        # implementation.  After the move the exact implementation lives here,
        # so call the moved function directly instead of importing gui.
        fn = fn.replace(
            "Phase6ApplicationHost._current_cabinet_type_name(self)",
            "_current_cabinet_type_name(self)",
        )
        pieces.append(fn + "\n")
    return "".join(pieces)


def make_command_module(lines: list[str], tree: ast.Module, methods: dict[str, ast.FunctionDef]) -> str:
    scheduler = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_Phase6UpdateScheduler"
    )
    pieces = [
        '"""Application update routing extracted from gui.py.\n\n'
        'This module owns scheduling/routing only; calculation/state authority remains on\n'
        'the application owner and its existing controllers/services.\n'
        '"""\n\n',
        textwrap.dedent(exact_segment(lines, scheduler)).rstrip() + "\n\n",
    ]
    for name in COMMAND_METHODS:
        pieces.append(dedented_function(lines, methods[name]) + "\n")
    return "".join(pieces)


def alias_block() -> str:
    rows = [
        "    # #289/T1 application lifecycle delegation; implementations live in focused modules.\n",
        "    __init__ = _phase6_lifecycle.phase6_application_host_init\n",
    ]
    for name in LIFECYCLE_METHODS:
        if name == "__init__":
            continue
        rhs = f"_phase6_lifecycle.{name}"
        if name in STATIC_METHODS:
            rhs = f"staticmethod({rhs})"
        rows.append(f"    {name} = {rhs}\n")
    for name in COMMAND_METHODS:
        rows.append(f"    {name} = _phase6_command_router.{name}\n")
    rows.append("\n")
    return "".join(rows)


def apply() -> None:
    text = GUI.read_text(encoding="utf-8")
    tree = parse(text)
    lines = source_lines(text)
    host, methods = direct_host_methods(tree)
    inline = set(methods).intersection(ALL_METHODS)
    scheduler_nodes = [
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "_Phase6UpdateScheduler"
    ]

    if not inline and not scheduler_nodes:
        # Idempotent generated-commit rerun.
        if len(text.splitlines()) > 9000:
            raise RuntimeError("T1 already extracted but gui.py line gate is RED")
        print("T1 extraction already applied")
        return

    missing = set(ALL_METHODS) - set(methods)
    if missing:
        raise RuntimeError(f"missing expected host methods before extraction: {sorted(missing)}")
    if len(scheduler_nodes) != 1:
        raise RuntimeError(f"expected exactly one scheduler class, found {len(scheduler_nodes)}")

    preamble = imported_preamble(tree, lines)
    lifecycle = make_lifecycle_module(preamble, lines, methods)
    command = make_command_module(lines, tree, methods)

    # Fail closed on module size before touching gui.py.
    if len(lifecycle.splitlines()) > 1500:
        raise RuntimeError(f"lifecycle.py exceeds 1500 lines: {len(lifecycle.splitlines())}")
    if len(command.splitlines()) > 1500:
        raise RuntimeError(f"command_router.py exceeds 1500 lines: {len(command.splitlines())}")

    removals: list[tuple[int, int]] = []
    for name in ALL_METHODS:
        removals.append(node_bounds(methods[name]))
    removals.append(node_bounds(scheduler_nodes[0]))

    # Remove from bottom to top so original line coordinates remain valid.
    edited = list(lines)
    for start, end in sorted(removals, reverse=True):
        del edited[start - 1:end]
    reduced = "".join(edited)

    # Insert one-way application-module imports after the last top-level import.
    reduced_tree = parse(reduced)
    reduced_lines = source_lines(reduced)
    last_import_end = max(
        int(n.end_lineno) for n in reduced_tree.body
        if isinstance(n, (ast.Import, ast.ImportFrom))
    )
    import_block = (
        "\nfrom gui_modules.application import lifecycle as _phase6_lifecycle\n"
        "from gui_modules.application import command_router as _phase6_command_router\n"
        "_Phase6UpdateScheduler = _phase6_command_router._Phase6UpdateScheduler\n"
    )
    reduced_lines.insert(last_import_end, import_block)
    reduced = "".join(reduced_lines)

    # Insert explicit delegation aliases as the first class-body responsibility.
    reduced_tree = parse(reduced)
    reduced_lines = source_lines(reduced)
    reduced_host = next(
        n for n in reduced_tree.body
        if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost"
    )
    reduced_lines.insert(int(reduced_host.lineno), alias_block())
    reduced = "".join(reduced_lines)

    # Structural fail-closed checks.
    final_tree = parse(reduced)
    final_host, final_methods = direct_host_methods(final_tree)
    remaining = set(final_methods).intersection(ALL_METHODS)
    if remaining:
        raise RuntimeError(f"moved methods still directly defined: {sorted(remaining)}")
    if any(isinstance(n, ast.ClassDef) and n.name == "_Phase6UpdateScheduler" for n in final_tree.body):
        raise RuntimeError("scheduler still defined inline")
    final_loc = len(reduced.splitlines())
    if final_loc > 9000:
        raise RuntimeError(f"T1 line gate RED: gui.py={final_loc} > 9000")

    APP_DIR.joinpath("__init__.py").write_text(
        '"""Focused application orchestration modules for the WHD GUI."""\n',
        encoding="utf-8",
    )
    APP_DIR.joinpath("lifecycle.py").write_text(lifecycle, encoding="utf-8")
    APP_DIR.joinpath("command_router.py").write_text(command, encoding="utf-8")
    GUI.write_text(reduced, encoding="utf-8")

    print(f"T1_GUI_LOC={final_loc}")
    print(f"T1_LIFECYCLE_LOC={len(lifecycle.splitlines())}")
    print(f"T1_COMMAND_ROUTER_LOC={len(command.splitlines())}")
    print(f"T1_MOVED_METHODS={len(ALL_METHODS)}")


if __name__ == "__main__":
    apply()
