import importlib.util
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "check_zh_tw_report.py"

spec = importlib.util.spec_from_file_location("check_zh_tw_report", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class LanguageGateTests(unittest.TestCase):
    def test_rejects_english_ui_and_wrong_lang(self):
        html = '''<!doctype html><html lang="en"><body>
        <h2>Top recommendation</h2><span>Strong</span>
        <div>Before</div><div>After</div>
        </body></html>'''
        errors = mod.validate_html(html)
        self.assertTrue(any("lang" in e for e in errors))
        self.assertTrue(any("Top recommendation" in e for e in errors))
        self.assertTrue(any("Strong" in e for e in errors))
        self.assertTrue(any("Before" in e for e in errors))

    def test_accepts_traditional_chinese_ui(self):
        html = '''<!doctype html><html lang="zh-Hant-TW"><body>
        <h2>最高優先建議</h2><span>強烈建議</span>
        <div>修改前</div><div>修改後</div>
        <code>CornerType OVERLAY FinalScene</code>
        </body></html>'''
        self.assertEqual([], mod.validate_html(html))

    def test_checks_accessible_labels_too(self):
        html = '''<!doctype html><html lang="zh-TW"><body>
        <button aria-label="Top recommendation">最高優先建議</button>
        </body></html>'''
        errors = mod.validate_html(html)
        self.assertTrue(any("aria-label" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
