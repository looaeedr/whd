"""#2517: canonical keyed material Fold reconciliation belongs to Engine, not GUI."""
from __future__ import annotations

from copy import deepcopy
import inspect

from ae_engine import manufacturing_api, merge_keyed_fold_profiles
from ae_engine.standard_part_fold_profiles import build_standard_part_fold_profiles
import phase6_settings_profile_projection as settings


def _defaults():
    return build_standard_part_fold_profiles(
        {"model": "金庫型", "w": 400, "h": 600, "d": 250,
         "t": 2, "part_dimensions": {"door": {"width": 300, "height": 500}}},
        "door",
    )


def test_public_owner_and_settings_adapter_only_delegates():
    assert merge_keyed_fold_profiles is manufacturing_api.merge_keyed_fold_profiles
    source = inspect.getsource(settings.merge_keyed_profiles)
    assert "return merge_keyed_fold_profiles(existing_profiles, default_profiles)" in source
    for forbidden in ("phase6_key", "len", "ui_len_add", "core", "clone_profile"):
        assert forbidden not in source


def test_changed_canonical_core_is_refreshed_while_operator_fold_and_bend_survive():
    defaults = _defaults()
    existing = deepcopy(defaults)
    face = next(row for row in existing["X"] if row.get("phase6_key") == "door_face_w")
    face.update({"len": 999, "ui_len_add": 99, "core": "stale", "angle": 45,
                 "metadata": {"operator": ["unchanged"]}})
    operator = {"len": 17, "angle": -90, "custom": {"labels": ["manual"]}}
    existing["X"].insert(1, operator)
    existing_before, defaults_before = deepcopy(existing), deepcopy(defaults)

    result = merge_keyed_fold_profiles(existing, defaults)
    updated = next(row for row in result["X"] if row.get("phase6_key") == "door_face_w")
    canonical = next(row for row in defaults["X"] if row.get("phase6_key") == "door_face_w")
    assert (updated["len"], updated["ui_len_add"], updated["core"]) == (
        canonical["len"], canonical["ui_len_add"], canonical["core"]
    )
    assert updated["angle"] == 45
    assert updated["metadata"] == {"operator": ["unchanged"]}
    assert result["X"][1] == operator
    assert result["X"][1] is not operator
    assert existing == existing_before and defaults == defaults_before
    result["X"][1]["custom"]["labels"].append("new")
    assert existing["X"][1]["custom"]["labels"] == ["manual"]


def test_missing_canonical_key_resets_only_affected_axis_to_engine_defaults():
    defaults = _defaults()
    existing = deepcopy(defaults)
    existing["X"] = [row for row in existing["X"] if row.get("phase6_key") != "door_face_w"]
    extra = {"len": 12, "angle": 90, "custom": "preserve"}
    existing["Y"].append(extra)
    result = merge_keyed_fold_profiles(existing, defaults)
    assert result["X"] == defaults["X"]
    assert result["X"] is not defaults["X"]
    assert result["Y"][-1] == extra
    assert result["Y"][-1] is not extra
    assert merge_keyed_fold_profiles({}, defaults) == defaults


def test_canonical_metadata_removed_when_engine_default_has_no_property():
    defaults = _defaults()
    defaults["X"][0].pop("ui_len_add")
    defaults["X"][0].pop("core", None)
    existing = deepcopy(_defaults())
    existing["X"][0]["ui_len_add"] = 999
    existing["X"][0]["core"] = "stale"
    merged = merge_keyed_fold_profiles(existing, defaults)
    assert "ui_len_add" not in merged["X"][0]
    assert "core" not in merged["X"][0]


def test_settings_projection_calls_public_engine_merge(monkeypatch):
    calls = []
    def fake_merge(existing, defaults):
        calls.append((existing, defaults))
        return {"X": [{"len": 42}], "Y": []}
    monkeypatch.setattr(settings, "merge_keyed_fold_profiles", fake_merge)
    actual = settings.merge_keyed_profiles({"X": []}, {"X": [{"len": 20}]})
    assert actual == {"X": [{"len": 42}], "Y": []}
    assert calls == [({"X": []}, {"X": [{"len": 20}]})]
