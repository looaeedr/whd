"""Static GUI -> public Engine Python API call-site index for the existing API Explorer.

Only direct calls to declared public ae_engine entrypoints are indexed. The
call-site scope is a code-path hint, not a runtime/certification assertion.
"""
from __future__ import annotations

import ast
from pathlib import Path

SOURCE_BASE = "https://github.com/looaeedr/whd/blob/localX/"
GUI_TOP_LEVEL = ("gui.py", "fold_designer_bridge.py")


def gui_sources(root: Path) -> list[Path]:
    files = [root / name for name in GUI_TOP_LEVEL]
    files.extend(root.glob("phase6_*.py"))
    files.extend((root / "gui_modules").rglob("*.py"))
    return sorted(path for path in set(files) if path.is_file())


def attach_gui_call_sites(root: Path, rows: list[dict]) -> list[dict]:
    """Attach provable AST Call expressions; never infer runtime availability."""
    by_route = {route: row for row in rows for route in row["entrypoints"]}
    sites: dict[int, set[tuple[str, int, str, str]]] = {
        id(row): set() for row in rows
    }

    for file in gui_sources(root):
        rel = file.relative_to(root).as_posix()
        top = ast.parse(file.read_text(encoding="utf-8-sig"), filename=rel)
        module_aliases: dict[str, str] = {}
        direct_aliases: dict[str, str] = {}
        # Imports can be placed inside GUI callbacks. AST discovery intentionally
        # records lexical calls; it does not claim those callbacks were executed.
        for node in ast.walk(top):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "ae_engine":
                        module_aliases[alias.asname or "ae_engine"] = "ae_engine"
                    elif alias.name in ("ae_engine.manufacturing_api", "ae_engine.integration_api"):
                        if alias.asname:
                            module_aliases[alias.asname] = alias.name
                        else:
                            module_aliases["ae_engine"] = "ae_engine"
            elif isinstance(node, ast.ImportFrom):
                if node.level or node.module not in (
                    "ae_engine", "ae_engine.manufacturing_api", "ae_engine.integration_api"
                ):
                    continue
                for alias in node.names:
                    local = alias.asname or alias.name
                    if node.module == "ae_engine" and alias.name in ("manufacturing_api", "integration_api"):
                        module_aliases[local] = "ae_engine." + alias.name
                    else:
                        direct_aliases[local] = node.module + "." + alias.name

        for node in ast.walk(top):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            route = direct_aliases.get(target.id) if isinstance(target, ast.Name) else None
            if isinstance(target, ast.Attribute):
                chain: list[str] = []
                current = target
                while isinstance(current, ast.Attribute):
                    chain.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    prefix = module_aliases.get(current.id)
                    if prefix:
                        route = prefix + "." + ".".join(reversed(chain))
            row = by_route.get(route)
            if row is None:
                continue
            receiving = "receiving" in rel.casefold() or "receiving" in row["name"].casefold()
            scope = "receiving" if receiving else "shared"
            sites[id(row)].add((rel, node.lineno, scope, route))

    for row in rows:
        row["gui_usage"] = [
            {
                "source": path,
                "line": lineno,
                "scope": scope,
                "via": route,
                "link": SOURCE_BASE + path + "#L" + str(lineno),
            }
            for path, lineno, scope, route in sorted(
                sites[id(row)], key=lambda entry: (entry[0], entry[1], entry[3])
            )
        ]
    return rows
