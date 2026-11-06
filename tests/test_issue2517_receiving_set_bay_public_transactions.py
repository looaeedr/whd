"""#2517 Receiving GUI Set/Bay mutations require the public Engine seam."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, receiving_layout_stable_ids,
)


def test_engine_owns_stable_id_sequence_and_set_append():
    raw = new_receiving_layout(width=800, height=1600, depth=350)
    assert api.receiving_layout_stable_ids(raw) == receiving_layout_stable_ids(raw)
    adapter = ReceivingSetBayAdapter(raw)
    assert adapter.select_set(2)
    assert adapter.layout == api.append_receiving_set(raw)
    assert len(api.receiving_layout_stable_ids(adapter.layout)) == 4


def test_shared_setting_adapter_matches_same_public_api_and_rejects_bad_brand():
    raw = new_receiving_layout(width=800, height=1600, depth=350)
    expected = api.edit_receiving_shared_setting(
        raw, set_index=0, bay_index=0, kind="inner_door_layers", value=2,
    )
    adapter = ReceivingSetBayAdapter(raw)
    adapter.update_setting("inner_door_layers", 2)
    assert adapter.layout == expected
    assert raw != expected
    with pytest.raises(ValueError, match="不支援的開關品牌"):
        api.require_receiving_operator_brand("unknown")


def test_gui_only_calls_public_api_and_nfb_transactions_remain_engine_owned():
    source = (
        Path(__file__).resolve().parents[1] /
        "gui_modules/application/receiving_set_bay_adapter.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "from ae_engine.receiving_layout import",
        "from ae_engine.receiving_shared_settings import",
        "from ae_engine.receiving_nfb_transactions import",
        "from ae_engine.receiving_switch_layout import",
        "from ae_engine.receiving_manufacturing_readiness import",
    ):
        assert forbidden not in source
    for name in (
        "submit_receiving_nfb_bays",
        "copy_receiving_submitted_nfb_bay",
        "restore_receiving_nfb_bays_unconfigured",
        "undo_receiving_nfb_transaction",
        "share_receiving_shared_setting",
        "unlink_receiving_shared_setting",
    ):
        assert "manufacturing_api." + name in source
        assert callable(getattr(api, name))


def _multi_bay_shared_setting_layout():
    from ae_engine.receiving_layout import resize_receiving_bays
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )


@pytest.mark.parametrize("bad_targets", (
    (0, 99), (0, True), (0, 1.0), (0, []), (0, {}),
    (0, -1), (0, 0), (), None,
))
def test_atomic_shared_setting_multi_bay_invalid_late_target(bad_targets):
    """No early Bay mutation survives one invalid highlighted destination."""
    raw = _multi_bay_shared_setting_layout()
    from copy import deepcopy

    before = deepcopy(raw)
    with pytest.raises((ValueError, IndexError)):
        api.edit_receiving_shared_setting_for_bays(
            raw, set_index=0, bay_indices=bad_targets,
            kind="inner_door_layers", value=2,
        )
    assert raw == before


@pytest.mark.parametrize("bad_set", (True, 0.0, "0", -1, 1, None))
def test_atomic_shared_setting_multi_bay_rejects_invalid_set(bad_set):
    raw = _multi_bay_shared_setting_layout()
    with pytest.raises((ValueError, IndexError)):
        api.edit_receiving_shared_setting_for_bays(
            raw, set_index=bad_set, bay_indices=(0, 1),
            kind="inner_door_layers", value=2,
        )


@pytest.mark.parametrize("bad_value", (True, 2.0, 3, None, "2", [], {}))
def test_atomic_shared_setting_multi_bay_invalid_value_preserves_original(bad_value):
    from copy import deepcopy

    raw = _multi_bay_shared_setting_layout()
    before = deepcopy(raw)
    with pytest.raises(ValueError):
        api.edit_receiving_shared_setting_for_bays(
            raw, set_index=0, bay_indices=(0, 2),
            kind="inner_door_layers", value=bad_value,
        )
    assert raw == before


def test_atomic_shared_setting_multi_bay_matches_sequential_engine_for_valid_bays():
    from ae_engine.receiving_shared_settings import setting_value

    raw = _multi_bay_shared_setting_layout()
    original = api.normalize_receiving_layout(raw)
    sequential = api.edit_receiving_shared_setting(
        raw, set_index=0, bay_index=0,
        kind="inner_door_layers", value=2,
    )
    sequential = api.edit_receiving_shared_setting(
        sequential, set_index=0, bay_index=2,
        kind="inner_door_layers", value=2,
    )
    atomic = api.edit_receiving_shared_setting_for_bays(
        raw, set_index=0, bay_indices=(0, 2),
        kind="inner_door_layers", value=2,
    )
    assert atomic == sequential
    assert raw == original
    assert [
        setting_value(atomic["sets"][0], i, "inner_door_layers")
        for i in range(3)
    ] == [2, 1, 2]


def test_atomic_shared_setting_multi_bay_preserves_shared_references_and_dirty_ids():
    from ae_engine.receiving_shared_settings import setting_value

    raw = _multi_bay_shared_setting_layout()
    linked = api.share_receiving_shared_setting(
        raw, set_index=0, source_bay_index=0,
        bay_indices=(0, 2), kind="inner_door_layers",
    )
    adapter = ReceivingSetBayAdapter(linked)
    selection_before = adapter.selection
    assert adapter.apply_setting_to_bays(
        "inner_door_layers", 2, (2,),
    )
    result = adapter.layout
    assert [
        setting_value(result["sets"][0], i, "inner_door_layers")
        for i in range(3)
    ] == [2, 1, 2]
    assert adapter.selection == selection_before
    linked_ids = {
        result["sets"][0]["bays"][i]["stable_id"] for i in (0, 2)
    }
    assert adapter._session_dirty_ids == linked_ids
    assert linked["sets"][0]["settings"] != result["sets"][0]["settings"]


def test_real_gui_settings_port_is_atomic_when_late_bay_highlight_is_invalid():
    """Regression for old GUI select_bay/update_setting per-Bay loop."""
    from copy import deepcopy
    from types import SimpleNamespace

    from gui_modules.application.fold_designer_composition_receiving import (
        receiving_settings_ports,
    )

    adapter = ReceivingSetBayAdapter(_multi_bay_shared_setting_layout())
    saved = deepcopy(adapter.layout)
    events = []

    class FakeComposition:
        def __init__(self):
            self.app = SimpleNamespace(
                _phase6_input_snapshot={},
                submit_update_intent=lambda *args, **kwargs: events.append("commit"),
            )

        def receiving_adapter(self, namespace):
            return adapter

        def sync_receiving_current_bay(self, namespace):
            events.append("sync")

    ports = receiving_settings_ports(FakeComposition(), None, 0)
    original_selection = adapter.selection
    with pytest.raises(IndexError):
        ports["change"]("inner_door_layers", 2, (0, 99))
    assert adapter.layout == saved
    assert adapter.selection == original_selection
    assert adapter._session_dirty_ids == set()
    assert not events

    assert ports["change"]("inner_door_layers", 2, (0, 2)) is True
    assert adapter.selection == original_selection
    assert events == ["sync", "commit"]
    assert adapter.layout["sets"][0]["settings"]["inner_door_layers"]


def test_gui_multi_bay_setting_port_no_longer_loops_over_engine_edit():
    from inspect import getsource
    from gui_modules.application.fold_designer_composition_receiving import (
        receiving_settings_ports,
    )
    from gui_modules.application.receiving_set_bay_adapter import (
        ReceivingSetBayAdapter,
    )

    gui = getsource(receiving_settings_ports)
    adapter = getsource(ReceivingSetBayAdapter.apply_setting_to_bays)
    assert "adapter.apply_setting_to_bays(kind, value, targets)" in gui
    assert "adapter.update_setting(kind, value)" not in gui
    assert "manufacturing_api.edit_receiving_shared_setting_for_bays_with_affected_ids(" in adapter
    assert "affected_refs" not in adapter
    assert '["settings"][kind]["refs"]' not in adapter


def test_shared_setting_affected_ids_use_canonical_refs_not_value_equality():
    """Noncontiguous linked Bays are affected; same-valued unlinked Bay is not."""
    from copy import deepcopy
    import ae_engine

    raw = _multi_bay_shared_setting_layout()
    linked = api.share_receiving_shared_setting(
        raw, set_index=0, source_bay_index=0,
        bay_indices=(0, 2), kind="inner_door_layers",
    )
    before = deepcopy(linked)
    updated, affected = api.edit_receiving_shared_setting_for_bays_with_affected_ids(
        linked, set_index=0, bay_indices=(i for i in (2,)),
        kind="inner_door_layers", value=2,
    )
    assert linked == before
    assert updated == api.edit_receiving_shared_setting_for_bays(
        linked, set_index=0, bay_indices=(2,),
        kind="inner_door_layers", value=2,
    )
    assert affected == tuple(updated["sets"][0]["bays"][i]["stable_id"] for i in (0, 2))
    assert ae_engine.edit_receiving_shared_setting_for_bays_with_affected_ids is (
        api.edit_receiving_shared_setting_for_bays_with_affected_ids
    )

    unchanged, unaffected = api.edit_receiving_shared_setting_for_bays_with_affected_ids(
        raw, set_index=0, bay_indices=(0,),
        kind="inner_door_layers", value=1,
    )
    assert unchanged == api.edit_receiving_shared_setting_for_bays(
        raw, set_index=0, bay_indices=(0,),
        kind="inner_door_layers", value=1,
    )
    # Old layouts may gain a canonical settings table even on a same-value Apply.
    assert raw == _multi_bay_shared_setting_layout()
    assert unaffected == (raw["sets"][0]["bays"][0]["stable_id"],)


@pytest.mark.parametrize("bad_targets", ((0, 99), (0, True), (0, 0), (), None))
def test_shared_setting_affected_ids_fail_closed_atomically(bad_targets):
    from copy import deepcopy

    raw = _multi_bay_shared_setting_layout()
    before = deepcopy(raw)
    adapter = ReceivingSetBayAdapter(raw)
    with pytest.raises((IndexError, ValueError)):
        api.edit_receiving_shared_setting_for_bays_with_affected_ids(
            raw, set_index=0, bay_indices=bad_targets,
            kind="inner_door_layers", value=2,
        )
    with pytest.raises((IndexError, ValueError)):
        adapter.apply_setting_to_bays("inner_door_layers", 2, bad_targets)
    assert raw == before
    assert adapter.layout == before
    assert adapter._session_dirty_ids == set()


def test_single_bay_setting_edit_marks_every_linked_physical_bay_dirty():
    """One door/head editor value edit changes all siblings sharing its ref."""
    from copy import deepcopy
    import ae_engine

    raw = _multi_bay_shared_setting_layout()
    linked = api.share_receiving_shared_setting(
        raw, set_index=0, source_bay_index=0,
        bay_indices=(0, 2), kind="inner_door_layers",
    )
    before = deepcopy(linked)
    expected, affected = api.edit_receiving_shared_setting_for_bays_with_affected_ids(
        linked, set_index=0, bay_indices=(2,), kind="inner_door_layers", value=2,
    )
    adapter = ReceivingSetBayAdapter(linked)
    adapter.select_bay(3)
    selection_before = adapter.selection
    adapter.update_setting("inner_door_layers", 2)
    assert adapter.selection == selection_before
    assert adapter.layout == expected
    assert adapter._session_dirty_ids == set(affected)
    assert affected == tuple(expected["sets"][0]["bays"][i]["stable_id"] for i in (0, 2))
    assert linked == before
    assert ae_engine.edit_receiving_shared_setting_for_bays_with_affected_ids is (
        api.edit_receiving_shared_setting_for_bays_with_affected_ids
    )


def test_share_setting_uses_engine_affected_ids_for_all_selected_targets():
    """Linking nonadjacent Bays changes the target ref even with equal values."""
    from copy import deepcopy
    import ae_engine

    raw = _multi_bay_shared_setting_layout()
    before = deepcopy(raw)
    expected, affected = api.share_receiving_shared_setting_with_affected_ids(
        raw, set_index=0, source_bay_index=0,
        bay_indices=(i for i in (2, 0)), kind="head_features",
    )
    assert expected == api.share_receiving_shared_setting(
        raw, set_index=0, source_bay_index=0,
        bay_indices=(2, 0), kind="head_features",
    )
    assert affected == tuple(expected["sets"][0]["bays"][i]["stable_id"] for i in (0, 2))
    assert raw == before
    assert ae_engine.share_receiving_shared_setting_with_affected_ids is (
        api.share_receiving_shared_setting_with_affected_ids
    )
    adapter = ReceivingSetBayAdapter(raw)
    selection_before = adapter.selection
    adapter.share_setting("head_features", (2, 0))
    assert adapter.layout == expected
    assert adapter.selection == selection_before
    assert adapter._session_dirty_ids == set(affected)


@pytest.mark.parametrize("bad_targets", ((0, 99), (0, True), (0, []), (0,), (), None))
def test_share_setting_invalid_targets_leave_layout_and_dirty_bookkeeping_untouched(bad_targets):
    from copy import deepcopy

    raw = _multi_bay_shared_setting_layout()
    before = deepcopy(raw)
    adapter = ReceivingSetBayAdapter(raw)
    with pytest.raises((ValueError, IndexError)):
        api.share_receiving_shared_setting_with_affected_ids(
            raw, set_index=0, source_bay_index=0,
            bay_indices=bad_targets, kind="inner_door_layers",
        )
    with pytest.raises((ValueError, IndexError)):
        adapter.share_setting("inner_door_layers", bad_targets)
    assert adapter.layout == before == raw
    assert adapter._session_dirty_ids == set()


def test_gui_single_and_share_setting_entrypoints_use_only_engine_affected_ids():
    from inspect import getsource

    single = getsource(ReceivingSetBayAdapter.update_setting)
    linked = getsource(ReceivingSetBayAdapter.share_setting)
    assert "edit_receiving_shared_setting_for_bays_with_affected_ids(" in single
    assert "share_receiving_shared_setting_with_affected_ids(" in linked
    for method in (single, linked):
        assert "self._session_dirty_ids.update(affected_ids)" in method
        assert "self.mark_current_bay_dirty()" not in method
        assert '["settings"]' not in method


def test_atomic_endcap_hole_editor_share_then_invalid_value_cannot_leave_partial_links():
    """A real GUI Hole Editor sync failure cannot mutate Set/Bay adapter state."""
    from copy import deepcopy
    from types import SimpleNamespace
    from inspect import getsource
    import ae_engine
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from gui_modules.application.fold_designer_composition_receiving import (
        receiving_settings_ports,
    )

    raw = _multi_bay_shared_setting_layout()
    linked = api.share_receiving_shared_setting(
        raw, set_index=0, bay_indices=(0, 1),
        source_bay_index=0, kind="tail_features",
    )
    before = deepcopy(linked)
    adapter = ReceivingSetBayAdapter(linked)
    events = []
    editor = {}
    candidate_features = []

    class FakeHost:
        def query(self, *args, **kwargs):
            return None

        def _open_unified_hole_editor(self, *args, **kwargs):
            editor.update(kwargs)

    class FakeComposition:
        def __init__(self, host):
            self.app = SimpleNamespace(
                _phase6_input_snapshot={"receiving_layout": deepcopy(linked)},
                _scene_query_callback=host.query,
                submit_update_intent=lambda *args, **kwargs: events.append("commit"),
            )

        def receiving_adapter(self, namespace):
            return adapter

        def sync_receiving_current_bay(self, namespace):
            events.append("sync")

    monkeypatch_source = SimpleNamespace(
        features=candidate_features, surface=None, width=800, depth=350,
        reference_guide=None,
    )
    # Explicit GUI caller seam, with a verified Engine-context response stub;
    # all link/update/validation operations remain the real public Engine APIs.
    original_project = api.project_receiving_endcap_hole_editor_context
    api.project_receiving_endcap_hole_editor_context = (
        lambda *args, **kwargs: monkeypatch_source
    )
    try:
        composition = FakeComposition(FakeHost())
        ports = receiving_settings_ports(composition, None, 0)
        ports["select"](2)  # original operator selection is Bay3
        selected = adapter.selection
        ports["holes"]("tail", (0, 2))
        assert "sync_callback" in editor

        candidate_features.append("invalid saved feature")
        with pytest.raises(ValueError, match="封頭尾設定"):
            editor["sync_callback"]()
        assert adapter.layout == before
        assert adapter.selection == selected
        assert adapter._session_dirty_ids == set()
        assert not events
        assert composition.app._phase6_input_snapshot["receiving_layout"] == before

        candidate_features[:] = [
            CircleFeature(
                anchor=FeatureAnchor.PANEL_CENTER,
                offset=Vec2(0, 0), diameter=8,
            )
        ]
        editor["sync_callback"]()
        result = adapter.layout
        assert adapter.selection == selected
        assert events == ["sync", "commit"]
        assert result == composition.app._phase6_input_snapshot["receiving_layout"]
        row = result["sets"][0]
        refs = row["settings"]["tail_features"]["refs"]
        assert len(set(refs.values())) == 1
        assert adapter._session_dirty_ids == {
            bay["stable_id"] for bay in row["bays"]
        }
        assert all(
            api.project_receiving_shared_setting_group(row, index, "tail_features")[0]
            == candidate_features
            for index in range(3)
        )
        assert linked == before
    finally:
        api.project_receiving_endcap_hole_editor_context = original_project

    assert ae_engine.share_and_edit_receiving_shared_setting_with_affected_ids is (
        api.share_and_edit_receiving_shared_setting_with_affected_ids
    )
    caller = getsource(receiving_settings_ports)
    callback = caller.split("        def save_features():", 1)[1].split(
        "        host._open_unified_hole_editor(", 1
    )[0]
    assert "adapter.share_and_update_setting(kind, features, targets)" in callback
    assert "adapter.share_setting(kind, targets)" not in callback
    assert "adapter.select_bay(targets[0] + 1)" not in callback


@pytest.mark.parametrize("invalid", ("invalid", object(), 5))
def test_atomic_endcap_multi_bay_engine_rejects_bad_feature_without_share(invalid):
    from copy import deepcopy
    import ae_engine

    raw = _multi_bay_shared_setting_layout()
    before = deepcopy(raw)
    adapter = ReceivingSetBayAdapter(raw)
    with pytest.raises(ValueError):
        api.share_and_edit_receiving_shared_setting_with_affected_ids(
            raw, set_index=0, bay_indices=(0, 2),
            source_bay_index=0, kind="tail_features", value=[invalid],
        )
    with pytest.raises(ValueError):
        adapter.share_and_update_setting("tail_features", [invalid], (0, 2))
    assert adapter.layout == before == raw
    assert adapter._session_dirty_ids == set()


def test_atomic_endcap_engine_invalid_late_target_and_generator_inputs():
    from copy import deepcopy

    raw = _multi_bay_shared_setting_layout()
    before = deepcopy(raw)
    with pytest.raises(IndexError):
        api.share_and_edit_receiving_shared_setting_with_affected_ids(
            raw, set_index=0, bay_indices=(0, 99),
            source_bay_index=0, kind="head_features", value=[],
        )
    assert raw == before
    candidate, affected_ids = api.share_and_edit_receiving_shared_setting_with_affected_ids(
        raw, set_index=0, bay_indices=(i for i in (2, 0)),
        source_bay_index=2, kind="head_features", value=[],
    )
    assert candidate == api.edit_receiving_shared_setting(
        api.share_receiving_shared_setting(
            raw, set_index=0, bay_indices=(2, 0),
            source_bay_index=2, kind="head_features",
        ), set_index=0, bay_index=2, kind="head_features", value=[],
    )
    assert affected_ids == tuple(candidate["sets"][0]["bays"][i]["stable_id"] for i in (0, 2))
