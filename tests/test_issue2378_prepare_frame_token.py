# -*- coding: utf-8 -*-
"""#2378 actual Door-local Frame plus HMAC prepare binding unit contracts."""
from copy import deepcopy

import pytest

from integration_cli.prepare_binding import (
    create_preparation_binding, verify_preparation_binding,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.prepare_frame import resolve_door_finished_local_frame

SECRET = b"trusted-test-worker-installation-key-" + b"x" * 32
ENV = "c" * 64
SOURCE = "f" * 64


def _spec_and_context():
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext, ManufacturingPolicy
    from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
    policy = ManufacturingPolicy(
        default_thickness=2.0, frame_width=25.0, door_gap_w=1.0, door_gap_h=1.5,
        door_fold_left=19.0, door_fold_right=21.0,
        door_fold_top=17.0, door_fold_bottom=18.0, indicator_box_fold=49.0,
    )
    spec = DoorPartSpec(
        width=500, height=600, thickness=2.0, frame_width=25.0,
        model_name="金庫型",
        frame_edges=DoorFrameEdges(left=True,right=False,top=True,bottom=False),
    )
    return spec, ManufacturingContext(policy=policy)


def _prepared_items():
    spec, context = _spec_and_context()
    frame = resolve_door_finished_local_frame(
        spec, context, physical_part_id="whd-door-1"
    )
    return [{
        "item_id": "門片-01",
        "physical_part_id": "whd-door-1",
        "source_part_ref": "來源DXF/門片-01",
        "source_document_sha256": SOURCE,
        "target_frame": frame,
        "locked_dimensions_mm": {
            "cabinet_width": 500.0, "cabinet_height": 600.0,
            "finished_width": frame["finished_face_dimensions_mm"]["width"],
            "finished_height": frame["finished_face_dimensions_mm"]["height"],
            "thickness": 2.0, "frame_width": 25.0,
        },
    }]


def _seal(items=None, **options):
    args = dict(worker_key=SECRET, client_installation_id="CAD-1",
                job_id="job-123", environment_fingerprint=ENV,
                prepared_items=_prepared_items() if items is None else items)
    args.update(options)
    return args


def test_door_local_frame_uses_real_whd_bottom_left_and_positive_y_up():
    from ae_engine.sheetmetal_part_adapters import build_door_result, build_finished_reference_guide
    from ae_engine.sheetmetal_features import (
        CircleFeature, FeatureAnchor, Vec2, feature_finished_point,
    )
    from ae_engine.manufacturing_api import door_finished_face_size

    spec, context = _spec_and_context()
    frame = resolve_door_finished_local_frame(spec, context, physical_part_id="whd-door-1")
    w, h = door_finished_face_size(spec, context)
    assert frame["finished_face_dimensions_mm"] == {"width":w,"height":h}
    assert frame["origin_xyz_mm"] == [0.0, 0.0, 0.0]
    assert frame["axis_x"] == [1.0, 0.0, 0.0]
    assert frame["axis_y"] == [0.0, 1.0, 0.0]
    assert frame["normal"] == [0.0, 0.0, 1.0]
    assert frame["face_role"] == "front"
    assert "NOT cabinet-world" in frame["origin_definition"]
    assert frame["viewed_from"] == "along_normal"
    p = context.policy
    result = build_door_result(
        w=spec.width,h=spec.height,t=spec.thickness,
        fw=spec.frame_width,gap_w=p.door_gap_w,gap_h=p.door_gap_h,
        fold_left=p.door_fold_left,fold_right=p.door_fold_right,
        fold_top=p.door_fold_top,fold_bottom=p.door_fold_bottom,
        frame_edges=spec.frame_edges,
    )
    guide = build_finished_reference_guide(
        "door", result, finished_width=w, finished_height=h
    )
    for anchor, xx, yy in (
        (FeatureAnchor.BOTTOM_LEFT, 0, 0),
        (FeatureAnchor.TOP_RIGHT, w, h),
        (FeatureAnchor.ABSOLUTE_FINISHED_FACE, 0, 0),
    ):
        local = feature_finished_point(
            CircleFeature(diameter=1, anchor=anchor, offset=Vec2(0,0)),w,h
        )
        assert (local.x,local.y) == (xx,yy)
        # Existing owner maps the same local frame to flattened sheet.
        assert (guide.min_point.x + local.x,guide.min_point.y + local.y) == (
            guide.min_point.x + xx,guide.min_point.y + yy
        )


def test_frame_rejects_unsupported_part_kind_and_untrusted_physical_id():
    from ae_engine.contracts import EndCapPartSpec
    spec, context = _spec_and_context()
    with pytest.raises(PrepareEvidenceError):
        resolve_door_finished_local_frame(spec,context,physical_part_id="../bad")
    endcap = EndCapPartSpec(width=500,depth=250,thickness=2,frame_width=25)
    with pytest.raises(PrepareEvidenceError):
        resolve_door_finished_local_frame(endcap,context,physical_part_id="endcap1")


def test_token_is_stable_opaque_and_contains_separate_per_item_digest():
    args = _seal()
    one = create_preparation_binding(**args)
    two = create_preparation_binding(**args)
    assert one == two
    assert one["prepare_token"].startswith("w3.")
    assert len(one["prepare_token"]) <= 256
    assert one["item_preparation_digests"]["門片-01"] != one["preparation_digest"]
    verify_preparation_binding(one["prepare_token"], **args)


@pytest.mark.parametrize("change", [
    "client", "job", "environment", "physical_id", "frame_id",
    "face_role", "dimensions", "source_sha", "source_part_ref", "item",
    "key", "token",
])
def test_token_rejects_changed_inputs_and_forged_frame(change):
    args = _seal()
    original = create_preparation_binding(**args)["prepare_token"]
    forged = deepcopy(args)
    check_token = original
    if change == "client":
        forged["client_installation_id"] = "CAD-2"
    elif change == "job":
        forged["job_id"] = "job-124"
    elif change == "environment":
        forged["environment_fingerprint"] = "d" * 64
    elif change == "physical_id":
        forged["prepared_items"][0]["physical_part_id"] = "whd-door-2"
    elif change == "frame_id":
        forged["prepared_items"][0]["target_frame"]["frame_id"] += "-unknown"
    elif change == "face_role":
        forged["prepared_items"][0]["target_frame"]["face_role"] = "back"
    elif change == "dimensions":
        forged["prepared_items"][0]["locked_dimensions_mm"]["cabinet_width"] = 499.0
    elif change == "source_sha":
        forged["prepared_items"][0]["source_document_sha256"] = "e" * 64
    elif change == "source_part_ref":
        forged["prepared_items"][0]["source_part_ref"] = "other-part"
    elif change == "item":
        forged["prepared_items"][0]["item_id"] = "門片-02"
    elif change == "key":
        forged["worker_key"] = b"another-trusted-secret-key-" + b"y" * 32
    elif change == "token":
        check_token = original[:-1] + ("0" if original[-1] != "0" else "1")
    with pytest.raises(PrepareEvidenceError) as exc:
        verify_preparation_binding(check_token, **forged)
    assert exc.value.code in {"WHD_PREPARE_STALE","WHD_PREPARE_INPUT_INVALID"}


def test_missing_installation_key_and_duplicate_physical_identity_fail_closed():
    args = _seal()
    args["worker_key"] = b"weak"
    with pytest.raises(PrepareEvidenceError) as exc:
        create_preparation_binding(**args)
    assert exc.value.code == "WHD_PREPARE_KEY_UNAVAILABLE"
    args["worker_key"] = SECRET
    args["prepared_items"] = _prepared_items() * 2
    with pytest.raises(PrepareEvidenceError) as exc:
        create_preparation_binding(**args)
    assert exc.value.code == "WHD_PREPARE_INPUT_INVALID"
