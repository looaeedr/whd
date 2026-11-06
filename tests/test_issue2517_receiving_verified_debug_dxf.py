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
