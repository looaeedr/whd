# -*- coding: utf-8 -*-
"""#1504 NFB-AC-29/SWT-AC-19: source V5 revalidation after Save→Reload.

The current numeric 士林 CSV, not historical SHADOW DXF, owns physical opening
dimensions and screw locations.  Change a PRIVATE copy of its *real* rows and
rebuild WHD's genuine installed FinalScene and original two-sheet export.
Never mutate the project's authoritative numeric CSV.  A prior green DXF or
stored source/preview flags cannot authorize geometry after source drift.
"""
import csv
import io
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine.receiving_nfb_numeric_catalog as catalog
import ae_engine.receiving_nfb_v5_configured_inner_door as physical_door
import ae_engine.receiving_nfb_v5_actual_base_screws as physical_base_screws
import ae_engine.receiving_nfb_v5_check_q_preview as check_q
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.sheetmetal_drawing import PolylinePrimitive
from phase6_project_file import PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V3, write_project, read_project
from phase6_receiving_modes import fresh_receiving_mode
from ae_engine.receiving_layout import update_receiving_bay
from tests.test_issue1502_current_csv_original_pair_dxf import _scene, _export
from tests.test_issue1504_ac27_swt06_v5_physical_q16_transactions import (
    _physical, _files, _shapes, _save,
)

V5 = numeric_model_ref("士林", "2P400")


def _isolated_csv(monkeypatch, tmp_path):
    original = catalog.brand_csv_path("士林")
    source = original.read_bytes()
    private = tmp_path / "test-only-shihlin.csv"
    private.write_bytes(source)
    monkeypatch.setattr(catalog, "brand_csv_path", lambda brand: (
        private if brand == "士林" else original
    ))
    monkeypatch.setattr(physical_door, "brand_csv_path", lambda brand: (
        private if brand == "士林" else original
    ))
    # Door and already-installed base each independently pin the SAME bytes
    # through their own imported brand_csv_path alias. Test-source isolation
    # must patch BOTH: leaving only one redirected correctly fails closed
    # at the real "inner door versus base source mismatch" hard gate.
    monkeypatch.setattr(physical_base_screws, "brand_csv_path", lambda brand: (
        private if brand == "士林" else original
    ))
    # The operator's CHECK/Q independently rehashes the very same source;
    # never bypass its hard gate or accept a door/base-only simulated source.
    monkeypatch.setattr(check_q, "brand_csv_path", lambda brand: (
        private if brand == "士林" else original
    ))
    assert catalog.model_spec("士林", "2P400") is not None
    return private, source


def _update_opening(path, new_size):
    rows = list(csv.DictReader(
        io.StringIO(path.read_text(encoding="utf-8-sig"))
    ))
    assert rows and tuple(rows[0]) == catalog.HEADER
    selected = [r for r in rows if r["型號"] == "2P400"]
    assert len(selected) == 1
    previous = selected[0]["開孔尺寸_mm"]
    selected[0]["開孔尺寸_mm"] = new_size
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=catalog.HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8-sig")
    assert catalog.model_spec("士林", "2P400").opening_mm == tuple(
        float(x) for x in new_size.split("X")
    )
    return previous


def _door_cuttings(parts):
    door = next(p for p in parts if p.part_key.startswith("inner_door:"))
    return tuple(sorted(
        tuple(sorted((round(float(pt.x), 5), round(float(pt.y), 5))
                     for pt in poly.points))
        for poly in door.render_data.scene.primitives
        if isinstance(poly, PolylinePrimitive)
        and poly.layer == "CUTTING" and poly.closed
    ))


def _valid_project():
    # Preserve the original upper physical WHD W800 inner-door geometry but
    # give the Bay a real validated ReceivingLayout owner for .p6fold Save.
    src = _physical("3P125SN")
    real = fresh_receiving_mode("set_bay", {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })
    layout = update_receiving_bay(
        real["receiving_layout"], set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=src["nfb_config"],
    )
    src["receiving_layout"] = layout
    bay = layout["sets"][0]["bays"][0]
    src["_receiving_runtime_selection"] = {
        "set_index": 0, "bay_index": 0,
        "set_id": layout["sets"][0]["stable_id"],
        "bay_id": bay["stable_id"],
    }
    assert bay["nfb_config"] == src["nfb_config"]
    assert _scene(src)
    return src


