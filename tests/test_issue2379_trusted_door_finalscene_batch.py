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


def _real_batch(tmp_path, count=2, *, circle_thickness=0.0):
    source = tmp_path / "original-cadsplit.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    centers = [(20.0 + 20 * i, 30.0 + 10 * i) for i in range(count)]
    radii = [3.0 + i for i in range(count)]
    handles = [
        doc.modelspace().add_circle((x, y), radius,
            dxfattribs={"layer": "CUTTING", **({"thickness": circle_thickness}
                        if circle_thickness else {})}).dxf.handle
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


@pytest.mark.parametrize("thickness", [0.25, 1e-12])
def test_extruded_original_circle_refused_before_output(tmp_path, thickness):
    """Nonzero DXF thickness must not become an ordinary planar CUTTING hole."""
    batch = _real_batch(tmp_path, circle_thickness=thickness)
    target = tmp_path / "out"
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(batch, target)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
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
    if fault in ("bulge", "tiny_bulge"):
        vertices = [(36,34,1e-12 if fault == "tiny_bulge" else 0.25),
                    (44,34,0), (44,46,0), (36,46,0)]
    if fault == "vertex_width":
        vertices = [(36,34,0.25,0,0), (44,34,0,0,0),
                    (44,46,0,0,0), (36,46,0,0,0)]
    rect = msp.add_lwpolyline(
        vertices,
        format=("xyb" if fault in ("bulge", "tiny_bulge")
                else "xyseb" if fault == "vertex_width" else "xy"),
        close=(fault != "open"),
        dxfattribs={"layer": "CUTTING", **({"const_width": 0.25}
                      if fault == "const_width" else {}),
                    **({"thickness": 0.25 if fault == "thickness" else 1e-12}
                       if fault in ("thickness", "tiny_thickness") else {})},
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



@pytest.mark.parametrize(("order", "accepted"), [
    ((0, 2, 1, 3), False),  # crossed bow-tie: exact same four coordinates
    ((1, 2, 3, 0), True),   # rotated start index: same edge cycle
    ((0, 3, 2, 1), True),   # reverse winding: same edge cycle
])
def test_finalscene_rectangle_contour_requires_canonical_edge_cycle(
    tmp_path, monkeypatch, order, accepted,
):
    """Accept cyclic start/reversed winding; never accept crossed edges."""
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    from ae_engine.sheetmetal_features import RectFeature, ResolvedRect

    batch = _mixed_rect_batch(tmp_path)
    target = tmp_path / "out"
    original = api.build_part_render_data
    tampered = []

    def cross_original_rectangle(spec, context):
        render = original(spec, context)
        rectangles = [
            x for x in _door_features_for_legacy_engine(spec, context)
            if isinstance(x, RectFeature)
        ]
        if not rectangles:
            return render
        assert len(rectangles) == 1
        rect = rectangles[0]
        expected = ResolvedRect(
            center=rect.offset, width=rect.width, height=rect.height,
            rotation_deg=rect.rotation_deg,
        ).points

        def same_corners(primitive):
            if not (isinstance(primitive, PolylinePrimitive)
                    and primitive.closed and primitive.layer == "CUTTING"
                    and len(primitive.points) == len(expected)):
                return False
            available = list(expected)
            for actual in primitive.points:
                matches = [
                    point for point in available
                    if math.isclose(actual.x, point.x, abs_tol=1e-6, rel_tol=0)
                    and math.isclose(actual.y, point.y, abs_tol=1e-6, rel_tol=0)
                ]
                if len(matches) != 1:
                    return False
                available.remove(matches[0])
            return True

        altered = DrawingScene()
        for primitive in render.scene.primitives:
            if same_corners(primitive):
                p = primitive.points
                # Preserve every source-attested coordinate and bounding box.
                altered.add(replace(primitive, points=tuple(p[i] for i in order)))
                tampered.append(True)
            else:
                altered.add(primitive)
        return replace(render, scene=altered)

    monkeypatch.setattr(api, "build_part_render_data", cross_original_rectangle)
    if accepted:
        output = _save(batch, target)
        assert len(output) == 2
        assert len(list(target.glob("*.dxf"))) == 2
    else:
        with pytest.raises(PrepareEvidenceError) as exc:
            _save(batch, target)
        assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
        assert not target.exists()
    assert tampered == [True], "test must alter the real source-derived RECT"


@pytest.mark.parametrize("fault", ["open", "bulge", "tiny_bulge", "vertex_width", "const_width", "thickness", "tiny_thickness", "bow_tie", "slanted", "claimed_width"])
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
    feature["points_mm"] = [[36,34],[44,34],[44,46],[36,47]]
    feature["closed"] = True
    for key in ("center_mm", "width_mm", "height_mm", "rotation_deg"):
        del feature[key]
    exported["request_digest"] = compute_wire_request_digest(exported)
    target = tmp_path / "out"
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(batch, target)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not target.exists()


def _mixed_source_profile_batch(tmp_path, *, fault=None, rotation=0):
    """Actual source CADSplit DXF with one Door circle and one concave profile."""
    batch = _real_batch(tmp_path, count=2)
    original, _, _, root, paths, source, centers, radii = batch
    doc = ezdxf.readfile(source)
    model = doc.modelspace()
    circles = list(model.query("CIRCLE"))
    handle_circle = circles[0].dxf.handle
    model.delete_entity(circles[1])
    vertices = [(36, 34), (46, 34), (46, 46), (41, 41), (36, 46)]
    source_vertices = list(vertices)
    if fault == "crossed_source":
        source_vertices[1], source_vertices[2] = source_vertices[2], source_vertices[1]
    raw = source_vertices
    fmt = "xy"
    if fault in ("bulge", "tiny_bulge"):
        raw = [(x, y, 1e-12 if fault == "tiny_bulge" and i == 0
                else 0.5 if i == 0 else 0) for i, (x, y) in enumerate(raw)]
        fmt = "xyb"
    if fault == "width":
        raw = [(x, y, 0.5 if i == 0 else 0, 0, 0)
               for i, (x, y) in enumerate(raw)]
        fmt = "xyseb"
    if fault == "polyline":
        source_entity = model.add_polyline2d(source_vertices, close=True)
    else:
        source_entity = model.add_lwpolyline(
            raw, format=fmt, close=(fault != "open"),
            dxfattribs={"layer": "CUTTING",
                        **({"thickness": 0.5} if fault == "thickness" else {})},
        )
    handle_profile = source_entity.dxf.handle
    doc.saveas(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for row in original["items"]:
        row["source_document_sha256"] = sha
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
            feature["feature_id"] = "original-concave-profile"
            feature["source_ref"] = "source-LWPOLYLINE"
            feature["type"] = "profile"
            del feature["radius_mm"]
            del feature["center_mm"]
            feature["closed"] = True
            feature["points_mm"] = [list(p) for p in vertices]
            feature["source_transform"]["source_entity_refs"] = [handle_profile]
            if rotation == 90:
                feature["source_transform"]["rotation_deg"] = 90
                feature["source_transform"]["matrix_2x2"] = [[0, -1], [1, 0]]
                feature["source_transform"]["translation_mm"] = [90, 0]
                feature["points_mm"] = [[90 - y, x] for x, y in vertices]
            if fault == "claimed_vertex":
                feature["points_mm"][3][0] += 2
        row["features"] = [feature]
    exported["request_digest"] = compute_wire_request_digest(exported)
    return original, receipt, exported, root, paths, source, centers, radii


@pytest.mark.parametrize("rotation", [0, 90])
def test_original_concave_profile_to_whd_finalscene_real_saved_dxf(tmp_path, rotation):
    """Prove actual source vertices survive WHD authoritative Door manufacturing."""
    from ae_engine.sheetmetal_features import ProfileFeature
    batch = _mixed_source_profile_batch(tmp_path, rotation=rotation)
    original, receipt, exported, root, paths, source, *_ = batch
    target = tmp_path / "out"
    output = _save(batch, target)
    assert len(output) == 2
    assert len(list(target.glob("*.dxf"))) == 2
    doc = ezdxf.readfile(output[receipt["items"][1]["physical_part_id"]])
    spec = door_spec_from_trusted_prepared_part(
        original["items"][1]["part"],
        api.resolve_policy(ManufacturingContext(resource_root=root)),
    )
    features = verify_trusted_original_dxf_circles(
        exported["items"][1]["features"], source_path=source,
        expected_document_sha256=original["items"][1]["source_document_sha256"],
    )
    assert len(features) == 1 and isinstance(features[0], ProfileFeature)
    context = ManufacturingContext(resource_root=root)
    spec = replace(spec, features=features, feature_space="finished_face")
    mapped = _door_features_for_legacy_engine(spec, context)[0]
    expected = tuple((mapped.offset.x + v.x, mapped.offset.y + v.y)
                     for v in mapped.points)
    matching = []
    for poly in doc.modelspace().query('LWPOLYLINE[layer=="CUTTING"]'):
        actual = tuple(poly.get_points("xy"))
        if not poly.closed or len(actual) != len(expected):
            continue
        if all(math.isclose(x, expected[i][0], abs_tol=1e-6, rel_tol=0)
               and math.isclose(y, expected[i][1], abs_tol=1e-6, rel_tol=0)
               for i, (x, y) in enumerate(actual)):
            matching.append(poly)
    assert len(matching) == 1, "WHD source-derived concave CUTTING path must survive disk DXF"
    assert any(entity.dxf.layer == "BEND" for entity in doc.modelspace())
    assert api.verify_saved_part_render_data_dxf(
        api.build_part_render_data(spec, context),
        output[receipt["items"][1]["physical_part_id"]],
    ).ok


@pytest.mark.parametrize("fault", [
    "open", "bulge", "tiny_bulge", "width", "thickness",
    "polyline", "crossed_source", "claimed_vertex",
])
def test_unverified_original_profile_never_stages_output(tmp_path, fault):
    batch = _mixed_source_profile_batch(tmp_path, fault=fault)
    target = tmp_path / "out"
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(batch, target)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not target.exists()


def test_original_profile_finalscene_crossed_edges_refuse_staging(tmp_path, monkeypatch):
    """Even genuine source points cannot be silently reconnected by WHD."""
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    from ae_engine.sheetmetal_features import ProfileFeature

    batch = _mixed_source_profile_batch(tmp_path)
    target = tmp_path / "out"
    original = api.build_part_render_data
    changed = []

    def tamper_profile(spec, context):
        render = original(spec, context)
        profiles = [
            p for p in _door_features_for_legacy_engine(spec, context)
            if isinstance(p, ProfileFeature)
        ]
        if not profiles:
            return render
        assert len(profiles) == 1
        expected = [(p.x + profiles[0].offset.x, p.y + profiles[0].offset.y)
                    for p in profiles[0].points]
        scene = DrawingScene()
        for prim in render.scene.primitives:
            if (isinstance(prim, PolylinePrimitive) and prim.closed
                    and prim.layer == "CUTTING"
                    and len(prim.points) == len(expected)
                    and all(math.isclose(point.x, expected[i][0], abs_tol=1e-6, rel_tol=0)
                            and math.isclose(point.y, expected[i][1], abs_tol=1e-6, rel_tol=0)
                            for i, point in enumerate(prim.points))):
                pts = prim.points
                scene.add(replace(prim, points=(pts[0], pts[2], pts[1], pts[3], pts[4])))
                changed.append(True)
            else:
                scene.add(prim)
        return replace(render, scene=scene)

    monkeypatch.setattr(api, "build_part_render_data", tamper_profile)
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(batch, target)
    assert changed == [True]
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not target.exists()


# #2380 W-04 -> W-06 PRIVATE handoff acceptance: real WHD original DXF,
# canonical FinalScene, independently reloaded physical DXFs, durable commit.
def test_real_source_to_whd_finalscene_durable_commit_and_receipt(tmp_path):
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal

    batch = _real_batch(tmp_path, count=2)
    export = batch[2]
    output = tmp_path / "durable-customer-output"
    store = tmp_path / "trusted-worker-installation"
    output.mkdir()
    store.mkdir()
    ledger = DurableJobIdentityLedger(store)
    result = _save(batch, output, durable_ledger=ledger)
    assert len(result) == 2
    assert {p.name for p in output.glob("*.dxf")} == {f"{name}.dxf" for name in result}
    assert not list(output.glob(".whd-dxf-stage-*"))
    assert DurableJobIdentityLedger(store).claim(export).state == "committed"
    assert DurableMultiDXFRollbackJournal(ledger)._read(export)[0] == "committed"
    assert all(len(ezdxf.readfile(p).modelspace().query("CIRCLE")) >= 1 for p in result.values())
    with pytest.raises(PrepareEvidenceError):
        _save(batch, output, durable_ledger=DurableJobIdentityLedger(store))
    assert DurableJobIdentityLedger(store).claim(export).state == "committed"


def test_real_source_durable_commit_crash_mid_batch_then_fresh_recovery(tmp_path, monkeypatch):
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal

    batch = _real_batch(tmp_path, count=2)
    export = batch[2]
    # W-06 must not silently turn an authenticated no-clobber request into
    # overwrite=True. Sign that semantic intent in the export wire itself.
    export["output"]["overwrite"] = True
    export["request_digest"] = compute_wire_request_digest(export)
    output = tmp_path / "durable-output"
    store = tmp_path / "worker-store"
    output.mkdir()
    store.mkdir()
    ledger = DurableJobIdentityLedger(store)
    first = batch[1]["items"][0]["physical_part_id"]
    second = batch[1]["items"][1]["physical_part_id"]
    prior_doc = ezdxf.new("R2010")
    prior_doc.modelspace().add_circle((1, 1), 7.0, dxfattribs={"layer": "CUTTING"})
    customer_first = output / f"{first}.dxf"
    prior_doc.saveas(customer_first)
    prior_bytes, prior_mtime = customer_first.read_bytes(), customer_first.stat().st_mtime_ns
    from integration_cli import batch_commit_journal as transaction
    apply_original = transaction.DurableMultiDXFRollbackJournal.apply

    def process_interrupted(self, request):
        def kill_after_first(n):
            if n == 1:
                raise SystemExit("manufacturing process terminated mid commit")
        return apply_original(self, request, after_replace=kill_after_first)

    monkeypatch.setattr(transaction.DurableMultiDXFRollbackJournal, "apply", process_interrupted)
    with pytest.raises(SystemExit):
        _save(batch, output, durable_ledger=ledger, overwrite=True)
    journal = DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store))
    assert journal._read(export)[0] == "applying"
    assert journal.recover_rollback(export) == "rolled_back"
    assert (customer_first.read_bytes(), customer_first.stat().st_mtime_ns) == (prior_bytes, prior_mtime)
    assert not (output / f"{second}.dxf").exists()
    assert len(ezdxf.readfile(customer_first).modelspace().query("CIRCLE")) == 1
    assert DurableJobIdentityLedger(store).claim(export).state == "rolled_back"


def test_private_durable_source_export_requires_preexisting_worker_output_store(tmp_path):
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    batch = _real_batch(tmp_path, count=2)
    store = tmp_path / "worker-owned-store"
    store.mkdir()
    ledger = DurableJobIdentityLedger(store)
    nonexistent = tmp_path / "must-not-create-output"
    with pytest.raises(PrepareEvidenceError):
        _save(batch, nonexistent, durable_ledger=ledger)
    assert not nonexistent.exists()
    assert not list(store.glob("*.dxf"))


def test_twenty_unperforated_door_and_small_door_from_empty_source_real_finalscene(
    tmp_path,
):
    """WHD-authored 20 physical DXFs, genuine independent Save->Reload."""
    from tests.test_issue2378_prepare_batch import (
        _twenty_mixed_door_small_door_prepare, _prepare,
        _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest

    root, _shared, original = _twenty_mixed_door_small_door_prepare(tmp_path)
    source = tmp_path / "CADSplit 真正無孔原圖.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    assert len(doc.modelspace()) == 0
    doc.saveas(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for row in original["items"]:
        row["source_document_sha256"] = source_sha
    original["request_digest"] = compute_wire_request_digest(original)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    assert all(not row["features"] for row in export["items"])
    sources = {row["item_id"]: source for row in original["items"]}
    output = tmp_path / "20 件 無孔 WHD 真DXF"
    written = _save(
        (original, receipt, export, root, sources, source), output,
    )
    assert len(written) == 20
    assert set(written) == {p["physical_part_id"] for p in receipt["items"]}
    assert {p["part"]["kind"] for p in original["items"]} == {
        "door", "indicator_small_door",
    }
    for actual in written.values():
        saved = ezdxf.readfile(actual)
        assert saved.modelspace().query('LINE[layer=="BEND"]')
        assert any(entity.dxf.layer == "CUTTING" for entity in saved.modelspace())


@pytest.mark.parametrize("missing_kind", ["door", "indicator_small_door"])
def test_missing_original_features_never_turns_source_geometry_into_hole_free_dxf(
    tmp_path, missing_kind,
):
    from tests.test_issue2378_prepare_batch import (
        _twenty_mixed_door_small_door_prepare, _prepare,
        _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest
    from tests.test_issue2379_wire_feature_preflight import _circle

    root, _, original = _twenty_mixed_door_small_door_prepare(tmp_path)
    source = tmp_path / "CADSplit 有圖元但未申報.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_circle((12, 12), 3, dxfattribs={"layer": "CUTTING"})
    doc.saveas(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for part in original["items"]:
        part["source_document_sha256"] = sha
    original["request_digest"] = compute_wire_request_digest(original)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    # Mixed all-or-nothing: even a *single* zero-feature item with a
    # source entity must reject the whole customer manufacturing batch.
    target_idx = 0 if missing_kind == "door" else 1
    assert original["items"][target_idx]["part"]["kind"] == missing_kind
    for i, row in enumerate(export["items"]):
        if i != target_idx:
            frame = receipt["items"][i]["target_frames"][0]
            f = _circle(frame)
            f["center_mm"] = [12, 12]
            f["radius_mm"] = 3
            f["source_transform"]["source_entity_refs"] = [
                next(iter(doc.modelspace())).dxf.handle,
            ]
            f["source_transform"]["target_dimensions_mm"] = dict(
                frame["finished_face_dimensions_mm"],
            )
            row["features"] = [f]
    export["request_digest"] = compute_wire_request_digest(export)
    output = tmp_path / "不可產生任何零件"
    source_docs = {part["item_id"]: source for part in original["items"]}
    with pytest.raises(PrepareEvidenceError) as exc:
        _save((original, receipt, export, root, source_docs, source), output)
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not list(output.glob("*.dxf")) if output.exists() else True


def _empty_indicator_box_mixed_batch(tmp_path, *, count=20):
    """W-03 real owners for 1..20 Door, small-door and shared indicator box."""
    from tests.test_issue2378_prepare_batch import (
        _request, _prepare, _export_request_from_prepared,
        _indicator_box_request, _indicator_small_door_request,
    )
    from integration_cli.request_canonical import compute_wire_request_digest

    root, _, box = _indicator_box_request(tmp_path)
    _, _, small, _ = _indicator_small_door_request(tmp_path)
    original = _request(count=count)
    for i, row in enumerate(original["items"]):
        if i % 3 == 1:
            row["part"] = deepcopy(small["items"][0]["part"])
            row["part"]["source_part_ref"] = f"physical-small-door-{i}"
        elif i % 3 == 2:
            row["part"] = deepcopy(box["items"][0]["part"])
            row["part"]["source_part_ref"] = f"physical-indicator-box-{i}"
    source = tmp_path / "CADSplit 原圖無圖元-盒子門片混批.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    assert len(doc.modelspace()) == 0
    doc.saveas(source)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for row in original["items"]:
        row["source_document_sha256"] = sha
    original["request_digest"] = compute_wire_request_digest(original)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    sources = {row["item_id"]: source for row in original["items"]}
    return original, receipt, export, root, sources, source


def test_twenty_mixed_real_box_small_door_and_door_source_empty_native_dxf(tmp_path):
    """20 actual WHD intrinsic box/door FinalScenes and Save->Reload DXFs."""
    batch = _empty_indicator_box_mixed_batch(tmp_path, count=20)
    original, receipt, export, root, sources, source = batch
    assert {row["part"]["kind"] for row in original["items"]} == {
        "door", "indicator_small_door", "indicator_box",
    }
    box_items = [row for row in receipt["items"]
                 if row["target_frames"][0]["frame_id"].startswith("indicator_box:")]
    assert box_items and all(
        row["target_frames"][0]["allowed_feature_types"] == []
        for row in box_items
    )
    output = tmp_path / "20 件 真實箱盒無孔"
    produced = _save(batch, output)
    assert len(produced) == 20
    assert set(produced) == {r["physical_part_id"] for r in receipt["items"]}
    for path in produced.values():
        doc = ezdxf.readfile(path)
        assert any(e.dxf.layer == "CUTTING" for e in doc.modelspace())
        assert doc.modelspace().query('LINE[layer=="BEND"]')


def test_indicator_box_original_entity_cannot_be_silently_dropped_by_empty_features(tmp_path):
    """The box size-only Frame is NOT permission to ignore real CADSplit holes."""
    from tests.test_issue2378_prepare_batch import (
        _indicator_box_request, _prepare, _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest

    root, _, original = _indicator_box_request(tmp_path)
    source = tmp_path / "不允許忽略來源盒孔.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_circle((9, 9), 2, dxfattribs={"layer": "CUTTING"})
    doc.saveas(source)
    original["items"][0]["source_document_sha256"] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    original["request_digest"] = compute_wire_request_digest(original)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    output = tmp_path / "不得出圖"
    with pytest.raises(PrepareEvidenceError) as exc:
        _save(
            (original, receipt, export, root,
             {original["items"][0]["item_id"]: source}, source), output,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not list(output.rglob("*.dxf")) if output.exists() else True


def _empty_vault_endcap_five_kind_batch(tmp_path, *, count=20):
    """All five WHD P0 physical kinds with original source explicitly empty."""
    from tests.test_issue2378_prepare_batch import (
        _request, _prepare, _export_request_from_prepared, _root,
        _indicator_box_request, _indicator_small_door_request,
    )
    import shutil
    from integration_cli.request_canonical import compute_wire_request_digest
    from tests.test_issue2378_prepare_batch import HERE

    root, _, _ = _indicator_box_request(tmp_path)
    _, _, small, _ = _indicator_small_door_request(tmp_path)
    _, _, box = _indicator_box_request(tmp_path)
    endcap_baseline = root / "基準檔" / "金庫型" / "封頭尾.dxf"
    endcap_baseline.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "基準檔" / "金庫型" / "封頭尾.dxf", endcap_baseline)
    original = _request(count=count)
    for index, row in enumerate(original["items"]):
        kind = index % 5
        if kind == 1:
            row["part"] = deepcopy(small["items"][0]["part"])
        elif kind == 2:
            row["part"] = deepcopy(box["items"][0]["part"])
        elif kind in (3, 4):
            row["part"] = {
                "kind": "end_cap_head" if kind == 3 else "end_cap_tail",
                "cabinet_family": "金庫型",
                "source_part_ref": f"vault-endcap-original-{index}",
                "dimension_semantics": "cabinet_outer",
                "dimensions_mm": {
                    "width": 500.0, "depth": 300.0, "thickness": 2.0,
                },
            }
        row["part"]["source_part_ref"] = f"physical-original-part-{index}"
    original_source = tmp_path / "CADSplit 全部空白的正式原圖.dxf"
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 4
    assert len(drawing.modelspace()) == 0
    drawing.saveas(original_source)
    sha = hashlib.sha256(original_source.read_bytes()).hexdigest()
    for row in original["items"]:
        row["source_document_sha256"] = sha
    original["request_digest"] = compute_wire_request_digest(original)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    documents = {row["item_id"]: original_source for row in original["items"]}
    return (original, receipt, export, root, documents, original_source)


def test_vault_head_tail_native_finalscene_twenty_mixed_five_physical_kinds(tmp_path):
    """Actual certified WHD source owners, not projected placeholder DXF."""
    batch = _empty_vault_endcap_five_kind_batch(tmp_path)
    original, receipt, export, root, documents, source = batch
    assert {row["part"]["kind"] for row in original["items"]} == {
        "door", "indicator_small_door", "indicator_box",
        "end_cap_head", "end_cap_tail",
    }
    assert all(
        row["target_frames"][0]["allowed_feature_types"] == []
        for original_row, row in zip(original["items"], receipt["items"])
        if original_row["part"]["kind"] in (
            "end_cap_head", "end_cap_tail", "indicator_box",
        )
    )
    finished = _save(batch, tmp_path / "真實五類20片出圖")
    assert len(finished) == 20
    assert set(finished) == {row["physical_part_id"] for row in receipt["items"]}
    for physical, filepath in finished.items():
        drawing = ezdxf.readfile(filepath)
        assert any(e.dxf.layer == "CUTTING" for e in drawing.modelspace()), physical
        assert drawing.modelspace().query('LINE[layer=="BEND"]'), physical


@pytest.mark.parametrize("kind", ["end_cap_head", "end_cap_tail"])
@pytest.mark.parametrize("attack", ["omitted_original_geometry", "forged_external_feature"])
def test_vault_endcap_rejects_nonempty_source_or_feature_before_any_dxf(
    tmp_path, kind, attack,
):
    from tests.test_issue2378_prepare_batch import (
        _vault_endcap_request, _prepare, _export_request_from_prepared,
    )
    root, _, request = _vault_endcap_request(tmp_path, kind=kind)
    source = tmp_path / f"CADSplit-{kind}-original.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if attack == "omitted_original_geometry":
        doc.modelspace().add_circle((9, 15), 3, dxfattribs={"layer": "CUTTING"})
    doc.saveas(source)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    if attack == "forged_external_feature":
        export["items"][0]["features"] = [_circle(receipt["items"][0]["target_frames"][0])]
        export["request_digest"] = compute_wire_request_digest(export)
    output = tmp_path / "受限制的封頭尾輸出"
    with pytest.raises(PrepareEvidenceError):
        _save(
            (request, receipt, export, root, {request["items"][0]["item_id"]: source}, source),
            output,
        )
    assert not list(output.rglob("*.dxf"))


@pytest.mark.parametrize("source_kind", ["circle", "rect", "profile"])
@pytest.mark.parametrize("invalid_layer", ["MARKING", "BEND", "CHECK", "0"])
def test_real_original_noncutting_entity_cannot_be_relabelled_as_through_cut(
    tmp_path, source_kind, invalid_layer,
):
    """A signed source handle/shape is NOT permission to manufacture a marker.

    Re-sign the real, modified DXF and prepare a fresh W-03 receipt so this
    asserts the source-layer trust boundary, not an unrelated SHA stale check.
    Preserve a preexisting customer output even under overwrite=True.
    """
    if source_kind == "circle":
        batch = _real_batch(tmp_path, count=1)
        attack_index = 0
    elif source_kind == "rect":
        batch = _mixed_rect_batch(tmp_path)
        attack_index = 1
    else:
        batch = _mixed_source_profile_batch(tmp_path)
        attack_index = 1
    original, _old_receipt, old_export, root, sources, source, *_ = batch
    feature = old_export["items"][attack_index]["features"][0]
    handle = feature["source_transform"]["source_entity_refs"][0]
    doc = ezdxf.readfile(source)
    entity = doc.entitydb.get(handle)
    assert entity is not None and entity.dxf.layer == "CUTTING"
    assert entity.dxftype() == ("CIRCLE" if source_kind == "circle" else "LWPOLYLINE")
    entity.dxf.layer = invalid_layer
    doc.saveas(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for item in original["items"]:
        item["source_document_sha256"] = source_sha
    original["request_digest"] = compute_wire_request_digest(original)
    from tests.test_issue2378_prepare_batch import _prepare, _export_request_from_prepared
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    for index, (old_item, new_item) in enumerate(zip(old_export["items"], export["items"])):
        # A changed original SHA changes the WHD-issued physical identity and
        # Frame ID. Bind the *same source handles* to the genuinely fresh
        # signed Frame, or this never reaches the source-layer RED oracle.
        fresh_frame = receipt["items"][index]["target_frames"][0]
        new_item["features"] = deepcopy(old_item["features"])
        for feature in new_item["features"]:
            feature["target_frame_id"] = fresh_frame["frame_id"]
            feature["source_transform"]["target_dimensions_mm"] = deepcopy(
                fresh_frame["finished_face_dimensions_mm"]
            )
    export["request_digest"] = compute_wire_request_digest(export)
    target = tmp_path / f"cannot-cut-{source_kind}-{invalid_layer}"
    target.mkdir()
    persisted = target / (receipt["items"][0]["physical_part_id"] + ".dxf")
    persisted.write_bytes(b"previous-customer-DXF-must-survive")
    with pytest.raises(PrepareEvidenceError) as exc:
        _save((original, receipt, export, root, sources, source),
              target, overwrite=True)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert persisted.read_bytes() == b"previous-customer-DXF-must-survive"
    assert list(target.glob("*.dxf")) == [persisted]
    assert not list(target.glob(".whd-dxf-stage-*"))


def test_real_source_case_insensitive_cutting_layer_is_still_supported(tmp_path):
    """DXF layer spelling case does not change the source's CUTTING meaning."""
    batch = _real_batch(tmp_path, count=1)
    source = batch[5]
    doc = ezdxf.readfile(source)
    circle = next(iter(doc.modelspace().query("CIRCLE")))
    circle.dxf.layer = "cutting"
    doc.saveas(source)
    original, _old_receipt, old_export, root, sources, *_ = batch
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for item in original["items"]:
        item["source_document_sha256"] = source_sha
    original["request_digest"] = compute_wire_request_digest(original)
    from tests.test_issue2378_prepare_batch import _prepare, _export_request_from_prepared
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    export["items"][0]["features"] = deepcopy(old_export["items"][0]["features"])
    fresh_frame = receipt["items"][0]["target_frames"][0]
    export["items"][0]["features"][0]["target_frame_id"] = fresh_frame["frame_id"]
    export["items"][0]["features"][0]["source_transform"]["target_dimensions_mm"] = (
        deepcopy(fresh_frame["finished_face_dimensions_mm"])
    )
    export["request_digest"] = compute_wire_request_digest(export)
    produced = _save((original, receipt, export, root, sources, source),
                     tmp_path / "case-insensitive-real-cutting")
    assert len(produced) == 1
    saved = ezdxf.readfile(next(iter(produced.values())))
    assert saved.modelspace().query('CIRCLE[layer=="CUTTING"]')
