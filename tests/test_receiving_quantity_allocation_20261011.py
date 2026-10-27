"""Two-stage Receiving candidate quantities: draft-only, then atomic 2D apply."""
from __future__ import annotations
from copy import deepcopy
import pytest

from ae_engine.receiving_hole_candidates import create_candidate
from ae_engine.receiving_quantity_allocation import (
    AllocationDraft, validate_quantity_allocation,
)
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


def _fixture():
    library, v1 = create_candidate(None, "head", [{"shape": "A"}])
    library, v2 = create_candidate(library, "head", [{"shape": "B"}])
    library, tail = create_candidate(library, "tail", [{"shape": "T"}])
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    adapter.set_bay_count(3)
    adapter.set_set_count(2)
    adapter.select_set(2)
    adapter.set_bay_count(2)
    adapter.select_set(1)
    return adapter, library, v1, v2, tail


def test_assignments_are_draft_until_confirm_and_do_not_follow_highlights():
    adapter, library, v1, v2, _ = _fixture()
    draft = AllocationDraft((3, 2))
    draft.add_version("head", v1)
    draft.set_quantity("head", v1, 2)
    draft.add_version("head", v2)
    draft.set_quantity("head", v2, 3)
    assert draft.ready_for_positioning("head")
    draft.active_version["head"] = v1
    draft.assign("head", 0, 2)
    draft.assign("head", 1, 1)
    draft.active_version["head"] = v2
    for target in ((0, 0), (0, 1), (1, 0)):
        draft.assign("head", *target)
    assert len(draft.assigned["head"]) == 5
    before = adapter.layout
    plan = validate_quantity_allocation(
        before, library, "head",
        draft.quantities["head"], draft.assigned["head"],
        expected_counts=(3, 2),
    )
    assert len(plan) == 5
    assert adapter.layout == before
    selection = adapter.selection
    assert adapter.apply_quantity_configuration(
        "head", library, draft.quantities["head"],
        draft.assigned["head"], expected_counts=(3, 2),
    ) == 5
    sets = adapter.layout["sets"]
    assert [setting_value(sets[0], i, "head_features") for i in range(3)] == [
        [{"shape": "B"}], [{"shape": "B"}], [{"shape": "A"}]
    ]
    assert [setting_value(sets[1], i, "head_features") for i in range(2)] == [
        [{"shape": "B"}], [{"shape": "A"}]
    ]
    assert all(setting_value(row, i, "tail_features") == []
               for row in sets for i in range(len(row["bays"])))
    assert adapter.selection == selection
    assert library["head"]["versions"][0]["features"] == [{"shape": "A"}]


def test_invalid_total_missing_duplicate_stale_id_and_topology_are_atomic():
    adapter, library, v1, v2, _ = _fixture()
    before = adapter.layout
    targets = {(0, 0): v1, (0, 1): v1, (0, 2): v2,
               (1, 0): v2, (1, 1): v2}
    bad_cases = [
        ({v1: 1, v2: 3}, targets, (3, 2)),  # total 4, expected 5
        ({v1: 2, v2: 3}, {k: v for k, v in targets.items() if k != (1, 1)}, (3, 2)),
        ({v1: 2, v2: 3}, {**targets, (2, 0): v1}, (3, 2)),
        ({v1: 2, v2: 3}, {**targets, (1, 1): "head-v999"}, (3, 2)),
        ({v1: 2, v2: 3}, targets, (5,)),  # Set count drift
        ({v1: 3, v2: 2}, targets, (3, 2)),  # actual count drift
        ({v1: 2, v2: 3}, {**targets, (0, 0): "tail-v1"}, (3, 2)),
    ]
    for qty, assignments, expected in bad_cases:
        with pytest.raises(ValueError):
            adapter.apply_quantity_configuration(
                "head", library, qty, assignments, expected_counts=expected
            )
        assert adapter.layout == before
    with pytest.raises(ValueError):
        validate_quantity_allocation(before, library, "head", {}, {}, expected_counts=(3, 2))