def _reloaded_project(snapshot, tmp_path):
    physical = deepcopy(snapshot)
    original_config = deepcopy(snapshot["nfb_config"])
    path = write_project(tmp_path / "real-nfb.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": deepcopy(snapshot),
    })
    stored = path.read_text(encoding="utf-8")
    assert '"manufacturing_ready"' not in stored
    assert '"nfb_trial_export_approved"' not in stored
    loaded = read_project(path)
    assert loaded["schema"] == PROJECT_SCHEMA_V3
    result = loaded["snapshot"]
    assert result["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] == original_config
    assert result["nfb_config"]["holes"] == original_config["holes"]
    assert physical == snapshot
    # The saved file must not carry a stale runtime selection.  The CURRENT
    # project reader deliberately reprojects the primary Set/Bay identities
    # into an in-memory runtime selection on reload.  Verify both halves.
    import json
    encoded = json.loads(stored)
    assert "_receiving_runtime_selection" not in encoded["snapshot"]
    assert result["_receiving_runtime_selection"] == (
        physical["_receiving_runtime_selection"]
    )
    assert result["nfb_config_submitted"] is True
    return result, path


def test_ac29_swt19_reload_current_v5_rederives_real_centres_and_cutting(
    monkeypatch, tmp_path,
):
    _isolated_csv(monkeypatch, tmp_path)
    original = _valid_project()
    original_parts = _scene(original)
    original_door = _door_cuttings(original_parts)
    saved, project_file = _reloaded_project(original, tmp_path)
    fresh_parts = _scene(saved)
    assert _door_cuttings(fresh_parts) == original_door
    assert saved["nfb_config"]["holes"] == original["nfb_config"]["holes"]
    assert saved["nfb_config"]["holes"][0]["model_filename"] == V5
    assert saved["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    receipt = _save(saved, fresh_parts, tmp_path / "after-reload")
    saved_paths = _files(receipt)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(_shapes(saved_paths[1])[0]) == 8
    assert project_file.is_file()


def test_ac29_swt19_csv_bytes_change_requires_fresh_finalscene_and_dxf(
    monkeypatch, tmp_path,
):
    csv_path, original_bytes = _isolated_csv(monkeypatch, tmp_path)
    snapshot = _valid_project()
    reloaded, _ = _reloaded_project(snapshot, tmp_path)
    original_parts = _scene(reloaded)
    old_door = _door_cuttings(original_parts)
    old_receipt = _save(reloaded, original_parts, tmp_path / "old-dxf")
    old_paths = _files(old_receipt)
    old_bytes = tuple(p.read_bytes() for p in old_paths)

    old_size = _update_opening(csv_path, "65X96")
    assert old_size != "65X96"
    assert csv_path.read_bytes() != original_bytes
    refreshed_parts = _scene(reloaded)
    new_door = _door_cuttings(refreshed_parts)
    assert new_door != old_door
    # The valid current physical opening must be re-derived even when the
    # project kept an old CONFIRMED X and unchanged source model identity.
    assert reloaded["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    rejected_dir = tmp_path / "old-scene-rejected"
    rejected_dir.mkdir()
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE|SOURCE|DIFFERS|CSV"):
        _export(reloaded, original_parts, rejected_dir)
    assert list(rejected_dir.glob("*.dxf")) == []

    new_receipt = _save(reloaded, refreshed_parts, tmp_path / "new-dxf")
    new_paths = _files(new_receipt)
    assert _shapes(new_paths[0]) != _shapes(old_paths[0])
    assert tuple(p.read_bytes() for p in old_paths) == old_bytes
    assert tuple(p.read_bytes() for p in new_paths) != old_bytes


@pytest.mark.parametrize("new_size,error_pattern", (
    ("400X96", "碰撞|相交|overlap"),
    ("750X96", "超出|內門平面|碰到"),
))
def test_ac29_swt19_source_revised_collision_or_boundary_cannot_use_old_green(
    monkeypatch, tmp_path, new_size, error_pattern,
):
    csv_path, _ = _isolated_csv(monkeypatch, tmp_path)
    snapshot = _valid_project()
    for row, position in zip(snapshot["nfb_config"]["holes"], (-90., 90.)):
        row["manual_x_mm"] = position
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snapshot["nfb_config"]
    )
    reloaded, _ = _reloaded_project(snapshot, tmp_path)
    old_parts = _scene(reloaded)
    old_dir = tmp_path / "legitimate-export"
    old_receipt = _save(reloaded, old_parts, old_dir)
    old_paths = _files(old_receipt)
    old_bytes = tuple(p.read_bytes() for p in old_paths)

    _update_opening(csv_path, new_size)
    with pytest.raises(ValueError, match=error_pattern):
        _scene(reloaded)
    rejected = tmp_path / "invalid-source-export"
    rejected.mkdir()
    with pytest.raises(ValueError):
        _export(reloaded, old_parts, rejected)
    assert not list(rejected.glob("*.dxf"))
    assert tuple(p.read_bytes() for p in old_paths) == old_bytes
    assert old_dir.joinpath(old_paths[0].name).is_file()
    assert reloaded["nfb_config"]["holes"][0]["manual_x_mm"] == -90.


def test_ac29_swt19_original_hole_editor_csv_proof_from_before_reload_cannot_be_reused(
    monkeypatch, tmp_path,
):
    import ae_engine.receiving_nfb_csv_editor_features as editor
    from ae_engine.receiving_nfb_csv_editor_features import (
        stage_csv_openings, csv_openings_to_editor_features,
    )
    from tests.test_issue1901_csv_native_editor import _real_csv_door

    csv_path, original_bytes = _isolated_csv(monkeypatch, tmp_path)
    monkeypatch.setattr(editor, "brand_csv_path", lambda brand: csv_path)
    snapshot, panel, original_trial, draft = _real_csv_door()
    original = stage_csv_openings(
        original_trial, snapshot=snapshot, draft=draft, current_features=(),
    )
    before = csv_openings_to_editor_features(
        original, snapshot=snapshot, draft=draft, current_features=(),
    )
    assert len(before) == 1
    assert before[0].source_type == "NFB_CSV_SOURCE"
    assert before[0].layer == "CUTTING"

    _update_opening(csv_path, "65X96")
    assert csv_path.read_bytes() != original_bytes
    with pytest.raises(ValueError, match="CSV 已更新"):
        csv_openings_to_editor_features(
            original, snapshot=snapshot, draft=draft, current_features=(),
        )
    # A genuine repeat source read has to reconstruct the new actual opening:
    # neither Save/Reload nor a past successful source proof authorizes reuse.
    new_trial = physical_door.trial_configured_nfb_v5_inner_door_render_data(
        snapshot, panel.inner_door_id,
        holes=(physical_door.NfbV5ConfiguredInnerDoorHole(
            "nfb:quantity:unit1", "士林", V5, 0., 1, 0,
        ),),
    )
    restaged = stage_csv_openings(
        new_trial, snapshot=snapshot, draft=draft, current_features=(),
    )
    after = csv_openings_to_editor_features(
        restaged, snapshot=snapshot, draft=draft, current_features=(),
    )
    assert len(after) == 1
    assert after[0].source_type == "NFB_CSV_SOURCE"
    assert after[0].points[1].x - after[0].points[0].x == pytest.approx(65.)
    assert before[0].points[1].x - before[0].points[0].x == pytest.approx(57.)
    assert before != after


def _canonical_cutting_scene_shapes(part):
    """FinalScene's CUTTING geometry in the same units as reopened DXF."""
    from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    primitives = tuple(part.render_data.scene.primitives)
    circles = tuple(sorted(
        (round(float(p.center.x), 5), round(float(p.center.y), 5),
         round(float(p.radius), 5))
        for p in primitives if isinstance(p, CirclePrimitive)
        and p.layer == "CUTTING"
    ))
    polygons = tuple(sorted(
        tuple(sorted((round(float(pt.x), 5), round(float(pt.y), 5))
                     for pt in p.points))
        for p in primitives if isinstance(p, PolylinePrimitive)
        and p.layer == "CUTTING" and p.closed
    ))
    return circles, polygons


def test_ac14_swt11_complete_real_scene_and_saved_dxf_roundtrip(monkeypatch, tmp_path):
    """One current V5 source must survive Set/Bay Save, FinalScene and DXF IO.

    This is a supported source-scoped 2D/3D installed-part check, NOT whole
    cabinet MFG-2 approval or a physical Windows operator GUI receipt.
    """
    _isolated_csv(monkeypatch, tmp_path)
    original = _valid_project()
    before = _scene(original)
    assert {part.part_key for part in before} == {
        "inner_door:upper:panel", "base_plate"
    }
    first = _save(original, before, tmp_path / "before")
    first_files = _files(first)
    before_dxf = tuple(_shapes(path) for path in first_files)
    for index, part in enumerate(before):
        # A 2D/3D installed part and the written manufacture geometry are
        # projections of the SAME typed physical FinalScene.
        assert _canonical_cutting_scene_shapes(part) == before_dxf[index]
        assert len(tuple(part.render_data.scene.primitives)) > 0

    restored, project_path = _reloaded_project(original, tmp_path)
    assert project_path.is_file()
    after = _scene(restored)
    assert tuple(p.part_key for p in after) == tuple(p.part_key for p in before)
    for original_part, saved_part in zip(before, after):
        assert saved_part.offset == original_part.offset
        assert saved_part.render_data.scene.primitives == original_part.render_data.scene.primitives
        assert saved_part.render_data.unfolded_topology == original_part.render_data.unfolded_topology
        assert saved_part.render_data.fold_guides == original_part.render_data.fold_guides
        assert saved_part.render_data.metadata["stable_id"] == original_part.render_data.metadata["stable_id"]
    second = _save(restored, after, tmp_path / "after")
    second_files = _files(second)
    assert first.source_hole_ids == second.source_hole_ids == ("nfb:0", "nfb:1")
    assert tuple(_shapes(p) for p in second_files) == before_dxf
    for index, part in enumerate(after):
        assert _canonical_cutting_scene_shapes(part) == _shapes(second_files[index])


def test_ac14_swt11_changed_nfb_source_never_reuses_an_old_3d_or_dxf(
    monkeypatch, tmp_path,
):
    """Source drift must reconstruct BOTH 2D and installed 3D before DXF."""
    _isolated_csv(monkeypatch, tmp_path)
    source = _valid_project()
    old_parts = _scene(source)
    old_receipt = _save(source, old_parts, tmp_path / "old")
    old_paths = _files(old_receipt)
    old_shapes = tuple(_shapes(path) for path in old_paths)
    original_bytes = tuple(path.read_bytes() for path in old_paths)

    changed = deepcopy(source)
    changed["nfb_config"]["holes"][1]["manual_x_mm"] -= 20.
    changed["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed["nfb_config"]
    )
    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE|SOURCE|DIFFERS|CSV"):
        _export(changed, old_parts, stale_dir)
    assert not list(stale_dir.glob("*.dxf"))

    new_parts = _scene(changed)
    assert tuple(p.part_key for p in new_parts) == tuple(p.part_key for p in old_parts)
    assert any(
        _canonical_cutting_scene_shapes(new) != _canonical_cutting_scene_shapes(old)
        for old, new in zip(old_parts, new_parts)
    )
    assert all(old.offset == new.offset for old, new in zip(old_parts, new_parts))
    new_receipt = _save(changed, new_parts, tmp_path / "new")
    new_paths = _files(new_receipt)
    new_shapes = tuple(_shapes(path) for path in new_paths)
    assert new_shapes != old_shapes
    for index, part in enumerate(new_parts):
        assert _canonical_cutting_scene_shapes(part) == new_shapes[index]
    assert tuple(path.read_bytes() for path in old_paths) == original_bytes


def test_ac14_swt11_real_3d_mesh_is_source_owned_after_reload_and_hole_edit(
    monkeypatch, tmp_path,
):
    """Render the same genuine installed source through the real 3D adapter.

    No simulated 3D triangles or independent approximations: the renderer
    triangulates the same physical FinalScene that produces verified DXF.
    """
    from dataclasses import replace
    from types import SimpleNamespace
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer
    from phase6_final_scene_contracts import (
        AssemblySceneRenderData, FinalSceneViewRequest,
    )
    from ae_engine.cabinet_types.policy import derive_inner_door_panels
    from ae_engine.inner_door_panels import inner_door_panel_part_profiles
    from ae_engine.receiving_base_plate_3d_profiles import (
        receiving_base_plate_3d_profiles,
    )

    _isolated_csv(monkeypatch, tmp_path)
    original = _valid_project()
    original_parts = _scene(original)

    def actual_mesh(parts, snapshot):
        # The _scene() helper is intentionally a 2D/DXF sheet fixture and
        # carries EMPTY 3D profiles. A genuine 3D request must instead use
        # the exact manufacturing-owned Fold Profiles from the same source.
        door_profiles = inner_door_panel_part_profiles(
            derive_inner_door_panels(snapshot)
        )
        base_profiles = receiving_base_plate_3d_profiles(snapshot)
        assert base_profiles is not None
        formed_parts = []
        for part in parts:
            profile = (door_profiles[part.part_key]
                       if part.part_key in door_profiles
                       else base_profiles if part.part_key == "base_plate"
                       else None)
            assert profile is not None, part.part_key
            width = sum(float(v["len"]) for v in profile["X"])
            height = sum(float(v["len"]) for v in profile["Y"])
            minx, miny, maxx, maxy = part.render_data.material.bounds
            assert width == pytest.approx(maxx - minx)
            assert height == pytest.approx(maxy - miny)
            formed_parts.append(replace(
                part,
                x_profile=tuple(dict(v) for v in profile["X"]),
                y_profile=tuple(dict(v) for v in profile["Y"]),
            ))

        figure = Figure(figsize=(5., 4.))
        ax = figure.add_subplot(111, projection="3d")
        renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
        triangles = renderer.render(FinalSceneViewRequest(
            part_key="assembly",
            render_data=AssemblySceneRenderData(
                assembly_parts=tuple(formed_parts), show_interference=False,
            ),
            x_profile=(), y_profile=(),
            finished_dimensions=(800., 1600., 350.),
            thickness=2.,
        ))
        skins = tuple(x for x in ax.collections
                      if isinstance(x, Poly3DCollection))
        assert len(skins) >= len(parts) == 2
        assert triangles and len(triangles) > 10
        assert len(renderer.last_cutting_material) == len(parts)
        assert tuple(renderer.last_cutting_mesh) == tuple(triangles)
        return tuple(
            tuple(tuple(round(float(value), 5) for value in vertex)
                  for vertex in face)
            for face in triangles
        )

    old_mesh = actual_mesh(original_parts, original)
    restored, file = _reloaded_project(original, tmp_path)
    assert file.exists()
    reloaded_parts = _scene(restored)
    assert actual_mesh(reloaded_parts, restored) == old_mesh

    moved = deepcopy(restored)
    moved["nfb_config"]["holes"][1]["manual_x_mm"] -= 20.
    moved["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        moved["nfb_config"]
    )
    new_parts = _scene(moved)
    new_mesh = actual_mesh(new_parts, moved)
    assert new_mesh != old_mesh
    # The physical part positions stay fixed. Only source CUTTING shifts.
    assert tuple(p.offset for p in new_parts) == tuple(
        p.offset for p in original_parts
    )
    assert _canonical_cutting_scene_shapes(new_parts[0]) != (
        _canonical_cutting_scene_shapes(original_parts[0])
    )
    # The corresponding base screw-hole set must move in step with the
    # inner-door source. The cabinet-centred physical sheet itself does not.
    assert _canonical_cutting_scene_shapes(new_parts[1]) != (
        _canonical_cutting_scene_shapes(original_parts[1])
    )
    assert new_parts[1].render_data.unfolded_topology == (
        original_parts[1].render_data.unfolded_topology
    )
    assert new_parts[1].render_data.fold_guides == (
        original_parts[1].render_data.fold_guides
    )
