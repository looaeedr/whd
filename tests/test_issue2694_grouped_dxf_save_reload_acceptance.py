"""#2694: cross-ticket persisted naming and grouped physical DXF parity."""
from __future__ import annotations

from tempfile import TemporaryDirectory

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_dxf_groups import commit_verified_receiving_groups
from ae_engine.receiving_layout import resize_receiving_bays
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue2692_receiving_grouped_dxf import _seven, _synthetic_rows


def test_save_reload_real_canonical_layout_then_three_modes_have_exact_bay_membership(tmp_path):
    layout = _seven()
    # Panel labels are operator input; changing them never rewrites physical IDs.
    first_id = layout["sets"][0]["bays"][0]["stable_id"]
    layout = manufacturing_api.rename_receiving_panel(
        layout, set_index=0, bay_index=1, panel_name="中間電盤",
    )
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=4)
    assert layout["sets"][0]["bays"][3]["panel_name"] == "P8"
    document = {
        "schema": PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱", "active_mode": "set_bay",
            "receiving_layout": layout,
        },
        "final_geometry": {},
    }
    path = write_project(tmp_path / "saved.p6fold", document)
    saved = read_project(path)["snapshot"]["receiving_layout"]
    assert saved["next_panel_number"] == 9
    assert saved["sets"][0]["bays"][0]["stable_id"] == first_id
    assert saved["sets"][0]["bays"][1]["panel_name"] == "中間電盤"
    edge = manufacturing_api.plan_receiving_grouped_dxf(
        saved, "END_VS_MIDDLE",
    )
    assert [name for name,_ in edge] == ["頭尾盤.dxf", "中間盤.dxf"]
    assert [name for _,_,name in edge[0][1]] == ["P1","P8","P5","P7"]
    assert [name for _,_,name in edge[1][1]] == ["中間電盤","P3","P6"]
    for mode, expected, counts in (
        ("PER_SET", ("第1套.dxf", "第2套.dxf"), (4, 3)),
        ("ALL", ("全部.dxf",), (7,)),
        ("END_VS_MIDDLE", ("頭尾盤.dxf", "中間盤.dxf"), (4, 3)),
    ):
        output = tmp_path / mode
        with TemporaryDirectory(dir=tmp_path) as staging:
            emitted = commit_verified_receiving_groups(
                saved, mode, _synthetic_rows(saved), staging, output,
                pre_commit_guard=lambda: None,
            )
        assert set(emitted) == set(expected)
        assert {p.name for p in output.glob("*.dxf")} == set(expected)
        for filename, physical_count in zip(expected, counts):
            doc = ezdxf.readfile(output / filename)
            model = tuple(doc.modelspace())
            # One independent closed blank and one source owner per Bay;
            # counts do not include only group labels or unsupported parts.
            assert sum(
                e.dxftype() == "LWPOLYLINE"
                and e.dxf.layer == "CUTTING" and e.closed
                for e in model
            ) == physical_count
            owners = [e.plain_text() for e in model
                      if e.dxftype() == "MTEXT"
                      and e.dxf.layer == "CHECK"]
            # Every sheet has physical DOOR provenance and its panel label.
            assert owners.count("door") == physical_count


def test_vault_blank_and_named_save_reload_are_deterministic(tmp_path):
    from datetime import datetime, timezone
    for name, expected in (
        ("", "金庫型_20261101_140504.dxf"),
        ("ABC-01", "ABC-01.dxf"),
    ):
        project = {"schema": PROJECT_SCHEMA,
                   "snapshot": manufacturing_api.set_cabinet_panel_name(
                       {"model": "金庫型"}, name,
                   ), "final_geometry": {}}
        path = write_project(tmp_path / (name or "empty") / "vault.p6fold", project)
        snapshot = read_project(path)["snapshot"]
        assert snapshot["panel_name"] == name
        assert manufacturing_api.vault_panel_dxf_filename(
            snapshot["panel_name"],
            at=datetime(2026,11,1,6,5,4,tzinfo=timezone.utc),
        ) == expected