def test_independent_head_and_tail_drafts_do_not_overwrite_each_other():
    draft = AllocationDraft((3, 2))
    draft.add_version("head", "head-v1")
    draft.set_quantity("head", "head-v1", 5)
    draft.add_version("tail", "tail-v1")
    draft.set_quantity("tail", "tail-v1", 5)
    draft.active_version["head"] = "head-v1"
    draft.assign("head", 0, 0)
    assert draft.assigned["tail"] == {}
    draft.active_version["tail"] = "tail-v1"
    draft.assign("tail", 1, 1)
    assert draft.assigned["head"] == {(0, 0): "head-v1"}
    draft.reconcile((3, 3), {"head": ["head-v1"], "tail": ["tail-v1"]})
    assert draft.assigned["head"] == {}
    assert draft.assigned["tail"] == {}
    assert draft.step == {"head": 1, "tail": 1}
    assert draft.quantities["head"] == {"head-v1": 5}
    assert draft.quantities["tail"] == {"tail-v1": 5}


def test_quantity_selection_rejects_overfill_and_can_toggle_or_reassign():
    draft = AllocationDraft((2,))
    draft.add_version("head", "head-v1")
    draft.set_quantity("head", "head-v1", 1)
    draft.add_version("head", "head-v2")
    draft.set_quantity("head", "head-v2", 1)
    draft.active_version["head"] = "head-v1"
    draft.assign("head", 0, 0)
    with pytest.raises(ValueError):
        draft.assign("head", 0, 1)
    draft.assign("head", 0, 0)  # toggles off
    draft.assign("head", 0, 1)
    draft.active_version["head"] = "head-v2"
    draft.assign("head", 0, 0)
    assert draft.assigned["head"] == {(0, 1): "head-v1", (0, 0): "head-v2"}
    draft.active_version["head"] = "head-v1"
    with pytest.raises(ValueError):
        draft.assign("head", 0, 0)  # role count full; previous stays unchanged
    assert draft.assigned["head"][(0, 0)] == "head-v2"
    with pytest.raises(ValueError):
        draft.assign("head", 2, 0)


