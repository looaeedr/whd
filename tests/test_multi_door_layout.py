import math

import ae_engine.ae as ae
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    derive_door_layout_cells,
    door_layout_part_key,
    calculate_door_finished_size as adapter_door_finished_size,
    build_door_result,
)


def test_layout_derives_missing_bottom_and_right_edges_from_position():
    cells = derive_door_layout_cells([
        (600, [600, 500, 700]),
        (500, [800, 1000]),
    ])

    assert [(c.column_index, c.row_index, c.start_width, c.start_height, c.edges) for c in cells] == [
        (0, 0, 600.0, 600.0, DoorFrameEdges(left=True, right=False, top=True, bottom=False)),
        (0, 1, 600.0, 500.0, DoorFrameEdges(left=True, right=False, top=True, bottom=False)),
        (0, 2, 600.0, 700.0, DoorFrameEdges(left=True, right=False, top=True, bottom=True)),
        (1, 0, 500.0, 800.0, DoorFrameEdges(left=True, right=True, top=True, bottom=False)),
        (1, 1, 500.0, 1000.0, DoorFrameEdges(left=True, right=True, top=True, bottom=True)),
    ]


def test_layout_formal_part_keys_are_stable_column_then_row():
    cells = derive_door_layout_cells([
        (600, [600, 500, 700]),
        (500, [800, 1000]),
    ])
    assert tuple(door_layout_part_key(cell) for cell in cells) == (
        "door_c1_r1", "door_c1_r2", "door_c1_r3", "door_c2_r1", "door_c2_r2",
    )


def test_single_door_edge_aware_size_matches_legacy_formula():
    expected = ae.calculate_door_finished_size(1000, 1800, 25, 3.5, 3.5, 2)
    actual = adapter_door_finished_size(
        w=1000, h=1800, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        frame_edges=DoorFrameEdges(),
    )
    assert actual == expected == (935.0, 1735.0)


def test_missing_bottom_frame_deducts_one_less_frame_span_but_door_keeps_four_folds():
    edges = DoorFrameEdges(bottom=False)
    finished = adapter_door_finished_size(
        w=1000, h=1800, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        frame_edges=edges,
    )
    assert finished == (935.0, 1764.0)

    result = build_door_result(
        w=1000, h=1800, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
        frame_edges=edges,
    )
    assert result.topology.left_fold == 19.0
    assert result.topology.right_fold == 15.0
    assert result.topology.top_fold == 15.0
    assert result.topology.bottom_fold == 15.0


def test_missing_right_frame_deducts_one_less_frame_span():
    assert adapter_door_finished_size(
        w=1000, h=1800, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        frame_edges=DoorFrameEdges(right=False),
    ) == (964.0, 1735.0)


def test_missing_bottom_and_right_frames_combine_independently():
    assert adapter_door_finished_size(
        w=1000, h=1800, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        frame_edges=DoorFrameEdges(right=False, bottom=False),
    ) == (964.0, 1764.0)


def test_ae_public_door_size_api_accepts_frame_edges_without_changing_legacy_default():
    assert ae.calculate_door_finished_size(1000, 1800, 25, 3.5, 3.5, 2) == (935.0, 1735.0)
    assert ae.calculate_door_finished_size(
        1000, 1800, 25, 3.5, 3.5, 2,
        frame_edges=DoorFrameEdges(right=False, bottom=False),
    ) == (964.0, 1764.0)


def test_layout_dimension_validation_requires_column_widths_and_each_height_stack_to_match_whd():
    from ae_engine.sheetmetal_part_adapters import validate_door_layout_dimensions

    cells = validate_door_layout_dimensions(
        [(600, [600, 500, 700]), (500, [800, 1000])],
        total_width=1100,
        total_height=1800,
    )
    assert len(cells) == 5

    try:
        validate_door_layout_dimensions(
            [(600, [600, 500, 700]), (450, [800, 1000])],
            total_width=1100,
            total_height=1800,
        )
    except ValueError as exc:
        assert "column widths" in str(exc)
    else:
        raise AssertionError("width mismatch should fail")

    try:
        validate_door_layout_dimensions(
            [(600, [600, 500, 650]), (500, [800, 1000])],
            total_width=1100,
            total_height=1800,
        )
    except ValueError as exc:
        assert "column 1 heights" in str(exc)
    else:
        raise AssertionError("height mismatch should fail")


