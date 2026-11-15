"""#2517 real persisted NFB Door/Base Request must carry source-owned 3D Fold.

The genuine paired NFB DXF route already knew the InnerDoor final 2D blank,
but its ManufacturingPartInput formerly dropped the original X/Y folded
profiles: a real physical Door therefore disappeared from the world's
cross-Bay collision inventory. The answer is the existing Engine Door profile
owner, NEVER a display-bbox or a second 90-degree formula in GUI/tests.
"""
from copy import deepcopy
from dataclasses import replace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.contracts import ResolvedManufacturingPart
from ae_engine.inner_door_panels import inner_door_panel_part_profiles
from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
import phase6_project_file as project
from tests.test_issue1502_current_csv_multi_bay_once import _provider
from tests.test_issue2517_saved_multiset_original_gui_grouped_dxf import (
    BAYS, _saved_with_real_inner_door_state, _run_gui_group, PREFIX,
)


def _actual_pair(source, si, bi):
    bay = source["receiving_layout"]["sets"][si]["bays"][bi]
    pair = api.receiving_committed_nfb_pair_request_for_bay(
        source["receiving_layout"], set_index=si, bay_index=bi,
        thickness_mm=source["t"],
    )
    assert len(pair.parts) == 2
    actual = pair.parts[0]
    projection = project_receiving_bay_legacy_aliases(
        source, set_index=si, bay_index=bi,
    )
    panel = next(
        p for p in derive_inner_door_panels(projection)
        if p.stable_id == actual.part_key
    )
    authoritative = inner_door_panel_part_profiles((panel,))[panel.stable_id]
    assert tuple(dict(x) for x in actual.x_profile) == tuple(authoritative["X"])
    assert tuple(dict(y) for y in actual.y_profile) == tuple(authoritative["Y"])
    assert sum(x["len"] for x in actual.x_profile) == pytest.approx(panel.unfolded_width)
    assert sum(y["len"] for y in actual.y_profile) == pytest.approx(panel.unfolded_height)
    assert actual.render_data.material.area > 0
    assert len(tuple(actual.render_data.fold_guides)) == 4
    world = api.build_joint_world_geometry((
        ResolvedManufacturingPart(
            part_key=actual.part_key,
            render_data=actual.render_data,
            x_profile=actual.x_profile,
            y_profile=actual.y_profile,
            placement="offset",
        ),
    ), (bay["width"], bay["height"], bay["depth"]),
        source["t"])
    assert world["world_triangles_by_part"][panel.stable_id]
    assert world["mapped_skin_triangles_by_part"][panel.stable_id]
    assert world["flat_material_by_part"][panel.stable_id].equals(
        actual.render_data.material
    )
    return pair, actual, world["world_triangles_by_part"][panel.stable_id]


def _fully_profiled_bay_source(source):
    original, calls = _provider(source)

    def provide(si, bi):
        scene = original(si, bi)
        pair, door, _ = _actual_pair(source, si, bi)
        assert pair.canonical_part_keys[0] == door.part_key
        assert scene.part(door.part_key).render_data.material.area > 0
        return replace(
            scene,
            parts=tuple(
                replace(p, x_profile=door.x_profile, y_profile=door.y_profile)
                if p.part_key == door.part_key else p
                for p in scene.parts
            ),
        )
    return provide, calls


def test_real_saved_two_sets_all_nfb_doors_have_2d_and_3d_parity(tmp_path):
    saved, source_bytes, source = _saved_with_real_inner_door_state(tmp_path)
    another_read = project.read_project(saved)["snapshot"]
    original = deepcopy(source)
    for si, bi in BAYS:
        old, before, old_world = _actual_pair(source, si, bi)
        new, after, new_world = _actual_pair(another_read, si, bi)
        assert old.canonical_part_keys == new.canonical_part_keys
        assert old.parts[0].x_profile == new.parts[0].x_profile
        assert old.parts[0].y_profile == new.parts[0].y_profile
        assert before.render_data.scene == after.render_data.scene
        assert before.render_data.material.equals(after.render_data.material)
        assert before.render_data.fold_guides == after.render_data.fold_guides
        assert old_world == new_world
    assert saved.read_bytes() == source_bytes
    assert source == original


