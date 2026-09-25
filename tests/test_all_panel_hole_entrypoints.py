from pathlib import Path
import inspect

from gui_modules.parts.panels import common


ROOT = Path(__file__).resolve().parents[1]


def test_every_primary_panel_uses_current_double_click_hole_entrypoint_owner():
    attach = inspect.getsource(common._attach_part_hole_entrypoint)
    assert 'Double-Button-1' in attach
    assert 'open_part_hole_editor' in attach
    assert 'canvas.unbind("<Button-3>")' in attach

    routed = {
        "door": ROOT / "gui_modules" / "parts" / "panels" / "door.py",
        "base_plate": ROOT / "gui_modules" / "parts" / "panels" / "base_plate.py",
        "indicator_box": ROOT / "gui_modules" / "parts" / "panels" / "indicator_box.py",
    }
    for key, path in routed.items():
        source = path.read_text(encoding="utf-8")
        assert "_attach_part_hole_entrypoint" in source
        assert f'"{key}"' in source

    indicator_source = routed["indicator_box"].read_text(encoding="utf-8")
    assert '"indicator_door"' in indicator_source

    # Box-body double-click resolves the selected physical piece before opening
    # its editor, so its current owner intentionally uses the piece-aware route.
    box_body = (ROOT / "gui_modules" / "parts" / "panels" / "box_body.py").read_text(encoding="utf-8")
    assert 'bind("<Double-Button-1>", self.on_box_body_piece_double_click)' in box_body

    # Endcaps retain their explicit head/tail key route in their panel owner.
    endcap = (ROOT / "gui_modules" / "parts" / "panels" / "endcap.py").read_text(encoding="utf-8")
    assert 'bind("<Double-Button-1>"' in endcap
    assert "open_hole_editor" in endcap
    assert "Button-3" not in endcap
