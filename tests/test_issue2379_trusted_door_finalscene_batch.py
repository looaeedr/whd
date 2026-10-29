# -*- coding: utf-8 -*-
"""#2379: authenticated original CIRCLEs through real WHD FinalScene batch.

The public CADSplit Worker is disabled; W-06 durable path/key custody is not
simulated as a shipped feature by these in-process regression tests.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import math

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_endcap_compat import _door_features_for_legacy_engine
from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene
from integration_cli.prepare_batch import door_spec_from_trusted_prepared_part
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from integration_cli.source_circle_verification import verify_trusted_original_dxf_circles
from tests.test_issue2378_prepare_batch import (
    KEY, COMMIT, ENGINE, _root, _prepare, _request, _export_request_from_prepared,
)
from tests.test_issue2379_wire_feature_preflight import _circle


def _real_batch(tmp_path, count=2):
    source = tmp_path / "original-cadsplit.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    centers = [(20.0 + 20 * i, 30.0 + 10 * i) for i in range(count)]
    radii = [3.0 + i for i in range(count)]
    handles = [
        doc.modelspace().add_circle((x, y), radius,
            dxfattribs={"layer": "CUTTING"}).dxf.handle
        for (x, y), radius in zip(centers, radii)
    ]
    doc.saveas(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    original = _request(count=count)
    for item in original["items"]:
        item["source_document_sha256"] = sha
    original["request_digest"] = compute_wire_request_digest(original)

    resource, _, _ = _root(tmp_path)
    receipt = _prepare(original, resource)
    export = _export_request_from_prepared(original, receipt)
    for i, (row, received) in enumerate(zip(export["items"], receipt["items"])):
        frame = received["target_frames"][0]
        feature = _circle(frame)
        feature["feature_id"] = f"door-circle-{i}"
        feature["source_ref"] = f"original-dxf-entity-{i}"
        feature["center_mm"] = list(centers[i])
        feature["radius_mm"] = radii[i]
        feature["source_transform"]["source_entity_refs"] = [handles[i]]
        feature["source_transform"]["target_dimensions_mm"] = deepcopy(
            frame["finished_face_dimensions_mm"])
        row["features"] = [feature]
    export["request_digest"] = compute_wire_request_digest(export)
    trusted_paths = {x["item_id"]: source for x in original["items"]}
    return original, receipt, export, resource, trusted_paths, source, centers, radii


def _save(batch, target, **kwargs):
    original, receipt, export, root, trusted_paths, *_ = batch
    arguments = {
        "source_documents": trusted_paths,
        "resource_root": root,
        "output_dir": target,
        "engine_commit": COMMIT,
        "engine_sha256": ENGINE,
        "build_id": "test-only-source",
        "worker_key": KEY,
    }
    arguments.update(kwargs)
    return save_trusted_door_circle_finalscene_batch(original, receipt, export, **arguments)


def test_real_two_door_original_source_to_canonical_finalscene_roundtrip(tmp_path, monkeypatch):
    original, receipt, export, root, paths, source, centers, radii = batch = _real_batch(tmp_path)
    from integration_cli import verified_door_finalscene as subject
    actual_rechecks = []
    real = subject.recheck_trusted_door_export

    def counted(*args, **kwargs):
        actual_rechecks.append(True)
        return real(*args, **kwargs)
    monkeypatch.setattr(subject, "recheck_trusted_door_export", counted)
    target = tmp_path / "manufacturing"
    output = _save(batch, target)
    assert len(output) == 2
    assert len(actual_rechecks) == 3  # before render, before staging, before commit
    assert set(output) == {i["physical_part_id"] for i in receipt["items"]}
    assert {f.name for f in target.glob("*.dxf")} == {f"{p}.dxf" for p in output}
    assert not list(target.glob(".whd-dxf-stage-*"))

    for i, (part, prepared, path) in enumerate(
        zip(original["items"], receipt["items"], output.values())
    ):
        doc = ezdxf.readfile(path)  # independent real disk reload
        modelspace = doc.modelspace()
        assert any(e.dxf.layer == "BEND" for e in modelspace)
        spec = door_spec_from_trusted_prepared_part(
            part["part"], api.resolve_policy(ManufacturingContext(resource_root=root)))
        source_features = verify_trusted_original_dxf_circles(
            export["items"][i]["features"], source_path=source,
            expected_document_sha256=part["source_document_sha256"])
        marked = tuple(replace(c, source_type="cadsplit_source_verified_circle_v1")
                       for c in source_features)
        spec = replace(spec, features=marked, feature_space="finished_face")
        context = ManufacturingContext(resource_root=root)
        mapped = _door_features_for_legacy_engine(spec, context)
        expected = mapped[0]
        circles = [
            e for e in modelspace.query('CIRCLE[layer=="CUTTING"]')
            if math.isclose(e.dxf.radius, radii[i], abs_tol=1e-6, rel_tol=0)
            and math.isclose(e.dxf.center.x, expected.offset.x, abs_tol=1e-6, rel_tol=0)
            and math.isclose(e.dxf.center.y, expected.offset.y, abs_tol=1e-6, rel_tol=0)
        ]
        assert len(circles) == 1, "source-attested WHD CIRCLE missing in saved FinalScene"
        assert api.verify_saved_part_render_data_dxf(
            api.build_part_render_data(spec, context), path
        ).ok


def test_source_mutation_after_staged_reload_refuses_entire_batch(tmp_path, monkeypatch):
    from ae_engine import manufacturing_verification
    batch = _real_batch(tmp_path)
    source = batch[5]
    target = tmp_path / "out"
    target.mkdir()
    name = batch[1]["items"][0]["physical_part_id"] + ".dxf"
    (target / name).write_bytes(b"existing-production-output")
    real = manufacturing_verification.verify_saved_part_render_data_dxf
    calls = []

    def change_source_after_reload(render, staged):
        outcome = real(render, staged)
        calls.append(staged)
        if len(calls) == 2:
            assert outcome.ok
            source.write_bytes(source.read_bytes() + b"\n")
        return outcome

    monkeypatch.setattr(manufacturing_verification, "verify_saved_part_render_data_dxf",
                        change_source_after_reload)
    with pytest.raises(PrepareEvidenceError) as err:
        _save(batch, target, overwrite=True)
    assert err.value.code == "WHD_SOURCE_UNVERIFIED"
    assert len(calls) == 2
    assert (target / name).read_bytes() == b"existing-production-output"
    assert {f.name for f in target.glob("*.dxf")} == {name}
    assert not list(target.glob(".whd-dxf-stage-*"))


def test_changed_source_or_missing_worker_custody_fails_before_any_output(tmp_path):
    batch = _real_batch(tmp_path)
    target = tmp_path / "out"
    original, receipt, export, resource, paths, source, *_ = batch
    with pytest.raises(PrepareEvidenceError) as missing:
        _save(batch, target, source_documents={})
    assert missing.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not target.exists()
    source.write_bytes(source.read_bytes() + b"changed-after-prepare")
    with pytest.raises(PrepareEvidenceError) as stale:
        _save(batch, target)
    assert stale.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not target.exists()


def test_invalid_transaction_and_empty_source_inventory_fail_closed(tmp_path):
    batch = _real_batch(tmp_path)
    export = batch[2]
    target = tmp_path / "out"
    export["transaction_mode"] = "per_part"
    export["request_digest"] = compute_wire_request_digest(export)
    with pytest.raises(PrepareEvidenceError) as mode:
        _save(batch, target)
    assert mode.value.code == "WHD_FINALSCENE_UNVERIFIED"
    export["transaction_mode"] = "all_or_nothing"
    export["items"][0]["features"] = []
    export["request_digest"] = compute_wire_request_digest(export)
    with pytest.raises(PrepareEvidenceError) as no_source:
        _save(batch, target)
    assert no_source.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not target.exists()


def test_whd_scene_dropping_attested_circle_is_not_saved(tmp_path, monkeypatch):
    batch = _real_batch(tmp_path)
    target = tmp_path / "out"
    original = api.build_part_render_data

    def lose_source_feature(spec, context):
        render = original(spec, context)
        filtered = DrawingScene()
        filtered.extend(p for p in render.scene.primitives
                        if not (isinstance(p, CirclePrimitive)
                        and p.source_type == "cadsplit_source_verified_circle_v1"))
        return replace(render, scene=filtered)

    monkeypatch.setattr(api, "build_part_render_data", lose_source_feature)
    with pytest.raises(PrepareEvidenceError) as missing:
        _save(batch, target)
    assert missing.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not target.exists()


def _mixed_rect_batch(tmp_path, *, fault=None, rotation=0):
    """One real source CIRCLE and one independently reloaded original rectangle."""
    batch = _real_batch(tmp_path, count=2)
    original, _old_receipt, _old_export, root, paths, source, centers, radii = batch
    doc = ezdxf.readfile(source)
    msp = doc.modelspace()
    previous = list(msp.query("CIRCLE"))
    assert len(previous) == 2
    handle_circle = previous[0].dxf.handle
    msp.delete_entity(previous[1])
    vertices = [(36,34), (44,34), (44,46), (36,46)]
    if fault == "bow_tie":
        vertices = [(36,34), (44,46), (44,34), (36,46)]
    if fault == "slanted":
        vertices = [(36,34), (44,34), (45,46), (36,46)]
    if fault == "bulge":
        vertices = [(36,34,0.25), (44,34,0), (44,46,0), (36,46,0)]
    rect = msp.add_lwpolyline(
        vertices, format="xyb" if fault == "bulge" else "xy",
        close=(fault != "open"), dxfattribs={"layer": "CUTTING"},
    )
    handle_rect = rect.dxf.handle
    doc.saveas(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for item in original["items"]:
        item["source_document_sha256"] = sha
    original["request_digest"] = compute_wire_request_digest(original)
    receipt = _prepare(original, root)
    exported = _export_request_from_prepared(original, receipt)
    for idx, row in enumerate(exported["items"]):
        frame = receipt["items"][idx]["target_frames"][0]
        feature = _circle(frame)
        feature["source_transform"]["target_dimensions_mm"] = deepcopy(
            frame["finished_face_dimensions_mm"])
        if idx == 0:
            feature["center_mm"] = [20, 30]
            feature["radius_mm"] = 3
            feature["source_transform"]["source_entity_refs"] = [handle_circle]
        else:
            feature["feature_id"] = "source-rectangle"
            feature["source_ref"] = "original-LWPOLYLINE"
            feature["type"] = "rect"
            del feature["radius_mm"]
            feature["width_mm"] = 8
            feature["height_mm"] = 12
            feature["rotation_deg"] = 0
            feature["center_mm"] = [40, 40]
            feature["source_transform"]["source_entity_refs"] = [handle_rect]
            if rotation == 90:
                feature["rotation_deg"] = 90
                feature["source_transform"]["rotation_deg"] = 90
                feature["source_transform"]["matrix_2x2"] = [[0,-1],[1,0]]
                feature["source_transform"]["translation_mm"] = [90, 0]
                feature["center_mm"] = [50,40]
            if fault == "claimed_width":
                feature["width_mm"] = 9
        row["features"] = [feature]
    exported["request_digest"] = compute_wire_request_digest(exported)
    return original, receipt, exported, root, paths, source, centers, radii


@pytest.mark.parametrize("turn", [0, 90])
def test_original_source_rectangle_and_circle_survive_real_finalscene_batch(tmp_path, turn):
    from ae_engine.sheetmetal_features import RectFeature, ResolvedRect
    batch = _mixed_rect_batch(tmp_path, rotation=turn)
    original, receipt, request, root, paths, source, *_ = batch
    target = tmp_path / "rect-manufacturing"
    output = _save(batch, target)
    assert len(output) == 2
    assert len(list(target.glob("*.dxf"))) == 2
    rect_path = output[receipt["items"][1]["physical_part_id"]]
    doc = ezdxf.readfile(rect_path)
    spec = door_spec_from_trusted_prepared_part(
        original["items"][1]["part"], api.resolve_policy(ManufacturingContext(resource_root=root)))
    features = verify_trusted_original_dxf_circles(
        request["items"][1]["features"], source_path=source,
        expected_document_sha256=original["items"][1]["source_document_sha256"],
    )
    assert len(features) == 1 and isinstance(features[0], RectFeature)
    assert features[0].rotation_deg == 0
    spec = replace(spec, features=features)
    context = ManufacturingContext(resource_root=root)
    mapped = _door_features_for_legacy_engine(spec, context)[0]
    expected = ResolvedRect(
        center=mapped.offset, width=mapped.width, height=mapped.height,
        rotation_deg=mapped.rotation_deg,
    ).points
    def covers_expected(poly):
        if not poly.closed:
            return False
        points = [(x,y) for x,y in poly.get_points("xy")]
        if len(points) != 4:
            return False
        remaining = list(expected)
        for x,y in points:
            found = [p for p in remaining
                     if math.isclose(p.x,x,abs_tol=1e-6,rel_tol=0)
                     and math.isclose(p.y,y,abs_tol=1e-6,rel_tol=0)]
            if len(found)!=1:
                return False
            remaining.remove(found[0])
        return True
    matches = [p for p in doc.modelspace().query('LWPOLYLINE[layer=="CUTTING"]')
               if covers_expected(p)]
    assert len(matches) == 1, "source-attested RECT must survive WHD DXF Save→Reload"
    assert any(e.dxf.layer == "BEND" for e in doc.modelspace())
    assert api.verify_saved_part_render_data_dxf(
        api.build_part_render_data(spec, context), rect_path).ok


@pytest.mark.parametrize("fault", ["open", "bulge", "bow_tie", "slanted", "claimed_width"])
def test_invalid_original_source_rectangle_refuses_any_output(tmp_path, fault):
    batch = _mixed_rect_batch(tmp_path, fault=fault)
    target = tmp_path / "out"
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(batch, target)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not target.exists()


def test_source_profile_remains_fail_closed_after_rect_adapter(tmp_path):
    batch = _mixed_rect_batch(tmp_path)
    exported = batch[2]
    feature = exported["items"][1]["features"][0]
    feature["type"] = "profile"
    feature["points_mm"] = [[36,34],[44,34],[44,46],[36,46]]
    feature["closed"] = True
    for key in ("center_mm", "width_mm", "height_mm", "rotation_deg"):
        del feature[key]
    exported["request_digest"] = compute_wire_request_digest(exported)
    target = tmp_path / "out"
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(batch, target)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not target.exists()