def test_allocation_ui_native_combobox_and_explicit_apply():
    import tkinter as tk
    from tkinter import ttk
    from types import SimpleNamespace
    from gui_modules.application.receiving_multi_settings_window import open_multi_settings

    root = tk.Tk()
    root.withdraw()
    counts = [3, 2]
    committed = []
    versions = {
        "head": [{"id": "head-v1", "features": [{"tag": "A"}]},
                 {"id": "head-v2", "features": [{"tag": "B"}]}],
        "tail": [{"id": "tail-v1", "features": [{"tag": "T"}]}],
    }
    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: tuple(counts)),
            switch_mode=lambda _value: True,
            resize_connections=lambda *_args: False,
            get_candidate_ports=lambda: {
                "versions": lambda role: versions[role],
                "edit": lambda *_args: None,
                "copy": lambda *_args: None,
                "delete": lambda *_args: None,
                "apply": lambda *_args: None,
                "apply_quantity": lambda role, q, assigned, expected:
                    committed.append((role, q, assigned, expected)),
            },
            get_settings_ports=lambda _set: {"select": lambda _bay: None},
        )
        root.update()
        listing = win._receiving_multi_setting_list
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        host = win._receiving_multi_settings_host
        manager = [w for w in host.winfo_children()
                   if isinstance(w, ttk.Button) and w.cget("text") == "版本管理"][0]
        manager.invoke()
        root.update()
        child = win._receiving_multi_manager_window["win"]
        assert child is not None and child.winfo_exists()
        assert child.master is win and child.grab_current() is child
        main_canvas = win._receiving_multi_canvas
        before_hits = main_canvas._receiving_bay_hitboxes
        pages = [
            frame for frame in child.winfo_children()[0].winfo_children()
            if isinstance(frame, ttk.Frame)
            and any(isinstance(w, ttk.Radiobutton) and
                    w.cget("text") == "數量配置" for w in frame.winfo_children())
        ]
        assert len(pages) == 1
        button = [w for w in pages[0].winfo_children()
                  if isinstance(w, ttk.Radiobutton) and w.cget("text") == "數量配置"][0]
        button.invoke()
        root.update()
        ui = child._receiving_quantity_ui
        assert child._receiving_manager_canvas is not main_canvas
        assert ui is not None
        assert ui.role == "head"
        assert ui.draft.counts == (3, 2)
        ui._operation(ui._add)
        root.update()
        combobox = [w for w in ui.host.winfo_children()
                    if isinstance(w, ttk.Frame)
                    for w in w.winfo_children() if isinstance(w, ttk.Combobox)][0]
        assert combobox.cget("state") == "readonly"
        assert tuple(combobox.cget("values")) == ("版本一", "版本二")
        # The first step is independent of existing 2D highlight selections.
        assert ui.draft.assigned["head"] == {}
        ui._operation(lambda: ui.draft.set_quantity("head", "head-v1", 2))
        root.update()
        ui._operation(ui._add)
        root.update()
        ui._operation(lambda: ui.draft.set_quantity("head", "head-v2", 3))
        root.update()
        assert ui.draft.ready_for_positioning("head")
        ui._operation(lambda: ui.draft.step.__setitem__("head", 2))
        root.update()
        assert len(child._receiving_manager_canvas._receiving_allocation_hitboxes) == 5
        assert main_canvas._receiving_bay_hitboxes == before_hits
        assert not hasattr(main_canvas, "_receiving_allocation_hitboxes")
        for version, bays in (
            ("head-v1", ((0, 1), (1, 0))),
            ("head-v2", ((0, 0), (0, 2), (1, 1))),
        ):
            ui._select_version(version)
            for si, bi in bays:
                box = next(b for b in ui._hitboxes if b[:2] == (si, bi))
                _, _, x0, y0, x1, y1 = box
                canvas = child._receiving_manager_canvas
                canvas.event_generate(
                    "<Button-1>",
                    x=int((x0 + x1) / 2), y=int((y0 + y1) / 2 - canvas.canvasy(0)),
                )
                root.update()
        assert not committed  # no automatic save when selecting Bays
        assert ui._ready_to_apply()
        ui._commit()
        root.update()
        assert len(committed) == 1
        role, q, assigned, expected = committed[0]
        assert (role, q, expected) == (
            "head", {"head-v1": 2, "head-v2": 3}, (3, 2)
        )
        assert assigned == {
            (0, 1): "head-v1", (1, 0): "head-v1",
            (0, 0): "head-v2", (0, 2): "head-v2", (1, 1): "head-v2",
        }
        win._receiving_multi_close()
        assert not child.winfo_exists()
    finally:
        root.destroy()


@pytest.mark.parametrize("bad_available", [
    {"head": "v", "tail": ["tail-v1"]},
    {"head": 42, "tail": ["tail-v1"]},
    {"head": ["v"], "tail": None},
    {"head": ["v"], "tail": [True]},
    {"head": ["v"], "tail": [["tail-v1"]]},
    {"head": ["v"]},
])
def test_r5_81_draft_reconcile_rejects_corrupt_candidate_inventory_atomically(bad_available):
    """A bad source must not partly erase a physical Bay's pending selection."""
    draft = AllocationDraft((2,))
    draft.add_version("head", "v")
    draft.set_quantity("head", "v", 2)
    draft.active_version["head"] = "v"
    draft.assign("head", 0, 0)
    before = deepcopy((draft.counts, draft.quantities, draft.assigned,
                       draft.active_version, draft.step))
    with pytest.raises(ValueError, match="候選版本"):
        draft.reconcile((3,), bad_available)
    assert (draft.counts, draft.quantities, draft.assigned,
            draft.active_version, draft.step) == before


def test_r5_81_draft_reconcile_keeps_valid_generator_candidate_ids():
    draft = AllocationDraft((2,))
    draft.add_version("head", "head-v1")
    draft.set_quantity("head", "head-v1", 2)
    draft.active_version["head"] = "head-v1"
    draft.assign("head", 0, 0)
    draft.reconcile((2,), {"head": (x for x in ("head-v1",)),
                           "tail": (x for x in ("tail-v1",))})
    assert draft.assigned["head"] == {(0, 0): "head-v1"}
    assert draft.quantities["head"] == {"head-v1": 2}
