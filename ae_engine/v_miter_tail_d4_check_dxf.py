# -*- coding: utf-8 -*-
"""#3317 Ø4 whole-Tail 2D CHECK DXF, strictly not a CNC/manufacturing export.

Only the proven D4 ResultScene outer CUTTING and unchanged authored source
holes are *projected* to CHECK. Actual original BEND lines are DATUM.
No production CUTTING/BEND/MARKING entities or manufacturing API is used.
"""
from __future__ import annotations

from pathlib import Path
import math
import os
import tempfile

import ezdxf

from .sheetmetal_drawing import (
    DrawingScene, PolylinePrimitive, CirclePrimitive, LinePrimitive,
)
from .sheetmetal_geometry_core import GeometryError
from .v_miter_tail_d4_check import (
    TailD4RootCheck, project_tail_d4_source_keyed_t_check,
    _require_authored_cutting_source, _require_exact_d4_outer_from_trusted_sharp,
)

_ALLOWED = frozenset(("CHECK", "DATUM"))
_FORBIDDEN = frozenset(("CUTTING", "BEND", "MARKING"))
_LABEL = "WHD #3317 D4 CHECK_NOT_CNC - NOT FOR MANUFACTURING"
_EPS = 1e-7


def _reject(msg):
    raise GeometryError("TAIL_D4_CHECK_DXF_" + msg)


def build_tail_d4_check_dxf_scene(flat, *, first_axis):
    """Requalify exact Factory/overlay and closed-T mesh before 2D projection."""
    # A CHECK-only adapter must not trust a pre-existing mesh that may
    # belong to a different scene, axis or edited drawing.
    full_t = project_tail_d4_source_keyed_t_check(flat, first_axis=first_axis)
    if not isinstance(full_t, TailD4RootCheck) or full_t.manufacturing_approved:
        _reject("UNVERIFIED_T_MESH")
    if full_t.bad_incidence_edges or full_t.bad_winding_edges:
        _reject("UNSEALED_T_MESH")

    source = flat.result_scene.primitives
    outers=tuple(p for p in source if isinstance(p,PolylinePrimitive)
                 and p.layer=="CUTTING" and p.closed
                 and p.semantic_id=="OUTER_BOUNDARY")
    if len(outers)!=1:
        _reject("OUTER_NOT_UNIQUE")
    outer=outers[0]
    # For hole identity, the guard walks trusted Factory and resolved overlays
    # and verifies every corresponding real hole loop, not a fixed count.
    from .manufacturing_render_data import material_polygon_from_final_scene
    stock=material_polygon_from_final_scene(flat.result_scene)
    features=_require_authored_cutting_source(flat,stock)
    _require_exact_d4_outer_from_trusted_sharp(flat,stock)
    actual_features=tuple(p for p in source if p.layer=="CUTTING" and p is not outer)
    if len(actual_features)!=len(features) or any(
        p is not q for p,q in zip(features,actual_features)
    ):
        _reject("SOURCE_FEATURES_CHANGED")

    bends=tuple(p for p in source if isinstance(p,LinePrimitive)
                and p.layer=="BEND")
    if not bends:
        _reject("REAL_BEND_REFERENCES_MISSING")

    scene=DrawingScene()
    scene.add(PolylinePrimitive(
        points=outer.points, layer="CHECK", closed=True, color=2,
        semantic_id="TAIL_D4_CHECK_NOT_CNC_OUTER",
    ))
    for p in features:
        if isinstance(p,CirclePrimitive):
            scene.add(CirclePrimitive(
                center=p.center,radius=p.radius,layer="CHECK",color=2,
                source_type=p.source_type,source_id=p.source_id,
            ))
        elif isinstance(p,PolylinePrimitive) and p.closed:
            scene.add(PolylinePrimitive(
                points=p.points,layer="CHECK",closed=True,color=2,
                semantic_id=p.semantic_id,
            ))
        else:
            _reject("UNSUPPORTED_AUTHORED_FEATURE")
    for p in bends:
        scene.add(LinePrimitive(p.p1,p.p2,layer="DATUM",color=6))

    # Visible caution belongs to the DXF itself, not merely its filename.
    # Text is placed outside the true outer boundary, and is never geometry.
    from .sheetmetal_drawing import TextPrimitive
    from .sheetmetal_geometry_core import Vec2
    xmin,ymin,xmax,ymax=stock.bounds
    scene.add(TextPrimitive(
        text=_LABEL+"\\PX/X or Y/Y is a CHECK fold order, not a press program",
        insert=Vec2(float(xmin),float(ymax)+12.),
        layer="CHECK",char_height=5.,attachment_point=1,
        color=1,semantic_id="TAIL_D4_CHECK_NOT_CNC_WARNING",
    ))
    if any(p.layer not in _ALLOWED for p in scene.primitives):
        _reject("MANUFACTURING_LAYER_FORBIDDEN")
    return scene


