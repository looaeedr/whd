#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


HELPERS = (
    "_configure_3d_only_figure",
    "_scale_current_3d_limits",
)


def _hash(node: ast.AST) -> str:
    normalized = ast.dump(
        node,
        annotate_fields=True,
        include_attributes=False,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--class-name", required=True)
    args = ap.parse_args()

    path = Path(args.source)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == args.class_name
    )
    methods = {
        node.name: _hash(node)
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    top = {
        node.name: _hash(node)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in HELPERS
    }
    missing = sorted(set(HELPERS) - set(top))
    if missing:
        raise SystemExit(f"missing renderer helpers: {missing}")

    payload = {
        "source": str(path),
        "class_name": args.class_name,
        "method_count": len(methods),
        "method_hashes": methods,
        "helper_hashes": top,
    }
    payload["aggregate"] = hashlib.sha256(
        json.dumps(
            {
                "methods": methods,
                "helpers": top,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
