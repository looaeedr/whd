"""#2517: Receiving inner-door physical offset & dimensions are public Engine-owned."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from gui import Phase6ApplicationHost as GUI


def _family(name):
    return {"model": name}


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_default_from_same_canonical_family_policy_and_legacy_missing_field(family):
    source = _family(family)
    expected = family_policy.default_inner_door_inward_offset_mm(source, default=0.0)
    assert api.resolve_operator_receiving_inner_door_inward_offset(source) == expected
    assert api.resolve_operator_receiving_inner_door_inward_offset(
        source, {"stable_id": "upper", "cell_key": "0:0"},
    ) == expected


@pytest.mark.parametrize("raw", (True, False, float("nan"), float("inf"),
                                 "-Infinity", None, "", "broken", -1, "-0.25", 10**400))
def test_invalid_operator_and_saved_inward_mm_fail_closed(raw):
    with pytest.raises(ValueError, match="內門內退尺寸"):
        api.normalize_operator_receiving_inner_door_inward_offset(raw)
    with pytest.raises(ValueError, match="內門內退尺寸"):
        api.resolve_operator_receiving_inner_door_inward_offset(
            _family("受電箱"), {"inward_offset_mm": raw},
        )
    with pytest.raises(ValueError, match="內門內退尺寸"):
        api.project_operator_receiving_inner_door_enabled_source(
            _family("受電箱"), "0:0",
            existing={"cell_key": "0:0", "inward_offset_mm": raw},
        )


@pytest.mark.parametrize("raw,expected", (("0", 0.0), (0, 0.0), ("70.25", 70.25),
                                           (105.5, 105.5)))
def test_zero_and_fractional_inward_mm_are_independent_and_source_preserving(raw, expected):
    source = {"cell_key": "0:0", "stable_id": "upper",
              "included_frame_sides": ["top", "left", "right"],
              "inward_offset_mm": raw}
    before = deepcopy(source)
    result = api.project_operator_receiving_inner_door_enabled_source(
        _family("受電箱"), "0:0", existing=source,
    )
    assert source == before
    assert result["stable_id"] == "upper"
    assert result["inward_offset_mm"] == expected
    assert result["included_frame_sides"] == ["top", "left", "right"]
    assert result["included_frame_sides"] is not source["included_frame_sides"]


def test_operator_physical_identity_defaults_are_engine_owned():
    actual = api.project_operator_receiving_inner_door_enabled_source(
        _family("受電箱"), "0:1",
    )
    assert actual["cell_key"] == "0:1"
    assert actual["included_frame_sides"] == ["top", "left", "right"]
    assert actual["stable_id"] == api.receiving_inner_door_stable_id_for_cell("0:1")
    assert actual["inward_offset_mm"] == pytest.approx(
        family_policy.default_inner_door_inward_offset_mm(_family("受電箱"))
    )
    with pytest.raises(ValueError, match="身份"):
        api.project_operator_receiving_inner_door_enabled_source(
            _family("受電箱"), "0:1",
            existing={"cell_key": "0:0", "inward_offset_mm": 50},
        )


def _host():
    return SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: "受電箱"),
        receiving_inner_doors=[{
            "cell_key": "0:0", "stable_id": "upper",
            "inward_offset_mm": 60.0,
        }],
    )


def test_main_gui_set_inward_mm_uses_engine_and_never_mutates_on_invalid():
    host = _host()
    saved = deepcopy(host.receiving_inner_doors)
    assert GUI._set_receiving_inner_door_inward_offset(host, "0:0", "65.25") == 65.25
    assert host.receiving_inner_doors[0]["inward_offset_mm"] == 65.25
    previous = deepcopy(host.receiving_inner_doors)
    with pytest.raises(ValueError, match="內門內退尺寸"):
        GUI._set_receiving_inner_door_inward_offset(host, "0:0", True)
    assert host.receiving_inner_doors == previous
    with pytest.raises(ValueError, match="內門內退尺寸"):
        GUI._set_receiving_inner_door_inward_offset(host, "0:0", float("nan"))
    assert host.receiving_inner_doors == previous
    assert saved[0]["inward_offset_mm"] == 60.0


def test_main_gui_enabled_uses_engine_physical_source_and_separate_cells():
    host = _host()
    assert GUI._set_receiving_inner_door_enabled(host, "0:0", True) is True
    assert host.receiving_inner_doors[0]["stable_id"] == "upper"
    assert host.receiving_inner_doors[0]["inward_offset_mm"] == 60.0
    assert GUI._set_receiving_inner_door_enabled(host, "0:1", True) is True
    by_cell = {row["cell_key"]: row for row in host.receiving_inner_doors}
    assert by_cell["0:0"]["inward_offset_mm"] == 60.0
    assert by_cell["0:1"]["inward_offset_mm"] == pytest.approx(80)
    assert by_cell["0:1"]["stable_id"] == api.receiving_inner_door_stable_id_for_cell("0:1")


def test_main_gui_read_rejects_corrupt_saved_value_instead_of_fabricating_default():
    host = _host()
    assert GUI._receiving_inner_door_inward_offset(host, "0:0") == 60.0
    host.receiving_inner_doors[0]["inward_offset_mm"] = float("nan")
    with pytest.raises(ValueError, match="內門內退尺寸"):
        GUI._receiving_inner_door_inward_offset(host, "0:0")
    prior = deepcopy(host.receiving_inner_doors)
    with pytest.raises(ValueError, match="內門內退尺寸"):
        GUI._set_receiving_inner_door_enabled(host, "0:0", True)
    assert host.receiving_inner_doors == prior


def test_corrupt_saved_mm_does_not_crash_commit_or_rewrite_physical_source():
    host = _host()
    host.receiving_inner_doors[0]["inward_offset_mm"] = True
    edits = []
    host.door_layout_inner_door_offset_vars = {
        "0:0": SimpleNamespace(get=lambda: "nan", set=lambda value: edits.append(value))
    }
    host._set_receiving_inner_door_inward_offset = (
        lambda cell, value: GUI._set_receiving_inner_door_inward_offset(host, cell, value)
    )
    host._receiving_inner_door_inward_offset = (
        lambda cell: GUI._receiving_inner_door_inward_offset(host, cell)
    )
    host._fold_designer_number_text = str
    assert GUI._commit_receiving_inner_door_inward_offset(host, "0:0") is False
    assert host.receiving_inner_doors[0]["inward_offset_mm"] is True
    assert edits == []


def test_gui_finished_dimensions_and_endcap_policy_call_public_engine(monkeypatch):
    seen = []
    monkeypatch.setattr(
        api, "resolve_operator_finished_dimensions",
        lambda key, **kw: seen.append((key, kw)) or ("existing-engine-result",),
    )
    host = SimpleNamespace(
        _make_original_fold_designer_snapshot=lambda: {
            "model": "受電箱", "w": 800, "h": 1600, "d": 350,
            "t": "2", "fw": "29",
        },
        _box_body_corner_policies=lambda frame: ("head-policy", "tail-policy"),
    )
    assert GUI._phase6_resolved_finished_dimensions(host, "box_body") == (
        "existing-engine-result",
    )
    assert seen[0][1]["thickness"] == 2.0
    assert seen[0][1]["head_corner_policy"] == "head-policy"
    assert api.project_operator_endcap_depth_comp_t("受電箱") == (
        family_policy.endcap_depth_comp_t("受電箱")
    )
    assert api.project_operator_endcap_depth_comp_t("金庫型") == (
        family_policy.endcap_depth_comp_t("金庫型")
    )


def test_gui_boundary_does_not_call_private_finished_dimensions_or_family_offset():
    src = (Path(__file__).resolve().parents[1] / "gui.py").read_text(encoding="utf-8")
    assert "from ae_engine.display_dimensions import resolve_operator_finished_dimensions" not in src
    a = src.index("    def _receiving_inner_door_inward_offset(")
    b = src.index("    def _commit_receiving_inner_door_checkbox(", a)
    section = src[a:b]
    assert "cabinet_family_policy.default_inner_door_inward_offset_mm(" not in section
    assert "float(value)" not in section
    assert "normalize_operator_receiving_inner_door_inward_offset(" in section
    assert "project_operator_receiving_inner_door_enabled_source(" in section
    assert "manufacturing_api.resolve_operator_finished_dimensions(" in src
    assert "manufacturing_api.project_operator_endcap_depth_comp_t(" in src
