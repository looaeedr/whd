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

# The export minute is frozen only for filename expectations. Production
# output obtains the Taiwan local minute once per atomic group transaction.
@pytest.fixture(autouse=True)
def _fixed_export_minute(monkeypatch):
    monkeypatch.setattr(
        "ae_engine.receiving_dxf_groups._taipei_output_stamp",
        lambda: "202611071258",
    )


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



def test_output_filename_stamp_panel_range_and_nonnumeric_names():
    state = _seven()
    stamp = "202611071258"
    all_plan = plan_receiving_grouped_dxf(state, "ALL", file_stamp=stamp)
    assert tuple(n for n, _ in all_plan) == (
        "202611071258_p1~p7全部.dxf",
    )
    per_set = plan_receiving_grouped_dxf(state, "PER_SET", file_stamp=stamp)
    assert tuple(n for n, _ in per_set) == (
        "202611071258_p1~p7第1套.dxf",
        "202611071258_p1~p7第2套.dxf",
    )
    groups = plan_receiving_grouped_dxf(state, "END_VS_MIDDLE",
                                        file_stamp=stamp)
    assert tuple(n for n, _ in groups) == (
        "202611071258_p1~p7頭尾盤.dxf",
        "202611071258_p1~p7中間盤.dxf",
    )
    renamed = manufacturing_api.rename_receiving_panel(
        state, set_index=0, bay_index=0, panel_name="入線",
    )
    renamed_plan = plan_receiving_grouped_dxf(
        renamed, "ALL", file_stamp=stamp,
    )
    assert "入線" in renamed_plan[0][0]
    assert renamed_plan[0][0].endswith("全部.dxf")
    assert len(renamed_plan[0][1]) == 7
    for invalid in ("2026110712", "202613071258", "../invalid000", "", 0):
        with pytest.raises(ValueError, match="TIMESTAMP_INVALID"):
            plan_receiving_grouped_dxf(state, "ALL", file_stamp=invalid)



def test_sixteen_bay_mother_range_is_shared_across_all_five_output_names():
    source = new_receiving_layout(width=800, height=1600, depth=350)
    source = resize_receiving_bays(source, set_index=0, bay_count=4)
    source = resize_receiving_sets(source, set_count=3)
    source = resize_receiving_bays(source, set_index=1, bay_count=3)
    source = resize_receiving_bays(source, set_index=2, bay_count=9)
    expected = {
        "ALL": ("202611071258_p1~p16全部.dxf",),
        "PER_SET": (
            "202611071258_p1~p16第1套.dxf",
            "202611071258_p1~p16第2套.dxf",
            "202611071258_p1~p16第3套.dxf",
        ),
        "END_VS_MIDDLE": (
            "202611071258_p1~p16頭尾盤.dxf",
            "202611071258_p1~p16中間盤.dxf",
        ),
    }
    for mode, names in expected.items():
        result = manufacturing_api.plan_receiving_grouped_dxf(
            source, mode, file_stamp="202611071258",
        )
        assert tuple(name for name, _ in result) == names
        assert sum(len(cells) for _, cells in result) == 16
    assert tuple(
        len(cells) for _, cells in
        manufacturing_api.plan_receiving_grouped_dxf(source, "PER_SET")
    ) == (4, 3, 9)
    assert tuple(
        len(cells) for _, cells in
        manufacturing_api.plan_receiving_grouped_dxf(source, "END_VS_MIDDLE")
    ) == (6, 10)



