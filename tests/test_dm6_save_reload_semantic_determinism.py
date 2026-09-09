# -*- coding: utf-8 -*-
from pathlib import Path

from shapely.geometry import Polygon

from ae_engine.drawing_annotations import plan_part_annotations
from ae_engine.drawing_annotation_layout import resolve_annotation_collisions
from ae_engine.manufacturing_api import PartRenderData
from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene, PolylinePrimitive, TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2
import phase6_project_file as project


def _render_from_authoritative_probe(probe):
    w = float(probe["width"])
    h = float(probe["height"])
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        (Vec2(0, 0), Vec2(w, 0), Vec2(w, h), Vec2(0, h)),
        "CUTTING", closed=True,
    ))
    for hole in probe["holes"]:
        scene.add(CirclePrimitive(
            Vec2(float(hole["x"]), float(hole["y"])),
            float(hole["diameter"]) / 2.0,
            "CUTTING",
            source_type=str(hole["source_type"]),
            source_id=str(hole["source_id"]),
        ))
    return PartRenderData(
        scene=scene,
        material=Polygon(((0, 0), (w, 0), (w, h), (0, h))),
        fold_guides=(),
    )


def _semantic_snapshot(render_data):
    plan = plan_part_annotations(render_data)
    layout = resolve_annotation_collisions(plan, manufacturing_scene=render_data.scene)
    return {
        "dimensions": tuple(
            (d.semantic_id, d.axis, d.value, d.start, d.end)
            for d in plan.overall_dimensions
        ),
        "features": tuple(
            (f.semantic_id, f.source_id, f.source_type, f.anchor)
            for f in plan.feature_callouts
        ),
        "text": tuple(
            (p.semantic_id, p.layer, p.insert)
            for p in layout.primitives
            if isinstance(p, TextPrimitive)
        ),
    }


def test_dm6_t4_save_reload_rebuilds_same_annotation_semantics(tmp_path):
    authoritative = {
        "width": 100.0,
        "height": 100.0,
        "holes": [
            {"source_id": "H1", "source_type": "mounting_hole", "x": 20.0, "y": 20.0, "diameter": 10.0},
            {"source_id": "H2", "source_type": "mounting_hole", "x": 80.0, "y": 20.0, "diameter": 10.0},
        ],
    }
    before = _semantic_snapshot(_render_from_authoritative_probe(authoritative))

    path = project.write_project(tmp_path / "dm6_roundtrip.p6fold", {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {"dm6_authoritative_probe": authoritative},
        "final_geometry": {"must_not_persist": True},
    })
    loaded = project.read_project(path)
    after_probe = loaded["snapshot"]["dm6_authoritative_probe"]
    after = _semantic_snapshot(_render_from_authoritative_probe(after_probe))

    assert loaded["final_geometry"] == {}
    assert before == after

    dim_ids = [row[0] for row in after["dimensions"]]
    assert len(dim_ids) == 2 and len(set(dim_ids)) == 2
    assert {row[1] for row in after["dimensions"]} == {"x", "y"}

    feature_rows = after["features"]
    assert len(feature_rows) == 2
    assert {row[1] for row in feature_rows} == {"H1", "H2"}
    assert len({row[0] for row in feature_rows}) == 2


def test_dm6_t4_production_source_has_no_display_text_semantic_authority():
    layout = Path("ae_engine/drawing_annotation_layout.py").read_text(encoding="utf-8")
    gui = Path("gui.py").read_text(encoding="utf-8")
    planner = Path("ae_engine/drawing_annotations.py").read_text(encoding="utf-8")
    persistence = (
        Path("phase6_project_file.py").read_text(encoding="utf-8")
        + Path("phase6_project_controller.py").read_text(encoding="utf-8")
    )

    forbidden_layout = [
        'item[3] == str(primitive.text)',
        'if str(getattr(dim, "label", "")) == str(primitive.text)',
        'Duplicate labels are resolved deterministically by distance',
    ]
    assert not [x for x in forbidden_layout if x in layout]

    start = gui.index("def _draw_phase6_annotation_projection")
    end = gui.index("def _draw_phase6_corner_dimension_overlay", start)
    sink = gui[start:end]
    assert "dimensions_by_label" not in sink
    assert "get(str(primitive.text)" not in sink
    assert "semantic_id" in sink

    # Planner semantic identity definitions must not use presentation label.
    semantic_blocks = planner.split("def semantic_id(self) -> str:")
    assert len(semantic_blocks) >= 5
    for block in semantic_blocks[1:5]:
        body = block.split("\n\n", 1)[0]
        assert "self.label" not in body

    # Persistence is authoritative-state only; it must not know annotation presentation.
    forbidden_persistence = [
        "TextPrimitive",
        "AnnotationPlan",
        "build_engineering_drawing_projection",
        "resolve_annotation_collisions",
    ]
    assert not [x for x in forbidden_persistence if x in persistence]
