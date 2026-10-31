"""Legacy submitted-NFB manufacturing safety belongs to headless Engine."""
import inspect

import pytest

from ae_engine import manufacturing_api
from gui_modules.project import export_actions


def test_deeply_saved_submitted_nfb_must_block_legacy_door_or_base_or_body():
    nested = {"project": {"sets": [{"bays": [
        {"quantity": {"versions": [{"nfb_config_submitted": True}]}}
    ]}]}}
    assert manufacturing_api.has_submitted_nfb_in_current_snapshot(nested)
    for key in ("door", "base_plate", "box_body"):
        with pytest.raises(ValueError, match="已提交 NFB"):
            manufacturing_api.assert_legacy_nfb_export_scope_safe(
                {key: True}, (nested,),
            )


def test_independent_head_tail_may_export_without_forging_nfb_body():
    nested = {"nfb_config_submitted": True}
    assert manufacturing_api.assert_legacy_nfb_export_scope_safe(
        {"head": True}, (nested,),
    ) is None
    assert manufacturing_api.assert_legacy_nfb_export_scope_safe(
        {"box_body": False}, (nested,),
    ) is None


def test_corrupt_saved_nfb_submission_and_excessive_depth_fail_closed():
    with pytest.raises(ValueError, match="must be boolean"):
        manufacturing_api.has_submitted_nfb_in_current_snapshot(
            {"nfb_config_submitted": "true"}
        )
    chain = {"leaf": None}
    for _ in range(34):
        chain = {"next": chain}
    with pytest.raises(ValueError, match="nesting exceeds safe bound"):
        manufacturing_api.has_submitted_nfb_in_current_snapshot(chain)


def test_gui_never_decides_legacy_nfb_manufacturing_eligibility():
    wrapper = inspect.getsource(export_actions._assert_legacy_nfb_export_scope_safe)
    walker = inspect.getsource(export_actions._has_submitted_nfb_in_current_snapshot)
    assert "manufacturing_api.assert_legacy_nfb_export_scope_safe(" in wrapper
    assert "manufacturing_api.has_submitted_nfb_in_current_snapshot(" in walker
    assert "nfb_config_submitted" not in wrapper
    assert "NFB saved submission flag must be boolean" not in walker
    assert "NFB saved submission flag must be boolean" in inspect.getsource(
        manufacturing_api.has_submitted_nfb_in_current_snapshot
    )
