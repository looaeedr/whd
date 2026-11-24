"""Existing ordinary Head ALL + total must be published as one live transaction."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api, manufacturing_export, receiving_dxf_groups
from tests.test_issue1502_current_csv_multi_bay_once import _provider
from tests.test_issue3414_scoped_marking_proto import _real_source


@pytest.mark.parametrize("prior_output", [True, False])
def test_actual_receiving_head_all_source_drift_rolls_back_outer_move(
    tmp_path, monkeypatch, prior_output,
):
    saved_source = _real_source()
    live_source = deepcopy(saved_source)
    destination = tmp_path / "released"
    # Fixed export-minute alias for two submissions of the same real panels.
    monkeypatch.setattr(
        receiving_dxf_groups, "_taipei_output_stamp", lambda: "202611242003",
    )

    def assert_live_source():
        if saved_source != live_source:
            raise ValueError("GROUPED_LIVE_WORKSPACE_CHANGED")

    def export():
        provider, calls = _provider(saved_source)
        result = api.export_grouped_receiving_multibay_dxf(
            saved_source, physical_bay_geometry_provider=provider,
            flags={"head": True}, group_mode="ALL", output_dir=destination,
            overwrite=True, pre_commit_guard=assert_live_source,
        )
        assert calls == [(0, 0), (0, 1)]
        return result

    clean = export()
    assert len(clean) == 2
    prior = {Path(p).name: Path(p).read_bytes() for p in clean.values()}
    assert {"全部", "總計"} == {Path(p).stem.split("p1~p2")[-1] for p in clean.values()}
    for path in clean.values():
        doc = ezdxf.readfile(path)
        assert doc.header["$INSUNITS"] == 4
        assert any(p.dxf.layer == "CUTTING" for p in doc.modelspace())
        assert any(p.dxf.layer == "BEND" for p in doc.modelspace())
    if not prior_output:
        for path in clean.values():
            Path(path).unlink()
        prior = {}

    original_replace = manufacturing_export.os.replace
    moved = []

    def change_live_source_after_first_outer_move(stage, target):
        result = original_replace(stage, target)
        target = Path(target)
        # Earlier independent-flat, composed substage, backup and restore
        # renames do not count: this is an actual final group file move.
        if target.parent == destination and Path(stage).parent.name.startswith(".whd-multibay-csv-"):
            moved.append(target.name)
            if len(moved) == 1:
                live_source["receiving_layout"]["sets"][0]["bays"][0]["width"] += 1
        return result

    monkeypatch.setattr(manufacturing_export.os, "replace", change_live_source_after_first_outer_move)
    with pytest.raises(ValueError, match="GROUPED_LIVE_WORKSPACE_CHANGED"):
        export()
    assert moved and moved[0] in {Path(p).name for p in clean.values()}
    assert {p.name: p.read_bytes() for p in destination.iterdir()} == prior

    monkeypatch.setattr(manufacturing_export.os, "replace", original_replace)
    live_source = deepcopy(saved_source)
    assert export() == clean
    assert {p.name for p in destination.iterdir()} == {Path(p).name for p in clean.values()}
