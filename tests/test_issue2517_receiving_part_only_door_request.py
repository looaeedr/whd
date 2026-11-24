"""Real reviewed factory Door sources: independent result and exact DXF reopen."""
from dataclasses import replace

import ezdxf
import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import receiving_factory_requests as factory
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue2517_receiving_confirmed_door_source import ROOT, SOURCE, UPPER_LOWER

CTX = ManufacturingContext(resource_root=ROOT)
UPPER, LOWER = ("door_c1_r1", "door_c1_r2")


def feature(x=350., y=225., diameter=14.):
    return CircleFeature(diameter=diameter, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                         offset=Vec2(x, y), layer="CUTTING")


def resolve(key, features=(), **kwargs):
    return api.resolve_receiving_part_only_door_request(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=UPPER_LOWER, door_part_key=key,
        features=features, context=CTX, **kwargs,
    )


@pytest.mark.parametrize("key", [UPPER, LOWER])
def test_real_confirmed_independent_door_reuses_factory_scene_and_dxf(key, tmp_path):
    assert ae_engine.resolve_receiving_part_only_door_request is api.resolve_receiving_part_only_door_request
    assert ae_engine.ReceivingPartOnlyDoorIndicatorIntent is api.ReceivingPartOnlyDoorIndicatorIntent
    raw = [feature()]
    normal = resolve(key, raw)
    assert tuple(p.part_key for p in normal.parts) == (key,)
    expected_owner = dict(api.plan_receiving_factory_confirmed_door_handoff(
        SOURCE, confirmation="fresh_family_confirmed", confirmed_door_layout_columns=UPPER_LOWER,
    ).door_parts)[key]
    expected = api.build_operator_part_render_data(replace(expected_owner, features=tuple(raw)), CTX)
    actual = normal.parts[0].render_data
    assert actual.scene == expected.scene and actual.material.equals(expected.material)
    assert raw == [feature()]
    seen = []
    files = api.save_verified_resolved_manufacturing_geometry_batch_dxf(
        (("source-panel", normal),), tmp_path, pre_commit_guard=lambda: seen.append(True),
    )
    path, = files.values()
    dxf = ezdxf.readfile(path)
    assert len(seen) >= 2 and dxf.units == 4 and not dxf.audit().errors
    assert any(c.dxf.layer == "CUTTING" and c.dxf.radius == pytest.approx(7)
               for c in dxf.modelspace().query("CIRCLE"))


def test_one_bad_door_does_not_disqualify_the_other_and_unknown_key_rejected():
    with pytest.raises(ValueError, match="(outside|超出|邊界)"):
        resolve(UPPER, (feature(900., 900.),))
    assert tuple(p.part_key for p in resolve(LOWER,(feature(),)).parts) == (LOWER,)
    with pytest.raises(ValueError, match="RECEIVING_PART_ONLY_DOOR_OWNER_REQUIRED"):
        resolve("door_c2_r1")


def test_wrong_engine_door_coordinate_space_is_rejected_not_relabelled(monkeypatch):
    original = factory.build_receiving_factory_confirmed_parts

    def drift(*args, **kwargs):
        return tuple((key, replace(spec, feature_space="legacy_unfolded"))
                     if isinstance(spec, DoorPartSpec) else (key, spec)
                     for key, spec in original(*args, **kwargs))

    monkeypatch.setattr(factory, "build_receiving_factory_confirmed_parts", drift)
    with pytest.raises(ValueError, match="RECEIVING_ENGINE_CONFIRMED_PART_ROLES_INVALID"):
        resolve(UPPER)


def test_indicator_source_uses_existing_engine_and_never_returns_hole_only_box(tmp_path):
    direct = api.ReceivingPartOnlyDoorIndicatorIntent("door_indicator", (2,), Vec2(350.,480.))
    assert tuple(p.part_key for p in resolve(UPPER, indicator=direct).parts) == (UPPER,)
    box = replace(direct, kind="indicator_box")
    result = resolve(UPPER, indicator=box)
    assert tuple(p.part_key for p in result.parts) == (
        UPPER, UPPER + "_indicator_box", UPPER + "_indicator_small_door",
    )
    files = api.save_verified_resolved_manufacturing_geometry_batch_dxf(
        (("source-panel", result),), tmp_path, pre_commit_guard=lambda: None,
    )
    assert len(files) == 3
    for path in files.values():
        doc=ezdxf.readfile(path)
        assert not doc.audit().errors and doc.units==4
    with pytest.raises(ValueError, match="RECEIVING_DOOR_INDICATOR_BOX_OUTSIDE_FACE"):
        resolve(UPPER, indicator=replace(box, finished_center=Vec2(2., 2.)))
    with pytest.raises(ValueError):
        resolve(UPPER, indicator=replace(box, groups=(True,)))


