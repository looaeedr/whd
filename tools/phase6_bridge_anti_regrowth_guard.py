from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Iterable, Mapping


BRIDGE_PATH = "fold_designer_bridge.py"


class GuardError(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GuardError(f"expected JSON object: {path}")
    return payload


def _run_git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GuardError(
            f"git {' '.join(args)} failed rc={proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout


def _git_show(root: Path, head: str, path: str) -> str:
    return _run_git(root, "show", f"{head}:{path}")


def _git_paths_at(root: Path, head: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in _run_git(root, "ls-tree", "-r", "--name-only", head).splitlines()
        if line.strip()
    )


def _current_tracked_paths(root: Path) -> tuple[str, ...]:
    raw = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
    return tuple(
        chunk.decode("utf-8", "surrogateescape")
        for chunk in raw.split(b"\0")
        if chunk
    )


def top_level_function_spans(source: str) -> dict[str, int]:
    tree = ast.parse(source)
    return {
        node.name: int(node.end_lineno) - int(node.lineno) + 1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def top_level_alias_names(source: str) -> set[str]:
    tree = ast.parse(source)
    aliases: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, (ast.Name, ast.Attribute)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                aliases.add(target.id)
    return aliases


def facade_binding_count(source: str) -> int:
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id == "install_fold_designer_bridge_facade"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "install_fold_designer_bridge_facade"
        )
    ]
    if len(calls) != 1:
        raise GuardError(f"expected exactly one facade install call, got {len(calls)}")
    dict_args = [arg for arg in calls[0].args if isinstance(arg, ast.Dict)]
    if len(dict_args) != 1:
        raise GuardError("facade binding dict not found")
    return len(dict_args[0].keys)


def imports_bridge(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "fold_designer_bridge"
                or alias.name.startswith("fold_designer_bridge.")
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "fold_designer_bridge" or node.module.startswith(
                "fold_designer_bridge."
            ):
                return True
    return False


def _iter_functions(
    tree: ast.AST, prefix: str = ""
) -> Iterable[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for node in getattr(tree, "body", ()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{prefix}{node.name}"
            yield name, node
        elif isinstance(node, ast.ClassDef):
            yield from _iter_functions(node, f"{prefix}{node.name}.")


def full_app_interfaces(source: str, param_names: Iterable[str]) -> set[str]:
    risky = set(str(x) for x in param_names)
    tree = ast.parse(source)
    out: set[str] = set()
    for qualname, node in _iter_functions(tree):
        args = [
            arg.arg
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        ]
        filtered = [arg for arg in args if arg not in {"self", "cls"}]
        if risky.intersection(filtered):
            out.add(f"{qualname}({','.join(filtered)})")
    return out


def composition_root_locations(
    sources: Mapping[str, str], class_name: str
) -> tuple[str, ...]:
    found: list[str] = []
    for path, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        if any(
            isinstance(node, ast.ClassDef) and node.name == class_name
            for node in tree.body
        ):
            found.append(path)
    return tuple(sorted(found))


def _valid_allowlist_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    return all(
        isinstance(entry.get(key), str) and bool(str(entry[key]).strip())
        for key in ("owner_rationale", "follow_up_removal_plan", "approved_issue")
    )


def bridge_growth_violations(
    baseline_source: str,
    current_source: str,
    *,
    threshold: int,
    allowlist: Mapping[str, object],
) -> list[dict]:
    baseline = top_level_function_spans(baseline_source)
    current = top_level_function_spans(current_source)
    violations: list[dict] = []
    for name, span in sorted(current.items()):
        growth = span - baseline.get(name, 0)
        if growth <= threshold:
            continue
        if _valid_allowlist_entry(allowlist.get(name)):
            continue
        violations.append(
            {
                "code": "LARGE_TOP_LEVEL_BODY_REVIEW_REQUIRED",
                "symbol": name,
                "baseline_span": baseline.get(name, 0),
                "current_span": span,
                "net_new_lines": growth,
                "threshold": threshold,
            }
        )
    return violations


def alias_redefinition_violations(
    baseline_source: str, current_source: str
) -> list[dict]:
    aliases = top_level_alias_names(baseline_source)
    current_defs = set(top_level_function_spans(current_source))
    return [
        {"code": "EXTRACTED_ALIAS_REDEFINED_IN_BRIDGE", "symbol": name}
        for name in sorted(aliases & current_defs)
    ]


def _matches_owner_scope(path: str, globs: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in globs)


def _is_production_python(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    blocked = ("tests/", "BACKUP/", ".agents/", "tools/")
    return not path.startswith(blocked)


def _load_authority(baseline_path: Path, c0_path: Path) -> dict:
    baseline = _read_json(baseline_path)
    c0 = _read_json(c0_path)
    gate = c0.get("quantitative_gate")
    if not isinstance(gate, dict):
        raise GuardError("C0 record missing quantitative_gate")
    accepted_final_loc = int(gate["final_bridge_loc"])
    accepted_facade_count = int(gate["facade_count"])
    effective_final_ceiling = int(gate["effective_final_ceiling"])
    loc_buffer = int(baseline["loc_buffer"])
    accepted_source_head = str(c0["tested_head"])
    return {
        "baseline": baseline,
        "c0": c0,
        "accepted_final_loc": accepted_final_loc,
        "accepted_facade_count": accepted_facade_count,
        "effective_final_ceiling": effective_final_ceiling,
        "loc_buffer": loc_buffer,
        "bridge_loc_limit": min(
            accepted_final_loc + loc_buffer, effective_final_ceiling
        ),
        "accepted_source_head": accepted_source_head,
    }


def evaluate_repository(root: Path, baseline_path: Path, c0_path: Path) -> dict:
    root = root.resolve()
    authority = _load_authority(baseline_path.resolve(), c0_path.resolve())
    baseline = authority["baseline"]
    accepted_head = authority["accepted_source_head"]

    current_bridge = (root / BRIDGE_PATH).read_text(encoding="utf-8")
    accepted_bridge = _git_show(root, accepted_head, BRIDGE_PATH)
    current_bridge_loc = current_bridge.count("\n")
    current_facade_count = facade_binding_count(current_bridge)

    violations: list[dict] = []
    if current_bridge_loc > authority["bridge_loc_limit"]:
        violations.append(
            {
                "code": "BRIDGE_LOC_BUDGET_EXCEEDED",
                "current": current_bridge_loc,
                "limit": authority["bridge_loc_limit"],
            }
        )
    if current_facade_count > authority["accepted_facade_count"]:
        violations.append(
            {
                "code": "FACADE_GROWTH",
                "current": current_facade_count,
                "accepted": authority["accepted_facade_count"],
            }
        )

    violations.extend(
        bridge_growth_violations(
            accepted_bridge,
            current_bridge,
            threshold=int(baseline["large_body_net_new_review_threshold"]),
            allowlist=baseline.get("large_body_allowlist", {}),
        )
    )
    violations.extend(alias_redefinition_violations(accepted_bridge, current_bridge))

    current_paths = _current_tracked_paths(root)
    accepted_paths = set(_git_paths_at(root, accepted_head))
    owner_globs = tuple(str(x) for x in baseline["owner_scope_globs"])
    owner_paths = sorted(
        path
        for path in current_paths
        if _matches_owner_scope(path, owner_globs) and path.endswith(".py")
    )

    reverse_imports = []
    for path in owner_paths:
        source = (root / path).read_text(encoding="utf-8")
        if imports_bridge(source):
            reverse_imports.append(path)
    for path in reverse_imports:
        violations.append({"code": "OWNER_REVERSE_IMPORTS_BRIDGE", "path": path})

    risky_params = tuple(str(x) for x in baseline["full_app_param_names"])
    full_app_allowlist = baseline.get("full_app_interface_allowlist", {})
    new_full_app: list[dict] = []
    for path in owner_paths:
        current_source = (root / path).read_text(encoding="utf-8")
        current_interfaces = full_app_interfaces(current_source, risky_params)
        baseline_interfaces: set[str] = set()
        if path in accepted_paths:
            baseline_interfaces = full_app_interfaces(
                _git_show(root, accepted_head, path), risky_params
            )
        for signature in sorted(current_interfaces - baseline_interfaces):
            key = f"{path}::{signature}"
            if _valid_allowlist_entry(full_app_allowlist.get(key)):
                continue
            row = {
                "code": "NEW_FULL_APP_OWNER_INTERFACE",
                "path": path,
                "signature": signature,
            }
            violations.append(row)
            new_full_app.append(row)

    production_sources = {
        path: (root / path).read_text(encoding="utf-8")
        for path in current_paths
        if _is_production_python(path)
    }
    expected_root = baseline["composition_root"]
    root_locations = composition_root_locations(
        production_sources, str(expected_root["class"])
    )
    expected_path = str(expected_root["path"])
    if root_locations != (expected_path,):
        violations.append(
            {
                "code": "SECOND_OR_MISSING_COMPOSITION_ROOT",
                "expected": expected_path,
                "found": list(root_locations),
            }
        )
    for forbidden in baseline.get("forbidden_composition_root_paths", []):
        if str(forbidden) in current_paths:
            violations.append(
                {
                    "code": "FORBIDDEN_COMPOSITION_ROOT_PATH",
                    "path": str(forbidden),
                }
            )

    return {
        "schema": "WHD_PHASE6_BRIDGE_ANTI_REGROWTH_RESULT_V1",
        "accepted_source_head": accepted_head,
        "accepted_final_loc": authority["accepted_final_loc"],
        "effective_final_ceiling": authority["effective_final_ceiling"],
        "loc_buffer": authority["loc_buffer"],
        "bridge_loc_limit": authority["bridge_loc_limit"],
        "current_bridge_loc": current_bridge_loc,
        "accepted_facade_count": authority["accepted_facade_count"],
        "current_facade_count": current_facade_count,
        "large_body_threshold": int(
            baseline["large_body_net_new_review_threshold"]
        ),
        "owner_scope_count": len(owner_paths),
        "reverse_import_count": len(reverse_imports),
        "composition_root_locations": list(root_locations),
        "new_full_app_interface_count": len(new_full_app),
        "violations": violations,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 6 Bridge permanent anti-regrowth guard"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--c0-record", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        payload = evaluate_repository(args.root, args.baseline, args.c0_record)
    except (OSError, KeyError, ValueError, SyntaxError, GuardError) as exc:
        print(f"PHASE6_BRIDGE_ANTI_REGROWTH_ERROR: {exc}")
        return 3

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"BRIDGE_LOC={payload['current_bridge_loc']}")
    print(f"BRIDGE_LOC_LIMIT={payload['bridge_loc_limit']}")
    print(f"FACADE_COUNT={payload['current_facade_count']}")
    print(f"FACADE_COUNT_LIMIT={payload['accepted_facade_count']}")
    print(f"REVERSE_IMPORT_COUNT={payload['reverse_import_count']}")
    print(
        f"NEW_FULL_APP_INTERFACE_COUNT={payload['new_full_app_interface_count']}"
    )
    if payload["violations"]:
        for violation in payload["violations"]:
            print(
                "ANTI_REGROWTH_VIOLATION="
                + json.dumps(violation, ensure_ascii=False, sort_keys=True)
            )
        print("PHASE6_BRIDGE_ANTI_REGROWTH_RED")
        return 2
    print("PHASE6_BRIDGE_ANTI_REGROWTH_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
