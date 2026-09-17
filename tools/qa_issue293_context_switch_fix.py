from pathlib import Path

GUI = Path("gui.py")
text = GUI.read_text(encoding="utf-8")
old = 'context_provider=lambda: {"width": live_context.width, "height": height},'
new = 'context_provider=lambda: {"width": live_context.width, "height": live_context.height},'
if old not in text and new not in text:
    raise SystemExit("feature-factory live-height wiring anchor missing")
text = text.replace(old, new, 1)
GUI.write_text(text, encoding="utf-8")

TEST = Path("tests/test_issue293_t5_feature_factory_slice.py")
test = TEST.read_text(encoding="utf-8")
old_assert = '    assert \'context_provider=lambda: {"width": width, "height": height}\' in gui\n'
new_assert = '    assert \'context_provider=lambda: {"width": live_context.width, "height": live_context.height}\' in gui\n'
if old_assert in test:
    test = test.replace(old_assert, new_assert, 1)
elif new_assert not in test:
    raise SystemExit("feature-factory wiring assertion anchor missing")
TEST.write_text(test, encoding="utf-8")