def _verify_reopen(scene, path):
    """Independently reopen and compare types, closed loops, layers and mm."""
    doc=ezdxf.readfile(path)
    audit=doc.audit()
    if audit.has_errors:
        _reject("DXF_AUDIT_FAILED")
    if int(doc.header.get("$INSUNITS",-1))!=4:
        _reject("MILLIMETERS_REQUIRED")
    if any(name in doc.layers for name in _FORBIDDEN):
        _reject("FORMAL_LAYER_TABLE_FORBIDDEN")
    actual=tuple(doc.modelspace())
    expected=tuple(scene.primitives)
    if len(actual)!=len(expected):
        _reject("REOPEN_ENTITY_COUNT")
    for i,(p,e) in enumerate(zip(expected,actual)):
        if e.dxf.layer!=p.layer or e.dxf.layer not in _ALLOWED:
            _reject(f"REOPEN_LAYER_{i}")
        if isinstance(p,PolylinePrimitive):
            if e.dxftype()!="LWPOLYLINE" or not e.closed or not p.closed:
                _reject(f"REOPEN_POLYLINE_{i}")
            points=tuple(e.get_points("xy"))
            if len(points)!=len(p.points) or any(
                abs(x-v.x)>_EPS or abs(y-v.y)>_EPS
                for (x,y),v in zip(points,p.points)
            ):
                _reject(f"REOPEN_POLYLINE_COORDS_{i}")
        elif isinstance(p,CirclePrimitive):
            if e.dxftype()!="CIRCLE" or any(
                abs(a-b)>_EPS for a,b in (
                    (e.dxf.center.x,p.center.x),
                    (e.dxf.center.y,p.center.y),
                    (e.dxf.radius,p.radius),
                )
            ):
                _reject(f"REOPEN_CIRCLE_{i}")
        elif isinstance(p,LinePrimitive):
            if e.dxftype()!="LINE" or any(
                abs(a-b)>_EPS for a,b in (
                    (e.dxf.start.x,p.p1.x),(e.dxf.start.y,p.p1.y),
                    (e.dxf.end.x,p.p2.x),(e.dxf.end.y,p.p2.y),
                )
            ):
                _reject(f"REOPEN_DATUM_{i}")
        else:
            from .sheetmetal_drawing import TextPrimitive
            if not isinstance(p,TextPrimitive) or e.dxftype()!="MTEXT":
                _reject(f"REOPEN_TEXT_TYPE_{i}")
            if (_LABEL not in e.text or
                    abs(e.dxf.insert.x-p.insert.x)>_EPS or
                    abs(e.dxf.insert.y-p.insert.y)>_EPS):
                _reject(f"REOPEN_TEXT_{i}")
    return doc


def save_tail_d4_check_dxf(flat, output_path, *, first_axis,
                           overwrite=False):
    """Fail closed before file creation; stage, independent reopen, atomic publish."""
    if type(overwrite) is not bool:
        _reject("INVALID_OVERWRITE")
    try:
        path=Path(output_path)
    except (TypeError,ValueError,OSError) as exc:
        raise GeometryError("TAIL_D4_CHECK_DXF_PATH_INVALID") from exc
    if path.suffix.lower()!=".dxf" or "CHECK_NOT_CNC" not in path.name.upper():
        _reject("FILENAME_MUST_DECLARE_CHECK_NOT_CNC")
    if not path.parent.is_dir():
        _reject("DIRECTORY_MISSING")
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))
    scene=build_tail_d4_check_dxf_scene(flat,first_axis=first_axis)

    fd,temp=tempfile.mkstemp(prefix=".tail_d4_check_",suffix=".dxf",dir=path.parent)
    os.close(fd)
    try:
        # AC1015 / R2000 writes a standard TEXT (ASCII) DXF with explicit mm.
        # This is a compatibility export, NOT evidence of opening in AutoCAD.
        doc=ezdxf.new("R2000",units=ezdxf.units.MM)
        doc.layers.new(name="CHECK",dxfattribs={"color":2})
        doc.layers.new(name="DATUM",dxfattribs={"color":6})
        msp=doc.modelspace()
        for p in scene.primitives:
            attrs={"layer":p.layer}
            if isinstance(p,PolylinePrimitive):
                msp.add_lwpolyline(
                    [(v.x,v.y) for v in p.points],close=True,dxfattribs=attrs,
                )
            elif isinstance(p,CirclePrimitive):
                msp.add_circle((p.center.x,p.center.y),p.radius,dxfattribs=attrs)
            elif isinstance(p,LinePrimitive):
                msp.add_line(
                    (p.p1.x,p.p1.y),(p.p2.x,p.p2.y),dxfattribs=attrs,
                )
            else:
                msp.add_mtext(p.text,dxfattribs={
                    **attrs,"insert":(p.insert.x,p.insert.y),
                    "char_height":p.char_height,
                    "attachment_point":p.attachment_point,
                })
        doc.saveas(temp)
        _verify_reopen(scene,Path(temp))
        if path.exists() and not overwrite:
            raise FileExistsError(str(path))
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return path