def test_confirmed_source_uses_cad_finished_face_anchors_and_process_layers():
    from ae_engine.manufacturing_door_indicator import door_finished_face_size
    from ae_engine.sheetmetal_feature_surface import reanchor_feature

    spec = dict(api.plan_receiving_factory_confirmed_door_handoff(
        SOURCE, confirmation="fresh_family_confirmed", confirmed_door_layout_columns=UPPER_LOWER,
    ).door_parts)[UPPER]
    width, height = door_finished_face_size(spec, CTX)
    absolute = feature()
    for anchor in FeatureAnchor:  # existing CAD extractor chooses nearest relative anchor
        relative = reanchor_feature(absolute, anchor, width, height)
        assert resolve(UPPER, (relative,)).parts[0].render_data.scene == resolve(
            UPPER, (absolute,),
        ).parts[0].render_data.scene
    holes = (
        replace(feature(), layer="BLIND_HOLE", add_centerline=True),
        replace(feature(x=450.), layer="MARKING"),
    )
    scene = resolve(UPPER, holes).parts[0].render_data.scene
    assert {"BLIND_HOLE", "MARKING"}.issubset({p.layer for p in scene.primitives})
    points = (Vec2(-4., -4.), Vec2(4., -4.), Vec2(4., 4.), Vec2(-4., 4.))
    profile = ProfileFeature(
        points=points, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(350., 225.), layer="FROM_DXF",
        layered_profiles=(("CUTTING", points, True),
                          ("MARKING", (Vec2(-2., 0.), Vec2(2., 0.)), False)),
    )
    assert any(p.layer == "MARKING"
               for p in resolve(UPPER, (profile,)).parts[0].render_data.scene.primitives)
    bad = (
        replace(absolute, anchor="legacy_unfolded"),
        replace(absolute, anchor="panel_center"),
        replace(absolute, layer="BEND"),
        replace(absolute, rotation_deg=True),
        replace(absolute, diameter=False),
        replace(profile, layered_profiles=(("BEND", points, True),)),
        replace(profile, layered_profiles=()),
    )
    for item in bad:
        with pytest.raises(ValueError, match="RECEIVING_PART_ONLY_DOOR_FEATURE_SOURCE_INVALID"):
            resolve(UPPER, (item,))
    # The existing source extractor is strict about touching the faced edge.
    for item in (feature(x=7.), feature(x=900.)):
        with pytest.raises(ValueError, match="feature outside canonical finished face"):
            resolve(UPPER, (item,))


def test_context_and_provenance_do_not_bypass_verified_sink(tmp_path):
    inputs = dict(confirmation="fresh_family_confirmed",
                  confirmed_door_layout_columns=UPPER_LOWER, door_part_key=UPPER)
    for bad in ({}, ManufacturingContext(policy=replace(api.resolve_policy(CTX), frame_width=35.))):
        with pytest.raises(ValueError, match="RECEIVING_PART_ONLY_DOOR_CONTEXT_INVALID"):
            api.resolve_receiving_part_only_door_request(SOURCE, **inputs, context=bad)
    for invalid_confirmation in (None, True, "saved_operator_confirmed"):
        with pytest.raises(ValueError, match="RECEIVING_PART_ONLY_DOOR_CONFIRMATION_REQUIRED"):
            api.resolve_receiving_part_only_door_request(
                SOURCE, **(inputs | {"confirmation": invalid_confirmation}), context=CTX,
            )
    with pytest.raises(ValueError):
        api.resolve_receiving_part_only_door_request(
            SOURCE | {"model": "金庫型"}, **inputs, context=CTX,
        )
    geometry = resolve(UPPER, (feature(),))
    assert len(geometry.parts) == 1 and not list(tmp_path.iterdir())

    def drift():
        raise ValueError("RECEIVING_SOURCE_REVISION_DRIFT")

    with pytest.raises(ValueError, match="RECEIVING_SOURCE_REVISION_DRIFT"):
        api.save_verified_resolved_manufacturing_geometry_batch_dxf(
            (("source-panel", geometry),), tmp_path, pre_commit_guard=drift,
        )
    assert not list(tmp_path.iterdir())


def test_public_api_explorer_lists_as_source_only():
    from tools.build_api_explorer import find_public_api

    row, = [item for item in find_public_api(ROOT)
            if item["name"] == "resolve_receiving_part_only_door_request"]
    assert row["category"] == "source"
    assert set(row["entrypoints"]) == {
        "ae_engine.resolve_receiving_part_only_door_request",
        "ae_engine.manufacturing_api.resolve_receiving_part_only_door_request",
    }
    assert "不等同已出圖" in row["status"]
