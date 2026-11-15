"""#2517: real .p6fold EAR side GUI → Engine 2D/3D → DXF roundtrip parity.

EAR SIDE CHECK and SIDE-only approved MARKING remain distinct from EAR
standalone fabrication, welding/NC or complete cabinet manufacturing.
No production Engine API is mocked; only the Tk chooser/message surfaces
are replaced by headless test sinks.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.assembly_geometry import build_joint_world_geometry
from ae_engine.manufacturing_scene_access import owner_render_data
from ae_engine.receiving_layout import new_receiving_layout, update_receiving_bay
from ae_engine.receiving_fixed_plate_weld_skin_mating import (
    resolve_receiving_ear_side_skin_mating_witnesses,
)
from gui_modules.project import export_actions as gui
import phase6_project_file as project
from tests.test_issue1050_receiving_mother_plate_marking import (
    _full_receiving_geometry,
)
from tests.test_issue1503_ear_side_check_gui_e2e_save_reload import (
    _marking_signature,
)
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_issue1503_side_only_mfg_gui import _host
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


SIDES = ("box_body:left_side", "box_body:right_side")
DIMS = (800.0, 1600.0, 350.0)


def _source_after_real_save_reload(tmp_path, *, factory=_assembled, ear_count=2):
    original, _prototype_geometry = _actual(factory)
    # The old signed-contact fixture carried an intentionally schema-less
    # in-memory NFB layout; a real saved project must instead commit its
    # physical Set1/Bay1 through the public Engine layout transaction.
    # Keep the exact same submitted NFB, switch brand, dimensions, Door and
    # side-contact source. Never weaken real .p6fold schema validation.
    saved_layout = original["receiving_layout"]
    layout = new_receiving_layout(
        width=original["w"], height=original["h"], depth=original["d"],
    )
    layout["sets"][0]["switch_brand"] = saved_layout["sets"][0]["switch_brand"]
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True,
        nfb_config=deepcopy(original["nfb_config"]),
    )
    original["receiving_layout"] = layout
    # Source normalization adds canonical neutral per-hole fields to the
    # committed Bay. The root/active operator projection must consume that
    # EXACT saved NFB row; otherwise Engine correctly rejects identity drift
    # before any physical EAR contact (not a codec or manufacturing bug).
    original["nfb_config"] = deepcopy(
        layout["sets"][0]["bays"][0]["nfb_config"]
    )
    original["_receiving_runtime_selection"] = {
        "set_index": 0,
        "bay_index": 0,
        "set_id": layout["sets"][0]["stable_id"],
        "bay_id": layout["sets"][0]["bays"][0]["stable_id"],
    }
    original_geometry = _full_receiving_geometry(original)
    retained = deepcopy(original)
    project_path = project.write_project(
        tmp_path / "receiving-ear-signed-side.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    assert project_path.is_file() and project_path.stat().st_size > 0
    saved_bytes = project_path.read_bytes()
    reopened = project.read_project(project_path)["snapshot"]
    assert original == retained
    assert reopened["model"] == "受電箱"
    assert reopened["nfb_config_submitted"] is True
    # The authoritative project codec fills neutral per-hole operator fields
    # omitted by the old in-memory helper. Compare actual physical NFB hole
    # identities and confirm neutral defaults, not raw dict shape.
    def physical_nfb(config):
        return (
            config["layer_count"],
            tuple((
                row["physical_hole_id"],
                row["model_filename"],
                row["slot_index"],
            ) for row in config["holes"]),
        )
    assert physical_nfb(reopened["nfb_config"]) == physical_nfb(original["nfb_config"])
    assert all(
        row["manual_x_state"] == "NONE" and row["rotation_deg"] == 0
        for row in reopened["nfb_config"]["holes"]
    )
    assert reopened["w"] == original["w"] == DIMS[0]
    assert reopened["h"] == original["h"] == DIMS[1]
    assert reopened["d"] == original["d"] == DIMS[2]
    assert reopened["t"] == original["t"] == 2.0
    assert project_path.read_bytes() == saved_bytes

    restored_geometry = _full_receiving_geometry(reopened)
    assert {row.part_key for row in original_geometry.parts} == {
        row.part_key for row in restored_geometry.parts
    }
    for owner in SIDES:
        old = owner_render_data(original_geometry, owner)
        new = owner_render_data(restored_geometry, owner)
        assert old is not None and new is not None
        assert new.material.equals(old.material)
        assert new.fold_guides == old.fold_guides
        assert new.scene == old.scene
        assert {"CUTTING", "BEND"} <= {
            p.layer for p in new.scene.primitives
        }

    worlds = tuple(build_joint_world_geometry(
        geo.parts, DIMS, 2.0,
    ) for geo in (original_geometry, restored_geometry))
    for owner in SIDES:
        assert worlds[0]["mapped_skin_triangles_by_part"][owner]
        assert (worlds[0]["mapped_skin_triangles_by_part"][owner]
                == worlds[1]["mapped_skin_triangles_by_part"][owner])

    witnesses = tuple(resolve_receiving_ear_side_skin_mating_witnesses(
        snap, world_geometry=world,
    ) for snap, world in zip((original, reopened), worlds))
    assert witnesses[0] == witnesses[1]
    assert len(witnesses[1]) == ear_count
    assert len({row.ear_part_id for row in witnesses[1]}) == ear_count
    assert [row.side_piece_id for row in witnesses[1]] == list(SIDES) * (ear_count // 2)
    assert [row.nfb_layer_index for row in witnesses[1]] == (
        [0, 0, 1, 1] if ear_count == 4 else [0, 0]
    )
    for row in witnesses[1]:
        assert row.full_contact_material_coverage_verified
        assert row.flange_skin_normal_opposed
        assert not row.manufacturing_ready
        assert not row.welding_workmanship_certified
    return project_path, saved_bytes, original, original_geometry, reopened, restored_geometry


def _gui_export(monkeypatch, snapshot, geometry, folder, *, mode):
    folder.mkdir()
    host, events = _host(snapshot, geometry)
    host.get_float_values = lambda: {
        key: snapshot[key] for key in ("w", "h", "d", "t", "fw")
    }
    host.baseline_var = SimpleNamespace(get=lambda: snapshot["model"])
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_kwargs: str(folder))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: events.append(("success", detail)))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: events.append(("error", detail)))
    action = (gui.export_receiving_ear_side_manufacturing_dxf
              if mode == "marking" else gui.export_receiving_ear_side_check_dxf)
    result = action(host)
    return result, events


def _reopened_layers(paths):
    layouts = {}
    for owner, filename in paths:
        assert owner in SIDES and Path(filename).is_file()
        doc = ezdxf.readfile(filename)
        assert not doc.audit().errors
        layers = Counter(entity.dxf.layer for entity in doc.modelspace())
        assert all(layers[layer] > 0 for layer in ("CUTTING", "BEND", "MARKING"))
        layouts[owner] = layers
    assert set(layouts) == set(SIDES)
    return layouts


@pytest.mark.parametrize("factory,ear_count", (
    pytest.param(_assembled, 2, id="one-tier"),
    pytest.param(_two_tier, 4, id="two-tier"),
))
@pytest.mark.parametrize("mode", ("check", "marking"))
def test_saved_real_ear_side_rebuilt_gui_2d_3d_dxf_equivalent(
    tmp_path, monkeypatch, mode, factory, ear_count,
):
    (saved_path, saved_bytes, before, before_geo, after, after_geo) = (
        _source_after_real_save_reload(
            tmp_path, factory=factory, ear_count=ear_count,
        )
    )
    original_saved = deepcopy(before)
    restored_saved = deepcopy(after)
    b, events_b = _gui_export(
        monkeypatch, before, before_geo, tmp_path / f"{mode}-before",
        mode=mode,
    )
    a, events_a = _gui_export(
        monkeypatch, after, after_geo, tmp_path / f"{mode}-reloaded",
        mode=mode,
    )
    assert b is not None, events_b
    assert a is not None, events_a
    assert [e[0] for e in events_b if isinstance(e, tuple)] == ["success"]
    assert [e[0] for e in events_a if isinstance(e, tuple)] == ["success"]
    assert len(b.output_paths) == len(a.output_paths) == 2
    assert _reopened_layers(b.output_paths) == _reopened_layers(a.output_paths)
    assert _marking_signature(b.output_paths) == _marking_signature(a.output_paths)
    assert all(
        len(lines) == 3 * (ear_count // 2)
        for lines in _marking_signature(a.output_paths).values()
    )
    assert b.marking_lines_verified == a.marking_lines_verified
    if mode == "check":
        assert len(b.part_ids) == len(a.part_ids) == ear_count
        assert b.saved_dxf_roundtrip_verified
        assert a.saved_dxf_roundtrip_verified
        assert b.manufacturing_ready is a.manufacturing_ready is False
    else:
        assert b.side_only_manufacturing_marking_verified
        assert a.side_only_manufacturing_marking_verified
        assert len(b.physical_ear_ids) == len(a.physical_ear_ids) == ear_count
        assert b.whole_cabinet_manufacturing_ready is False
        assert a.whole_cabinet_manufacturing_ready is False
    assert before == original_saved and after == restored_saved
    assert saved_path.read_bytes() == saved_bytes


@pytest.mark.parametrize("factory,ear_count", (
    pytest.param(_assembled, 2, id="one-tier"),
    pytest.param(_two_tier, 4, id="two-tier"),
))
@pytest.mark.parametrize("mode", ("check", "marking"))
def test_saved_ear_side_unsubmitted_snapshot_cannot_export_old_geometry(
    tmp_path, monkeypatch, mode, factory, ear_count,
):
    (saved_path, original_bytes, _before, _before_geo,
     after, after_geo) = _source_after_real_save_reload(
        tmp_path, factory=factory, ear_count=ear_count,
    )
    tampered = deepcopy(after)
    tampered["nfb_config_submitted"] = False
    folder = tmp_path / f"{mode}-rejected"
    # The original real Engine 2D/3D was resolved from a submitted NFB.
    # Withdrawing submission after reload must reject before folder selection
    # or writing any approved physical CHECK/MARKING DXF.
    host, events = _host(tampered, after_geo)
    host.baseline_var = SimpleNamespace(get=lambda: "受電箱")
    host.get_float_values = lambda: {
        key: tampered[key] for key in ("w", "h", "d", "t", "fw")
    }
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_kwargs: pytest.fail("invalid source asked for folder"))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: events.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: events.append(("success", detail)))
    action = (gui.export_receiving_ear_side_manufacturing_dxf
              if mode == "marking" else gui.export_receiving_ear_side_check_dxf)
    assert action(host) is None
    assert any(isinstance(e, tuple) and e[0] == "error" for e in events)
    assert not any(isinstance(e, tuple) and e[0] == "success" for e in events)
    assert not folder.exists()
    assert saved_path.read_bytes() == original_bytes
