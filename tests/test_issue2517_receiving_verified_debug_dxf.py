"""#2517 verified receiving diagnostic layout: true physical holes and Q."""
from __future__ import annotations

import ezdxf
import pytest
from tempfile import TemporaryDirectory

from ae_engine.manufacturing_export import receiving_instance_namespace
from ae_engine.receiving_dxf_groups import commit_verified_receiving_groups
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_verified_debug_dxf import (
    _source_signature_for_quantity, _role, compose_verified_receiving_debug_layout,
)
from tests.test_issue2690_composed_panel_dxf import _flat


def _three_bays():
    source = new_receiving_layout(width=800, height=1600, depth=350)
    return resize_receiving_bays(source, set_index=0, bay_count=3)


def _row_data(source):
    rows = []
    for si, group in enumerate(source["sets"]):
        for bi, bay in enumerate(group["bays"]):
            ns = receiving_instance_namespace(
                set_id=group["stable_id"], bay_id=bay["stable_id"],
            )
            # Bay3 door physically has one fewer CUTTING circle; equal size
            # MUST NOT let the quantity aggregator invent Q3 for it.
            parts = (
                ("box_body:left_side", _flat("left", hole=True)),
                ("box_body:back", _flat("back", hole=True)),
                ("box_body:right_side", _flat("right", hole=False)),
                ("head", _flat("head", hole=bi < 2)),
                ("tail", _flat("tail", hole=False)),
                ("door_c1_r1", _flat("upper", hole=bi < 2)),
                ("door_c1_r2", _flat("lower", hole=True)),
                ("inner_door:upper:top_frame", _flat("top_frame", hole=False)),
                ("inner_door:upper:left_frame", _flat("left_frame", hole=False)),
                ("inner_door:upper:right_frame", _flat("right_frame", hole=False)),
                ("inner_door:upper:panel", _flat("inner", hole=True)),
                ("divider", _flat("divider", hole=False)),
                ("base_plate", _flat("base", hole=True)),
            )
            rows.extend((ns, key, ns + "__" + key + ".dxf", render)
                        for key, render in parts)
    return tuple(rows)


def test_q_only_same_physical_role_and_all_holes_in_verified_diagnostic(tmp_path,
                                                                         monkeypatch):
    monkeypatch.setattr(
        "ae_engine.receiving_dxf_groups._taipei_output_stamp",
        lambda: "202611071258",
    )
    layout = _three_bays()
    originals = _row_data(layout)
    prior = tuple(tuple(render.scene.primitives)
                  for _, _, _, render in originals)
    with TemporaryDirectory(dir=tmp_path) as stage:
        receipts = commit_verified_receiving_groups(
            layout, "ALL", originals, stage, tmp_path/"manufacturing",
            pre_commit_guard=lambda: None, emit_debug=True,
        )
    assert set(receipts) == {
        "202611071258_p1~p3全部.dxf",
        "202611071258_p1~p3總計.dxf",
        "202611071258_p1~p3debug.dxf",
    }
    assert tuple(tuple(render.scene.primitives) for _, _, _, render in originals) == prior
    manufacture = ezdxf.readfile(receipts["202611071258_p1~p3全部.dxf"])
    assert not manufacture.audit().errors
    assert any(e.dxf.layer == "CUTTING" for e in manufacture.modelspace())
    diagnostic = ezdxf.readfile(receipts["202611071258_p1~p3debug.dxf"])
    assert not diagnostic.audit().errors
    assert all(e.dxf.layer == "CHECK" for e in diagnostic.modelspace())
    texts = [e.plain_text() for e in diagnostic.modelspace()
             if e.dxftype() == "MTEXT"]
    assert "DEBUG ONLY - NOT FOR NC / 只供檢查" in texts
    assert {"盤名 P1", "盤名 P2", "盤名 P3"} <= set(texts)
    assert any(s.startswith("上門 / door_c1_r1  Q2") for s in texts)
    assert any(s.startswith("上門 / door_c1_r1  Q1") for s in texts)
    assert any(s.startswith("左側板 / box_body:left_side  Q3") for s in texts)
    assert any(s.startswith("右側板 / box_body:right_side  Q3") for s in texts)
    assert any(s.startswith("封頭 / head  Q2") for s in texts)
    assert any(s.startswith("封頭 / head  Q1") for s in texts)
    assert any(s.startswith("底板 / base_plate  Q3") for s in texts)
    checks = texts.index("封頭 / head  Q2")
    assert checks < texts.index("盤名 P1")


def test_same_size_but_different_source_layers_or_lock_holes_are_never_summed():
    normal = _flat("left", width=100, height=60)
    no_cut_hole = _flat("left", width=100, height=60, hole=False)
    assert _source_signature_for_quantity(normal) != _source_signature_for_quantity(no_cut_hole)
    assert _role("box_body:left_side") != _role("box_body:right_side")
    rows = [
        ("P1", (("box_body:left_side", normal),)),
        ("P2", (("box_body:left_side", no_cut_hole),)),
    ]
    _scene, quantities = compose_verified_receiving_debug_layout(rows)
    assert sorted(q.count for q in quantities) == [1, 1]


