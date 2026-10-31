"""#2517: edited/custom BoxBody Fold reconciliation belongs to public Engine."""
from __future__ import annotations
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api, merge_box_body_fold_profile
from phase6_fold_profiles import merge_box_body_profile as gui_merge
from tests.test_phase6_linked_fold_chain_and_parts import _box_profile, _segment


BASE = {
    "model": "金庫型", "w": 400, "h": 600, "d": 250, "t": 2,
    "fw": 25, "zl1": 15, "zl2": 20, "zr2": 20, "zr1": 15,
}


@pytest.mark.parametrize("count", (5, 20))
def test_engine_preserves_custom_fold_topology_and_refreshes_shared_core(count):
    extra = [_segment(7 + i, -45 if i % 2 else 90) for i in range(count - 5)]
    profile = _box_profile(extra_left=extra)
    original = deepcopy(profile)
    merged = merge_box_body_fold_profile(profile, BASE)
    assert merge_box_body_fold_profile is manufacturing_api.merge_box_body_fold_profile
    assert profile == original
    assert merged == gui_merge(profile, BASE)
    assert len(merged) == count
    assert [r.get("phase6_key") for r in merged] == [r.get("phase6_key") for r in original]
    assert [r["len"] for r in merged[:len(extra)]] == [r["len"] for r in original[:len(extra)]]
    canonical = {row.get("phase6_key"): row for row in manufacturing_api.build_box_body_fold_profile(BASE)}
    for row in merged:
        if row.get("phase6_key") in {"d_left", "w", "d_right", "fw_left", "fw_right"}:
            assert row["len"] == canonical[row["phase6_key"]]["len"]
    assert [row.get("core") for row in merged].count("D") == 2
    assert [row.get("core") for row in merged].count("W") == 1


def test_receiving_family_removes_old_vault_terminal_without_recreating_outer_folds():
    vault = manufacturing_api.build_box_body_fold_profile(BASE)
    assert "zr1" in [row.get("phase6_key") for row in vault]
    receiving = {**BASE, "model": "受電箱"}
    merged = merge_box_body_fold_profile(vault, receiving)
    assert "zr1" not in [row.get("phase6_key") for row in merged]
    assert len(merged) == len(vault) - 1
    assert [r.get("core") for r in merged].count("D") == 2
    assert [r.get("core") for r in merged].count("W") == 1


def test_corrupt_fold_missing_w_core_refused_even_when_other_dimensions_exist():
    source = [row for row in _box_profile() if row.get("core") != "W"]
    with pytest.raises(ValueError, match="D-W-D"):
        merge_box_body_fold_profile(source, BASE)


def test_phase6_editor_merger_only_calls_engine_manufacturing_api():
    text = inspect.getsource(gui_merge)
    assert "manufacturing_api.merge_box_body_fold_profile(" in text
    assert "transform_box_body_profile(" not in text
    assert "D-W-D" not in text
    assert "from phase6_" not in inspect.getsource(merge_box_body_fold_profile)