def _certified_body(layout, si, bi, *, thickness_mm=2.0):
    """Use actual Engine Family/Joint production geometry in grouped acceptance."""
    from ae_engine.contracts import ManufacturingContext
    bay = layout["sets"][si]["bays"][bi]
    values = {"w": bay["width"], "h": bay["height"], "d": bay["depth"],
              "t": thickness_mm}
    fresh = dict(manufacturing_api.build_receiving_factory_confirmed_parts(
        values, confirmation="fresh_family_confirmed",
    ))["box_body"]
    physical = manufacturing_api.bind_receiving_factory_box_body_to_bay(
        fresh, layout, set_index=si, bay_index=bi,
    )
    return manufacturing_api.build_box_body_structure_render_data(
        physical, ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
    )


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
    ("PER_SET", ("202611071258_p1~p7第1套.dxf","202611071258_p1~p7第2套.dxf")),
    ("ALL", ("202611071258_p1~p7全部.dxf",)),
    ("END_VS_MIDDLE", ("202611071258_p1~p7頭尾盤.dxf","202611071258_p1~p7中間盤.dxf")),
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
    assert {p.name for p in (tmp_path/"out").glob("*.dxf")} == set(expected)
    assert len(counts) >= 2
    for filename in expected:
        entities = tuple(ezdxf.readfile(tmp_path/"out"/filename).modelspace())
        assert any(e.dxftype()=="LWPOLYLINE" and e.dxf.layer=="CUTTING"
                   for e in entities)
        assert all(e.dxf.layer=="CHECK" for e in entities
                   if e.dxftype()=="MTEXT" and e.plain_text().startswith("P"))



def test_single_bay_grouped_box_body_and_head_writes_one_verified_dxf(tmp_path):
    """An ALL operator choice may not fall back to separate source-sheet files."""
    from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart

    layout = new_receiving_layout(width=800, height=1600, depth=350)
    source = {
        "model": "受電箱", "active_mode": "set_bay",
        "w": 800, "h": 1600, "d": 350, "t": 2,
        "receiving_layout": layout,
    }
    calls = []
    def provider(si, bi):
        calls.append((si, bi))
        return ResolvedManufacturingGeometry(parts=(
            ResolvedManufacturingPart("box_body", _certified_body(layout, si, bi)),
            ResolvedManufacturingPart("head", _flat("head", width=90)),
        ))

    output = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider,
        flags={"box_body": True, "head": True},
        output_dir=tmp_path / "out", group_mode="ALL",
        pre_commit_guard=lambda: None,
    )
    assert calls == [(0, 0)]
    assert set(output) == {"202611071258_p1全部.dxf"}
    assert {p.name for p in (tmp_path / "out").glob("*.dxf")} == {"202611071258_p1全部.dxf"}
    document = ezdxf.readfile(tmp_path / "out" / "202611071258_p1全部.dxf")
    entities = tuple(document.modelspace())
    assert sum(entity.dxftype() == "LWPOLYLINE" and
               entity.dxf.layer == "CUTTING" for entity in entities) >= 4
    checks = [entity.plain_text() for entity in entities
              if entity.dxftype() == "MTEXT" and entity.dxf.layer == "CHECK"]
    assert {"box_body:box_body_left_side", "box_body:box_body_right_side", "box_body:box_body_back",
            "head", "P1"} <= set(checks)


def test_single_bay_grouped_missing_canonical_scene_refuses_zero_output(tmp_path):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    source = {
        "model": "受電箱", "active_mode": "set_bay",
        "w": 800, "h": 1600, "d": 350, "t": 2,
        "receiving_layout": layout,
    }
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE_MISSING"):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=lambda _si, _bi: None,
            flags={"box_body": True}, output_dir=tmp_path / "out",
            group_mode="ALL", pre_commit_guard=lambda: None,
        )
    assert not list((tmp_path / "out").glob("*.dxf"))



def test_single_bay_grouped_requested_missing_base_fails_closed(tmp_path):
    from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    source = {
        "model": "受電箱", "active_mode": "set_bay",
        "w": 800, "h": 1600, "d": 350, "t": 2,
        "receiving_layout": layout,
    }
    def provider(_si, _bi):
        return ResolvedManufacturingGeometry(parts=(
            ResolvedManufacturingPart("head", _flat("head")),
        ))
    with pytest.raises(ValueError, match="SELECTED_BASE_PLATE_PHYSICAL_SOURCE_MISSING"):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider,
            flags={"head": True, "base_plate": True},
            output_dir=tmp_path / "out", group_mode="ALL",
            pre_commit_guard=lambda: None,
        )
    assert not list((tmp_path / "out").glob("*.dxf"))



