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
          target_snapshot=None):
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
        source_group_id=group_id,
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
            source_group_id=source_id,
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
