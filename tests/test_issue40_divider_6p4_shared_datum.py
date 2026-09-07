# -*- coding: utf-8 -*-
from __future__ import annotations

from math import hypot
from pathlib import Path
import shutil

import ezdxf
import pytest
from shapely.geometry import Polygon

from ae_engine.contracts import ManufacturingContext
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.manufacturing_api import build_box_body_divider_render_data
from ae_engine.assembly_placement import resolve_divider_placement
from ae_engine.sheetmetal_drawing import CirclePrimitive
from phase6_final_scene_view import AssemblyScenePart
from tests.test_issue39_divider_relief import _snapshot, _body_part
import fold_designer_bridge as bridge


def _six4(render):
    return [
        p for p in render.scene.primitives
        if isinstance(p, CirclePrimitive)
        and abs(float(p.radius) - 3.2) <= 1e-6
    ]


def _divider_anchor_group(render):
    holes = _six4(render)
    assert len(holes) == 3
    # A is the hole nearest the post-relief outer side; B/C are ordered by
    # distance from A. This is geometry-role identification, not source handle.
    a = min(holes, key=lambda p: float(p.center.x))
    rest = sorted(
        (p for p in holes if p is not a),
        key=lambda p: hypot(float(p.center.x-a.center.x), float(p.center.y-a.center.y)),
    )
    return a, rest[0], rest[1]


def _divider_post_relief_center_frame(material):
    minx, _miny, _maxx, _maxy = map(float, material.bounds)
    coords = list(material.exterior.coords)
    candidates = []
    for p, q in zip(coords, coords[1:]):
        if abs(float(p[0])-minx) <= 1e-5 and abs(float(q[0])-minx) <= 1e-5:
            length = abs(float(q[1])-float(p[1]))
            if length > 1e-6:
                candidates.append((length, p, q))
    assert candidates
    _length, p, q = max(candidates, key=lambda row: row[0])
    y0, y1 = sorted((float(p[1]), float(q[1])))
    center = (minx, (y0+y1)/2.0)
    # Canonical Divider post-relief span runs toward +Y; material is inward +X.
    return center, (0.0, 1.0), (1.0, 0.0)


