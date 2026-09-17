from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_EXPR = '(ROOT / "gui_modules" / "editors" / "hole_editor_composition.py").read_text(encoding="utf-8")'


def replace_test(path: str, name: str, body: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    pattern = rf"def {re.escape(name)}\(\):\n.*?(?=\ndef |\Z)"
    replacement = f"def {name}():\n{body.rstrip()}\n"
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"expected exactly one {name} in {path}, got {count}")
    p.write_text(new_text, encoding="utf-8")


replace_test(
    "tests/test_issue293_t5_canvas_renderer_slice.py",
    "test_gui_wiring_uses_one_live_render_context_provider",
    f'''    gui = GUI.read_text(encoding="utf-8")
    composition = {COMPOSITION_EXPR}
    assert "HoleEditorCanvasRenderer as _HoleEditorCanvasRenderer" in gui
    assert "canvas_renderer = d._HoleEditorCanvasRenderer(" in composition
    assert "s.redraw = canvas_renderer.redraw" in composition
    assert "s.indicator_redraw[0] = s.redraw" in composition
    for fragment in (
        '"feature_list": s.live_context.feature_list',
        '"surface": s.live_context.surface',
        '"width": s.live_context.width',
        '"height": s.live_context.height',
        '"reference_guide": s.live_context.reference_guide',
        '"baseline_scene": s.live_context.baseline_scene',
        '"active_part_key": s.active_part_key[0]',
    ):
        assert fragment in composition''',
)

replace_test(
    "tests/test_issue293_t5_context_switch_slice.py",
    "test_gui_wiring_uses_live_context_instead_of_stale_lambda_captures",
    f'''    gui = GUI.read_text(encoding="utf-8")
    composition = {COMPOSITION_EXPR}
    assert "HoleEditorLiveContext as _HoleEditorLiveContext" in gui
    assert "HoleEditorContextSwitcher as _HoleEditorContextSwitcher" in gui
    assert "s.live_context = d._HoleEditorLiveContext(" in composition
    assert "context_switcher = d._HoleEditorContextSwitcher(" in composition
    assert "s.switch_editor_context = context_switcher.switch" in composition
    assert "switch_editor_context=s.switch_editor_context" in composition

    tree = ast.parse(composition)
    stale = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Lambda):
            continue
        loaded = {{
            child.id for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in TRACKED
        }}
        if loaded:
            stale.append((node.lineno, sorted(loaded)))
    assert not stale, f"T5 RED: composition callbacks still capture stale context locals: {{stale}}"''',
)

replace_test(
    "tests/test_issue293_t5_feature_factory_slice.py",
    "test_gui_wiring_uses_live_size_context_provider",
    f'''    composition = {COMPOSITION_EXPR}
    assert '"width": s.live_context.width' in composition
    assert '"height": s.live_context.height' in composition
    assert "s.make_feature = feature_factory.make_feature" in composition''',
)

replace_test(
    "tests/test_issue293_t5_indicator_fit_validation_slice.py",
    "test_gui_wiring_keeps_collect_state_late_bound",
    f'''    composition = {COMPOSITION_EXPR}
    assert "collect_state=lambda: s.collect_indicator_state()" in composition, "T5 RED: indicator-state collection must stay late-bound"
    assert "collect_state=s.collect_indicator_state," not in composition''',
)

print("reconciled 4 composition-root regression contracts")
