# -*- coding: utf-8 -*-
"""#2383 Vault/Receiving family bridge: real W-03/W-04 source-to-DXF parity.

The request uses actual WHD Receiving family inputs, the existing Vault
baseline path from the Receiving family authority and a genuinely empty
original DXF. No CADSplit source geometry or unapproved Receiving EndCap is
silently inferred.
"""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import (
    build_part_render_data, resolve_policy, verify_saved_part_render_data_dxf,
)
from integration_cli.prepare_batch import (
    door_spec_from_trusted_prepared_part,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import (
    save_trusted_door_circle_finalscene_batch,
)
from tests.test_issue2378_prepare_batch import (
    KEY, COMMIT, ENGINE, _root, _prepare, _request,
    _export_request_from_prepared,
)


def _family_batch(tmp_path):
    resource, _, _ = _root(tmp_path)
    source = tmp_path / "CADSplit 真正空白的原始來源.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    assert not list(doc.modelspace())
    doc.saveas(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()

    request = _request(count=3)
    family_dimensions = (
        ("金庫型", 500.0, 600.0, True),
        ("受電箱", 800.0, 1100.0, False),
        ("受電箱", 800.0, 500.0, True),
    )
    for item, (family, width, height, bottom) in zip(
        request["items"], family_dimensions,
    ):
        item["source_document_sha256"] = sha
        p = item["part"]
        p["cabinet_family"] = family
        p["dimensions_mm"] = {"width": width, "height": height, "thickness": 2.0}
        p["frame_edges"] = {
            "left": True, "right": True, "top": True, "bottom": bottom,
        }
        if family == "受電箱":
            p.update({
                "frame_width_mm": 29.0, "gap_w_mm": 3.5, "gap_h_mm": 3.5,
                "fold_left_mm": 19.0, "fold_right_mm": 19.0,
                "fold_top_mm": 19.0, "fold_bottom_mm": 19.0,
            })
    request["request_digest"] = compute_wire_request_digest(request)
    return resource, source, request


def test_vault_and_receiving_outer_doors_true_worker_finalscene_dxf_reload(tmp_path):
    resource, source, request = _family_batch(tmp_path)
    receipt = _prepare(request, resource)
    assert receipt["status"] == "success"
    assert len({row["physical_part_id"] for row in receipt["items"]}) == 3
    assert all(row["target_frames"][0]["face_role"] == "front"
               for row in receipt["items"])

    export = _export_request_from_prepared(request, receipt)
    out = tmp_path / "金庫型與受電箱的真實板件 DXF"
    result = save_trusted_door_circle_finalscene_batch(
        request, receipt, export,
        source_documents={row["item_id"]: source for row in request["items"]},
        resource_root=resource, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    assert len(result) == 3
    ctx = ManufacturingContext(resource_root=resource)
    policy = resolve_policy(ctx)
    for original, prepared in zip(request["items"], receipt["items"]):
        path = out / (prepared["physical_part_id"] + ".dxf")
        assert path.is_file()
        assert str(path) == str(result[prepared["physical_part_id"]])
        spec = door_spec_from_trusted_prepared_part(original["part"], policy)
        expected = build_part_render_data(spec, ctx)
        verified = verify_saved_part_render_data_dxf(expected, path)
        assert verified.ok, (original["part"]["cabinet_family"], verified.issues)
        reopened = ezdxf.readfile(path)
        assert any(e.dxf.layer == "CUTTING" for e in reopened.modelspace())
        assert any(e.dxf.layer == "BEND" for e in reopened.modelspace())
        assert spec.model_name == original["part"]["cabinet_family"]


def test_receiving_endcap_cannot_fall_back_to_vault_manufacturing(tmp_path):
    resource, source, request = _family_batch(tmp_path)
    request = deepcopy(request)
    request["items"] = [request["items"][1]]
    p = request["items"][0]["part"]
    p["kind"] = "end_cap_head"
    p["dimensions_mm"] = {"width": 800.0, "depth": 350.0, "thickness": 2.0}
    for key in ("frame_edges", "frame_width_mm", "gap_w_mm", "gap_h_mm",
                "fold_left_mm", "fold_right_mm", "fold_top_mm", "fold_bottom_mm"):
        p.pop(key, None)
    request["request_digest"] = compute_wire_request_digest(request)
    with pytest.raises(PrepareEvidenceError, match="Receiving EndCap"):
        _prepare(request, resource)
    assert not list(tmp_path.rglob("*.dxf")) or all(
        candidate == source or candidate.is_relative_to(resource)
        for candidate in tmp_path.rglob("*.dxf")
    )


def test_installed_worker_advertises_exact_vault_receiving_kind_matrix(monkeypatch):
    """No unverified Receiving EndCap/BoxBody through a Vault capability."""
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    from integration_cli import cadsplit_worker as worker
    from integration_cli import private_worker_installation as installation

    # Check exactly the installed v1.1 response path. Provisioning is mocked;
    # this is a contract test, NOT proof that a real installation exists.
    source = worker._capabilities(COMMIT, "test-build", ENGINE)
    monkeypatch.setattr(worker.sys, "frozen", True, raising=False)
    monkeypatch.setattr(worker.sys, "platform", "win32")
    monkeypatch.setattr(worker, "_capabilities", lambda *a: deepcopy(source))
    monkeypatch.setattr(installation, "load_private_execution", lambda *a, **k: object())
    advertised = worker._installed_capabilities(COMMIT, "test-build", ENGINE, "installed-01")
    schema_path = Path(__file__).resolve().parents[1] / "integration_cli" / "schemas" / "capabilities_v1_1.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(advertised)

    indexed = {entry["part_kind"]: entry for entry in advertised["capabilities"]}
    assert set(indexed) == set(advertised["supported_part_kinds"])
    assert indexed["door"]["cabinet_families"] == ["金庫型", "受電箱"]
    assert indexed["end_cap_head"]["cabinet_families"] == ["金庫型"]
    assert indexed["end_cap_tail"]["cabinet_families"] == ["金庫型"]
    assert indexed["base_plate"]["cabinet_families"] == ["金庫型"]
    assert indexed["inner_door"]["cabinet_families"] == ["受電箱"]
    assert indexed["box_body"]["cabinet_families"] == ["金庫型"]
    assert indexed["indicator_box"]["cabinet_families"] == ["金庫型", "受電箱"]
    assert indexed["box_body"]["cabinet_families"] == ["金庫型"]
    assert not advertised["capability_flags"]["cancellation"]
    assert not advertised["capability_flags"]["crash_recovery"]
