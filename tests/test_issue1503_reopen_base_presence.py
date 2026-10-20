# -*- coding: utf-8 -*-
"""#1503 true Windows saved v3 RED: valid loaded NFB base absent from live scene.

No operator project content is checked into Git. Synthetic source authority
matches the canonical existing 2026-10-18 receiving NFB/base contract.
"""
from copy import deepcopy
from types import SimpleNamespace

from tests.test_receiving_committed_nfb_depth_base_part_flow import _snapshot


def test_loaded_receiving_project_restores_its_existing_explicit_base_source():
    from gui_modules.project_actions import load_phase6_project

    saved = _snapshot()
    # The old v3 file's existing_parts may only list the Box Body; however
    # receiving_base_plate is STILL an explicit original source authority.
    saved["existing_parts"] = ["box_body"]
    designer = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱"},
        available_parts=("box_body",),
    )
    app = SimpleNamespace(
        fold_designer_app=None,
        project_controller=SimpleNamespace(
            load=lambda _path: ({"snapshot": saved}, deepcopy(saved)),
        ),
        _apply_phase6_project_snapshot=lambda incoming: deepcopy(incoming),
        open_original_fold_designer=lambda: designer,
    )
    out = load_phase6_project(app, "legacy-v3-receiving.p6fold", open_designer=True)
    assert out is designer
    assert designer._phase6_input_snapshot.get("receiving_base_plate") == saved["receiving_base_plate"], (
        "LOADED_V3_SAVED_BASE_SOURCE_SILENTLY_LOST"
    )


def test_submitted_nfb_with_real_source_enters_canonical_assembly_without_legacy_part_checkbox():
    from phase6_manufacturing_adapter import _canonical_part_keys

    source = _snapshot()
    host = SimpleNamespace(
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
        _phase6_input_snapshot=source,
    )
    assert "base_plate" in _canonical_part_keys(host), (
        "LOADED_SUBMITTED_NFB_VALID_BASE_NOT_REGISTERED"
    )

    no_submit = deepcopy(source)
    no_submit["nfb_config_submitted"] = False
    assert "base_plate" not in _canonical_part_keys(
        SimpleNamespace(
            designer_workspace=SimpleNamespace(available_parts=("box_body",)),
            _phase6_input_snapshot=no_submit,
        )
    ), "a draft never adds source geometry"


def test_unresolved_physical_source_never_creates_base_on_a_saved_project():
    from phase6_manufacturing_adapter import _canonical_part_keys
    source = _snapshot()
    source.pop("receiving_base_plate")
    source["nfb_config_submitted"] = False
    host = SimpleNamespace(
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
        _phase6_input_snapshot=source,
    )
    assert _canonical_part_keys(host) == ("box_body",)
