"""#2517 Bay live features, upper Hole Editor panel and cache witness are Engine."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    receiving_bay_assembly_offsets, receiving_bay_joint_face_features,
)


def layout():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=4,
    )


@pytest.mark.parametrize("bay", range(4))
def test_source_owned_feature_sync_publishes_real_panel_and_joint_faces(bay):
    source = {"model": "受電箱", "active_mode": "set_bay", "t": 2, "fw": 29,
              "surface_features": {"head": ["hole:H"], "tail": ["hole:T"]},
              "part_features": {"inner_door:upper:panel": ["hole:upper"]}}
    before = deepcopy(source)
    live = api.project_operator_receiving_live_bay_features(
        source, available_parts=("inner_door:upper:panel", "inner_door:upper:top_frame",
                                 "box_body", "door"),
        layout=layout(), set_index=0, bay_index=bay, existing_box_body_faces={},
    )
    assert isinstance(live, api.OperatorReceivingLiveBayFeaturePlan)
    assert live.surface_updates == (("head", ["hole:H"]), ("tail", ["hole:T"]))
    assert live.inner_panel_updates == (("inner_door:upper:panel", ["hole:upper"]),)
    assert live.box_body_joint_faces == receiving_bay_joint_face_features(
        layout(), set_index=0, bay_index=bay, thickness=2, frame_width=29,
        existing={},
    )
    assert source == before


def test_quantity_mode_does_not_inherit_a_stale_selected_bay_panel():
    source = {"model": "受電箱", "active_mode": "quantity",
              "part_features": {"inner_door:upper:panel": ["stale"]}}
    got = api.project_operator_receiving_live_bay_features(
        source, available_parts=("inner_door:upper:panel",),
        layout=layout(), set_index=0, bay_index=0,
    )
    assert got.inner_panel_updates == ()


def test_unrelated_family_fails_closed():
    with pytest.raises(ValueError, match="RECEIVING_BAY_LIVE_FEATURE_FAMILY_REQUIRED"):
        api.project_operator_receiving_live_bay_features(
            {"model": "金庫型"}, available_parts=(), layout=layout(),
            set_index=0, bay_index=0,
        )


@pytest.mark.parametrize("bay", range(4))
def test_joint_world_source_witness_preserves_nonuniform_bay_history(bay):
    actual = update_receiving_bay(
        layout(), set_index=0, bay_index=1,
        width=930, height=1740, depth=410,
    )
    before = deepcopy(actual)
    witness = api.project_receiving_bay_preview_cache_source_witness(
        actual, set_index=0, bay_index=bay,
    )
    assert isinstance(witness, api.ReceivingBayPreviewCacheSourceWitness)
    assert witness.source_prefix == tuple(
        (float(b["width"]), float(b["height"]), float(b["depth"]))
        for b in actual["sets"][0]["bays"][:bay + 1]
    )
    assert witness.world_anchor == receiving_bay_assembly_offsets(actual)[bay]
    assert actual == before


@pytest.mark.parametrize("invalid", [True, -1, 4, 9])
def test_invalid_bay_rejected_before_cache_reuse(invalid):
    with pytest.raises(IndexError):
        api.project_receiving_bay_preview_cache_source_witness(
            layout(), set_index=0, bay_index=invalid,
        )


def upper_snapshot():
    return {
        "model": "受電箱", "w": 800, "h": 1600, "d": 350, "t": 2,
        "fw": 29, "door_gap_w": 3.5, "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_columns": [[800, [1100, 500]]],
        "inner_doors": [{"stable_id": "upper", "cell_key": "0:0",
                         "included_frame_sides": ["top", "left", "right"]}],
    }


def test_real_upper_inner_panel_is_exact_hole_editor_factory_part():
    snap = upper_snapshot()
    original = deepcopy(snap)
    key = api.resolve_receiving_upper_inner_door_editor_part_key(snap)
    assert key == "inner_door:upper:panel"
    assert api.resolve_inner_door_hole_editor_context(snap, key).panel.stable_id == key
    assert snap == original


def test_no_or_ambiguous_upper_panel_must_fail_closed(monkeypatch):
    with pytest.raises(ValueError, match="上層實體內門"):
        api.resolve_receiving_upper_inner_door_editor_part_key(
            {**upper_snapshot(), "inner_doors": []},
        )
    monkeypatch.setattr(policy, "derive_inner_door_panels", lambda s: (
        SimpleNamespace(stable_id="u1", cell_key="0:0"),
        SimpleNamespace(stable_id="u2", cell_key="1:0"),
    ))
    with pytest.raises(ValueError, match="上層實體內門"):
        api.resolve_receiving_upper_inner_door_editor_part_key(upper_snapshot())


def test_gui_delegates_all_three_physical_sources_and_engine_has_no_reverse_import():
    root = Path(__file__).resolve().parents[1]
    gui = (root / "gui_modules/application/fold_designer_composition_receiving.py"
           ).read_text(encoding="utf-8")
    live = gui.split("def sync_receiving_current_bay(", 1)[1].split(
        "def commit_receiving_current_bay_controls(", 1,
    )[0]
    assert "manufacturing_api.project_operator_receiving_live_bay_features(" in live
    assert "receiving_bay_joint_face_features(" not in live
    assert 'str(key).startswith("inner_door:")' not in live
    upper = gui.split("def current_inner_editor_part_key(", 1)[1].split(
        "def launch_inner_editor(", 1,
    )[0]
    assert "manufacturing_api.resolve_receiving_upper_inner_door_editor_part_key(" in upper
    assert "derive_inner_door_panels(" not in upper
    preview = gui.split("def receiving_bay_preview_request(", 1)[1].split(
        "def receiving_layer_preview_payload(", 1,
    )[0]
    assert "manufacturing_api.project_receiving_bay_preview_cache_source_witness(" in preview
    assert 'float(bay["width"])' not in preview
    for name in ("operator_part_session_profiles.py", "receiving_inner_door_editor.py",
                 "receiving_bay_preview_source.py"):
        engine = (root / "ae_engine" / name).read_text(encoding="utf-8")
        assert "from gui_modules" not in engine and "from phase6_" not in engine
