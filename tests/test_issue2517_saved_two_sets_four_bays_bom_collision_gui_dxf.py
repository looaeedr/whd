"""#2517 two genuine Receiving Sets × two Bays: physical BOM, 3D audit and GUI DXF.

These are independent real committed numeric-CSV NFB Bays, persisted as one
project. The Engine owns the physical inventory, Set/Bay identity, world
placement, manufacturing eligibility and collision diagnostic. An unresolved
collision is reported, never promoted to whole-cabinet manufacturing approval.
"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_export import resolved_physical_render_parts
from ae_engine.receiving_layout import (
    receiving_bay_assembly_offsets, resize_receiving_bays,
    resize_receiving_sets, update_receiving_bay,
)
from gui_modules.project import export_actions as gui
import phase6_project_file as project
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _provider
from tests.test_issue1502_multibay_original_gui_export_integration import (
    _native_callback_host,
)


BAY_INDICES = ((0, 0), (0, 1), (1, 0), (1, 1))
PHYSICAL_SIDES = {"box_body:left_side", "box_body:back", "box_body:right_side"}


def _saved_two_sets(tmp_path):
    source = _multi()
    original_layout = source["receiving_layout"]
    assert len(original_layout["sets"]) == 1
    layout = resize_receiving_sets(original_layout, set_count=2)
    # A Set's switch brand is operator authority; it is not a cloned first
    # Set identity. Use the same already-confirmed real numeric CSV brand.
    layout["sets"][1]["switch_brand"] = "士林"
    layout = resize_receiving_bays(layout, set_index=1, bay_count=2)
    for bi in (0, 1):
        # The existing Engine writer must own each submitted Bay's stable
        # identity. A copy's old X datum is not itself a new confirmation.
        config = deepcopy(original_layout["sets"][0]["bays"][0]["nfb_config"])
        config["holes"][0]["manual_x_mm"] += 40.0 + bi * 20.0
        layout = update_receiving_bay(
            layout, set_index=1, bay_index=bi,
            nfb_config_submitted=True, nfb_config=config,
        )
    source["receiving_layout"] = layout
    before = deepcopy(source)
    saved = project.write_project(
        tmp_path / "receiving-two-sets-four-bays.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    unchanged = saved.read_bytes()
    restored = project.read_project(saved)["snapshot"]
    assert source == before and saved.read_bytes() == unchanged
    assert restored["active_mode"] == "set_bay"
    assert len(restored["receiving_layout"]["sets"]) == 2
    assert [len(s["bays"]) for s in restored["receiving_layout"]["sets"]] == [2, 2]
    assert [bay["stable_id"] for s in restored["receiving_layout"]["sets"]
            for bay in s["bays"]] == [
        bay["stable_id"] for s in layout["sets"] for bay in s["bays"]
    ]
    assert [bay["panel_name"] for s in restored["receiving_layout"]["sets"]
            for bay in s["bays"]] == [
        bay["panel_name"] for s in layout["sets"] for bay in s["bays"]
    ]
    assert all(bay["nfb_config_submitted"] is True
               for s in restored["receiving_layout"]["sets"] for bay in s["bays"])
    return saved, unchanged, source, restored


def _engine_four_bay_witness(authored, loaded):
    old, old_calls = _provider(authored)
    new, new_calls = _provider(loaded)
    full_bom = {}
    released = {}
    collisions = {}
    world_offsets = {}
    for si, bi in BAY_INDICES:
        previous = old(si, bi)
        scene = new(si, bi)
        assert {p.part_key for p in previous.parts} == {
            p.part_key for p in scene.parts
        }
        old_full = dict(resolved_physical_render_parts(
            previous, include_unreleased_source_flats=True,
        ))
        new_full = dict(resolved_physical_render_parts(
            scene, include_unreleased_source_flats=True,
        ))
        assert set(old_full) == set(new_full)
        assert PHYSICAL_SIDES <= set(new_full)
        for key in new_full:
            assert old_full[key].material.equals(new_full[key].material), key
            assert old_full[key].scene == new_full[key].scene, key
            assert old_full[key].fold_guides == new_full[key].fold_guides, key

        old_release = dict(resolved_physical_render_parts(previous))
        new_release = dict(resolved_physical_render_parts(scene))
        assert set(old_release) == set(new_release)
        assert set(new_release) <= set(new_full)
        namespace = api.receiving_manufacturing_instance_namespace(
            set_id=loaded["receiving_layout"]["sets"][si]["stable_id"],
            bay_id=loaded["receiving_layout"]["sets"][si]["bays"][bi]["stable_id"],
        )
        assert namespace not in full_bom
        full_bom[namespace] = frozenset(new_full)
        released[namespace] = frozenset(new_release)

        dims = (loaded["w"], loaded["h"], loaded["d"])
        before_3d = api.resolve_box_body_true_world_piece_meshes(
            previous.part("box_body"), dimensions=dims,
            thickness=loaded["t"],
        )
        after_3d = api.resolve_box_body_true_world_piece_meshes(
            scene.part("box_body"), dimensions=dims,
            thickness=loaded["t"],
        )
        assert len(before_3d) == len(after_3d) == 3
        assert all(triangles for _, triangles in after_3d)
        assert before_3d == after_3d

        # Public Engine collision display, not a GUI-calculated "safe" flag:
        # check all three physical BoxBody sheets plus the actual Head/Tail.
        before_audit = api.project_assembly_collision_display_audit(
            previous.parts, dims, loaded["t"],
            visible_part_keys={"box_body", "head", "tail"},
        )
        after_audit = api.project_assembly_collision_display_audit(
            scene.parts, dims, loaded["t"],
            visible_part_keys={"box_body", "head", "tail"},
        )
        assert after_audit == before_audit
        assert PHYSICAL_SIDES <= set(after_audit.visible_keys)
        assert after_audit.evaluated_pair_count == (
            len(after_audit.visible_keys) * (len(after_audit.visible_keys) - 1) // 2
        )
        collisions[namespace] = after_audit

        world = receiving_bay_assembly_offsets(
            loaded["receiving_layout"], set_index=si,
        )[bi]
        projected = api.project_receiving_bay_preview_assembly_members(
            loaded["receiving_layout"], scene.parts, set_index=si, bay_index=bi,
        )
        assert projected.bay_offset == world
        assert projected.part_placements
        world_offsets[(si, bi)] = world

    # Four distinct physical owners, same locally reusable part roles.
    assert len(full_bom) == len(released) == len(collisions) == 4
    assert all(PHYSICAL_SIDES <= part_keys for part_keys in full_bom.values())
    assert world_offsets[(0, 0)] == world_offsets[(1, 0)] == (0.0, 0.0, 0.0)
    assert world_offsets[(0, 1)][0] > 0 and world_offsets[(1, 1)][0] > 0
    assert old_calls == new_calls == list(BAY_INDICES)
    return full_bom, released, collisions


def _original_gui_export(monkeypatch, source, output):
    output.mkdir()
    previewed = []
    host = _native_callback_host(monkeypatch, source, previewed)
    host.baseline_var = SimpleNamespace(get=lambda: "受電箱")
    errors, successes = [], []
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_kw: str(output))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: errors.append((title, detail)))
    monkeypatch.setattr(gui.messagebox, "showwarning",
                        lambda title, detail: errors.append((title, detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: successes.append((title, detail)))
    monkeypatch.setattr(gui.messagebox, "askyesno",
                        lambda *_a, **_kw: pytest.fail("unexpected partial release"))
    gui.export_selected_dxf(host)
    return previewed, errors, successes


def test_saved_two_sets_four_bay_full_physical_bom_world_audit_and_gui_dxf(
    tmp_path, monkeypatch,
):
    saved, original_bytes, authored, loaded = _saved_two_sets(tmp_path)
    full, released, collision = _engine_four_bay_witness(authored, loaded)
    assert len(set(full)) == 4
    assert all(len(parts) > 3 for parts in full.values())
    assert all(len(released[ns]) <= len(full[ns]) for ns in full)

    out = tmp_path / "original-gui-two-sets"
    calls, errors, successes = _original_gui_export(monkeypatch, loaded, out)
    assert not errors, errors
    assert len(successes) == 1
    assert calls == list(BAY_INDICES)
    dxfs = tuple(sorted(out.glob("*.dxf")))
    assert len(dxfs) >= 40
    assert len(dxfs) == len({p.name for p in dxfs})
    for namespace in full:
        scoped = tuple(p for p in dxfs if namespace in p.name)
        assert scoped, namespace
        assert sum("fixing_plate" in p.name for p in scoped) == 2
        assert sum("base_plate" in p.name and "fixing_plate" not in p.name
                   for p in scoped) == 1
        assert sum("inner_door" in p.name and "panel" in p.name
                   for p in scoped) == 1
        assert sum("left_side" in p.name for p in scoped) == 1
        assert sum("right_side" in p.name for p in scoped) == 1
        assert namespace in collision and collision[namespace].pairs
    for physical in dxfs:
        doc = ezdxf.readfile(physical)
        assert not doc.audit().errors, physical.name
        assert any(e.dxf.layer == "CUTTING" for e in doc.modelspace())
    assert saved.read_bytes() == original_bytes


def test_saved_second_set_missing_nfb_cannot_borrow_first_set_or_release_batch(
    tmp_path, monkeypatch,
):
    saved, original_bytes, _authored, loaded = _saved_two_sets(tmp_path)
    bad = deepcopy(loaded)
    bay = bad["receiving_layout"]["sets"][1]["bays"][1]
    assert bay["nfb_config_submitted"] is True
    bay["nfb_config"]["holes"][0]["model_filename"] = (
        "nfbv5:士林:SOURCE-NOT-FOUND-SECOND-SET"
    )
    out = tmp_path / "invalid-second-set"
    _calls, errors, successes = _original_gui_export(monkeypatch, bad, out)
    assert errors and not successes
    assert not list(out.iterdir())
    assert saved.read_bytes() == original_bytes
