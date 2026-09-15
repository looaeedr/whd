#!/usr/bin/env python3
"""Narrow #289 T1 duplicate guard to symbols actually moved by T1."""
from __future__ import annotations

import ast

import issue289_extract_t1 as base


def direct_host_methods(tree: ast.Module):
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    methods = {}
    for node in host.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in base.ALL_METHODS and node.name in methods:
            raise RuntimeError(f"duplicate T1 host method: {node.name}")
        # Getter/setter pairs outside the T1 move set are legitimate and are
        # intentionally left untouched; only the last AST node is irrelevant
        # because those names are never consumed by the extractor.
        methods[node.name] = node
    return host, methods


base.direct_host_methods = direct_host_methods
base.apply()
