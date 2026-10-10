"""Actual machining equality, stable groups, atomic DXF and operator export."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.manufacturing_quantity import PhysicalPartDemand
from ae_engine.manufacturing_render_data import PartRenderData, material_polygon_from_final_scene
from ae_engine.sheetmetal_drawing import DrawingScene, TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2


def render(width=20, height=30, *, hole=None, bend=None, marking=None, check=None):
    scene = DrawingScene()
    scene.add_polyline(((0, 0), (width, 0), (width, height), (0, height)),
                       layer="CUTTING", closed=True)
    if hole is not None:
        scene.add_circle(hole, 1, layer="CUTTING")
    if bend is not None:
        scene.add_line((bend, 0), (bend, height), layer="BEND")
    if marking is not None:
        scene.add(TextPrimitive(marking, Vec2(4, 4), "MARKING", 1, 5, 211))
    if check is not None:
        scene.add(TextPrimitive(check, Vec2(2, 2), "CHECK", 1, 5, 2))
    return PartRenderData(scene, material_polygon_from_final_scene(scene))


def row(version, physical, count, data, per_box=1):
    return PhysicalPartDemand(version, physical, physical, count, per_box, data)


def parameters(rows, *, material="STEEL", thickness=2, process=None):
    return {(r.version_id, r.source_part_id):
            ManufacturingParameters(material, thickness, process or {"cut": "laser"})
            for r in rows}


def groups(rows, **kw):
    return api.group_quantity_physical_demands(rows, parameters(rows, **kw))


def test_body_5_two_head_hole_groups_3_and_2_and_shared_tail_5():
    body, tail = render(), render(10, 11)
    head_a, head_b = render(10, 12, hole=(2, 2)), render(10, 12, hole=(3, 2))
    rows = (row("a", "box_body", 3, body), row("b", "box_body", 2, body),
            row("a", "head", 3, head_a), row("b", "head", 2, head_b),
            row("a", "tail", 3, tail), row("b", "tail", 2, tail))
    result = groups(rows)
    assert len(result) == 4
    totals = {(tuple(sorted({r.physical_id for r in g.members})), g.quantity)
              for g in result}
    assert totals == {(("box_body",), 5), (("head",), 3), (("head",), 2), (("tail",), 5)}


def test_custom_30_plus_20_each_two_sheets_is_one_group_100():
    data = render()
    rows = (row("a", "custom:1", 30, data, 2), row("b", "custom:1", 20, data, 2))
    result = groups(rows)
    assert len(result) == 1 and result[0].quantity == 100
    # Different physical names never prevent true manufacturing equivalence.
    more = (*rows, row("c", "another_part", 7, data))
    assert groups(more)[0].quantity == 107


@pytest.mark.parametrize("difference", ["hole", "bend", "marking", "material", "thickness", "process"])
def test_same_outline_and_hole_count_cannot_hide_machining_differences(difference):
    first = render(hole=(4, 4), bend=10, marking="A")
    second = render(hole=(5 if difference == "hole" else 4, 4),
                    bend=11 if difference == "bend" else 10,
                    marking="B" if difference == "marking" else "A")
    rows = (row("a", "head", 3, first), row("b", "head", 2, second))
    params = parameters(rows)
    if difference in {"material", "thickness", "process"}:
        change = {"material": "ALUMINUM"} if difference == "material" else (
            {"thickness": 3} if difference == "thickness" else {"process": {"cut": "waterjet"}})
        params[("b", "head")] = replace(params[("b", "head")], **change)
    assert len(api.group_quantity_physical_demands(rows, params)) == 2


def test_check_q_order_and_ring_origin_do_not_enter_machining_key():
    a, b = render(check="Q3", hole=(4, 4), bend=10), render(check="q900", hole=(4, 4), bend=10)
    outline = b.scene.primitives[0]
    points = outline.points
    b.scene.primitives[0] = replace(outline, points=tuple(reversed(points[2:] + points[:2])))
    b.scene.primitives.reverse()
    rows = (row("a", "one", 3, a), row("b", "two", 2, b))
    result = groups(rows)
    assert len(result) == 1 and result[0].quantity == 5
    assert result[0].key == groups((rows[0],))[0].key
    float_params = parameters(rows, thickness=2.0)
    assert api.group_quantity_physical_demands(rows, float_params)[0].key == result[0].key


def test_inserting_version_or_changing_quantity_does_not_rename_unrelated_groups():
    a, b = row("a", "head", 3, render(hole=(3, 3))), row("b", "head", 2, render(hole=(5, 3)))
    before = {g.key: g.filename for g in groups((a, b))}
    inserted = row("middle", "head", 7, render(hole=(7, 3)))
    after = {g.key: g.filename for g in groups((replace(b, piece_count=100), inserted, a))}
    assert all(after[key] == filename for key, filename in before.items())
    assert [g.key for g in groups((a, b))] == [g.key for g in groups((b, a))]


def test_collision_and_missing_parameters_fail_before_export(monkeypatch, tmp_path):
    import ae_engine.manufacturing_equivalence as equivalence
    rows = (row("a", "head", 3, render()), row("b", "head", 2, render(hole=(4, 4))))
    with pytest.raises(KeyError):
        api.group_quantity_physical_demands(rows, {})
    class Digest:
        def hexdigest(self):
            return "0" * 64
    monkeypatch.setattr(equivalence.hashlib, "sha256", lambda value: Digest())
    with pytest.raises(ValueError, match="collision"):
        groups(rows)
    assert not list(tmp_path.iterdir())


def test_saved_group_dxfs_reopen_exact_physical_render_and_serialize_once(tmp_path, monkeypatch):
    rows = (row("a", "head", 3, render(hole=(3, 3))),
            row("b", "head", 2, render(hole=(5, 3))),
            row("a", "tail", 3, render(10, 11)),
            row("b", "tail", 2, render(10, 11)))
    result = groups(rows)
    original = api.save_part_render_data_dxf
    seen = []
    def save(data, path, **kw):
        seen.append(data)
        return original(data, path, **kw)
    monkeypatch.setattr(api, "save_part_render_data_dxf", save)
    outputs = api.save_quantity_manufacturing_groups_dxf(result, tmp_path)
    assert len(seen) == len(result) == len(outputs) == len(list(tmp_path.glob("*.dxf")))
    for group in result:
        assert api.verify_saved_part_render_data_dxf(group.render_data, outputs[group.key]).ok
    assert not list(tmp_path.glob(".whd-*"))


@pytest.mark.parametrize("failure", ["serialization", "commit"])
def test_atomic_serialization_and_commit_failure_restore_original_bytes(failure, tmp_path, monkeypatch):
    import ae_engine.manufacturing_export as export
    result = groups((row("a", "head", 3, render(hole=(3, 3))),
                     row("b", "head", 2, render(hole=(5, 3)))))
    outputs = api.save_quantity_manufacturing_groups_dxf(result, tmp_path)
    before = {name: Path(path).read_bytes() for name, path in outputs.items()}
    if failure == "serialization":
        original = api.save_part_render_data_dxf
        calls = []
        def save(data, path, **kw):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected serialization failure")
            return original(data, path, **kw)
        monkeypatch.setattr(api, "save_part_render_data_dxf", save)
    else:
        original = export.os.replace
        failed = []
        def move(source, destination):
            if (not failed and Path(source).parent.name.startswith(".whd-dxf-stage-")
                    and Path(destination).name == result[1].filename):
                failed.append(True)
                raise OSError("injected commit failure")
            return original(source, destination)
        monkeypatch.setattr(export.os, "replace", move)
    with pytest.raises(OSError, match="injected"):
        api.save_quantity_manufacturing_groups_dxf(result, tmp_path, overwrite=True)
    assert {name: Path(path).read_bytes() for name, path in outputs.items()} == before
    assert not list(tmp_path.glob(".whd-*"))


def test_actual_gui_output_uses_all_quantity_versions_and_custom_physical_demands(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from gui_modules.project.export_actions import _export_selected_parts
    from phase6_manufacturing_adapter import (build_manufacturing_request,
        build_scene_payload_for_app, operator_finished_dimensions_for_app)
    from phase6_quantity_manufacturing import resolve_quantity_manufacturing, quantity_manufacturing_groups
    root = tk.Tk()
    root.withdraw()
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("金庫型")
        root.update()
        designer = main.open_original_fold_designer()
        root.update()
        ws = designer.designer_workspace
        custom = ws.add_custom_part(display_name="加強板", fold_axis="X",
                                    transverse_length=234, per_box_count=2)
        controls = designer.receiving_mode_controls.quantity_editor
        controls.count_var.set("30")
        assert controls.commit_count()
        controls.add()
        second = ws.quantity_model.selected_version_id
        controls.count_var.set("20")
        assert controls.commit_count()
        ws.quantity_model.set_version_features(second, "head",
            [CircleFeature(8, FeatureAnchor.PANEL_CENTER, Vec2(10, 0))])
        root.update()
        before = deepcopy(ws.snapshot())
        def legacy_selected_resolver():
            raise AssertionError("quantity Output must not export just the selected version")
        monkeypatch.setattr(designer, "_phase6_resolve_manufacturing_geometry", legacy_selected_resolver)
        flags = {key: True for key in ("box_body", "head", "tail", "door", "base_plate",
                                      "indicator_box", "indicator_door")}
        exported, problems = _export_selected_parts(main, str(tmp_path), {}, flags, False)
        assert not problems, problems
        assert exported and all(name.startswith("part_") for name in exported)
        assert len(exported) == len(set(exported)) == len(list(tmp_path.glob("*.dxf")))
        request = build_manufacturing_request(
            designer, scene_payload_builder=lambda key: build_scene_payload_for_app(designer, key),
            render_data_provider=designer._scene_query_callback,
            part_spec_provider=designer._part_spec_query_callback,
            finished_dimensions_provider=lambda key=None: operator_finished_dimensions_for_app(designer, key))
        batch = resolve_quantity_manufacturing(request, ws.snapshot())
        result = quantity_manufacturing_groups(batch)
        assert set(exported) == {g.filename for g in result}
        custom_groups = [g for g in result if any(r.source_part_id == custom for r in g.members)]
        assert len(custom_groups) == 1 and custom_groups[0].quantity == 100
        head_groups = [g for g in result if any(r.source_part_id == "head" for r in g.members)]
        assert len(head_groups) == 2 and sorted(g.quantity for g in head_groups) == [20, 30]
        for group in result:
            assert api.verify_saved_part_render_data_dxf(group.render_data, tmp_path / group.filename).ok
        assert ws.snapshot() == before
        assert not errors, errors
    finally:
        root.destroy()



def test_corrupt_staged_dxf_never_replaces_existing_output(tmp_path, monkeypatch):
    result = groups((row("a", "head", 3, render()),))
    outputs = api.save_quantity_manufacturing_groups_dxf(result, tmp_path)
    path = Path(outputs[result[0].key])
    before = path.read_bytes()
    import ezdxf
    def corrupt(data, destination, **kw):
        ezdxf.new("R2010").saveas(destination)
        return str(destination)
    monkeypatch.setattr(api, "save_part_render_data_dxf", corrupt)
    with pytest.raises(ValueError, match="staged manufacturing DXF verification failed"):
        api.save_quantity_manufacturing_groups_dxf(result, tmp_path, overwrite=True)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".whd-*"))
