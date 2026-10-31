# -*- coding: utf-8 -*-
"""#2383 real Receiving inner-door PANEL factory geometry → signed W03/W04 DXF."""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.manufacturing_api import (
    build_inner_door_panel_render_data,
    save_verified_final_scene_batch_dxf,
    verify_saved_part_render_data_dxf,
)
from integration_cli.worker_inner_door_panel import (
    receiving_inner_door_panel_from_trusted_part,
    resolve_receiving_inner_door_panel_frame,
    require_canonical_receiving_inner_door_panel_frame,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest


def _part(door_id="upper", cell_key="0:0"):
    return {
        "kind": "inner_door", "cabinet_family": "受電箱",
        "source_part_ref": f"inner_door:{door_id}:panel",
        "dimension_semantics": "part_formed_outer",
        "inner_door_id": door_id, "inner_door_cell_key": cell_key,
        "dimensions_mm": {"width": 700.0, "height": 1000.0, "thickness": 2.0},
    }


@pytest.mark.parametrize("door_id,cell_key", [
    ("upper", "0:0"), ("lower", "0:1"), ("right_2", "2:0"),
])
def test_receiving_inner_door_real_panel_four_fold_dxf_save_reload(tmp_path, door_id, cell_key):
    from ae_engine.inner_door_panels import derive_inner_door_panel
    p = _part(door_id, cell_key)
    panel = receiving_inner_door_panel_from_trusted_part(p)
    assert panel == derive_inner_door_panel(
        door_id, cell_key=cell_key, width=700, height=1000, thickness=2,
    )
    assert panel.stable_id == p["source_part_ref"]
    assert panel.unfolded_width == pytest.approx(734.0)
    assert panel.unfolded_height == pytest.approx(1034.0)
    data = build_inner_door_panel_render_data(panel)
    assert data.material.is_valid and data.material.area > 0
    assert len(data.fold_guides) >= 4
    physical = "whd-" + hashlib.sha256(door_id.encode()).hexdigest()[:24]
    frame = resolve_receiving_inner_door_panel_frame(panel, physical_part_id=physical)
    require_canonical_receiving_inner_door_panel_frame(frame, physical_part_id=physical)
    assert frame["allowed_feature_types"] == []
    out = tmp_path / "source-owned-receiving-panel"
    exported = save_verified_final_scene_batch_dxf(
        [(physical, data)], out, pre_commit_guard=lambda: None,
    )
    path = out / (physical + ".dxf")
    assert exported == {physical: str(path)}
    assert path.is_file()
    verify = verify_saved_part_render_data_dxf(data, path)
    assert verify.ok, verify.issues
    readback = ezdxf.readfile(path)
    assert readback.modelspace().query('*[layer=="CUTTING"]')
    assert readback.modelspace().query('*[layer=="BEND"]')


@pytest.mark.parametrize("change", [
    "wrong_family", "wrong_semantics", "wrong_physical_ref", "missing_door_id",
    "missing_cell", "unconfirmed_cell", "invalid_id", "zero_w", "negative_h",
    "bool_t", "nan_w", "missing_h", "depth", "fold_override", "frame_edges",
    "external_fold", "indicator_group",
])
def test_receiving_inner_door_denies_unverified_panel_source(change):
    p = _part()
    dims = p["dimensions_mm"]
    if change == "wrong_family": p["cabinet_family"] = "金庫型"
    elif change == "wrong_semantics": p["dimension_semantics"] = "cabinet_outer"
    elif change == "wrong_physical_ref": p["source_part_ref"] = "inner_door:lower:panel"
    elif change == "missing_door_id": del p["inner_door_id"]
    elif change == "missing_cell": del p["inner_door_cell_key"]
    elif change == "unconfirmed_cell": p["inner_door_cell_key"] = "unknown"
    elif change == "invalid_id": p["inner_door_id"] = "upper:left"
    elif change == "zero_w": dims["width"] = 0
    elif change == "negative_h": dims["height"] = -2
    elif change == "bool_t": dims["thickness"] = True
    elif change == "nan_w": dims["width"] = float("nan")
    elif change == "missing_h": del dims["height"]
    elif change == "depth": dims["depth"] = 350
    elif change == "fold_override": p["fold_left_mm"] = 25
    elif change == "frame_edges": p["frame_edges"] = {"left": True}
    elif change == "external_fold": p["fold_profile"] = []
    elif change == "indicator_group": p["indicator_groups"] = [1]
    with pytest.raises(PrepareEvidenceError):
        receiving_inner_door_panel_from_trusted_part(p)


def test_receiving_inner_door_refuses_forged_frame_fields():
    p = _part()
    panel = receiving_inner_door_panel_from_trusted_part(p)
    physical = "whd-" + "d" * 24
    frame = resolve_receiving_inner_door_panel_frame(panel, physical_part_id=physical)
    for key, value in (
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [0, 100, 0]),
        ("face_role", "front"),
        ("frame_id", "door:fake"),
    ):
        bad = deepcopy(frame)
        bad[key] = value
        with pytest.raises(PrepareEvidenceError):
            require_canonical_receiving_inner_door_panel_frame(
                bad, physical_part_id=physical,
            )


def _signed_input(tmp_path, *, source_has_circle=False):
    from tests.test_issue2378_prepare_batch import _root, _request
    root, _, _ = _root(tmp_path)
    source = tmp_path / "CADSplit-source.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if source_has_circle:
        doc.modelspace().add_circle((100, 100), 10, dxfattribs={"layer": "CUTTING"})
    doc.saveas(source)
    request = _request()
    item = request["items"][0]
    item["part"] = _part()
    item["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    return root, source, request


def test_receiving_inner_door_authentic_prepare_export_dxf_reopen(tmp_path):
    from tests.test_issue2378_prepare_batch import (
        _prepare, _export_request_from_prepared, COMMIT, ENGINE, KEY,
    )
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, source, request = _signed_input(tmp_path)
    receipt = _prepare(request, root)
    assert receipt["status"] == "success"
    record = receipt["items"][0]
    assert record["target_frames"][0]["frame_id"].startswith("inner_door:")
    assert record["target_frames"][0]["allowed_feature_types"] == []
    exported_request = _export_request_from_prepared(request, receipt)
    out = tmp_path / "signed-inner-door"
    result = save_trusted_door_circle_finalscene_batch(
        request, receipt, exported_request,
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    dest = out / (record["physical_part_id"] + ".dxf")
    assert result == {record["physical_part_id"]: str(dest)}
    panel = receiving_inner_door_panel_from_trusted_part(_part())
    verify = verify_saved_part_render_data_dxf(build_inner_door_panel_render_data(panel), dest)
    assert verify.ok, verify.issues
    assert ezdxf.readfile(dest).modelspace().query('*[layer=="BEND"]')


def test_receiving_inner_door_untransferred_original_hole_refused_before_dxf(tmp_path):
    from tests.test_issue2378_prepare_batch import (
        _prepare, _export_request_from_prepared, COMMIT, ENGINE, KEY,
    )
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, source, request = _signed_input(tmp_path, source_has_circle=True)
    receipt = _prepare(request, root)
    exported_request = _export_request_from_prepared(request, receipt)
    out = tmp_path / "must-not-create"
    with pytest.raises(PrepareEvidenceError) as error:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, exported_request,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=out,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert error.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not out.exists()
