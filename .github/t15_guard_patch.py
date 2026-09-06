from pathlib import Path

path = Path("tests/test_phase6_t11_integration_matrix.py")
text = path.read_text(encoding="utf-8")
old = '''        frame_keys = {k for k in app.designer_workspace.available_parts if k.startswith("inner_door:")}\n        assert divider_keys == ["box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"]\n        assert frame_keys == {\n            "inner_door:upper:top_frame",\n            "inner_door:upper:left_frame",\n            "inner_door:upper:right_frame",\n        }\n'''
new = '''        frame_keys = {\n            k for k in app.designer_workspace.available_parts\n            if k.startswith("inner_door:") and k.endswith("_frame")\n        }\n        panel_keys = {\n            k for k in app.designer_workspace.available_parts\n            if k.startswith("inner_door:") and k.endswith(":panel")\n        }\n        assert divider_keys == ["box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"]\n        assert frame_keys == {\n            "inner_door:upper:top_frame",\n            "inner_door:upper:left_frame",\n            "inner_door:upper:right_frame",\n        }\n        assert panel_keys == {"inner_door:upper:panel"}\n'''
if new not in text:
    if text.count(old) != 1:
        raise RuntimeError(f"T15 guard oracle anchor expected once, got {text.count(old)}")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
