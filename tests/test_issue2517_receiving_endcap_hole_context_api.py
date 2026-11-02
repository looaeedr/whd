"""#2517 Receiving physical Head/Tail Hole Editor obtains source from Engine API."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
)
from ae_engine.receiving_shared_settings import edit_setting, share_setting, setting_value
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, RectGuide,
    resolve_endcap_finished_face_guide, feature_surface_from_rect,
)


def _source():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1, width=920, depth=440,
    )
    head_hole = CircleFeature(
        diameter=6.4, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0),
    )
    tail_hole = CircleFeature(
        diameter=9, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(10, 0),
    )
    layout = edit_setting(
        layout, set_index=0, bay_index=1, kind="head_features",
        value=[head_hole],
    )
    layout = edit_setting(
        layout, set_index=0, bay_index=0, kind="tail_features",
        value=[tail_hole],
    )
    return {"model": "受電箱", "t": 2, "w": 999, "d": 999}, layout, head_hole, tail_hole


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_engine_context_is_real_selected_bay_not_stale_root(family):
    snapshot, layout, head, tail = _source()
    snapshot["model"] = family
    before = deepcopy(layout)
    ctx = api.project_receiving_endcap_hole_editor_context(
        snapshot, layout, set_index=0, bay_index=1, role="head",
    )
    assert (ctx.width, ctx.depth) == (920, 440)
    assert ctx.features == [head]
    guide = resolve_endcap_finished_face_guide(920, 440, 2)
    assert ctx.surface == feature_surface_from_rect(
        "head_finished_face", guide.min_point, guide.max_point,
    )
    assert ctx.reference_guide == RectGuide(
        Vec2(0, 0), Vec2(920, 440), "finished_boundary",
    )
    assert layout == before
    assert ctx.features is not setting_value(layout["sets"][0], 1, "head_features")
    ctx.features.clear()
    assert setting_value(layout["sets"][0], 1, "head_features") == [head]


def test_head_tail_source_isolated_and_shared_setting_uses_selected_bay():
    snapshot, layout, head, tail = _source()
    first = api.project_receiving_endcap_hole_editor_context(
        snapshot, layout, set_index=0, bay_index=0, role="tail",
    )
    second = api.project_receiving_endcap_hole_editor_context(
        snapshot, layout, set_index=0, bay_index=1, role="head",
    )
    assert first.features == [tail] and second.features == [head]
    layout = share_setting(
        layout, set_index=0, bay_indices=(0, 1),
        source_bay_index=1, kind="head_features",
    )
    linked = api.project_receiving_endcap_hole_editor_context(
        snapshot, layout, set_index=0, bay_index=0, role="head",
    )
    assert linked.features == [head]
    assert first.features == [tail]


@pytest.mark.parametrize("invalid", ({"model": "金庫型"}, {"model": "UNKNOWN"}))
def test_wrong_cabinet_family_never_opens_receiving_physical_face(invalid):
    _, layout, *_ = _source()
    with pytest.raises(ValueError, match="FAMILY_REQUIRED"):
        api.project_receiving_endcap_hole_editor_context(
            invalid, layout, set_index=0, bay_index=0, role="head",
        )


@pytest.mark.parametrize("role", ("door", "base_plate", "", None))
def test_unknown_hole_role_fails_closed(role):
    snapshot, layout, *_ = _source()
    with pytest.raises(ValueError, match="ROLE_INVALID"):
        api.project_receiving_endcap_hole_editor_context(
            snapshot, layout, set_index=0, bay_index=0, role=role,
        )


@pytest.mark.parametrize("set_index,bay_index", ((True, 0), (0, False), (-1, 0), (0, 2)))
def test_invalid_physical_set_or_bay_never_borrows_neighbor(set_index, bay_index):
    snapshot, layout, *_ = _source()
    with pytest.raises(IndexError):
        api.project_receiving_endcap_hole_editor_context(
            snapshot, layout, set_index=set_index, bay_index=bay_index,
            role="head",
        )


def test_gui_receiving_port_has_no_own_endcap_placement_or_share_policy():
    root = Path(__file__).resolve().parents[1]
    source = (root / "gui_modules/application/fold_designer_composition_receiving.py").read_text(encoding="utf-8")
    section = source.split("def receiving_settings_ports(")[1].split("def open_receiving_layer_preview(")[0]
    assert "manufacturing_api.project_receiving_endcap_hole_editor_context(" in section
    assert "resolve_endcap_finished_face_guide(" not in section
    assert "feature_surface_from_rect(" not in section
    assert "setting_value(" not in section
    assert "RectGuide(" not in section
    engine = (root / "ae_engine/operator_receiving_endcap_hole_context.py").read_text(encoding="utf-8")
    assert "from gui_modules" not in engine and "from phase6_" not in engine
