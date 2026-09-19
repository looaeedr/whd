# -*- coding: utf-8 -*-
import os

import pytest

from phase6_settings_transaction_controller import Phase6SettingsTransactionController


def test_restore_setting_clears_service_owned_pending_entry():
    pending = {"w": 80.0, "h": 700.0}
    controller = Phase6SettingsTransactionController(
        settings_values={"w": 80.0, "h": 700.0},
        input_snapshot={"w": 80.0, "h": 700.0},
        box_whd={"w": 1300.0, "h": 700.0},
        pending_settings=pending,
    )

    controller.restore_setting("w", 1300.0)

    assert controller.pending == {"h": 700.0}


def test_assembly_intent_keeps_available_parts_projection_only():
    from phase6_settings_transitions import assembly_intent

    source = {
        "model": "金庫型",
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
    }
    plan = assembly_intent(
        source,
        {},
        {},
        "INSERT_OVERLAY",
        available_parts=(
            "box_body",
            "head",
            "tail",
            "door_c1_r1",
            "door_c1_r2",
            "base_plate_c1_r1",
            "base_plate_c1_r2",
        ),
    )

    assert plan.input_snapshot["existing_parts"] == source["existing_parts"]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_real_designer_composition_keeps_settings_maps_and_family_transition_live(monkeypatch):
    import tkinter as tk
    import gui
    import traceback
    import fold_designer_bridge as bridge
    from gui_modules.application.fold_designer_adapter import Phase6FoldDesignerComposition

    events = []
    target_names = {
        "_settings_values",
        "_phase6_input_snapshot",
        "_phase6_box_whd",
        "_phase6_pending_settings",
    }
    original_setattr = bridge.Phase6FoldDesignerApp.__setattr__
    service_created = [False]
    def traced_setattr(owner, name, value):
        if name in target_names:
            stack = ()
            if service_created[0]:
                stack = tuple(
                    (frame.name, frame.lineno)
                    for frame in traceback.extract_stack(limit=10)[:-1]
                )
            events.append(("assign", id(owner), name, id(value), type(value).__name__, stack))
        return original_setattr(owner, name, value)
    monkeypatch.setattr(
        bridge.Phase6FoldDesignerApp, "__setattr__", traced_setattr, raising=False
    )

    original_settings_service = Phase6FoldDesignerComposition.settings_service
    def traced_settings_service(composition):
        before = composition._settings_service
        result = original_settings_service(composition)
        if before is None:
            service_created[0] = True
            owner = composition.app
            events.append((
                "service-create",
                id(owner),
                id(getattr(owner, "_settings_values", None)),
                id(getattr(owner, "_phase6_input_snapshot", None)),
                id(getattr(owner, "_phase6_box_whd", None)),
                id(getattr(owner, "_phase6_pending_settings", None)),
                id(result._settings_values),
                id(result._input_snapshot),
                id(result._box_whd),
                id(result._pending),
            ))
        return result
    monkeypatch.setattr(
        Phase6FoldDesignerComposition,
        "settings_service",
        traced_settings_service,
    )

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        root.update_idletasks()
        root.update()

        service = bridge._phase6_settings_service(designer)
        transactions = bridge._phase6_settings_transactions(designer)

        for event in events:
            print("LIFETIME_EVENT", repr(event))
        print(
            "LIFETIME_FINAL",
            id(designer),
            id(service._input_snapshot),
            id(designer._phase6_input_snapshot),
        )
        assert service._input_snapshot is designer._phase6_input_snapshot, events
        assert transactions._input_snapshot is designer._phase6_input_snapshot
        assert service._settings_values is designer._settings_values
        assert transactions._settings_values is designer._settings_values
        assert service._box_whd is designer._phase6_box_whd
        assert transactions._box_whd is designer._phase6_box_whd

        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()

        assert designer._phase6_input_snapshot["model"] == "受電箱"
        assert transactions._input_snapshot["model"] == "受電箱"
        assert str(designer._phase6_input_snapshot["assembly_type"]) == "WRAP_OVERLAY"
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
