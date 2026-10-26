# -*- coding: utf-8 -*-
"""#1501 no old full door/body/base output after NFB was truly submitted."""
from types import SimpleNamespace

import pytest

from gui_modules.project.export_actions import (
    _has_submitted_nfb_in_current_snapshot,
    _assert_legacy_nfb_export_scope_safe,
    _export_selected_parts,
)


class Workspace:
    def __init__(self,payload):
        self.payload=payload
    def snapshot(self):
        return self.payload


def _user(payload):
    designer=SimpleNamespace(
        _phase6_input_snapshot={"model":"受電箱"},
        designer_workspace=Workspace(payload),
    )
    return SimpleNamespace(fold_designer_app=designer)


def _submitted():
    return {"receiving_layout":{"sets":[{
        "stable_id":"set-a",
        "bays":[{"stable_id":"bay-a","nfb_config_submitted":True,
                 "nfb_config":{"holes":[{"physical_hole_id":"hole-1"}]}}],
    }]}}


def test_submitted_nfb_blocks_unverified_old_full_door_body_base_only(tmp_path):
    user=_user(_submitted())
    for flags in (
        {"door":True},
        {"box_body":True},
        {"base_plate":True},
        {"head":True,"door":True},
    ):
        with pytest.raises(ValueError,match="不得忽略 NFB"):
            _assert_legacy_nfb_export_scope_safe(user,flags)
        filenames,issues=_export_selected_parts(
            user,str(tmp_path),{},flags,False,
        )
        assert filenames==[]
        assert any("不得忽略 NFB" in issue for issue in issues)
        assert not list(tmp_path.rglob("*.dxf"))


def test_unrelated_head_tail_indicator_and_custom_dont_get_nfb_only_block():
    user=_user(_submitted())
    for flags in (
        {"head":True},
        {"tail":True},
        {"indicator_box":True},
        {"indicator_door":True},
        {"door":False,"box_body":False,"base_plate":False},
    ):
        # The true original manufacturing guard must explicitly approve
        # unrelated physical intentions; do not only rely on no exception.
        assert _assert_legacy_nfb_export_scope_safe(user,flags) is None


def test_legacy_and_draft_no_submission_preserve_old_export(tmp_path):
    for row in (
        {},
        {"nfb_config_submitted":False},
        {"nfb_draft_preview":{"holes":[{"model":"士林"}]}},
    ):
        scope={"receiving_layout":{"sets":[{"bays":[row]}]}}
        user=_user(scope)
        _assert_legacy_nfb_export_scope_safe(
            user,{"door":True,"box_body":True,"base_plate":True},
        )
        assert not _has_submitted_nfb_in_current_snapshot(scope)


def test_nested_quantity_version_submitted_cannot_downgrade_to_legacy_export():
    nested={"active_mode":"quantity","quantity":{"versions":[
        {"version_id":"v1","receiving_layout":{"sets":[{
            "bays":[{"nfb_config_submitted":True,"nfb_config":{}}],
        }]}}
    ]}}
    assert _has_submitted_nfb_in_current_snapshot(nested)
    user=_user(nested)
    with pytest.raises(ValueError,match="NFB"):
        _assert_legacy_nfb_export_scope_safe(
            user,{"door":True,"box_body":True},
        )


def test_nonboolean_saved_submission_fails_closed():
    for value in ("true",1,None):
        with pytest.raises(ValueError,match="boolean"):
            _has_submitted_nfb_in_current_snapshot({
                "receiving_layout":{"sets":[{"bays":[
                    {"nfb_config_submitted":value},
                ]}]},
            })