def test_drift_on_second_group_preserves_all_old_outputs(tmp_path):
    layout = _seven()
    out = tmp_path/"out"
    out.mkdir()
    first, second = out/"202611071258_p1~p7頭尾盤.dxf", out/"202611071258_p1~p7中間盤.dxf"
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
    # Use independently source-eligible physical Head sheets; full NFB MFG-2
    # remains unreleased rather than accepted from a preview flag.
    output = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider, flags={"head": True},
        output_dir=tmp_path/"output", group_mode="ALL",
        pre_commit_guard=lambda: checked.append("verified"),
    )
    assert set(output) == {"202611071258_p1~p2全部.dxf"}
    assert len(list((tmp_path/"output").glob("*.dxf"))) == 1
    assert calls == [(0,0),(0,1)]
    assert len(checked)>=2
    assert len(tuple(ezdxf.readfile(tmp_path/"output"/"202611071258_p1~p2全部.dxf").modelspace()))>2



def test_grouped_physical_flats_retain_canonical_body_owner(tmp_path):
    """Grouped Bay exporter may not lose order when it detaches the flat scenes."""
    from ae_engine.manufacturing_render_data import (
        BoxBodyPieceRenderData, BoxBodyStructureRenderData,
    )
    state = _seven()
    ns = receiving_instance_namespace(
        set_id=state["sets"][0]["stable_id"],
        bay_id=state["sets"][0]["bays"][0]["stable_id"],
    )
    flats = {
        "box_body_left_side": _flat("left", width=110.0),
        "box_body_back": _flat("back", width=120.0, height=42.0),
        "box_body_right_side": _flat("right", width=130.0),
    }
    # Source order is intentionally incorrect. Only the original Engine
    # BoxBodyStructureRenderData knows real formed-width/order and back inset.
    pieces = (
        BoxBodyPieceRenderData("box_body_right_side", "right_side",
                               800.0, 800.0, (), flats["box_body_right_side"]),
        BoxBodyPieceRenderData("box_body_back", "back",
                               100.0, 700.0, (), flats["box_body_back"],
                               formed_y_offset=20.0),
        BoxBodyPieceRenderData("box_body_left_side", "left_side",
                               0.0, 0.0, (), flats["box_body_left_side"]),
    )
    owner = BoxBodyStructureRenderData(
        "side_back", pieces, _flat("preview"), _flat("canonical"),
    )
    rows = list(_synthetic_rows(state))
    rows.extend(
        (ns, f"box_body:{piece.key}", f"{ns}__{piece.key}.dxf",
         piece.render_data)
        for piece in pieces
    )
    with TemporaryDirectory(dir=tmp_path) as staging:
        receipts = commit_verified_receiving_groups(
            state, "PER_SET", rows, staging, tmp_path / "output",
            pre_commit_guard=lambda: None,
            box_body_owner_by_namespace={ns: owner},
        )
    assert set(receipts) == {"202611071258_p1~p7第1套.dxf", "202611071258_p1~p7第2套.dxf"}
    doc = ezdxf.readfile(tmp_path / "output" / "202611071258_p1~p7第1套.dxf")
    checks = [e.plain_text() for e in doc.modelspace()
              if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"]
    assert checks.index("box_body:box_body_left_side") < (
        checks.index("box_body:box_body_back")
    ) < checks.index("box_body:box_body_right_side")
    outlines = {}
    for ent in doc.modelspace():
        if ent.dxftype() != "LWPOLYLINE" or ent.dxf.layer != "CUTTING" or not ent.closed:
            continue
        pts = tuple(ent.get_points("xy"))
        span = round(max(pt[0] for pt in pts) - min(pt[0] for pt in pts), 1)
        if span in (110.0, 120.0, 130.0):
            outlines[span] = min(pt[1] for pt in pts)
    assert set(outlines) == {110.0, 120.0, 130.0}
    assert outlines[120.0] - outlines[110.0] == 20.0
    assert set((tmp_path / "output").glob("*.dxf")) == {
        tmp_path / "output" / "202611071258_p1~p7第1套.dxf",
        tmp_path / "output" / "202611071258_p1~p7第2套.dxf",
    }


def test_grouped_export_rejects_untrusted_body_owner_without_publishing(tmp_path):
    state = _seven()
    ns = receiving_instance_namespace(
        set_id=state["sets"][0]["stable_id"],
        bay_id=state["sets"][0]["bays"][0]["stable_id"],
    )
    out = tmp_path / "out"
    out.mkdir()
    old = out / "202611071258_p1~p7第1套.dxf"
    old.write_bytes(b"old-file-preserved")
    with TemporaryDirectory(dir=tmp_path) as staging:
        with pytest.raises(TypeError, match="COMPOSED_DXF_BOX_BODY_OWNER_TYPE_INVALID"):
            commit_verified_receiving_groups(
                state, "PER_SET", _synthetic_rows(state), staging, out,
                overwrite=True, pre_commit_guard=lambda: None,
                box_body_owner_by_namespace={ns: object()},
            )
    assert old.read_bytes() == b"old-file-preserved"
    assert not (out / "202611071258_p1~p7第2套.dxf").exists()


def _complete_committed_nfb_requests_for_core(source):
    """One real mother layout, two genuine approved NFB pairs, no cloned identities."""
    from copy import deepcopy
    api = manufacturing_api
    fresh = api.fresh_receiving_mode(
        "set_bay", {"w": source["w"], "h": source["h"], "d": source["d"]},
        thickness=source["t"],
    )
    layout = api.resize_receiving_bays_with_family_defaults(
        fresh["receiving_layout"], set_index=0,
        bay_count=len(source["receiving_layout"]["sets"][0]["bays"]),
    )
    layout["sets"][0]["switch_brand"] = "士林"
    assert [
        (group["stable_id"], bay["stable_id"])
        for group in layout["sets"] for bay in group["bays"]
    ] == [
        (group["stable_id"], bay["stable_id"])
        for group in source["receiving_layout"]["sets"]
        for bay in group["bays"]
    ]
    from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS
    for bay in layout["sets"][0]["bays"]:
        # Preserve the complete original Engine Door schema (including scope,
        # nameplate, handle and inner-door topology), not a two-field mock.
        bay["door_state"] = {
            key: deepcopy(fresh[key])
            for key in RECEIVING_DOOR_STATE_KEYS if key in fresh
        }
    for bi in range(len(layout["sets"][0]["bays"])):
        draft = api.candidate_receiving_nfb_csv_for_fresh_bay(
            layout, set_index=0, bay_index=bi, thickness_mm=source["t"],
            layers=1, models=[["nfbv5:士林:2P400"], ""],
        )
        layout, _accepted = api.approve_receiving_nfb_csv_default_x(
            layout, set_index=0, bay_index=bi, thickness_mm=source["t"],
            source=draft, confirmation="ACCEPT_CURRENT_WHD_NFB_DEFAULT_X",
        )
    return layout, tuple(api.receiving_committed_nfb_pair_request_for_bay(
        layout, set_index=0, bay_index=bi, thickness_mm=source["t"],
    ) for bi in range(len(layout["sets"][0]["bays"])))



def test_main_grouped_export_includes_saved_confirmed_nfb_pair_in_one_file(tmp_path):
    """Public Engine projects original approved pair Requests; no side NFB DXF."""
    source = _multi()
    layout, requests = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = layout
    before = tuple(
        (request.input_snapshot, request.canonical_part_keys)
        for request in requests
    )
    provider, _calls = _provider(source)
    result = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider,
        flags={"head": True, "door": True, "base_plate": True},
        output_dir=tmp_path / "out", group_mode="ALL",
        pre_commit_guard=lambda: None, include_saved_nfb_pairs=True,
    )
    assert set(result) == {"202611071258_p1~p2全部.dxf"}
    assert {path.name for path in (tmp_path / "out").rglob("*.dxf")} == {"202611071258_p1~p2全部.dxf"}
    doc = ezdxf.readfile(result["202611071258_p1~p2全部.dxf"])
    assert not doc.audit().errors
    checks = [e.plain_text() for e in doc.modelspace()
              if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"]
    assert checks.count("head") == 2
    assert sum(key.startswith("inner_door:") for key in checks) == 2
    assert checks.count("base_plate") == 2
    assert before == tuple(
        (request.input_snapshot, request.canonical_part_keys)
        for request in requests
    )
    assert not (tmp_path / "out" / "NFB_PART_ONLY").exists()


def test_main_grouped_export_rejects_partly_confirmed_nfb_instead_of_partial_output(tmp_path):
    source = _multi()
    layout, _requests = _complete_committed_nfb_requests_for_core(source)
    layout["sets"][0]["bays"][1]["nfb_config_submitted"] = False
    source["receiving_layout"] = layout
    provider, _calls = _provider(source)
    with pytest.raises(ValueError, match="RECEIVING_COMPOSED_NFB_PARTIAL_BAY_CONFIRMATION"):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider,
            flags={"head": True, "door": True, "base_plate": True},
            output_dir=tmp_path / "out", group_mode="ALL",
            pre_commit_guard=lambda: None, include_saved_nfb_pairs=True,
        )
    assert not list((tmp_path / "out").rglob("*.dxf"))


