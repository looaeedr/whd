"""#3414 first bounded manual source→target copy: two saved Receiving LEFT sheets.

Real .p6fold source snapshots, real Engine final flat, new group ID, and the
original full arm/hole gate; no implicit generic Family/Set/Bay authorization.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from phase6_project_file import read_project, write_project, PROJECT_SCHEMA
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet
from tests.test_issue3413_manual_group_engine import _group


def _persisted_pair(actual_sheet, tmp_path, *, pattern="solid"):
    original, _render, ctx, _, _ = actual_sheet
    group = _group(actual_sheet, pattern=pattern, dash=2, gap=7)
    from ae_engine.operator_manual_marking_groups import source_group
    source = deepcopy(original)
    source["part_features"] = {"base_plate": [group]}
    source["workspace"] = {"part_features": {"base_plate": [group]}}
    target = deepcopy(original)
    target["part_features"] = {"base_plate": []}
    target["workspace"] = {"part_features": {"base_plate": []}}
    a = Path(write_project(tmp_path / "source.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": source,
    }))
    b = Path(write_project(tmp_path / "target.p6fold", {
        "schema": PROJECT_SCHEMA, "snapshot": target,
    }))
    return a, b, group, ctx


def _copy(a, b, context, group_id, *, features=(), source_snapshot=None,
          target_snapshot=None, target_position=Vec2(100, 100)):
    return api.copy_saved_manual_marking_group_to_selected_sheet(
        source_snapshot=(read_project(a)["snapshot"]
                         if source_snapshot is None else source_snapshot),
        source_project_path=a,
        source_project_sha256=sha256(a.read_bytes()).hexdigest(),
        target_snapshot=(read_project(b)["snapshot"]
                         if target_snapshot is None else target_snapshot),
        target_project_path=b,
        target_project_sha256=sha256(b.read_bytes()).hexdigest(),
        target_context=context, target_features=features,
        source_group_id=group_id, target_position=target_position,
    )


def test_two_independently_saved_baseplates_copy_group_new_stable_id(actual_sheet, tmp_path):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    old_id = api.group_parameters(group)["group_id"]
    clone = _copy(a, b, ctx, old_id)
    assert api.is_manual_group(clone)
    assert api.group_parameters(clone)["group_id"] != old_id
    assert api.group_parameters(clone)["members"] == api.group_parameters(group)["members"]
    assert dict(api.group_member_world_points(clone)) == dict(api.group_member_world_points(group))
    assert api.propose_operator_physical_sheet_hole_features(
        "base_plate", ctx, (clone,),
    ) == (clone,)
    assert read_project(a)["snapshot"]["part_features"]["base_plate"] == [group]
    assert read_project(b)["snapshot"]["part_features"]["base_plate"] == []


def test_different_project_filename_does_not_authorize_same_file_or_other_bay(actual_sheet, tmp_path):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    group_id = api.group_parameters(group)["group_id"]
    with pytest.raises(ValueError, match="SAME_PHYSICAL_PROJECT"):
        _copy(a, a, ctx, group_id)
    saved_source = read_project(a)["snapshot"]
    saved_source["_receiving_runtime_selection"] = {
        "set_id": "S1", "bay_id": "B1", "version_id": "v1",
    }
    with pytest.raises(ValueError, match="SET_BAY_OWNER_UNRESOLVED"):
        _copy(a, b, ctx, group_id, source_snapshot=saved_source)
    saved_target = read_project(b)["snapshot"]
    saved_target["receiving_layout"] = {"sets": [{"bays": [{}, {}]}]}
    with pytest.raises(ValueError, match="SET_BAY_OWNER_UNRESOLVED"):
        _copy(a, b, ctx, group_id, target_snapshot=saved_target)


def test_copy_rejects_drifted_saved_source_and_hidden_dash_hole(actual_sheet, tmp_path):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path, pattern="dashed")
    source_id = api.group_parameters(group)["group_id"]
    with pytest.raises(ValueError, match="SOURCE_SAVED_SOURCE_CHANGED"):
        api.copy_saved_manual_marking_group_to_selected_sheet(
            source_snapshot=read_project(a)["snapshot"],
            source_project_path=a, source_project_sha256="0"*64,
            target_snapshot=read_project(b)["snapshot"],
            target_project_path=b,
            target_project_sha256=sha256(b.read_bytes()).hexdigest(),
            target_context=ctx, target_features=(),
            source_group_id=source_id, target_position=Vec2(100, 100),
        )
    from ae_engine.operator_manual_marking_groups import source_group
    full = source_group(group)[2][0]
    a_xy = full.coords[0]
    b_xy = full.coords[-1]
    # Each actual 12-mm arm has 2-mm ink, then a 7-mm blank.
    at = Vec2(a_xy[0]+(b_xy[0]-a_xy[0])*4/12,
              a_xy[1]+(b_xy[1]-a_xy[1])*4/12)
    hole = CircleFeature(
        diameter=.4, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=at, layer="CUTTING",
    )
    with pytest.raises(ValueError, match="完整筆畫|碰觸孔位"):
        _copy(a, b, ctx, source_id, features=(hole,))
    assert read_project(b)["snapshot"]["part_features"]["base_plate"] == []


def test_source_workspace_duplicate_conflict_and_missing_id_never_copy(actual_sheet, tmp_path):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    original = read_project(a)["snapshot"]
    original["workspace"]["part_features"]["base_plate"] = []
    with pytest.raises(ValueError, match="WORKSPACE_MARKING_DRIFT"):
        _copy(a, b, ctx, api.group_parameters(group)["group_id"],
              source_snapshot=original)
    with pytest.raises(ValueError, match="SOURCE_GROUP_AMBIGUOUS"):
        _copy(a, b, ctx, "unknown-group-id")


def test_copy_rejects_stale_marked_snapshot_with_current_clean_source_digest(actual_sheet, tmp_path):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    source_claim = read_project(a)["snapshot"]
    clean_bytes = b.read_bytes()
    a.write_bytes(clean_bytes)
    assert read_project(a)["snapshot"]["part_features"]["base_plate"] == []
    with pytest.raises(ValueError, match="MANUAL_COPY_SOURCE_SAVED_SNAPSHOT_MISMATCH"):
        _copy(a, b, ctx, api.group_parameters(group)["group_id"], source_snapshot=source_claim)
    assert a.read_bytes() == b.read_bytes() == clean_bytes


def test_copy_rejects_stale_receiving_target_snapshot_with_current_other_family_digest(
    actual_sheet, tmp_path,
):
    from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _configured
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    target_claim = read_project(b)["snapshot"]
    write_project(b, {"schema": PROJECT_SCHEMA, "snapshot": _configured("金庫型")})
    other_family = b.read_bytes()
    assert read_project(b)["snapshot"]["model"] != target_claim["model"]
    with pytest.raises(ValueError, match="MANUAL_COPY_TARGET_SAVED_SNAPSHOT_MISMATCH"):
        _copy(a, b, ctx, api.group_parameters(group)["group_id"], target_snapshot=target_claim)
    assert b.read_bytes() == other_family


def test_copy_accepts_same_saved_normalized_snapshot_with_other_json_key_order(
    actual_sheet, tmp_path,
):
    import json

    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    original_source = read_project(a)["snapshot"]
    original_target = read_project(b)["snapshot"]
    for path in (a, b):
        data = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    # The digest is current, while the original readback has the same physical
    # content even though the JSON object key order changed on disk.
    clone = _copy(a, b, ctx, api.group_parameters(group)["group_id"],
                  source_snapshot=original_source, target_snapshot=original_target)
    assert api.group_parameters(clone)["group_id"] != api.group_parameters(group)["group_id"]


@pytest.mark.parametrize("role", ("SOURCE", "TARGET"))
def test_matching_digest_cannot_make_invalid_project_bytes_authoritative(
    role, actual_sheet, tmp_path,
):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    source_claim = read_project(a)["snapshot"]
    target_claim = read_project(b)["snapshot"]
    path = a if role == "SOURCE" else b
    malformed = b'{"snapshot":'
    path.write_bytes(malformed)
    with pytest.raises(ValueError, match=f"MANUAL_COPY_{role}_SAVED_PROJECT_INVALID"):
        _copy(a, b, ctx, api.group_parameters(group)["group_id"],
              source_snapshot=source_claim, target_snapshot=target_claim)
    assert path.read_bytes() == malformed


def test_persisted_round_ink_coexists_without_becoming_a_group_copy(actual_sheet, tmp_path):
    import ezdxf

    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    point = ctx.render_data.material.representative_point()
    ring = api.create_physical_manual_round_marking(
        "base_plate", ctx, (group,), centre=Vec2(point.x, point.y), diameter=12,
    )

    def save_features(path, rows):
        snapshot = read_project(path)["snapshot"]
        snapshot["part_features"] = {"base_plate": rows}
        snapshot["workspace"] = {"part_features": {"base_plate": rows}}
        write_project(path, {"schema": PROJECT_SCHEMA, "snapshot": snapshot})
        return read_project(path)["snapshot"]["part_features"]["base_plate"]

    assert save_features(a, [group, ring]) == [group, ring]
    target_rows = save_features(b, [ring])
    assert target_rows == [ring]
    a_before, b_before = a.read_bytes(), b.read_bytes()
    clone = _copy(a, b, ctx, api.group_parameters(group)["group_id"], features=target_rows)
    assert api.is_manual_group(clone)
    assert api.group_parameters(clone)["group_id"] != api.group_parameters(group)["group_id"]
    assert a.read_bytes() == a_before and b.read_bytes() == b_before

    target_rows = save_features(b, [ring, clone])
    render = api.with_physical_sheet_features("base_plate", ctx.render_data, target_rows)
    out = tmp_path / "copied-group-with-existing-round-mark.dxf"
    api.save_part_render_data_dxf(render, out, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(render, out).ok
    doc = ezdxf.readfile(out)
    circle, = doc.modelspace().query('CIRCLE[layer=="MARKING"]')
    assert (circle.dxf.center.x, circle.dxf.center.y, circle.dxf.radius) == pytest.approx(
        (point.x, point.y, 6),
    )
    assert doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]')


@pytest.mark.parametrize("kind", ("l", "cross", "pair_l", "quad_l"))
def test_copy_places_on_operator_anchor_preserving_local_offsets(actual_sheet, tmp_path, kind):
    a, b, _, ctx = _persisted_pair(actual_sheet, tmp_path)
    source = read_project(a)["snapshot"]
    original = _group(actual_sheet, kind=kind, pattern="dashed", dash=2, gap=5)
    member = api.group_parameters(original)["members"][0][0]
    original = api.edit_physical_manual_group(
        original, member_id=member, offset_x=3, offset_y=-2,
        angle=17, mirror_vertical=True,
    )
    source["part_features"] = {"base_plate": [original]}
    source["workspace"] = {"part_features": {"base_plate": [original]}}
    write_project(a, {"schema": PROJECT_SCHEMA, "snapshot": source})
    before = (a.read_bytes(), b.read_bytes())
    target = Vec2(150, 110)
    clone = _copy(a, b, ctx, api.group_parameters(original)["group_id"],
                  target_position=target)
    src_params, dst_params = api.group_parameters(original), api.group_parameters(clone)
    assert src_params.pop("group_id") != dst_params.pop("group_id")
    assert src_params == dst_params
    src_points = dict(api.group_member_world_points(original))
    dst_points = dict(api.group_member_world_points(clone))
    if kind in ("l", "cross"):
        source_anchor, dest_anchor = src_points[member], dst_points[member]
    else:
        source_anchor, dest_anchor = original.offset, clone.offset
    assert (dest_anchor.x, dest_anchor.y) == pytest.approx((target.x, target.y))
    for name in src_points:
        assert (dst_points[name].x - src_points[name].x,
                dst_points[name].y - src_points[name].y) == pytest.approx(
                    (target.x - source_anchor.x, target.y - source_anchor.y))
    assert before == (a.read_bytes(), b.read_bytes())


def test_copy_invalid_target_and_missing_position_never_insert(actual_sheet, tmp_path):
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path)
    before = (a.read_bytes(), b.read_bytes())
    gid = api.group_parameters(group)["group_id"]
    with pytest.raises(ValueError, match="完整筆畫|無材料"):
        _copy(a, b, ctx, gid, target_position=Vec2(-10, -10))
    with pytest.raises(ValueError, match="TARGET_POSITION_REQUIRED"):
        _copy(a, b, ctx, gid, target_position=None)
    assert before == (a.read_bytes(), b.read_bytes())


def test_relocated_copy_full_dash_blank_is_checked_at_new_anchor(actual_sheet, tmp_path):
    from ae_engine.operator_manual_marking_groups import source_group
    a, b, group, ctx = _persisted_pair(actual_sheet, tmp_path, pattern="dashed")
    gid = api.group_parameters(group)["group_id"]
    position = Vec2(150, 110)
    clone = _copy(a, b, ctx, gid, target_position=position)
    full = source_group(clone)[2][0]
    p = full.interpolate(4)
    hole = CircleFeature(diameter=.4, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                         offset=Vec2(p.x, p.y), layer="CUTTING")
    with pytest.raises(ValueError, match="完整筆畫|碰觸孔位"):
        _copy(a, b, ctx, gid, target_position=position, features=(hole,))
    assert read_project(b)["snapshot"]["part_features"]["base_plate"] == []
