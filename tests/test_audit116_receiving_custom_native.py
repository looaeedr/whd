"""Windows native Tk contract for Receiving Bay W/H/D source through fold edits."""
import os
import time
import pytest

@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="native Tk required")
def test_live_receiving_bay_whd_survives_thickness_editor_and_custom_switch():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    def pump(n=9):
        for _ in range(n):
            root.update()
            time.sleep(0.11)
    try:
        app.baseline_var.set("受電箱")
        pump(4)
        designer = app.open_original_fold_designer()
        pump(10)
        assert designer._phase6_input_snapshot["model"] == "受電箱"
        for axis, value in (("w", 820), ("h", 1700), ("d", 360)):
            getattr(designer, "v_" + axis).set(str(value))
            pump()
        bay = designer._phase6_input_snapshot["receiving_layout"]["sets"][0]["bays"][0]
        assert (bay["width"], bay["height"], bay["depth"]) == pytest.approx((820, 1700, 360))
        assert tuple(designer._phase6_input_snapshot[k] for k in ("w","h","d")) == pytest.approx((820, 1700, 360))
        designer.left_global_vars["t"].set("2.5")
        pump()
        assert tuple(designer._phase6_input_snapshot[k] for k in ("w","h","d")) == pytest.approx((820, 1700, 360))
        assert tuple(float(getattr(designer, "v_" + k).get()) for k in ("w","h","d")) == pytest.approx((820, 1700, 360))
        assert designer._phase6_input_snapshot["t"] == pytest.approx(2.5)
        bay = designer._phase6_input_snapshot["receiving_layout"]["sets"][0]["bays"][0]
        assert (bay["width"], bay["height"], bay["depth"]) == pytest.approx((820, 1700, 360))
        designer.baseline_model_var.set("自訂")
        pump()
        assert tuple(designer._phase6_input_snapshot[k] for k in ("w","h","d","t")) == pytest.approx((820, 1700, 360, 2.5))
        assert tuple(float(getattr(designer, "v_" + k).get()) for k in ("w","h","d")) == pytest.approx((820, 1700, 360))
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except tk.TclError:
            pass
        root.destroy()