def test_door_blank_size_and_scene_propagate_frame_edges():
    edges = DoorFrameEdges(right=False, bottom=False)
    blank = ae.calculate_door_blank_size(
        1000, 1800, 2, 25, 3.5, 3.5, 19, 15, 15, 15,
        frame_edges=edges,
    )
    # finished 964 x 1764, then Door panel four-fold blank formula remains unchanged.
    assert blank == (994.0, 1790.0)

    scene = ae._build_door_scene(
        w=1000, h=1800, t=2, fw=25, gw=3.5, gh=3.5,
        fl=19, fr=15, ft=15, fb=15, frame_edges=edges,
    )
    cutting = next(p for p in scene.primitives if getattr(p, "layer", None) == "CUTTING")
    xs = [p.x for p in cutting.points]
    ys = [p.y for p in cutting.points]
    assert math.isclose(max(xs) - min(xs), 994.0)
    assert math.isclose(max(ys) - min(ys), 1790.0)


def test_door_layout_export_filename_is_stable_and_one_based():
    from ae_engine.sheetmetal_part_adapters import door_layout_export_filename
    cell = derive_door_layout_cells([(600, [600, 500, 700]), (500, [800, 1000])])[3]
    assert door_layout_export_filename(cell) == "door_c2_r1.dxf"


def test_export_door_dxf_round_trip_uses_cell_frame_edges(tmp_path):
    import ezdxf

    path = tmp_path / "door_c1_r1.dxf"
    ae.export_door_dxf(
        str(path), 600, 600, 2, 25, 3.5, 3.5, 19, 15, 15, 15,
        draw_stock=False,
        frame_edges=DoorFrameEdges(right=False, bottom=False),
    )
    doc = ezdxf.readfile(path)
    cutting = list(doc.modelspace().query('LWPOLYLINE[layer=="CUTTING"]'))
    assert cutting
    pts = list(cutting[0].get_points('xy'))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert round(max(xs) - min(xs), 6) == 594.0
    assert round(max(ys) - min(ys), 6) == 590.0


def test_left_one_right_two_edge_rules_match_user_examples():
    cells = derive_door_layout_cells([
        (600, [1800]),
        (500, [800, 1000]),
    ])
    left, right_top, right_bottom = cells
    assert left.edges == DoorFrameEdges(left=True, right=False, top=True, bottom=True)
    assert right_top.edges == DoorFrameEdges(left=True, right=True, top=True, bottom=False)
    assert right_bottom.edges == DoorFrameEdges()


def test_default_door_scene_is_identical_to_explicit_four_frame_edges():
    kwargs = dict(w=1000, h=1800, t=2, fw=25, gw=3.5, gh=3.5, fl=19, fr=15, ft=15, fb=15)
    default_scene = ae._build_door_scene(**kwargs)
    explicit_scene = ae._build_door_scene(**kwargs, frame_edges=DoorFrameEdges())
    assert default_scene.primitives == explicit_scene.primitives


def test_complete_partition_appends_positive_remainder_and_promotes_edited_auto_value():
    from ae_engine.sheetmetal_part_adapters import complete_partition

    completed = complete_partition([400], 1000)
    assert completed.values == (400.0, 600.0)
    assert completed.auto_index == 1
    assert completed.valid is True
    assert completed.excess == 0.0

    # Editing the generated 600 to 400 means it is now a fixed value;
    # a new generated remainder must appear after it.
    completed = complete_partition([400, 400], 1000)
    assert completed.values == (400.0, 400.0, 200.0)
    assert completed.auto_index == 2
    assert completed.valid is True


def test_complete_partition_recomputes_after_delete_and_does_not_generate_zero_cell():
    from ae_engine.sheetmetal_part_adapters import complete_partition

    completed = complete_partition([400, 400], 1000)
    assert completed.values == (400.0, 400.0, 200.0)

    completed = complete_partition([400], 1000)
    assert completed.values == (400.0, 600.0)

    exact = complete_partition([400, 600], 1000)
    assert exact.values == (400.0, 600.0)
    assert exact.auto_index is None
    assert exact.valid is True


def test_complete_partition_reports_excess_without_negative_remainder():
    from ae_engine.sheetmetal_part_adapters import complete_partition

    completed = complete_partition([700, 400], 1000)
    assert completed.values == (700.0, 400.0)
    assert completed.auto_index is None
    assert completed.valid is False
    assert completed.excess == 100.0