def _endcap_mother_rule(path: Path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    outlines = list(msp.query('LWPOLYLINE[layer=="CUTTING"]'))
    assert outlines
    outer = max(
        outlines,
        key=lambda e: abs(Polygon([(float(x), float(y)) for x, y, *_ in e.get_points()]).area),
    )
    pts = [(float(x), float(y)) for x, y, *_ in outer.get_points()]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    poly = Polygon(pts)
    circles = [
        e for e in msp.query("CIRCLE")
        if abs(float(e.dxf.radius)-3.2) <= 1e-6
    ]
    assert len(circles) == 2
    hc = [(float(e.dxf.center.x), float(e.dxf.center.y), e) for e in circles]
    hv = (hc[1][0]-hc[0][0], hc[1][1]-hc[0][1])
    hlen = hypot(*hv)
    hu = (hv[0]/hlen, hv[1]/hlen)

    candidates = []
    for p, q in zip(pts, pts[1:]):
        vx, vy = q[0]-p[0], q[1]-p[1]
        length = hypot(vx, vy)
        if length <= 1e-9:
            continue
        tu = (vx/length, vy/length)
        if abs(tu[0]*hu[0] + tu[1]*hu[1]) < 0.999:
            continue
        center = ((p[0]+q[0])/2.0, (p[1]+q[1])/2.0)
        # Both holes must project inside this finite straight segment.
        projections = [
            (h[0]-center[0])*tu[0] + (h[1]-center[1])*tu[1]
            for h in hc
        ]
        if max(abs(v) for v in projections) > length/2.0 + 1e-6:
            continue
        distances = [
            abs((h[0]-center[0])*(-tu[1]) + (h[1]-center[1])*tu[0])
            for h in hc
        ]
        candidates.append((sum(distances)/len(distances), center, tu, length))
    assert candidates
    _dist, center, tu, _length = min(candidates, key=lambda row: row[0])

    # Orient tangent canonically from lexicographically smaller endpoint toward larger.
    if tu[0] < -1e-9 or (abs(tu[0]) <= 1e-9 and tu[1] < 0):
        tu = (-tu[0], -tu[1])

    centroid = (float(poly.centroid.x), float(poly.centroid.y))
    n1 = (-tu[1], tu[0])
    if (centroid[0]-center[0])*n1[0] + (centroid[1]-center[1])*n1[1] < 0:
        inward = (-n1[0], -n1[1])
    else:
        inward = n1

    ranked = []
    for x, y, entity in hc:
        axial = (x-center[0])*tu[0] + (y-center[1])*tu[1]
        inward_offset = (x-center[0])*inward[0] + (y-center[1])*inward[1]
        ranked.append((axial, inward_offset, entity))
    axial, inward_offset, entity = max(ranked, key=lambda row: row[0])
    return {
        "center": center,
        "axial": axial,
        "inward": inward_offset,
        "handle": str(entity.dxf.handle),
        "tangent": tu,
        "inward_unit": inward,
    }


def _divider_part_with_context(snapshot, context=None):
    divider = derive_box_body_dividers(
        tuple(
            (float(w), tuple(float(h) for h in hs))
            for w, hs in snapshot["door_layout_columns"]
        ),
        depth=snapshot["d"],
        thickness=snapshot["t"],
        layout_scope=snapshot["door_layout_scope"],
        handle_edges={},
        model_name="受電箱",
    )[0]
    render = build_box_body_divider_render_data(
        divider,
        context=context or ManufacturingContext(),
    )
    placement = resolve_divider_placement(snapshot, divider.stable_id)
    profiles = {
        "X": [
            {
                "len": float(row.length),
                **({"angle": float(row.angle)} if row.angle is not None else {}),
                **({"core": str(row.core)} if row.core else {}),
                **({"phase6_key": str(row.phase6_key)} if row.phase6_key else {}),
            }
            for row in divider.fold_profile
        ],
        "Y": [{"len": float(divider.span)}],
    }
    return divider, AssemblyScenePart(
        part_key=divider.stable_id,
        render_data=render,
        x_profile=tuple(profiles["X"]),
        y_profile=tuple(profiles["Y"]),
        placement=placement.placement_kind,
        offset=placement.world_offset,
    )


def _solved(context=None):
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part_with_context(snap, context=context)
    solved_parts, diagnostics, joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    render = next(p.render_data for p in solved_parts if p.part_key == divider.stable_id)
    assert diagnostics[0].illegal_penetration is False
    return divider, render


def test_t4_red_divider_A_does_not_yet_follow_endcap_post_relief_center_datum():
    _divider, render = _solved()
    a, b, c = _divider_anchor_group(render)
    center, tangent, inward = _divider_post_relief_center_frame(render.material)
    mother = _endcap_mother_rule(Path("基準檔/金庫型/封頭尾.dxf"))
    expected = (
        center[0] + mother["axial"]*tangent[0] + mother["inward"]*inward[0],
        center[1] + mother["axial"]*tangent[1] + mother["inward"]*inward[1],
    )
    actual = (float(a.center.x), float(a.center.y))
    print("mother_rule=", mother)
    print("divider_A_actual=", actual, "expected=", expected)
    assert actual == pytest.approx(expected, abs=1e-6)


def test_t4_red_editing_endcap_mother_moves_divider_ABC_rigidly(tmp_path):
    root = tmp_path
    folder = root / "基準檔" / "金庫型"
    folder.mkdir(parents=True)
    for name in ("封頭尾.dxf", "中隔.dxf"):
        shutil.copy2(Path("基準檔/金庫型")/name, folder/name)

    ctx = ManufacturingContext(resource_root=root)
    _divider, before = _solved(context=ctx)
    a0, b0, c0 = _divider_anchor_group(before)

    mother_path = folder / "封頭尾.dxf"
    rule = _endcap_mother_rule(mother_path)
    doc = ezdxf.readfile(mother_path)
    entity = doc.entitydb[rule["handle"]]
    entity.dxf.center = (
        float(entity.dxf.center.x) + float(rule["tangent"][0]),
        float(entity.dxf.center.y) + float(rule["tangent"][1]),
        float(entity.dxf.center.z),
    )
    doc.saveas(mother_path)

    _divider, after = _solved(context=ctx)
    a1, b1, c1 = _divider_anchor_group(after)

    delta = (float(a1.center.x-a0.center.x), float(a1.center.y-a0.center.y))
    print("ABC_delta=", delta)
    assert delta == pytest.approx((0.0, 1.0), abs=1e-6)
    assert (float(b1.center.x-b0.center.x), float(b1.center.y-b0.center.y)) == pytest.approx(delta)
    assert (float(c1.center.x-c0.center.x), float(c1.center.y-c0.center.y)) == pytest.approx(delta)

    # Divider-owned relative vectors must not change.
    assert (float(b1.center.x-a1.center.x), float(b1.center.y-a1.center.y)) == pytest.approx(
        (float(b0.center.x-a0.center.x), float(b0.center.y-a0.center.y))
    )
    assert (float(c1.center.x-a1.center.x), float(c1.center.y-a1.center.y)) == pytest.approx(
        (float(c0.center.x-a0.center.x), float(c0.center.y-a0.center.y))
    )



def _five3(render):
    return sorted(
        (
            round(float(p.center.x), 6),
            round(float(p.center.y), 6),
            round(float(p.radius), 6),
        )
        for p in render.scene.primitives
        if isinstance(p, CirclePrimitive)
        and abs(float(p.radius) - 2.65) <= 1e-6
    )


def test_t4_editing_endcap_mother_inward_moves_divider_ABC_inward_only(tmp_path):
    root = tmp_path
    folder = root / "基準檔" / "金庫型"
    folder.mkdir(parents=True)
    for name in ("封頭尾.dxf", "中隔.dxf"):
        shutil.copy2(Path("基準檔/金庫型") / name, folder / name)

    ctx = ManufacturingContext(resource_root=root)
    _divider, before = _solved(context=ctx)
    a0, b0, c0 = _divider_anchor_group(before)
    five3_before = _five3(before)

    mother_path = folder / "封頭尾.dxf"
    original_bytes = mother_path.read_bytes()
    rule = _endcap_mother_rule(mother_path)
    doc = ezdxf.readfile(mother_path)
    entity = doc.entitydb[rule["handle"]]
    entity.dxf.center = (
        float(entity.dxf.center.x) + float(rule["inward_unit"][0]),
        float(entity.dxf.center.y) + float(rule["inward_unit"][1]),
        float(entity.dxf.center.z),
    )
    doc.saveas(mother_path)
    edited_bytes = mother_path.read_bytes()
    assert edited_bytes != original_bytes

    _divider, after = _solved(context=ctx)
    a1, b1, c1 = _divider_anchor_group(after)
    delta = (float(a1.center.x-a0.center.x), float(a1.center.y-a0.center.y))
    print("ABC_inward_delta=", delta)
    assert delta == pytest.approx((1.0, 0.0), abs=1e-6)
    assert (float(b1.center.x-b0.center.x), float(b1.center.y-b0.center.y)) == pytest.approx(delta)
    assert (float(c1.center.x-c0.center.x), float(c1.center.y-c0.center.y)) == pytest.approx(delta)
    assert _five3(after) == five3_before

    # Resolver must consume, never rewrite, the EndCap mother DXF.
    assert mother_path.read_bytes() == edited_bytes


def test_t4_uses_no_third_common_dxf_and_records_semantic_datum():
    _divider, render = _solved()
    metadata = dict(render.metadata["divider_endcap_shared_6p4_datum"])
    assert metadata["datum_kind"] == "POST_RELIEF_CENTER_SPAN_CENTER"
    assert metadata["mother_source_file"] == "封頭尾.dxf"
    assert tuple(metadata["rigid_delta"]) == pytest.approx((3.0, -50.4999999777035), abs=1e-6)
    assert not Path("基準檔/金庫型/共用孔位.dxf").exists()
    assert not Path("基準檔/金庫型/6.4共用孔位.dxf").exists()