def test_head_only_does_not_auto_include_unselected_nfb_pairs(tmp_path):
    source = _multi()
    layout, _requests = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = layout
    provider, _calls = _provider(source)
    result = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider,
        flags={"head": True}, output_dir=tmp_path / "out",
        group_mode="ALL", pre_commit_guard=lambda: None,
        include_saved_nfb_pairs=True,
    )
    assert set(result) == {"202611071258_p1~p2全部.dxf"}
    doc = ezdxf.readfile(result["202611071258_p1~p2全部.dxf"])
    checks = [e.plain_text() for e in doc.modelspace()
              if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"]
    assert checks.count("head") == 2
    assert not any(k == "base_plate" or k.startswith("inner_door:") for k in checks)



def test_grouped_nfb_pair_verified_source_exports_only_one_composed_file(tmp_path):
    """Each source-confirmed NFB pair joins its own Bay; no parallel PART_ONLY files."""
    source = _multi()
    layout, requests = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = layout  # the SAME approved physical source
    provider, _calls = _provider(source)
    result = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=provider,
        flags={"head": True}, output_dir=tmp_path / "out",
        group_mode="PER_SET", pre_commit_guard=lambda: None,
        nfb_pair_requests=requests,
    )
    assert set(result) == {"202611071258_p1~p2第1套.dxf"}
    assert list((tmp_path / "out").glob("*.dxf")) == [
        tmp_path / "out" / "202611071258_p1~p2第1套.dxf"
    ]
    doc = ezdxf.readfile(result["202611071258_p1~p2第1套.dxf"])
    assert not doc.audit().errors
    checks = [entity.plain_text() for entity in doc.modelspace()
              if entity.dxftype() == "MTEXT" and entity.dxf.layer == "CHECK"]
    assert checks.count("head") == 2
    assert sum(key.startswith("inner_door:") for key in checks) == 2
    assert checks.count("base_plate") == 2
    # Composing verified PART_ONLY flats does not publish standalone pairs.
    assert not list((tmp_path / "out").rglob("NFB_PART_ONLY/*.dxf"))


