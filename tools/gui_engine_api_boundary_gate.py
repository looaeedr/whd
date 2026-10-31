"""Executable, fail-closed non-regrowth guard for the GUI -> Engine API seam.

Compares AST violation fingerprints between exact PR base/head. Existing
legacy crossings are not automatically claimed fixed, but may not increase.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys

API_MODULES = frozenset({"ae_engine.contracts", "ae_engine.manufacturing_api"})
ROOT_API_EXPORTS = frozenset({
    "manufacturing_api", "contracts", "generate_part", "resolve_policy",
    "expected_baseline_path_for", "door_finished_face_size",
    "door_indicator_offset_for_finished_center", "indicator_box_opening_feature",
    "indicator_small_door_spec", "ManufacturingPolicy", "ManufacturingContext",
    "DoorPartSpec", "BoxBodyPartSpec", "EndCapPartSpec", "BasePlatePartSpec",
    "IndicatorBoxPartSpec", "CustomFoldPartSpec", "PartSpec", "PartExportResult",
})
DOMAIN_FUNCTION = re.compile(
    r"^_*(?:build|calculate|compute|derive|generate|resolve|construct|make)_"
    r"(?:\w+_)?(?:manufacturing_geometry|unfold(?:ed|ing)?|bend_lines?|cutting|"
    r"relief_(?:geometry|offset)|toolpath|fold_profile)(?:_|$)"
)
FABRICATION_VALUES = {
    "bend_allowance", "unfold_length", "unfolded_length", "cut_length",
    "cutting_length", "relief_compensation", "manufacturing_offset",
}


class BoundaryGateError(RuntimeError):
    pass


def is_gui_path(path: str) -> bool:
    return path in {"gui.py", "fold_designer_bridge.py"} or (
        path.startswith("gui_modules/") and path.endswith(".py")
    ) or (path.startswith("phase6_") and path.endswith(".py"))


def is_engine_path(path: str) -> bool:
    return path.startswith("ae_engine/") and path.endswith(".py")


def _gui_dependency(module: str) -> bool:
    return (
        module in {"gui", "gui_modules", "fold_designer_bridge", "tkinter"}
        or module.startswith(("gui_modules.", "phase6_", "tkinter."))
    )


def violations(source: str, path: str) -> Counter[str]:
    """Count each forbidden ownership site, independent of line-number drift."""
    findings: Counter[str] = Counter()
    gui = is_gui_path(path)
    if not gui and not is_engine_path(path):
        return findings
    try:
        root = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise BoundaryGateError(f"{path}: invalid Python syntax: {exc}") from exc
    for node in ast.walk(root):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if gui:
                    if module == "ezdxf" or module.startswith("ezdxf."):
                        findings["GUI_LOW_LEVEL_DXF_IMPORT:" + module] += 1
                    if module.startswith("ae_engine.") and module not in API_MODULES:
                        findings["GUI_ENGINE_INTERNAL_IMPORT:" + module] += 1
                elif _gui_dependency(module):
                    findings["ENGINE_REVERSE_IMPORT:" + module] += 1
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if gui:
                if module == "ezdxf" or module.startswith("ezdxf."):
                    findings["GUI_LOW_LEVEL_DXF_IMPORT:" + module] += 1
                if module == "ae_engine":
                    for alias in node.names:
                        if alias.name not in ROOT_API_EXPORTS:
                            findings["GUI_ENGINE_INTERNAL_IMPORT:ae_engine." + alias.name] += 1
                elif module.startswith("ae_engine."):
                    if module not in API_MODULES:
                        findings["GUI_ENGINE_INTERNAL_IMPORT:" + module] += 1
                    else:
                        for alias in node.names:
                            if alias.name.startswith("_") or alias.name == "*":
                                findings["GUI_PRIVATE_API_IMPORT:" + module + "." + alias.name] += 1
            elif node.level == 0 and _gui_dependency(module):
                findings["ENGINE_REVERSE_IMPORT:" + module] += 1
        if not gui:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if DOMAIN_FUNCTION.search(node.name):
                findings["GUI_MANUFACTURING_FORMULA_OWNER:" + node.name] += 1
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if (
                (name.startswith("ae.export_") or name.startswith("ae_engine.ae.export_"))
                and ("dxf" in name or "drawing" in name)
            ):
                findings["GUI_DIRECT_LOW_LEVEL_EXPORT:" + name] += 1
            if name.startswith(("manufacturing_api._", "ae_engine.manufacturing_api._")):
                findings["GUI_PRIVATE_API_CALL:" + name] += 1
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv)
        ):
            names = {
                x.id.lower() for x in ast.walk(node) if isinstance(x, ast.Name)
            } | {
                x.attr.lower() for x in ast.walk(node) if isinstance(x, ast.Attribute)
            }
            for key in sorted(names & FABRICATION_VALUES):
                findings["GUI_DERIVES_MANUFACTURING_VALUE:" + key] += 1
    return findings


def added_violations(previous: str, candidate: str, path: str) -> list[str]:
    return sorted((violations(candidate, path) - violations(previous, path)).elements())


def _git(root: Path, *arguments: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True,
        text=True, encoding="utf-8", check=False,
    )
    if proc.returncode != 0:
        raise BoundaryGateError(
            f"git {' '.join(arguments)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def evaluate_pr(root: Path, base: str, head: str) -> list[str]:
    for ref in (base, head):
        if re.fullmatch(r"[0-9a-f]{40}", ref) is None:
            raise BoundaryGateError("exact 40-character commit SHAs required")
        _git(root, "rev-parse", "--verify", ref + "^{commit}")
    diff = _git(root, "diff", "--name-status", "--find-renames", base, head, "--")
    findings: list[str] = []
    for line in diff.splitlines():
        fields = line.split("\t")
        status = fields[0][0] if fields and fields[0] else None
        if status not in {"A", "M", "R", "C", "D"}:
            raise BoundaryGateError(f"unsupported diff record: {line!r}")
        if len(fields) != (3 if status in {"R", "C"} else 2):
            raise BoundaryGateError(f"unexpected diff field count: {line!r}")
        if status == "D":
            continue
        old_path, path = ((fields[1], fields[2]) if status in {"R", "C"}
                          else (fields[1], fields[1]))
        if not (is_gui_path(path) or is_engine_path(path)):
            continue
        previous = (
            "" if status in {"A", "C"} else _git(root, "show", f"{base}:{old_path}")
        )
        candidate = _git(root, "show", f"{head}:{path}")
        for item in added_violations(previous, candidate, path):
            findings.append(f"{path}: {item}")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        findings = evaluate_pr(args.repo, args.base, args.head)
    except (BoundaryGateError, OSError) as exc:
        print(f"GUI_ENGINE_API_BOUNDARY_BLOCKED: {exc}", file=sys.stderr)
        return 2
    if findings:
        print("GUI_ENGINE_API_BOUNDARY_BLOCKED\n" + "\n".join(findings),
              file=sys.stderr)
        return 1
    print(f"GUI_ENGINE_API_BOUNDARY_PASS base={args.base} head={args.head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
