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


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_real_designer_composition_keeps_settings_maps_and_family_transition_live():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

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

        assert service._input_snapshot is designer._phase6_input_snapshot
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
