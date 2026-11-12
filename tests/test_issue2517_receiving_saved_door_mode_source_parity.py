"""#2517: original Receiving project Door mode must agree across Bay, PartSpec and DXF.

A .p6fold can preserve a textual operator boolean. The Engine must not treat
"false" as true in the transient Set/Bay projector, or reject "true" when
constructing an explicitly confirmed manufacturing request.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays,
    project_receiving_bay_legacy_aliases,
)
from tests.test_issue2517_receiving_confirmed_door_source import (
    SOURCE, UPPER_LOWER, _saved,
)
import phase6_project_file as project


def _saved_confirmed_with_mode(flag):
    state = _saved()
    state["multi_door_enabled"] = flag
    state["door_layout_columns"] = deepcopy(UPPER_LOWER)
    return state


def _actual_bay_source(flag):
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    assert "door_state" not in layout["sets"][0]["bays"][1]
    return {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout,
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "multi_door_enabled": flag,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        # A non-empty root inner-door store is intentionally present; only
        # the actual enabled flag may authorize a new Bay's transient frame.
        "inner_doors": [{"stable_id": "legacy-inner", "cell_key": "0:0"}],
    }


@pytest.mark.parametrize("flag", (False, "false", " FALSE ", "off", "0", 0))
def test_saved_false_root_never_invents_unconfigured_second_bay_inner_door(flag):
    original = _actual_bay_source(flag)
    before = deepcopy(original)
    view = project_receiving_bay_legacy_aliases(
        original, set_index=0, bay_index=1, validate_common=False,
    )
    for field in ("multi_door_enabled", "door_layout_columns", "inner_doors"):
        assert field not in view
    assert "door_state" not in view["receiving_layout"]["sets"][0]["bays"][1]
    assert original == before


@pytest.mark.parametrize("flag", (True, "true", " TRUE ", "on", "1", 1))
def test_saved_true_root_preserves_existing_legacy_secondary_bay_projection(flag):
    original = _actual_bay_source(flag)
    before = deepcopy(original)
    view = project_receiving_bay_legacy_aliases(
        original, set_index=0, bay_index=1, validate_common=False,
    )
    assert view["multi_door_enabled"] is True
    assert view["door_layout_columns"]
    assert view["inner_doors"]
    assert view["door_layout_columns"][0][0] == 800.0
    assert view["receiving_layout"]["sets"][0]["bays"][1]["stable_id"] == (
        original["receiving_layout"]["sets"][0]["bays"][1]["stable_id"]
    )
    assert "door_state" not in view["receiving_layout"]["sets"][0]["bays"][1]
    assert original == before


@pytest.mark.parametrize("flag", (None, "sometimes", 2, -1, 0.5, [], {}))
def test_bad_saved_root_boolean_cannot_authorize_other_bay_physical_frames(flag):
    original = _actual_bay_source(flag)
    before = deepcopy(original)
    with pytest.raises(ValueError, match="設定的布林值"):
        project_receiving_bay_legacy_aliases(
            original, set_index=0, bay_index=1, validate_common=False,
        )
    assert original == before


@pytest.mark.parametrize("flag", (True, "true", " TRUE ", "on", "1", 1, 1.0))
def test_confirmed_receiving_door_api_preserves_serialized_saved_true(flag):
    saved = _saved_confirmed_with_mode(flag)
    before = deepcopy(saved)
    via_saved = api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_door_layout_columns=UPPER_LOWER,
    )
    canonical = api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=_saved_confirmed_with_mode(True),
        confirmed_door_layout_columns=UPPER_LOWER,
    )
    assert via_saved == canonical
    assert [key for key, _ in via_saved] == [
        "box_body", "head", "tail", "door_c1_r1", "door_c1_r2",
    ]
    assert saved == before


@pytest.mark.parametrize("flag", (False, "false", " FALSE ", "off", "0", 0,
                                    None, "invalid", 2, -1, float("nan")))
def test_disabled_or_corrupt_saved_door_mode_never_builds_factory_door_specs(flag):
    saved = _saved_confirmed_with_mode(flag)
    before = deepcopy(saved)
    with pytest.raises(ValueError, match="RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="saved_operator_confirmed",
            operator_snapshot=saved, confirmed_door_layout_columns=UPPER_LOWER,
        )
    # NaN is unequal to itself; source stays non-mutated by representation.
    assert repr(saved) == repr(before)


def test_actual_p6fold_false_root_does_not_create_other_bay_door_frames(tmp_path):
    root = _actual_bay_source("false")
    file = project.write_project(
        tmp_path / "receiving-second-bay-false.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": root},
    )
    saved = project.read_project(file)["snapshot"]
    view = project_receiving_bay_legacy_aliases(
        saved, set_index=0, bay_index=1, validate_common=False,
    )
    assert "inner_doors" not in view
    assert "door_layout_columns" not in view
    assert "multi_door_enabled" not in view
    assert "door_state" not in view["receiving_layout"]["sets"][0]["bays"][1]


def test_saved_true_door_source_uses_real_verified_engine_factory_dxf(tmp_path):
    root = _actual_bay_source("true")
    file = project.write_project(
        tmp_path / "receiving-door-true.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": root},
    )
    reopened = project.read_project(file)["snapshot"]
    assert reopened["multi_door_enabled"] == "true"

    saved = _saved_confirmed_with_mode(reopened["multi_door_enabled"])
    saved["door_layout_columns"] = deepcopy(reopened["door_layout_columns"])
    parts = api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, confirmed_door_layout_columns=UPPER_LOWER,
    )
    bay = ManufacturingResolvedBayInput(
        family="receiving",
        source=ManufacturingSourceIdentity(
            "P1", "saved-operator-boolean-source", "SetA", "Bay1",
        ),
        confirmed_parts=parts,
        door_layout_columns=UPPER_LOWER,
    )
    exported = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "manufacturing",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: None,
    )
    assert exported.physical_dxf_roundtrip_verified
    assert len(exported.output_files) == 7
    door_paths = [
        Path(out) for out in exported.output_files.values()
        if "door_c1_r" in Path(out).name
    ]
    assert len(door_paths) == 2
    for path in door_paths:
        assert {"CUTTING", "BEND"} <= {
            item.dxf.layer for item in ezdxf.readfile(path).modelspace()
        }