def test_grouped_nfb_missing_second_pair_rejects_entire_group(tmp_path):
    source = _multi()
    layout, approved = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = layout
    provider, _calls = _provider(source)
    requests = approved[:1]
    with pytest.raises(ValueError, match="RECEIVING_COMPOSED_NFB_ALL_BAYS_REQUIRED"):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider,
            flags={"head": True}, output_dir=tmp_path / "out",
            group_mode="PER_SET", pre_commit_guard=lambda: None,
            nfb_pair_requests=requests,
        )
    assert not list((tmp_path / "out").rglob("*.dxf"))


def test_grouped_nfb_wrong_bay_owner_rejected_before_output(tmp_path):
    source = _multi()
    layout, approved = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = layout
    provider, _calls = _provider(source)
    requests = tuple(reversed(approved))
    with pytest.raises(ValueError, match="RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH"):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider,
            flags={"head": True}, output_dir=tmp_path / "out",
            group_mode="PER_SET", pre_commit_guard=lambda: None,
            nfb_pair_requests=requests,
        )
    assert not list((tmp_path / "out").rglob("*.dxf"))



def test_grouped_nfb_same_ids_dimensions_but_foreign_csv_source_rejected(tmp_path):
    """A distinct project's approved pair cannot replace this saved Bay's NFB."""
    source = _multi()
    approved_layout, requests = _complete_committed_nfb_requests_for_core(source)
    saved_layout = source["receiving_layout"]  # intentionally NOT the approved source
    assert [
        (group["stable_id"], bay["stable_id"],
         bay["width"], bay["height"], bay["depth"])
        for group in saved_layout["sets"] for bay in group["bays"]
    ] == [
        (group["stable_id"], bay["stable_id"],
         bay["width"], bay["height"], bay["depth"])
        for group in approved_layout["sets"] for bay in group["bays"]
    ]
    assert (
        saved_layout["sets"][0]["bays"][0]["nfb_config"]
        != approved_layout["sets"][0]["bays"][0]["nfb_config"]
    )
    provider, _calls = _provider(source)
    with pytest.raises(
        ValueError, match="RECEIVING_COMPOSED_NFB_PHYSICAL_SOURCE_MISMATCH"
    ):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider,
            flags={"head": True}, output_dir=tmp_path / "out",
            group_mode="PER_SET", pre_commit_guard=lambda: None,
            nfb_pair_requests=requests,
        )
    assert not list((tmp_path / "out").rglob("*.dxf"))

