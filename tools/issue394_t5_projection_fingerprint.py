#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


NAMES = (
    "_phase6_profile_base_index",
    "_phase6_profile_geometry",
    "_phase6_fold_mask_for_cross_coordinate",
    "_phase6_profile_map_with_guides",
    "_phase6_profile_map",
    "_phase6_profile_flat_map",
    "_phase6_folded_mesh_from_polygon",
    "_phase6_mesh_feature_segments",
    "_phase6_fitted_limits_from_vertices",
    "_phase6_scene_fold_boundaries",
    "_phase6_profile_to_scene_boundaries",
    "_phase6_fold_ownership_exemptions",
    "_default_number_text",
    "_phase6_folded_outside_envelope",
    "_phase6_profile_operator_fold_values",
    "_phase6_contract_profile_rows",
    "_phase6_box_body_piece_world_mapper",
    "_phase6_box_body_piece_dimension_lines",
    "_phase6_box_body_structure_meshes",
    "format_operator_info_text",
    "_phase6_triangle_bounds",
    "_phase6_place_assembly_triangles",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    args = ap.parse_args()
    path = Path(args.source)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(NAMES) - set(defs))
    if missing:
        raise SystemExit(f"missing projection definitions: {missing}")

    hashes = {}
    for name in NAMES:
        normalized = ast.dump(
            defs[name],
            annotate_fields=True,
            include_attributes=False,
        )
        hashes[name] = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    payload = {
        "source": str(path),
        "count": len(hashes),
        "hashes": hashes,
        "aggregate": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
