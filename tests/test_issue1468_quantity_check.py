"""CHECK quantity annotation on actual grouped manufacturing DXF."""
from dataclasses import replace
from pathlib import Path
import re

import ezdxf
import pytest
from shapely.geometry import Point

from ae_engine import manufacturing_api as api
from ae_engine.drawing_annotation_layout import (
    annotate_quantity_render_data, _quantity_text_box, _quantity_obstacles,
)
from ae_engine.dxf_serialization import verify_quantity_check_dxf
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.manufacturing_quantity import PhysicalPartDemand
from ae_engine.manufacturing_render_data import PartRenderData, material_polygon_from_final_scene
from ae_engine.sheetmetal_drawing import DrawingScene, TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2


def render(width=200, height=160, obstacle=None):
    scene = DrawingScene()
    scene.add_polyline(((0, 0), (width, 0), (width, height), (0, height)),
                       layer="CUTTING", closed=True)
    center = (width/2, height/2)
    if obstacle == "hole":
        scene.add_circle(center, 20, layer="CUTTING")
    elif obstacle in {"CUTTING", "BEND", "MARKING", "BLIND_HOLE"}:
        scene.add_line((width/2, 0), (width/2, height), layer=obstacle)
    elif obstacle == "text":
        scene.add(TextPrimitive("KEEP", Vec2(*center), "CHECK", 20, 5, 2))
    elif obstacle == "marking_text":
        scene.add(TextPrimitive("PROCESS", Vec2(*center), "MARKING", 10, 5, 211))
    return PartRenderData(scene, material_polygon_from_final_scene(scene))


def demands(counts=(6, 4), *, data=None):
    data = data or render()
    return tuple(PhysicalPartDemand(str(i), "body", "body", n, 1, data)
                 for i, n in enumerate(counts))


def group(rows):
    parameters = {(r.version_id, r.source_part_id):
                  ManufacturingParameters("STEEL", 2, {"cut": "laser"}) for r in rows}
    return api.group_quantity_physical_demands(rows, parameters)


def q_text(data):
    return [p for p in data.scene.primitives if isinstance(p, TextPrimitive)
            and re.fullmatch(r"[Qq][0-9]+", p.text)]


@pytest.mark.parametrize("quantity", [10, 6, 4, 100])
def test_uppercase_single_q_at_formal_center_and_parser_reopen(quantity, tmp_path):
    source = render()
    result = annotate_quantity_render_data(source, quantity)
    text, = q_text(result)
    assert (text.text, text.layer, text.color, text.attachment_point) == (
        f"Q{quantity}", "CHECK", 2, 5)
    assert text.insert == Vec2(100, 80)
    assert source.material is result.material
    assert result.scene.primitives[:-1] == source.scene.primitives
    assert all(a is b for a, b in zip(result.scene.primitives[:-1], source.scene.primitives))
    groups = group(demands((quantity,), data=source))
    outputs = api.save_quantity_manufacturing_groups_dxf(groups, tmp_path)
    path = outputs[groups[0].key]
    doc = ezdxf.readfile(path)
    text_entities = [e for e in doc.modelspace().query("MTEXT") if e.plain_text().startswith("Q")]
    entity, = text_entities
    assert entity.plain_text() == f"Q{quantity}"
    assert entity.dxf.layer == "CHECK" and entity.dxf.color == 2
    assert doc.layers.get("CHECK").dxf.linetype == "CONTINUOUS"
    verify_quantity_check_dxf(result.scene, path)
    assert api.verify_saved_part_render_data_dxf(result, path).ok


@pytest.mark.parametrize("obstacle", ["hole", "CUTTING", "BEND", "MARKING",
                                    "BLIND_HOLE", "text", "marking_text"])
def test_center_collision_deterministically_avoids_final_primitives(obstacle):
    source = render(obstacle=obstacle)
    before = tuple(source.scene.primitives)
    result = annotate_quantity_render_data(source, 10)
    repeated = annotate_quantity_render_data(source, 10)
    text, = q_text(result)
    assert text.insert != Vec2(100, 80)
    assert repeated.scene.primitives == result.scene.primitives
    box = _quantity_text_box(text)
    assert source.material.covers(box.buffer(1))
    assert not any(box.intersects(item) for item in _quantity_obstacles(before, 1))
    assert source.material is result.material and tuple(source.scene.primitives) == before
    assert all(a is b for a, b in zip(before, result.scene.primitives[:-1]))


def test_replaces_old_check_q_only_and_count_font_layout_never_change_key():
    source = render()
    source.scene.add(TextPrimitive("q999", Vec2(50, 50), "CHECK", 3, 5, 2))
    source.scene.add(TextPrimitive("Q1", Vec2(70, 50), "CHECK", 3, 5, 2))
    unchanged = group(demands(data=source))[0]
    first = annotate_quantity_render_data(source, 10, char_height=15)
    second = annotate_quantity_render_data(first, 100, char_height=8)
    assert [p.text for p in q_text(first)] == ["Q10"]
    assert [p.text for p in q_text(second)] == ["Q100"]
    assert group(demands((100,), data=second))[0].key == unchanged.key
    assert unchanged.filename == group(demands((100,), data=second))[0].filename
    assert first.material is second.material is source.material