def test_invalid_debug_flag_rejects_before_creating_any_dxf(tmp_path):
    layout = _three_bays()
    with TemporaryDirectory(dir=tmp_path) as stage:
        with pytest.raises(TypeError, match="FLAG_MUST_BE_BOOL"):
            commit_verified_receiving_groups(
                layout, "ALL", _row_data(layout), stage, tmp_path/"out",
                pre_commit_guard=lambda: None, emit_debug="yes",
            )
    assert not tuple(tmp_path.rglob("*.dxf"))


def test_real_left_and_right_baselines_are_different_machining_patterns():
    """Original trusted source DXFs, not guessed 9 identical side holes."""
    from collections import Counter
    from pathlib import Path

    from ae_engine.receiving_panel_baselines import (
        _reference_outline, receiving_piece_baseline_features,
    )

    root = Path(__file__).resolve().parents[1] / "基準檔" / "受電箱"
    signatures = {}
    for role, filename, expected in (
        ("left_side", "左側板.dxf",
         {"CUTTING": 8, "BLIND_HOLE": 1}),
        ("right_side", "右側板.dxf",
         {"CUTTING": 6, "MARKING": 2, "BLIND_HOLE": 1}),
    ):
        path = root / filename
        drawing = ezdxf.readfile(path)
        assert not drawing.audit().errors
        _material, (_ox, _oy, width, height) = _reference_outline(
            drawing.modelspace()
        )
        circles, metadata = receiving_piece_baseline_features(
            role, expected_path=path, width=width, height=height,
        )
        assert Counter(p.layer for p in circles) == expected
        assert metadata["baseline_fit_valid"] is True
        assert metadata["baseline_feature_count"] == 9
        signatures[role] = tuple(sorted(
            (c.layer, round(c.center.x, 5), round(c.center.y, 5),
             round(c.radius, 5)) for c in circles
        ))
    assert signatures["left_side"] != signatures["right_side"]


def test_joint_lock_sources_only_exist_on_actual_mating_bay_sides():
    """Outer side of first/last Bay must not inherit an interior Joint lock."""
    from types import SimpleNamespace
    from ae_engine.receiving_layout import receiving_bay_joint_face_features

    layout = _three_bays()
    stale = SimpleNamespace(source_type="receiving_joint_side_lock")
    for bi in range(3):
        projected = receiving_bay_joint_face_features(
            layout, set_index=0, bay_index=bi,
            thickness=2.0, frame_width=29.0,
            existing={"left": [stale], "right": [stale]},
        )
        left = tuple(p for p in projected.get("left", ())
                     if getattr(p, "source_type", "") == "receiving_joint_side_lock")
        right = tuple(p for p in projected.get("right", ())
                      if getattr(p, "source_type", "") == "receiving_joint_side_lock")
        assert bool(left) is (bi > 0)
        assert bool(right) is (bi < 2)
        assert stale not in left + right



