"""Receiving Single W/H/D quantity and highlighted multi-size Bay allocation."""
from types import SimpleNamespace
import tkinter as tk

import pytest

from ae_engine.receiving_layout import new_receiving_layout, normalize_receiving_layout
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application.receiving_multi_settings_window import (
    dimension_group_summary, open_multi_settings,
)


def adapter_with_bays(count=5):
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    adapter.set_bay_count(count)
    return adapter


def test_highlighted_arbitrary_dimension_groups_round_trip_and_rejection():
    adapter = adapter_with_bays()
    assert dimension_group_summary(adapter.layout["sets"][0]["bays"]) == (
        ((800.0, 1600.0, 350.0), (0, 1, 2, 3, 4)),
    )
    adapter.apply_dimensions_to_bays(
        0, (1, 4), width=750, height=1600, depth=350, expected_count=2,
    )
    groups = dimension_group_summary(adapter.layout["sets"][0]["bays"])
    assert groups == (
        ((800.0, 1600.0, 350.0), (0, 2, 3)),
        ((750.0, 1600.0, 350.0), (1, 4)),
    )
    adapter.apply_dimensions_to_bays(
        0, (2,), width=700, height=1700, depth=400, expected_count=1,
    )
    groups = dimension_group_summary(adapter.layout["sets"][0]["bays"])
    assert len(groups) == 3
    assert sorted(len(indices) for _, indices in groups) == [1, 2, 2]
    before = adapter.layout
    with pytest.raises(ValueError, match="高亮"):
        adapter.apply_dimensions_to_bays(
            0, (1, 3), width=990, height=1600, depth=350, expected_count=3,
        )
    assert adapter.layout == before
    assert normalize_receiving_layout(adapter.layout) == before


def test_new_bay_dimensions_read_live_receiving_family_defaults(monkeypatch):
    from ae_engine.cabinet_types import receiving
    adapter = adapter_with_bays(1)
    adapter.apply_dimensions_to_bays(
        0, (0,), width=750, height=1600, depth=350, expected_count=1,
    )
    monkeypatch.setitem(receiving.BOX_BODY_DEFAULTS, "w", 910.0)
    adapter.set_bay_count(3)
    widths = [bay["width"] for bay in adapter.layout["sets"][0]["bays"]]
    assert widths == [750.0, 910.0, 910.0]


def test_single_dialog_has_no_set_bay_controls_and_updates_common_quantity():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    mode = {"value": "set_bay"}
    values = {"width": 800, "height": 1600, "depth": 350,
              "count": 1, "total_count": 1, "version_count": 1}
    writes = []

    def switch(target):
        mode["value"] = target
        return True

    def update(w, h, d, count):
        writes.append((w, h, d, count))
        values.update(width=w, height=h, depth=d, count=count, total_count=count)
        return True

    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": mode["value"]},
            get_switch=lambda: None, switch_mode=switch,
            resize_connections=lambda *_: False,
            get_single_size_quantity=lambda: dict(values),
            set_single_size_quantity=update, dialog_kind="single",
        )
        root.update()
        assert mode["value"] == "quantity"
        assert win.title() == "單只設定"
        assert not any(button.winfo_ismapped() for button in win._receiving_multi_set_buttons)
        assert not win._receiving_multi_rows_host.winfo_children()
        assert tuple(win._receiving_multi_setting_list.get(0, tk.END)) == ("封頭尾", "內門")
        inputs = win._receiving_dimension_group_input
        inputs["width"].set("875")
        inputs["count"].set("3")
        for button in win._receiving_dimension_groups_host.winfo_children()[0].winfo_children():
            if getattr(button, "cget", None):
                try:
                    if button.cget("text") == "確定":
                        button.invoke()
                except tk.TclError:
                    pass
        # Nested Entry row is the first child within single size frame.
        if not writes:
            body = win._receiving_dimension_groups_host.winfo_children()[0]
            row = body.winfo_children()[0]
            next(widget for widget in row.winfo_children()
                 if widget.winfo_class() == "TButton").invoke()
        assert writes == [(875, 1600, 350, 3)]
        assert values["total_count"] == 3
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_multi_dialog_uses_sketch_highlight_for_second_and_third_size():
    root = tk.Tk()
    root.geometry("900x700+0+0")
    root.update()
    adapter = adapter_with_bays(5)
    applied = []

    def assign(si, indices, w, h, d, count):
        applied.append((si, tuple(indices), w, h, d, count))
        return adapter.apply_dimensions_to_bays(
            si, indices, width=w, height=h, depth=d, expected_count=count,
        )

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(
                connection_counts=lambda: (5,), layout=adapter.layout,
            ),
            switch_mode=lambda *_: True,
            resize_connections=lambda *_: False,
            get_dimension_group=assign,
        )
        root.update()
        win._receiving_multi_apply(0)
        root.update()
        assert len(dimension_group_summary(adapter.layout["sets"][0]["bays"])) == 1
        canvas = win._receiving_multi_canvas
        boxes = canvas._receiving_bay_hitboxes

        def click(index):
            x0, y0, x1, y1 = boxes[index]
            canvas.event_generate(
                "<Button-1>", x=int((x0 + x1) / 2), y=int((y0 + y1) / 2),
            )
            root.update()

        click(0)  # clear initial selection
        click(1)
        click(4)
        inputs = win._receiving_dimension_group_input
        inputs["width"].set("750")
        inputs["count"].set("2")
        win._receiving_dimension_group_confirm()
        assert applied[-1] == (0, (1, 4), 750, 1600, 350, 2)
        assert sorted(len(indices) for _, indices in
                      dimension_group_summary(adapter.layout["sets"][0]["bays"])) == [2, 3]
        click(1)
        click(4)
        click(2)
        inputs["width"].set("700")
        inputs["count"].set("1")
        win._receiving_dimension_group_confirm()
        assert applied[-1] == (0, (2,), 700, 1600, 350, 1)
        assert len(dimension_group_summary(adapter.layout["sets"][0]["bays"])) == 3
        win._receiving_multi_close()
    finally:
        root.destroy()


