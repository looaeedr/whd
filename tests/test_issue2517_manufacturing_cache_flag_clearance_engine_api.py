# -*- coding: utf-8 -*-
"""#2517: pre-scan manufacturing cache and full request use identical Engine inputs."""
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from phase6_manufacturing_geometry import (
    _phase6_assembly_relief_clearance,
    _phase6_manufacturing_state_signature,
)
from tests.test_issue359_manufacturing_cache_service import _app


def _headless_signature(**changes):
    kwargs = dict(
        input_snapshot={"model": "金庫型", "w": 400, "h": 600, "d": 200},
        settings_values={"t": 2}, working_box={"w": 400, "h": 600, "d": 200},
        corner_state={}, endcap_fw_state={}, endcap_bottom_wrap_state={},
        available_parts=("box_body",), part_profiles={"box_body": {}},
        assembly_intent="INSERT", ignore_fixed_corner=False,
        relief_clearance=0.0,
    )
    kwargs.update(changes)
    return api.manufacturing_state_fingerprint(**kwargs)


@pytest.mark.parametrize("raw,expected", [
    (None, False), ("", False), ("false", False), (" FALSE ", False),
    ("0", False), (False, False), (0, False),
    ("true", True), ("1", True), (1, True), (True, True),
])
def test_headless_cache_flag_is_identical_to_manufacturing_request_flag(raw, expected):
    assert api.normalize_operator_3d_fallback_flag(raw) is expected
    assert _headless_signature(ignore_fixed_corner=raw) == _headless_signature(
        ignore_fixed_corner=expected
    )


@pytest.mark.parametrize("invalid", ["yes", "no", "off", "on", 2, -1, 0.3, float("nan"), {}])
def test_headless_cache_rejects_invalid_3d_fallback_flag(invalid):
    with pytest.raises(ValueError, match="MANUFACTURING_3D_FALLBACK_FLAG_INVALID"):
        _headless_signature(ignore_fixed_corner=invalid)


@pytest.mark.parametrize("raw,expected", [
    (None, 0.0), ("", 0.0), ("  ", 0.0), ("2.5", 2.5),
    (2.5, 2.5), ("-9", 0.0), (-9, 0.0),
])
def test_headless_cache_clearance_matches_request_normalization(raw, expected):
    assert api.normalize_operator_relief_clearance(raw) == expected
    assert _headless_signature(relief_clearance=raw) == _headless_signature(
        relief_clearance=expected
    )


@pytest.mark.parametrize("invalid", ["invalid", "NaN", float("inf"), False, True, 10 ** 400])
def test_headless_cache_rejects_invalid_clearance(invalid):
    with pytest.raises(ValueError, match="MANUFACTURING_RELIEF_CLEARANCE_INVALID"):
        _headless_signature(relief_clearance=invalid)


def test_bridge_preview_legacy_zero_is_never_manufacturing_cache_authority():
    app = SimpleNamespace(assembly_relief_clearance_var=SimpleNamespace(get=lambda: "bad"))
    # Existing uncommitted UI preview remains finite rather than raising.
    assert _phase6_assembly_relief_clearance(app) == 0.0
    with pytest.raises(ValueError, match="MANUFACTURING_RELIEF_CLEARANCE_INVALID"):
        api.normalize_operator_relief_clearance("bad")
    app.assembly_relief_clearance_var = SimpleNamespace(get=lambda: "-2")
    assert _phase6_assembly_relief_clearance(app) == 0.0


def test_gui_manufacturing_cache_rejects_invalid_clearance_even_if_preview_uses_zero():
    app = _app()
    app.assembly_relief_clearance_var = SimpleNamespace(get=lambda: "bad")
    assert _phase6_assembly_relief_clearance(app) == 0.0
    with pytest.raises(ValueError, match="MANUFACTURING_RELIEF_CLEARANCE_INVALID"):
        _phase6_manufacturing_state_signature(app)


def test_gui_cache_signature_no_longer_uses_nonempty_string_truthiness():
    app = _app()
    app.assembly_ignore_fixed_corner_var = SimpleNamespace(get=lambda: "false")
    assert _phase6_manufacturing_state_signature(app) == _headless_signature(
        input_snapshot=app._phase6_input_snapshot,
        settings_values=app._settings_values,
        working_box=app._phase6_box_whd,
        corner_state=app._phase6_corner_state,
        endcap_fw_state=app._phase6_endcap_fw_state,
        endcap_bottom_wrap_state=app._phase6_endcap_bottom_wrap_state,
        available_parts=app.designer_workspace.available_parts,
        part_profiles={
            part: app.designer_workspace.profiles_for(part, {})
            for part in app.designer_workspace.available_parts
        },
        assembly_intent=app._phase6_assembly_type.value,
        ignore_fixed_corner=False,
        relief_clearance=0.0,
    )
    app.assembly_ignore_fixed_corner_var = SimpleNamespace(get=lambda: "yes")
    with pytest.raises(ValueError, match="MANUFACTURING_3D_FALLBACK_FLAG_INVALID"):
        _phase6_manufacturing_state_signature(app)


def test_broken_live_fold_provider_cannot_reuse_empty_profile_cache_key():
    app = _app()
    app.designer_workspace.profiles_for = lambda key, default: (_ for _ in ()).throw(
        RuntimeError("live profile read failed")
    )
    with pytest.raises(ValueError, match="MANUFACTURING_CACHE_PROFILE_READ_FAILED:box_body") as exc:
        _phase6_manufacturing_state_signature(app)
    assert isinstance(exc.value.__cause__, RuntimeError)
