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
    # Selection is a runtime-only UI state and must not be serialized.
    assert "_receiving_runtime_selection" not in result
    result["_receiving_runtime_selection"] = deepcopy(
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
    ("310X96", "碰撞|相交|overlap"),
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