def test_debug_arranges_physical_relatives_not_unrelated_global_rows():
    """Diagnostic view places genuine verified flats by their own role and bounds."""
    from ae_engine.sheetmetal_drawing import DrawingScene, TextPrimitive
    from ae_engine.receiving_verified_debug_dxf import _scene_bounds

    render_by_id = {
        "box_body:left_side": _flat("left", width=110, height=160),
        "box_body:back": _flat("back", width=350, height=210),
        "box_body:right_side": _flat("right", width=120, height=180),
        "head": _flat("head", width=250, height=48, hole=False),
        "tail": _flat("tail", width=190, height=52, hole=False),
        "door_c1_r1": _flat("upper", width=280, height=120),
        "door_c1_r2": _flat("lower", width=230, height=170),
        "inner_door:upper:panel": _flat("inner", width=220, height=170),
        "inner_door:upper:top_frame": _flat("frame_top", width=180, height=25, hole=False),
        "inner_door:upper:left_frame": _flat("frame_left", width=24, height=190, hole=False),
        "inner_door:upper:right_frame": _flat("frame_right", width=32, height=205, hole=False),
        "inner_door:upper:bottom_frame": _flat("frame_bottom", width=200, height=30, hole=False),
        "divider": _flat("divider", width=180, height=35, hole=False),
        "base_plate": _flat("base", width=210, height=90, hole=False),
    }
    # Deliberately shuffled: layout is determined by physical identity, not
    # input enumeration, drawing order, or specimen coordinates.
    keys = (
        "inner_door:upper:right_frame", "tail", "door_c1_r2",
        "inner_door:upper:bottom_frame", "box_body:back", "base_plate",
        "head", "inner_door:upper:left_frame", "door_c1_r1",
        "box_body:right_side", "inner_door:upper:panel",
        "divider", "inner_door:upper:top_frame", "box_body:left_side",
    )
    before = {key: tuple(render.scene.primitives) for key, render in render_by_id.items()}
    scene, quantities = compose_verified_receiving_debug_layout(
        (("P1", tuple((key, render_by_id[key]) for key in keys)),)
    )
    assert len(quantities) == len(keys)
    assert all(p.layer == "CHECK" for p in scene.primitives)
    assert before == {key: tuple(render.scene.primitives) for key, render in render_by_id.items()}

    positioned = {}
    for index, primitive in enumerate(scene.primitives):
        if not isinstance(primitive, TextPrimitive):
            continue
        if primitive.semantic_id != "debug_source_label":
            continue
        for key in keys:
            if primitive.text.startswith(f"{_role(key)} / {key}  Q"):
                count = len(render_by_id[key].scene.primitives)
                translated = DrawingScene(scene.primitives[index + 1:index + 1 + count])
                positioned[key] = _scene_bounds(translated)
                break
    assert set(positioned) == set(keys)

    def center_x(key):
        x0, _y0, x1, _y1 = positioned[key]
        return (x0 + x1) / 2

    def center_y(key):
        _x0, y0, _x1, y1 = positioned[key]
        return (y0 + y1) / 2

    back, head, tail = (positioned[key] for key in (
        "box_body:back", "head", "tail",
    ))
    assert head[1] > back[3]
    assert tail[3] < back[1]
    assert center_x("head") == pytest.approx(center_x("box_body:back"))
    assert center_x("tail") == pytest.approx(center_x("box_body:back"))
    assert positioned["box_body:left_side"][2] < back[0]
    assert positioned["box_body:right_side"][0] > back[2]

    upper, lower = positioned["door_c1_r1"], positioned["door_c1_r2"]
    assert lower[3] < upper[1]
    assert center_x("door_c1_r1") == pytest.approx(center_x("door_c1_r2"))

    inner, upper_frame, lower_frame, left_frame, right_frame = (
        positioned[key] for key in (
            "inner_door:upper:panel", "inner_door:upper:top_frame",
            "inner_door:upper:bottom_frame", "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
        )
    )
    assert upper_frame[1] > inner[3]
    assert lower_frame[3] < inner[1]
    assert left_frame[2] < inner[0]
    assert right_frame[0] > inner[2]
    for key in (
        "inner_door:upper:top_frame", "inner_door:upper:bottom_frame",
    ):
        assert center_x(key) == pytest.approx(center_x("inner_door:upper:panel"))
    for key in (
        "inner_door:upper:left_frame", "inner_door:upper:right_frame",
    ):
        assert center_y(key) == pytest.approx(center_y("inner_door:upper:panel"))
    assert positioned["divider"][3] < inner[1]
    assert positioned["base_plate"][3] < positioned["divider"][1]


def test_debug_keeps_multiple_inner_door_frame_owners_separate():
    from ae_engine.receiving_verified_debug_dxf import _debug_layout_for_panel

    parts = (
        ("inner_door:lower:right_frame", _flat("lower-right", width=19, height=135)),
        ("inner_door:upper:panel", _flat("upper", width=120, height=95)),
        ("inner_door:lower:panel", _flat("lower", width=150, height=110)),
        ("inner_door:upper:top_frame", _flat("upper-top", width=140, height=20)),
        ("inner_door:lower:left_frame", _flat("lower-left", width=18, height=135)),
        ("inner_door:upper:left_frame", _flat("upper-left", width=16, height=115)),
        ("inner_door:lower:top_frame", _flat("lower-top", width=160, height=22)),
        ("inner_door:upper:right_frame", _flat("upper-right", width=17, height=115)),
    )
    placed, _height = _debug_layout_for_panel(parts)
    assert len(placed) == len(parts)
    bounds = {}
    for key, render, x, y in placed:
        from ae_engine.receiving_verified_debug_dxf import _scene_bounds
        x0, y0, x1, y1 = _scene_bounds(render.scene)
        bounds[key] = (x, y, x + x1 - x0, y + y1 - y0)
    assert bounds["inner_door:upper:panel"][1] > bounds["inner_door:lower:panel"][3]
    for owner in ("upper", "lower"):
        panel = bounds[f"inner_door:{owner}:panel"]
        top = bounds[f"inner_door:{owner}:top_frame"]
        left = bounds[f"inner_door:{owner}:left_frame"]
        right = bounds[f"inner_door:{owner}:right_frame"]
        assert top[1] > panel[3]
        assert left[2] < panel[0]
        assert right[0] > panel[2]
    assert _role("box_body:divider:door-grid:H:0:1") == "下框／中隔"
