from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection,
    normalize_corner_selection,
)

from ae_engine.corner_type_ui import (
    UNKNOWN_MODEL_NAME,
    is_unknown_model,
    apply_manual_corner_selection,
    build_corner_type_preview_geometry,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    policy_from_corner_state,
    set_manual_corner_pair_same,
    with_unknown_model,
)


def test_unknown_model_is_appended_once_without_replacing_vault():
    models = with_unknown_model(["金庫型", "指示燈"])
    assert models == ["金庫型", "指示燈", "自訂"]
    assert with_unknown_model(models) == models
    assert is_unknown_model("自訂")
    assert is_unknown_model("未知類型")  # legacy alias
    assert not is_unknown_model("金庫型")


def test_manual_corner_state_defaults_to_cross_standard_per_part_and_per_corner():
    state = new_manual_corner_state(["door", "head"])
    assert state["door"]["top_left"].type_id is CornerTypeId.CROSS
    assert state["door"]["top_left"].cross_mode is CrossCornerMode.STANDARD
    assert state["head"]["bottom_right"].type_id is CornerTypeId.CROSS
    state["door"]["top_left"] = CornerTypeSelection(CornerTypeId.C02, 1)
    assert state["head"]["top_left"].type_id is CornerTypeId.CROSS


def test_policy_from_corner_state_preserves_c02_orientation():
    state = new_manual_corner_state(["door"])["door"]
    state["bottom_left"] = state["bottom_left"].__class__(CornerTypeId.C02, 1)
    policy = policy_from_corner_state(state, fw=25)
    assert policy.bottom_left.type_id is CornerTypeId.C02
    assert policy.bottom_left.rotation_quadrants == 1
    assert policy.top_right.type_id is CornerTypeId.CROSS
    assert policy.top_right.cross_mode is CrossCornerMode.STANDARD


def test_manual_corner_pair_same_defaults_to_top_and_bottom_same():
    same = new_manual_corner_pair_same_state(["door", "head"])
    assert same["door"] == {"top": True, "bottom": True}
    assert same["head"] == {"top": True, "bottom": True}


def test_pair_selection_updates_both_sides_by_default_then_allows_split_override():
    state = new_manual_corner_state(["door"])["door"]
    same = new_manual_corner_pair_same_state(["door"])["door"]
    insert_overlay = CornerTypeSelection(CornerTypeId.INSERT_OVERLAY)
    apply_manual_corner_selection(state, same, "top", insert_overlay)
    assert state["top_left"] == insert_overlay
    assert state["top_right"] == insert_overlay

    set_manual_corner_pair_same(state, same, "top", False)
    overlay = CornerTypeSelection(CornerTypeId.OVERLAY)
    apply_manual_corner_selection(state, same, "top_right", overlay)
    assert state["top_left"] == insert_overlay
    assert state["top_right"] == overlay


def test_reenabling_pair_same_uses_left_value_as_authority():
    state = new_manual_corner_state(["door"])["door"]
    same = new_manual_corner_pair_same_state(["door"])["door"]
    set_manual_corner_pair_same(state, same, "bottom", False)
    state["bottom_left"] = CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH, amount_t=0.5,
    )
    state["bottom_right"] = CornerTypeSelection(CornerTypeId.OVERLAY)
    set_manual_corner_pair_same(state, same, "bottom", True)
    assert state["bottom_right"] == state["bottom_left"]
    assert state["bottom_left"].cross_mode is CrossCornerMode.EXTRA_CUT


def test_corner_preview_is_built_from_semantic_manufacturing_geometry():
    selections = (
        CornerTypeSelection(CornerTypeId.CROSS),
        CornerTypeSelection(CornerTypeId.OVERLAY),
        CornerTypeSelection(CornerTypeId.INSERT),
        CornerTypeSelection(CornerTypeId.INSERT_OVERLAY),
    )
    previews = []
    for selection in selections:
        preview = build_corner_type_preview_geometry(selection)
        previews.append(preview)
        assert preview.source_part == f"semantic:{selection.type_id.value}"
        assert preview.source_corner == "top_left"
        points = [p for path in preview.cut_paths for p in path]
        assert max(p.x for p in points) == preview.span
        assert max(p.y for p in points) == preview.span
        assert min(p.x for p in points) == 0.0
        assert min(p.y for p in points) == 0.0
        assert preview.bend_paths
    assert len({round(p.span, 6) for p in previews}) == 1


