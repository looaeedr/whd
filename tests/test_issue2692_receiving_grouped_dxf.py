"""#2692: physical per-Set/Bay group modes, source/atomic acceptance."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.manufacturing_export import receiving_instance_namespace
from ae_engine.receiving_dxf_groups import (
    commit_verified_receiving_groups, plan_receiving_grouped_dxf,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, resize_receiving_sets,
)
from tests.test_issue2690_composed_panel_dxf import _flat
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _provider
from tests.test_issue1502_single_button_full_csv_receiving_export import _flags


def _seven():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=4)
    layout = resize_receiving_sets(layout, set_count=2)
    layout = resize_receiving_bays(layout, set_index=1, bay_count=3)
    return layout


def _names(cells):
    return tuple(name for _, _, name in cells)


def test_three_modes_on_two_sets_of_four_plus_three_physical_bays():
    state = _seven()
    for row, names in zip(state["sets"], (("P1","P2","P3","P4"), ("P5","P6","P7"))):
        assert tuple(bay["panel_name"] for bay in row["bays"]) == names
    per_set = manufacturing_api.plan_receiving_grouped_dxf(state, "PER_SET")
    assert tuple(n for n, _ in per_set) == ("第1套.dxf", "第2套.dxf")
    assert _names(per_set[0][1]) == ("P1","P2","P3","P4")
    assert _names(per_set[1][1]) == ("P5","P6","P7")
    assert manufacturing_api.plan_receiving_grouped_dxf(state, "ALL") == (
        ("全部.dxf", per_set[0][1] + per_set[1][1]),)
    grouped = manufacturing_api.plan_receiving_grouped_dxf(state, "END_VS_MIDDLE")
    assert tuple(n for n, _ in grouped) == ("頭尾盤.dxf", "中間盤.dxf")
    assert _names(grouped[0][1]) == ("P1","P4","P5","P7")
    assert _names(grouped[1][1]) == ("P2","P3","P6")


def test_one_bay_and_two_bays_only_end_no_empty_middle():
    state = new_receiving_layout(width=800, height=1600, depth=350)
    state = resize_receiving_sets(state, set_count=2)
    state = resize_receiving_bays(state, set_index=1, bay_count=2)
    groups = plan_receiving_grouped_dxf(state, "END_VS_MIDDLE")
    assert len(groups) == 1
    assert groups[0][0] == "頭尾盤.dxf"
    assert _names(groups[0][1]) == ("P1","P2","P3")


def test_renaming_or_gaps_never_reclassifies_physical_edges():
    state = _seven()
    # Assign nonnumeric/nonnatural names in different physical cells.
    state = manufacturing_api.rename_receiving_panel(
        state, set_index=0, bay_index=0, panel_name="入線",
    )
    state = manufacturing_api.rename_receiving_panel(
        state, set_index=0, bay_index=2, panel_name="主盤",
    )
    groups = plan_receiving_grouped_dxf(state, "END_VS_MIDDLE")
    assert _names(groups[0][1]) == ("入線","P4","P5","P7")
    assert _names(groups[1][1]) == ("P2","主盤","P6")
    with pytest.raises(ValueError, match="MODE_UNSUPPORTED"):
        plan_receiving_grouped_dxf(state, "UNKNOWN")


def _synthetic_rows(layout):
    rows=[]
    for si, group in enumerate(layout["sets"]):
        for bi, bay in enumerate(group["bays"]):
            ns=receiving_instance_namespace(
                set_id=group["stable_id"], bay_id=bay["stable_id"],
            )
            rows.append((ns, "door", f"{ns}__door.dxf",
                         _flat("door", width=80+si*4+bi)))
    return tuple(rows)


@pytest.mark.parametrize("mode,expected", [
    ("PER_SET", ("第1套.dxf","第2套.dxf")),
    ("ALL", ("全部.dxf",)),
    ("END_VS_MIDDLE", ("頭尾盤.dxf","中間盤.dxf")),
])
def test_group_commit_is_a_atomic_batch_with_dxf_readback(tmp_path, mode, expected):
    layout = _seven()
    counts = []
    with TemporaryDirectory(dir=tmp_path) as stage:
        receipts = commit_verified_receiving_groups(
            layout, mode, _synthetic_rows(layout), stage, tmp_path/"out",
            pre_commit_guard=lambda: counts.append("verified"),
        )
    assert tuple(receipts.keys()) == expected
    assert tuple(p.name for p in (tmp_path/"out").glob("*.dxf")) == expected
    assert len(counts) >= 2
    for filename in expected:
        entities = tuple(ezdxf.readfile(tmp_path/"out"/filename).modelspace())
        assert any(e.dxftype()=="LWPOLYLINE" and e.dxf.layer=="CUTTING"
                   for e in entities)
        assert all(e.dxf.layer=="CHECK" for e in entities
                   if e.dxftype()=="MTEXT" and e.plain_text().startswith("P"))


def test_drift_on_second_group_preserves_all_old_outputs(tmp_path):
    from ae_engine import composed_panel_dxf
    layout = _seven()
    out = tmp_path/"out"
    out.mkdir()
    first, second = out/"頭尾盤.dxf", out/"中間盤.dxf"
    first.write_bytes(b"old head")
    second.write_bytes(b"old middle")
    calls = 0
    def guard():
        nonlocal calls
        calls += 1
        if calls == 3:  # between groups, after first group is staged
            raise ValueError("SAVED_SOURCE_FINGERPRINT_CHANGED")
    with TemporaryDirectory(dir=tmp_path) as stage, pytest.raises(ValueError, match="FINGERPRINT_CHANGED"):
        commit_verified_receiving_groups(
            layout, "END_VS_MIDDLE", _synthetic_rows(layout),
            stage, out, pre_commit_guard=guard, overwrite=True,
        )
    assert first.read_bytes()==b"old head"
    assert second.read_bytes()==b"old middle"


def test_missing_bay_source_refuses_every_output(tmp_path):
    layout = _seven()
    rows = _synthetic_rows(layout)[:-1]
    with TemporaryDirectory(dir=tmp_path) as stage, pytest.raises(ValueError, match="INCOMPLETE_BAY_SOURCE"):
        commit_verified_receiving_groups(
            layout, "ALL", rows, stage, tmp_path/"output",
            pre_commit_guard=lambda: None,
        )
    assert not list((tmp_path/"output").glob("*.dxf"))


def test_legacy_current_csv_export_and_new_group_mode_share_real_source_guard(tmp_path):
    source = _multi()
    provider, calls = _provider(source)
    checked = []
    output = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider, flags=_flags(),
        output_dir=tmp_path/"output", group_mode="ALL",
        pre_commit_guard=lambda: checked.append("verified"),
    )
    assert set(output) == {"全部.dxf"}
    assert len(list((tmp_path/"output").glob("*.dxf"))) == 1
    assert calls == [(0,0),(0,1)]
    assert len(checked)>=2
    assert len(tuple(ezdxf.readfile(tmp_path/"output"/"全部.dxf").modelspace()))>20