def test_horizontal_scene_mirror_transforms_every_positioned_primitive_and_keeps_y():
    from ae_engine.sheetmetal_drawing import (
        DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive, TextPrimitive,
        mirror_drawing_scene_x,
    )
    from ae_engine.sheetmetal_geometry import Vec2

    scene = DrawingScene([
        PolylinePrimitive((Vec2(10, 1), Vec2(30, 2)), "CUTTING", False, 3),
        LinePrimitive(Vec2(12, 3), Vec2(20, 4), "BEND", 5),
        CirclePrimitive(Vec2(14, 5), 2, "BLIND_HOLE", 1),
        TextPrimitive("check", Vec2(16, 6), "CHECK", 30, 8, 2),
    ])
    mirrored = mirror_drawing_scene_x(scene, 10, 30)

    poly, line, circle, text = mirrored.primitives
    assert [(p.x, p.y) for p in poly.points] == [(30.0, 1.0), (10.0, 2.0)]
    assert (line.p1.x, line.p1.y, line.p2.x, line.p2.y) == (28.0, 3.0, 20.0, 4.0)
    assert (circle.center.x, circle.center.y) == (26.0, 5.0)
    assert (text.insert.x, text.insert.y) == (24.0, 6.0)


def test_formula_door_export_is_horizontal_mirror_but_canonical_scene_stays_normal(tmp_path):
    import ezdxf
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive

    kwargs = dict(
        w=1000, h=1800, t=2, fw=25, gw=3.5, gh=3.5,
        fl=19, fr=15, ft=15, fb=15,
    )
    feature = CircleFeature(
        diameter=10, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(120, 300), layer="BLIND_HOLE", add_centerline=True,
    )
    canonical = ae._build_door_scene(**kwargs, user_features=[feature])
    cutting = next(p for p in canonical.primitives if getattr(p, "layer", None) == "CUTTING" and hasattr(p, "points"))
    min_x = min(p.x for p in cutting.points)
    max_x = max(p.x for p in cutting.points)
    canonical_circle = next(p for p in canonical.primitives if isinstance(p, CirclePrimitive) and p.layer == "BLIND_HOLE")
    canonical_bend = next(p for p in canonical.primitives if isinstance(p, LinePrimitive) and p.layer == "BEND")
    before = canonical_circle.center.x

    path = tmp_path / "door.dxf"
    ae.export_door_dxf(
        str(path), 1000, 1800, 2, 25, 3.5, 3.5, 19, 15, 15, 15,
        draw_stock=False, user_features=[feature],
    )
    doc = ezdxf.readfile(path)
    exported_circle = list(doc.modelspace().query('CIRCLE[layer=="BLIND_HOLE"]'))[0]
    assert round(exported_circle.dxf.center.x, 6) == round(min_x + max_x - canonical_circle.center.x, 6)
    assert round(exported_circle.dxf.center.y, 6) == round(canonical_circle.center.y, 6)

    exported_bends = list(doc.modelspace().query('LINE[layer=="BEND"]'))
    assert any(
        round(line.dxf.start.x, 6) == round(min_x + max_x - canonical_bend.p1.x, 6)
        and round(line.dxf.start.y, 6) == round(canonical_bend.p1.y, 6)
        for line in exported_bends
    )
    # Export must not mutate canonical edit coordinates.
    assert canonical_circle.center.x == before


def test_stretched_door_export_applies_same_horizontal_mirror_once(tmp_path, monkeypatch):
    import ezdxf
    from ae_engine.sheetmetal_drawing import DrawingScene, SceneData, PolylinePrimitive, CirclePrimitive
    from ae_engine.sheetmetal_geometry import Vec2

    source = DrawingScene([
        PolylinePrimitive((Vec2(0, 0), Vec2(100, 0), Vec2(100, 50), Vec2(0, 50)), "CUTTING", True, 3),
        CirclePrimitive(Vec2(20, 25), 5, "MARKING", 211),
    ])
    fake = SceneData(scene=source, params={
        "total_width": 100.0, "total_depth": 50.0,
        "finished_w": 80.0, "finished_h": 30.0,
        "door_fold_l": 10.0, "door_fold_r": 10.0,
        "door_fold_t": 10.0, "door_fold_b": 10.0,
    })
    monkeypatch.setattr(ae, "get_stretched_door_data", lambda *args, **kwargs: fake)

    path = tmp_path / "stretched.dxf"
    ae.export_stretched_door_dxf(str(path), "dummy", 100, 50, 2, 25, draw_stock=False)
    doc = ezdxf.readfile(path)
    circle = list(doc.modelspace().query('CIRCLE[layer=="MARKING"]'))[0]
    assert round(circle.dxf.center.x, 6) == 80.0
    assert round(circle.dxf.center.y, 6) == 25.0