def test_legacy_c01_to_c04_preview_inputs_normalize_to_current_semantics():
    legacy = (
        CornerTypeSelection(CornerTypeId.C01),
        CornerTypeSelection(CornerTypeId.C02, 0),
        CornerTypeSelection(CornerTypeId.C03),
        CornerTypeSelection(CornerTypeId.C04),
    )
    for old in legacy:
        current = normalize_corner_selection(old)
        old_preview = build_corner_type_preview_geometry(old)
        new_preview = build_corner_type_preview_geometry(current)
        assert old_preview == new_preview


def test_legacy_c02_rotation_normalizes_retain_direction_in_semantic_preview():
    x_leave = build_corner_type_preview_geometry(CornerTypeSelection(CornerTypeId.C02, 0))
    y_leave = build_corner_type_preview_geometry(CornerTypeSelection(CornerTypeId.C02, 1))
    assert {(13.0, 16.0), (13.0, 0.0)} <= _path_points(x_leave.cut_paths)
    assert {(15.0, 14.0), (0.0, 14.0)} <= _path_points(y_leave.cut_paths)
    assert x_leave.source_part == y_leave.source_part == "semantic:CROSS"


def test_corner_preview_module_does_not_rederive_corner_formulas():
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath('ae_engine', 'corner_type_ui.py').read_text(encoding='utf-8')
    assert 'resolve_corner_relief' not in source
    assert 'normalize_corner_selection' in source
    assert 'resolve_endcap_assembly_semantics' in source
    assert 'build_unknown_endcap_result' in source


def test_gui_corner_preview_has_no_illustrative_fold_constants():
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath('gui.py').read_text(encoding='utf-8')
    body = source[source.index('    def _draw_corner_type_icon'):source.index('    def _pair_for_corner_target')]
    assert 'fold_u=12.0' not in body
    assert 'fold_v=12.0' not in body
    assert 'thickness=4.0' not in body
    assert 'fw=8.0' not in body


def _path_points(paths):
    return {(round(p.x, 6), round(p.y, 6)) for path in paths for p in path}


def test_corner_preview_uses_real_semantic_cutting_paths_not_removed_area_polygons():
    standard = build_corner_type_preview_geometry(CornerTypeSelection(CornerTypeId.CROSS))
    retain = build_corner_type_preview_geometry(CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.RETAIN,
        direction=CornerDirection.WIDTH, amount_t=1.0,
    ))
    extra = build_corner_type_preview_geometry(CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH, amount_t=0.5,
    ))
    hybrid = build_corner_type_preview_geometry(CornerTypeSelection(CornerTypeId.INSERT_OVERLAY))

    for preview in (standard, retain, extra, hybrid):
        points = _path_points(preview.cut_paths)
        assert (0.0, preview.span) in points
        assert (preview.span, 0.0) in points

    assert {(0.0, 16.0), (15.0, 16.0), (15.0, 0.0)} <= _path_points(standard.cut_paths)
    assert {(0.0, 16.0), (13.0, 16.0), (13.0, 0.0)} <= _path_points(retain.cut_paths)
    assert {(0.0, 17.0), (16.0, 17.0), (16.0, 0.0)} <= _path_points(extra.cut_paths)
    assert {(40.0, 0.0), (40.0, 39.0), (16.0, 39.0), (16.0, 43.0), (0.0, 43.0)} <= _path_points(hybrid.cut_paths)


def test_corner_preview_crops_real_semantic_bend_segments_with_cutting():
    standard = build_corner_type_preview_geometry(CornerTypeSelection(CornerTypeId.CROSS))
    retain = build_corner_type_preview_geometry(CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.RETAIN,
        direction=CornerDirection.WIDTH, amount_t=1.0,
    ))
    extra = build_corner_type_preview_geometry(CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.BOTH, amount_t=0.5,
    ))

    assert (15.0, 16.0) in _path_points(standard.bend_paths)
    assert any(all(round(p.x, 6) == 15.0 for p in path) for path in retain.bend_paths)
    assert (13.0, 16.0) in _path_points(retain.cut_paths)
    assert any(all(round(p.x, 6) == 15.0 for p in path) for path in extra.bend_paths)
    assert (16.0, 17.0) in _path_points(extra.cut_paths)


def test_gui_corner_thumbnail_draws_cutting_and_bend_paths_without_filled_cut_polygon():
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath('gui.py').read_text(encoding='utf-8')
    body = source[source.index('    def _draw_corner_type_icon'):source.index('    def _pair_for_corner_target')]
    assert 'preview.cut_paths' in body
    assert 'preview.bend_paths' in body
    assert 'create_polygon' not in body
    assert "fill='#30d158'" in body
