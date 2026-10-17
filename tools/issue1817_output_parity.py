# -*- coding: utf-8 -*-
"""#1817 strict final-sheet and project-file parity acceptance.

This is a verifier, not a geometry implementation or a cache. It serializes
the actual manufacturing scenes through the real DXF writer then independently
reopens them with ezdxf. Volatile DXF handles/header timestamps are excluded,
but every supported cutting, bending and marking entity is compared.
"""
from __future__ import annotations

from pathlib import Path


def _dxf_entities(path):
    import ezdxf
    doc = ezdxf.readfile(path)
    result = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        attrs = (kind, entity.dxf.layer, entity.dxf.get("color", None))
        if kind == "LWPOLYLINE":
            shape = (bool(entity.closed),
                     tuple(tuple(float(v) for v in row)
                           for row in entity.get_points("xyb")))
        elif kind == "LINE":
            shape = ((float(entity.dxf.start.x), float(entity.dxf.start.y)),
                     (float(entity.dxf.end.x), float(entity.dxf.end.y)))
        elif kind == "CIRCLE":
            shape = (float(entity.dxf.center.x), float(entity.dxf.center.y),
                     float(entity.dxf.radius))
        elif kind == "MTEXT":
            shape = (entity.plain_text(),
                     float(entity.dxf.insert.x), float(entity.dxf.insert.y),
                     float(entity.dxf.char_height),
                     int(entity.dxf.attachment_point))
        else:
            raise AssertionError(f"unsupported exported DXF type: {kind}")
        result.append((attrs, shape))
    return tuple(result)


def _sheets(part):
    rendered = part.render_data
    pieces = tuple(getattr(rendered, "pieces", ()) or ())
    if pieces:
        return tuple((str(piece.key), piece.render_data) for piece in pieces)
    return (("whole", rendered),)


def assert_preview_output_parity(selective, forced_full, output_dir, *, label):
    """Compare every physical sheet, world placement and reopened exported DXF."""
    from ae_engine.dxf_serialization import save_scene_dxf

    left = tuple(selective.render_data.assembly_parts)
    right = tuple(forced_full.render_data.assembly_parts)
    if not left or len(left) != len(right):
        raise AssertionError(f"{label}: final manufactured part count mismatch")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    for index, (before, after) in enumerate(zip(left, right)):
        if (before.part_key, before.placement, before.offset,
            before.x_profile, before.y_profile) != (
                after.part_key, after.placement, after.offset,
                after.x_profile, after.y_profile):
            raise AssertionError(f"{label}: part identity/3D/world profile mismatch: {index}")
        before_sheets, after_sheets = _sheets(before), _sheets(after)
        if len(before_sheets) != len(after_sheets):
            raise AssertionError(f"{label}: physical sheet count differs: {before.part_key}")
        for sheet_index, ((a_key, a), (b_key, b)) in enumerate(
                zip(before_sheets, after_sheets)):
            identity = f"{label}/{before.part_key}/{a_key}"
            if a_key != b_key:
                raise AssertionError(f"{identity}: physical piece name differs")
            if a.material is None or b.material is None:
                raise AssertionError(f"{identity}: sheet material missing")
            if not a.material.equals(b.material):
                raise AssertionError(f"{identity}: final 2D material differs")
            if a.scene is None or b.scene is None:
                raise AssertionError(f"{identity}: physical DrawingScene missing")
            if (tuple(a.scene.primitives) != tuple(b.scene.primitives)
                    or tuple(a.fold_guides) != tuple(b.fold_guides)
                    or a.unfolded_topology != b.unfolded_topology
                    or a.metadata != b.metadata):
                raise AssertionError(f"{identity}: cutting/bending/marking/topology/metadata differs")
            first = directory / f"{index}-{sheet_index}-selective.dxf"
            second = directory / f"{index}-{sheet_index}-forced.dxf"
            save_scene_dxf(first, a.scene)
            save_scene_dxf(second, b.scene)
            encoded_a, encoded_b = _dxf_entities(first), _dxf_entities(second)
            if not encoded_a or len(encoded_a) != len(a.scene.primitives):
                raise AssertionError(f"{identity}: DXF export missing/duplicate entities")
            if encoded_a != encoded_b:
                raise AssertionError(f"{identity}: independently reloaded DXF entity differs")
            count += 1
    return count


def save_reload_receiving_authority(snapshot, output_dir):
    """Real .p6fold write/read, not JSON deepcopy or cached final geometry."""
    from ae_engine.receiving_layout import normalize_receiving_layout
    from phase6_project_file import (
        PROJECT_SCHEMA_V1, read_project, write_project,
    )

    if "receiving_layout" not in snapshot:
        raise AssertionError("committed Receiving project has no layout authority")
    path = Path(output_dir) / "issue1817-manufacturing-parity.p6fold"
    payload = {
        "schema": PROJECT_SCHEMA_V1,
        "saved_at": "2026-10-17T00:00:00+08:00",
        "snapshot": dict(snapshot),
        "final_geometry": {},
    }
    write_project(path, payload)
    recovered = read_project(path)
    if recovered["final_geometry"]:
        raise AssertionError("project reload improperly reuses derived geometry")
    before = normalize_receiving_layout(snapshot["receiving_layout"])
    after = normalize_receiving_layout(recovered["snapshot"]["receiving_layout"])
    if before != after:
        raise AssertionError("saved/reloaded canonical Receiving Bay/Joint authority changed")
    return recovered["snapshot"]