def test_every_multi_door_formula_export_is_mirrored_exactly_once(tmp_path):
    import ezdxf
    from ae_engine.sheetmetal_drawing import drawing_scene_x_bounds, LinePrimitive

    cells = derive_door_layout_cells([
        (600, [600, 500, 700]),
        (500, [800, 1000]),
    ])
    for cell in cells:
        path = tmp_path / f"door_c{cell.column_index+1}_r{cell.row_index+1}.dxf"
        canonical = ae._build_door_scene(
            w=cell.start_width, h=cell.start_height,
            t=2, fw=25, gw=3.5, gh=3.5,
            fl=19, fr=15, ft=15, fb=15,
            frame_edges=cell.edges,
        )
        min_x, max_x = drawing_scene_x_bounds(canonical)
        canonical_bends = [p for p in canonical.primitives if isinstance(p, LinePrimitive) and p.layer == "BEND"]

        ae.export_door_dxf(
            str(path), cell.start_width, cell.start_height,
            2, 25, 3.5, 3.5, 19, 15, 15, 15,
            draw_stock=False, frame_edges=cell.edges,
        )
        doc = ezdxf.readfile(path)
        exported_bends = list(doc.modelspace().query('LINE[layer=="BEND"]'))
        assert len(exported_bends) == len(canonical_bends)
        for canonical_line, exported_line in zip(canonical_bends, exported_bends):
            assert round(exported_line.dxf.start.x, 6) == round(min_x + max_x - canonical_line.p1.x, 6)
            assert round(exported_line.dxf.end.x, 6) == round(min_x + max_x - canonical_line.p2.x, 6)
            assert round(exported_line.dxf.start.y, 6) == round(canonical_line.p1.y, 6)
            assert round(exported_line.dxf.end.y, 6) == round(canonical_line.p2.y, 6)


def test_door_enclosure_reference_offsets_use_configured_gaps_and_edge_presence():
    from ae_engine.sheetmetal_features import door_enclosure_reference_offsets

    full = door_enclosure_reference_offsets(
        DoorFrameEdges(), frame_width=25, thickness=2, gap_w=4, gap_h=6
    )
    assert full == {"left": 33.0, "right": 33.0, "top": 35.0, "bottom": 35.0}

    partial = door_enclosure_reference_offsets(
        DoorFrameEdges(right=False, bottom=False),
        frame_width=25, thickness=2, gap_w=4, gap_h=6,
    )
    assert partial == {"left": 33.0, "right": 4.0, "top": 35.0, "bottom": 6.0}


def test_door_indicator_measurement_box_reference_respects_missing_right_bottom_edges_and_nondefault_gap():
    from ae_engine.sheetmetal_features import (
        DoorIndicatorContext,
        measure_door_indicator_position,
        resolve_door_indicator_layout,
    )
    from ae_engine.sheetmetal_geometry import Vec2

    context = DoorIndicatorContext(
        finished_width=500, finished_height=700, left_fold=19, bottom_fold=15
    )
    layout = resolve_door_indicator_layout(context, (2,), Vec2(0, 0))
    normal = measure_door_indicator_position(
        layout, context, frame_width=25, thickness=2, use_box_distance=False,
        frame_edges=DoorFrameEdges(right=False, bottom=False), gap_w=4, gap_h=6,
    )
    boxed = measure_door_indicator_position(
        layout, context, frame_width=25, thickness=2, use_box_distance=True,
        frame_edges=DoorFrameEdges(right=False, bottom=False), gap_w=4, gap_h=6,
    )
    # X is measured from the left enclosure side; left edge exists => +25+4+4 = 33.
    assert boxed.distance_x - normal.distance_x == 33.0
    # Y is measured from the top enclosure side; top edge exists => +25+4+6 = 35.
    assert boxed.distance_y - normal.distance_y == 35.0


