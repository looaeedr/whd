# -*- coding: utf-8 -*-
"""#2383: real 3-piece Receiving box body in one signed W-03/W-04 transaction.

Each physical sheet is already a separate certified Worker role:
LEFT and RIGHT side_panel, FULL/BACK_OPENING back_panel. No fantasy fourth
aggregate DXF and no claim that assembly/weld joints are certified.
"""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import verify_saved_part_render_data_dxf
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from integration_cli.worker_receiving_side_panel import (
    receiving_side_panel_spec_from_trusted_part, receiving_side_panel_render,
    receiving_side_panel_expected_baselines,
)
from integration_cli.worker_receiving_back_panel import (
    receiving_back_panel_spec_from_trusted_part, receiving_back_panel_render,
)
from tests.test_issue2378_prepare_batch import (
    _request, _prepare, _export_request_from_prepared,
    COMMIT, ENGINE, KEY,
)
from tests.test_issue2383_receiving_side_panel_worker_api import (
    _root_with_receiving_baselines, _part as side_part,
)
from tests.test_issue2383_receiving_back_panel_worker_api import _part as back_part


_ROLES = ("left_side", "back", "right_side")


def _three_sheets(tmp_path, *, back_mode="FULL", hole_role=None):
    root, _ = _root_with_receiving_baselines(tmp_path)
    original = _request(count=3)
    source_documents = {}
    for index, role in enumerate(_ROLES):
        row = original["items"][index]
        row["item_id"] = f"source-physical-{role}"
        row["part"] = back_part(back_mode) if role == "back" else side_part(role)
        source = tmp_path / f"original-cadsplit-{role}.dxf"
        doc = ezdxf.new("R2010")
        doc.header["$INSUNITS"] = 4
        if role == hole_role:
            doc.modelspace().add_circle(
                (80.0, 50.0), 5.0, dxfattribs={"layer": "CUTTING"},
            )
        doc.saveas(source)
        row["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        source_documents[row["item_id"]] = source
    original["request_digest"] = compute_wire_request_digest(original)
    return root, original, source_documents


@pytest.mark.parametrize("mode,expected_closed", [
    ("FULL", 5), ("BACK_OPENING", 6),
])
def test_one_exact_job_three_receiving_physical_sheets_all_reopen_and_verify(
    tmp_path, mode, expected_closed,
):
    root, request, sources = _three_sheets(tmp_path, back_mode=mode)
    receipt = _prepare(request, root)
    assert receipt["status"] == "success"
    assert receipt["manufacturing_verified"] is False
    assert len(receipt["items"]) == 3
    physical_ids = [item["physical_part_id"] for item in receipt["items"]]
    assert len(set(physical_ids)) == 3
    assert len({item["preparation_digest"] for item in receipt["items"]}) == 3
    assert [item["target_frames"][0]["frame_id"].split(":")[0]
            for item in receipt["items"]] == [
                "side_panel", "back_panel", "side_panel",
            ]
    assert all(item["target_frames"][0]["allowed_feature_types"] == []
               for item in receipt["items"])
    assert len(set(receipt["environment_fingerprint"] for _ in physical_ids)) == 1
    export = _export_request_from_prepared(request, receipt)
    out = tmp_path / "one-atomic-three-piece-batch"
    saved = save_trusted_door_circle_finalscene_batch(
        request, receipt, export,
        source_documents=sources,
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    assert set(saved) == set(physical_ids)
    assert {path.name for path in out.glob("*.dxf")} == {
        physical + ".dxf" for physical in physical_ids
    }
    expected = {}
    for index, role in enumerate(_ROLES):
        part = request["items"][index]["part"]
        if role == "back":
            spec = receiving_back_panel_spec_from_trusted_part(part)
            render = receiving_back_panel_render(
                spec, ManufacturingContext(resource_root=root),
            )
        else:
            spec, resolved_role = receiving_side_panel_spec_from_trusted_part(part)
            assert resolved_role == role
            render = receiving_side_panel_render(
                spec, resolved_role, ManufacturingContext(resource_root=root),
            )
        dest = out / (physical_ids[index] + ".dxf")
        assert saved[physical_ids[index]] == str(dest)
        assert dest.is_file() and dest.stat().st_size > 0
        valid = verify_saved_part_render_data_dxf(render, dest)
        assert valid.ok, valid.issues
        reopened = ezdxf.readfile(dest).modelspace()
        assert reopened.query('*[layer=="CUTTING"]')
        if role == "back":
            assert not reopened.query('*[layer=="BEND"]')
            assert sum(
                e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "CUTTING"
                and bool(e.closed) for e in reopened
            ) == expected_closed
        else:
            assert reopened.query('*[layer=="BEND"]')
            assert reopened.query('*[layer=="BLIND_HOLE"]')
        expected[role] = dest
    assert len(expected) == 3


@pytest.mark.parametrize("tainted_role", _ROLES)
def test_unsupported_original_feature_in_any_one_part_refuses_all_three_dxfs(
    tmp_path, tainted_role,
):
    root, request, sources = _three_sheets(
        tmp_path, hole_role=tainted_role,
    )
    receipt = _prepare(request, root)
    exported = _export_request_from_prepared(request, receipt)
    out = tmp_path / "must-not-create-partial-three-piece"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, exported,
            source_documents=sources,
            resource_root=root, output_dir=out,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not out.exists()


def test_three_piece_job_entire_batch_revoked_by_any_dedicated_baseline_drift(tmp_path):
    from integration_cli.prepare_recheck import recheck_trusted_door_export

    root, request, sources = _three_sheets(tmp_path)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    # Even a baseline used by another item shares the same signed environment.
    baseline = receiving_side_panel_expected_baselines(root)[1]
    dxf = ezdxf.readfile(baseline)
    dxf.modelspace().add_line((1.0, 1.0), (2.0, 2.0), dxfattribs={"layer": "MARKING"})
    dxf.saveas(baseline)
    with pytest.raises(PrepareEvidenceError) as exc:
        recheck_trusted_door_export(
            request, receipt, export, source_documents=sources,
            resource_root=root, engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not (tmp_path / "must-not-create-partial-three-piece").exists()


def test_three_piece_job_rejects_cross_sheet_source_identity_swap(tmp_path):
    from integration_cli.prepare_recheck import recheck_trusted_door_export

    root, request, sources = _three_sheets(tmp_path)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    mixed = deepcopy(export)
    mixed["items"][1]["part"], mixed["items"][2]["part"] = (
        mixed["items"][2]["part"], mixed["items"][1]["part"],
    )
    mixed["request_digest"] = compute_wire_request_digest(mixed)
    with pytest.raises(PrepareEvidenceError):
        recheck_trusted_door_export(
            request, receipt, mixed, source_documents=sources,
            resource_root=root, engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