@pytest.mark.parametrize("mode, filenames", [
    ("ALL", ("202611071258_p1~p2全部.dxf",)),
    ("PER_SET", ("202611071258_p1~p2第1套.dxf",)),
    ("END_VS_MIDDLE", ("202611071258_p1~p2頭尾盤.dxf",)),
])
def test_same_saved_nfb_source_allows_only_independent_core_flat_scope(
    tmp_path, mode, filenames,
):
    """An approved pair can share its exact saved source with independent core.

    A non-NFB Body is never treated as an EAR/PAD certified whole cabinet.
    Engine must still rederive every approved pair from this saved Layout.
    """
    from ae_engine.contracts import (
        ResolvedManufacturingGeometry, ResolvedManufacturingPart,
    )

    source = _multi()
    approved_layout, requests = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = approved_layout

    def independent_core(si, bi):
        return ResolvedManufacturingGeometry(parts=(
            ResolvedManufacturingPart(
                "head", _flat("head", width=80 + bi),
            ),
            ResolvedManufacturingPart(
                "box_body", _certified_body(
                    approved_layout, si, bi, thickness_mm=source["t"],
                ),
            ),
        ))

    out = tmp_path / "group"
    files = manufacturing_api.export_grouped_receiving_multibay_dxf(
        source, physical_bay_geometry_provider=independent_core,
        flags={"head": True, "box_body": True},
        output_dir=out, group_mode=mode,
        pre_commit_guard=lambda: None, nfb_pair_requests=requests,
    )
    assert tuple(files) == filenames
    assert len(tuple(out.glob("*.dxf"))) == len(filenames)
    doc = ezdxf.readfile(next(out.glob("*.dxf")))
    assert not doc.audit().errors
    check = [e.plain_text() for e in doc.modelspace()
             if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"]
    assert check.count("head") == 2
    assert all(check.count(role) == 2 for role in (
        "box_body:box_body_left_side", "box_body:box_body_back", "box_body:box_body_right_side",
    ))
    assert sum(key.startswith("inner_door:") for key in check) == 2
    assert check.count("base_plate") == 2
    assert "nfb_pad" not in check
    assert not list(out.rglob("NFB_PART_ONLY/*.dxf"))


def test_nfb_composition_does_not_enable_non_core_selected_manufacturing(tmp_path):
    """NFB pair proof does not authorize PAD/EAR or Base MFG-2 scope."""
    source = _multi()
    approved_layout, requests = _complete_committed_nfb_requests_for_core(source)
    source["receiving_layout"] = approved_layout
    provider, _calls = _provider(source)
    with pytest.raises(
        ValueError, match="RECEIVING_COMPOSED_NFB_INDEPENDENT_CORE_SCOPE_REQUIRED",
    ):
        manufacturing_api.export_grouped_receiving_multibay_dxf(
            source, physical_bay_geometry_provider=provider,
            flags={"head": True, "base_plate": True},
            output_dir=tmp_path / "out", group_mode="ALL",
            pre_commit_guard=lambda: None, nfb_pair_requests=requests,
        )
    assert not tuple((tmp_path / "out").glob("*.dxf"))