def test_indicator_box_opening_size_uses_each_cells_layer_group_configuration():
    from ae_engine.sheetmetal_features import indicator_box_opening_size

    # One layer / one group: box outer 326 x 445; Door cutout = outer - 98 - T.
    assert indicator_box_opening_size((1,), thickness=2) == (226.0, 345.0)
    # Three layers, max 3 groups: outer W=486, H=1005; same cutout rule.
    assert indicator_box_opening_size((3, 2, 1), thickness=2) == (386.0, 905.0)


def test_door_enclosure_reference_guide_extends_finished_boundary_per_edge_and_gap():
    from ae_engine.sheetmetal_features import RectGuide, door_enclosure_reference_guide
    from ae_engine.sheetmetal_geometry import Vec2
    base = RectGuide(Vec2(19, 15), Vec2(519, 715), "finished_boundary")
    guide = door_enclosure_reference_guide(
        base,
        DoorFrameEdges(right=False, bottom=False),
        frame_width=25, thickness=2, gap_w=4, gap_h=6,
    )
    assert guide.min_point == Vec2(-14, 9)       # left: 25+4+4=33, bottom: gap_h only 6
    assert guide.max_point == Vec2(523, 750)     # right: gap_w only 4, top: 25+4+6=35
    assert guide.role == "door_enclosure_reference"


def test_baseline_source_label_is_explicit_when_present_or_formula_generated(tmp_path, monkeypatch):
    model_dir = tmp_path / "基準檔" / "金庫型"
    model_dir.mkdir(parents=True)
    (model_dir / "門.dxf").write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(ae, "get_resource_path", lambda p: str(tmp_path / p))

    assert ae.baseline_source_label("金庫型", "門.dxf") == "基準檔：金庫型/門.dxf"
    assert ae.baseline_source_label("金庫型", "箱身.dxf") == "未使用基準檔（程式計算生成）"
    assert ae.baseline_source_label("", "門.dxf") == "未使用基準檔（程式計算生成）"


def test_real_vault_door_baseline_loads_secondary_geometry_for_partial_frame_edges():
    from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive
    data = ae.get_stretched_door_data(
        "金庫型", 600, 600, 2, 25, 3.5, 3.5, 19, 15, 15, 15,
        frame_edges=DoorFrameEdges(right=False, bottom=False),
    )
    assert data.params["total_width"] == 594.0
    assert data.params["total_depth"] == 590.0
    secondary = [p for p in data.scene.primitives if getattr(p, "layer", "") in {"MARKING", "CUTTING"}]
    # More than the structural outline proves the supplied 門.dxf contributed mapped content.
    assert len(secondary) > 1


def test_general_hole_reference_distance_changes_to_enclosure_guide():
    from ae_engine.sheetmetal_features import (
        CircleFeature, FeatureAnchor, feature_surface_from_structural_result,
        reference_distances, feature_reference_anchor,
        door_enclosure_reference_guide,
    )
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_part_adapters import build_door_result, build_finished_reference_guide

    edges = DoorFrameEdges(right=False, bottom=False)
    result = build_door_result(
        w=600, h=600, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
        frame_edges=edges,
    )
    finished_w, finished_h = ae.calculate_door_finished_size(600,600,25,3.5,3.5,2,frame_edges=edges)
    base = build_finished_reference_guide('door', result, finished_width=finished_w, finished_height=finished_h)
    enclosure = door_enclosure_reference_guide(
        base, edges, frame_width=25, thickness=2, gap_w=3.5, gap_h=3.5,
    )
    surface = feature_surface_from_structural_result('door', result)
    feature = CircleFeature(20.0, FeatureAnchor.PANEL_CENTER, Vec2(-100.0, 100.0))
    normal = reference_distances(surface, [feature], 0, feature_reference_anchor(feature), result.width, result.height, reference_guide=base)
    boxed = reference_distances(surface, [feature], 0, feature_reference_anchor(feature), result.width, result.height, reference_guide=enclosure)
    # Feature is deliberately on the left/top half: those sides exist and gain FW+2T+gap.
    assert round(boxed.x_edge_distance - normal.x_edge_distance, 6) == 32.5
    assert round(boxed.y_edge_distance - normal.y_edge_distance, 6) == 32.5