def test_actual_two_sets_cross_bay_world_includes_every_nfb_inner_door(tmp_path):
    saved, source_bytes, source = _saved_with_real_inner_door_state(tmp_path)
    restored = project.read_project(saved)["snapshot"]
    first, before_calls = _fully_profiled_bay_source(source)
    second, after_calls = _fully_profiled_bay_source(restored)
    for si in (0, 1):
        before = api.project_receiving_set_cross_bay_collision_display_audit(
            source["receiving_layout"], first, set_index=si,
            thickness_mm=source["t"],
        )
        after = api.project_receiving_set_cross_bay_collision_display_audit(
            restored["receiving_layout"], second, set_index=si,
            thickness_mm=restored["t"],
        )
        assert before == after
        assert all(any(key.endswith("::inner_door:upper:panel") for key in group)
                   for group in after.physical_keys_by_bay)
        assert not after.missing_world_keys, after.missing_world_keys
        assert after.complete
        assert after.require_complete() is True
        assert after.evaluated_pair_count == (
            len(after.physical_keys_by_bay[0]) * len(after.physical_keys_by_bay[1])
        )
        # A visible cross-Bay mesh is only surface diagnostic. Unresolved
        # contacts remain unresolved even after the missing panel is meshed.
        assert all(row.status in (
            "AABB_SEPARATED", "NO_NONCOPLANAR_CROSSING", "UNRESOLVED_CROSSING"
        ) for row in after.pairs)
    assert before_calls == after_calls == list(BAYS)
    assert saved.read_bytes() == source_bytes


def test_original_gui_true_nfb_group_dxf_unchanged_after_3d_profile_fix(
    tmp_path, monkeypatch,
):
    saved, unchanged, source = _saved_with_real_inner_door_state(tmp_path)
    # Original GUI export callback is the real operator entrance. The saved
    # project, current NFB source and all Engine-authorized flat geometries
    # still independently pass full DXF reopen and owner/BOM checks.
    out = tmp_path / "nfb-door-profile-unchanged-dxf"
    # This module imports the genuine GUI fixture helper, not the other
    # module's autouse pytest fixture. Freeze the Engine-owned output minute
    # in THIS test rather than assuming an unrelated fixture ran.
    monkeypatch.setattr(
        "ae_engine.receiving_dxf_groups._taipei_output_stamp",
        lambda: PREFIX.split("_", 1)[0],
    )
    calls, errors, infos = _run_gui_group(
        monkeypatch, source, out, mode="ALL", with_nfb=True,
    )
    assert not errors, errors
    assert len(infos) == 1 and calls == list(BAYS)
    assert {p.name for p in out.glob("*.dxf")} == {
        PREFIX + "全部.dxf", PREFIX + "總計.dxf"
    }
    doc = ezdxf.readfile(out / (PREFIX + "全部.dxf"))
    assert not doc.audit().errors
    msp = doc.modelspace()
    labels = [e.plain_text() for e in msp
              if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"]
    assert len([x for x in labels if x.startswith("inner_door:")
                and " × " not in x]) == 4
    assert "base_plate" in labels
    assert any(e.dxf.layer == "CUTTING" for e in msp)
    assert any(e.dxf.layer == "BEND" for e in msp)
    assert saved.read_bytes() == unchanged


def test_missing_actual_inner_door_source_still_blocks_nfb_pair_request(tmp_path):
    _saved, _bytes, source = _saved_with_real_inner_door_state(tmp_path)
    altered = deepcopy(source)
    bay = altered["receiving_layout"]["sets"][1]["bays"][1]
    bay["door_state"]["inner_doors"] = []
    with pytest.raises(ValueError, match="NFB_PAIR_REQUEST_REAL_INNER_DOOR_REQUIRED"):
        api.receiving_committed_nfb_pair_request_for_bay(
            altered["receiving_layout"], set_index=1, bay_index=1,
            thickness_mm=altered["t"],
        )