def test_receiving_heights_are_independent_and_persist_with_candidate_version():
    from ae_engine.receiving_inner_door_candidates import (
        create_inner_candidate, inner_config, normalize_inner_candidates,
    )
    from ae_engine.receiving_shared_settings import setting_value, validate_setting

    assert validate_setting("inner_door_layer_heights_mm", [330, 830]) == [330., 830.]
    for bad in ([830, 330], [330, 330], [330, -1], [330], [330, float("nan")]):
        with pytest.raises(ValueError):
            validate_setting("inner_door_layer_heights_mm", bad)
    library, version = create_inner_candidate(None, {
        "layers": 2, "models": ["", ""], "layer_heights_mm": [330, 830],
    })
    assert inner_config(normalize_inner_candidates(library), version)["layer_heights_mm"] == [330., 830.]
    adapter = adapter_with_bays(3)
    adapter.apply_inner_door_candidate_to_bays(
        inner_config(library, version), 0, (0, 2), version_id=version,
    )
    owner = adapter.layout["sets"][0]
    assert setting_value(owner, 0, "inner_door_layer_heights_mm") == [330., 830.]
    assert setting_value(owner, 1, "inner_door_version_id") is None
    assert setting_value(owner, 2, "inner_door_version_id") == version
    assert setting_value(owner, 2, "inner_door_layer_heights_mm") == [330., 830.]


def test_nfb_preview_uses_operator_heights_instead_of_hardcoded_old_y():
    from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft, nfb_ui1a_preview

    draft = new_nfb_ui1a_draft(set_brand="士林", layer_count=2)
    preview = nfb_ui1a_preview(
        draft, bay_width_mm=800, upper_cell_height_mm=1100,
        layer_heights_mm=[330, 830],
    )
    assert [row["nominal_y_from_top_mm"] for row in preview["layers"]] == [330., 830.]
    assert preview["can_manufacture"] is False
    with pytest.raises(ValueError):
        nfb_ui1a_preview(
            draft, bay_width_mm=800, upper_cell_height_mm=800,
            layer_heights_mm=[330, 830],
        )


def test_new_height_fields_live_in_receiving_editor_without_extra_store():
    import inspect
    import gui_modules.application.fold_designer_composition_receiving as bridge

    source = inspect.getsource(bridge.open_receiving_multi_settings)
    assert 'text=f"第 {idx+1} 層高度（距作業區上緣 mm）"' in source
    assert '"layer_heights_mm": read_layer_heights()' in source
    assert "if direct_to_drawing:" in source
    assert "persist_inner(saved)" in source
    assert 'adapter.update_setting(kind, value)' in source
    assert "if bay.get(\"nfb_config_submitted\") is True:" in source


def test_old_nfb_setting_absence_preserves_previous_y_until_explicit_change():
    from ae_engine.receiving_shared_settings import normalize_set_settings, setting_value
    from ae_engine.receiving_nfb_y_projection import approved_nominal_y_mm

    fresh = new_receiving_layout(width=800, height=1600, depth=350)
    assert setting_value(fresh["sets"][0], 0, "inner_door_layer_heights_mm") == [330., 830.]

    legacy = new_receiving_layout(width=800, height=1600, depth=350)
    row = legacy["sets"][0]
    row["settings"] = normalize_set_settings(None, row["bays"])
    del row["settings"]["inner_door_layer_heights_mm"]
    migrated = normalize_receiving_layout(legacy)
    assert setting_value(migrated["sets"][0], 0, "inner_door_layer_heights_mm") is None
    assert approved_nominal_y_mm(2) == (290.0, 790.0)
    # Applying an old two-key candidate must NOT secretly move old NFB holes.
    adapter = ReceivingSetBayAdapter(migrated)
    adapter.apply_inner_door_candidate_to_bays(
        {"layers": 2, "models": ["", ""]}, 0, (0,),
    )
    assert setting_value(
        adapter.layout["sets"][0], 0, "inner_door_layer_heights_mm"
    ) is None