def test_real_6_plus_4_head_holes_and_shared_tail_have_q10_q6_q4(tmp_path):
    body, tail = render(), render(180, 150)
    a, b = render(180, 140), render(180, 140)
    a.scene.add_circle((50, 50), 5, layer="CUTTING")
    b.scene.add_circle((60, 50), 5, layer="CUTTING")
    a = replace(a, material=material_polygon_from_final_scene(a.scene))
    b = replace(b, material=material_polygon_from_final_scene(b.scene))
    rows = tuple(PhysicalPartDemand(v, name, name, count, 1, data)
                 for v, count, head in (("a", 6, a), ("b", 4, b))
                 for name, data in (("body", body), ("head", head), ("tail", tail)))
    groups = group(rows)
    outputs = api.save_quantity_manufacturing_groups_dxf(groups, tmp_path)
    assert len(outputs) == 4
    labels = []
    for g in groups:
        data = annotate_quantity_render_data(g.render_data, g.quantity)
        verify_quantity_check_dxf(data.scene, outputs[g.key])
        labels.append(q_text(data)[0].text)
    assert sorted(labels) == ["Q10", "Q10", "Q4", "Q6"]


def test_no_readable_space_fails_before_io_and_preserves_existing_bytes(tmp_path):
    tiny = render(3, 3)
    target = tmp_path / "operator.dxf"
    target.write_bytes(b"existing operator output")
    with pytest.raises(ValueError, match="no legal readable position"):
        api.save_quantity_manufacturing_groups_dxf(group(demands(data=tiny)), tmp_path)
    assert target.read_bytes() == b"existing operator output"
    assert set(p.name for p in tmp_path.iterdir()) == {"operator.dxf"}
    # Large material fully occupied by existing engineering text is also illegal.
    blocked = render()
    blocked.scene.add(TextPrimitive("BUSY"*20, Vec2(100,80), "MARKING", 400, 5, 211))
    with pytest.raises(ValueError, match="no legal readable position"):
        annotate_quantity_render_data(blocked, 10)


@pytest.mark.parametrize("corruption", ["lowercase", "count", "color", "position",
                                       "linetype", "duplicate"])
def test_staged_q_corruption_never_replaces_existing_dxf(corruption, tmp_path, monkeypatch):
    groups = group(demands())
    outputs = api.save_quantity_manufacturing_groups_dxf(groups, tmp_path)
    path = Path(outputs[groups[0].key])
    before = path.read_bytes()
    original = api.save_part_render_data_dxf
    def save(data, output, **kw):
        result = original(data, output, **kw)
        doc = ezdxf.readfile(result)
        entity, = [e for e in doc.modelspace().query("MTEXT") if e.plain_text() == "Q10"]
        if corruption == "lowercase":
            entity.text = "q10"
        elif corruption == "count":
            entity.text = "Q11"
        elif corruption == "color":
            entity.dxf.color = 3
        elif corruption == "position":
            entity.dxf.insert = (9999, 9999)
        elif corruption == "linetype":
            doc.layers.get("CHECK").dxf.linetype = "CENTER"
        else:
            doc.modelspace().add_mtext("Q10", dxfattribs={"layer": "CHECK"})
        doc.saveas(result)
        return result
    monkeypatch.setattr(api, "save_part_render_data_dxf", save)
    with pytest.raises(ValueError, match="quantity CHECK|manufacturing DXF verification"):
        api.save_quantity_manufacturing_groups_dxf(groups, tmp_path, overwrite=True)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".whd-*"))


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5])
def test_invalid_quantity_is_rejected(quantity):
    with pytest.raises(ValueError, match="positive integer"):
        annotate_quantity_render_data(render(), quantity)

def test_mirrored_external_check_note_stays_outside_and_q_is_centered():
    from ae_engine.sheetmetal_drawing import mirror_drawing_scene_y
    source = render(422, 300)
    source.scene.add(TextPrimitive("LONG NOTE\n"*8, Vec2(211,350), "CHECK", 30, 8))
    source.scene.add(TextPrimitive("PROCESS", Vec2(30,30), "MARKING", 5, 8, 211))
    scene = mirror_drawing_scene_y(source.scene,300)
    note, = [p for p in scene.primitives if isinstance(p, TextPrimitive) and p.layer == "CHECK"]
    marking, = [p for p in scene.primitives if isinstance(p, TextPrimitive) and p.layer == "MARKING"]
    assert note.insert == Vec2(211,-50) and note.attachment_point == 2
    assert marking.attachment_point == 8
    material = material_polygon_from_final_scene(scene)
    assert not _quantity_text_box(note).intersects(material)
    result = annotate_quantity_render_data(replace(source, scene=scene, material=material),20)
    assert q_text(result)[0].insert == Vec2(211,150)


def test_actual_gui_quantity_output_contains_custom_q100_and_split_heads(tmp_path, monkeypatch):
    from tests.test_issue1467_quantity_dxf_groups import (
        test_actual_gui_output_uses_all_quantity_versions_and_custom_physical_demands,
    )
    test_actual_gui_output_uses_all_quantity_versions_and_custom_physical_demands(tmp_path, monkeypatch)
    labels = []
    for path in tmp_path.glob("*.dxf"):
        rows = [e for e in ezdxf.readfile(path).modelspace().query("MTEXT")
                if re.fullmatch(r"[Qq][0-9]+", e.plain_text())]
        entity, = rows
        assert entity.dxf.layer == "CHECK" and entity.dxf.color == 2
        labels.append(entity.plain_text())
    assert labels.count("Q100") == 1
    assert "Q20" in labels and "Q30" in labels
    assert all(label.startswith("Q") for label in labels)
