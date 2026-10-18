"""#1959: real CADCraft DXF -> WHD Session confirm -> WHD manufacturing exporter.

Isolated flat-panel acceptance slice ONLY. CADCraft never supplies CUTTING or
overwrites a WHD manufacturing file. Source material/part specs are WHD-owned;
the new DXF is emitted by WHD's canonical manufacturing_api serializer.
No NFB / 3D / actual enclosure release is certified by this test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon

from ae_engine.cutting_material import material_from_cutting_components
from ae_engine.manufacturing_api import (
    save_part_render_data_dxf, verify_saved_part_render_data_dxf,
)
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import (
    DrawingScene, resolved_features_to_primitives,
)
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, ResolvedCircle, ResolvedProfile, ResolvedRect,
    Vec2, feature_surface_from_rect, resolve_surface_features,
)
from gui_modules.editors.cadcraft_command_session_bridge import (
    stage_verified_cadcraft_drawing,
)
from phase6_hole_editor_session import Phase6HoleEditorSession
from tools.issue1959_cadcraft_session_trial import demo_source_features


def _geometry_from_resolved(feature):
    if isinstance(feature, ResolvedCircle):
        return Point(feature.center.x,feature.center.y).buffer(
            feature.radius,quad_segs=32)
    if isinstance(feature, ResolvedRect):
        return Polygon([(p.x,p.y) for p in feature.points])
    if isinstance(feature, ResolvedProfile) and not feature.layered_profiles:
        return Polygon([(p.x,p.y) for p in feature.points])
    raise ValueError("UNSUPPORTED_CANONICAL_WHD_HOLE_GEOMETRY")


def try_wdh_manufacturing_slice(actual_cadcraft_dxf: Path, isolated_wdh_dxf: Path) -> dict:
    """Real canonical WHD DXF serializer, not a CADCraft file copy."""
    actual_cadcraft_dxf=Path(actual_cadcraft_dxf)
    isolated_wdh_dxf=Path(isolated_wdh_dxf)
    if isolated_wdh_dxf.exists() or isolated_wdh_dxf.resolve()==actual_cadcraft_dxf.resolve():
        raise ValueError("REFUSE_TO_OVERWRITE_ANY_EXISTING_OR_SOURCE_DXF")
    source_hash=hashlib.sha256(actual_cadcraft_dxf.read_bytes()).hexdigest()

    surface=feature_surface_from_rect("1959-flat-sheet-witness",
                                      Vec2(-100,-100),Vec2(200,200))
    old=CircleFeature(diameter=4,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(-70,-70),layer="CUTTING")
    attached=[old]
    session=Phase6HoleEditorSession("1959-flat-sheet-witness",attached)
    staged=stage_verified_cadcraft_drawing(
        output=actual_cadcraft_dxf,
        whd_candidates=demo_source_features(),
        session=session,surface=surface,width=300,height=300,
    )
    staged.confirm()
    if len(attached)!=4 or session.has_active_edit:
        raise AssertionError("WHD_HOLE_EDITOR_CONFIRM_NOT_COMMITTED")

    # The material and scenes come from WHD features / WHD face authority.
    resolved=tuple(resolve_surface_features(surface,attached,300,300))
    scene=DrawingScene()
    sheet=surface.polygon
    min_x,min_y,max_x,max_y=sheet.bounds
    scene.add_polyline((
        (min_x,min_y),(max_x,min_y),(max_x,max_y),(min_x,max_y)
    ),layer="CUTTING",closed=True)
    scene.extend(resolved_features_to_primitives(resolved))
    material=material_from_cutting_components(
        primary=sheet,
        secondary=tuple(_geometry_from_resolved(f) for f in resolved),
    )
    rendered=PartRenderData(scene=scene,material=material)
    isolated_wdh_dxf.parent.mkdir(parents=True,exist_ok=True)
    save_part_render_data_dxf(rendered,isolated_wdh_dxf,overwrite=False)
    verified=verify_saved_part_render_data_dxf(rendered,isolated_wdh_dxf)
    doc=ezdxf.readfile(isolated_wdh_dxf)
    layers=[entity.dxf.layer for entity in doc.modelspace()]
    source_preserved=(source_hash==hashlib.sha256(actual_cadcraft_dxf.read_bytes()).hexdigest())
    expected_count=1+len(resolved)
    result={
        "stage":"ISSUE1959_CANONICAL_WHD_CUTTING_EXPORT_SLICE",
        "status":"PASS" if verified.ok and source_preserved and len(layers)==expected_count
            and set(layers)=={"CUTTING"} else "FAIL",
        "cadcraft_was_used_only_as_geometry_witness":True,
        "whd_is_manufacturing_serializer":True,
        "whd_confirmed_hole_count":len(resolved),
        "manufacturing_entity_count":len(layers),
        "manufacturing_layers":sorted(set(layers)),
        "manufacturing_dxf_units_header":doc.header.get("$INSUNITS"),
        "whd_material_area":round(float(material.area),6),
        "whd_acceptance_ok":bool(verified.ok),
        "whd_acceptance_issue_codes":[issue.code for issue in verified.issues],
        "original_cadcraft_dxf_unchanged":source_preserved,
        "not_a_full_board_or_3d_certification":True,
    }
    if result["status"]!="PASS":
        raise AssertionError(json.dumps(result,ensure_ascii=False))
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--evidence",required=True,type=Path)
    args=parser.parse_args()
    report=try_wdh_manufacturing_slice(args.input,args.output)
    args.evidence.parent.mkdir(parents=True,exist_ok=True)
    args.evidence.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
