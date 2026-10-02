import importlib.util
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / 'check_zh_tw_report.py'

spec = importlib.util.spec_from_file_location('check_zh_tw_report', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SkillSourceLanguageTests(unittest.TestCase):
    def test_rejects_legacy_english_template(self):
        legacy = '''# HTML Report Format\n\n## Scaffold\n<html lang="en">\n## Candidate card\nPlain English.\n## Top recommendation section\n'''
        errors = mod.validate_skill_sources('''# 掃描深模組''', legacy)
        self.assertTrue(errors)

    def test_current_skill_and_template_are_traditional_chinese_first(self):
        skill = (SKILL_DIR / 'SKILL.md').read_text(encoding='utf-8')
        template = (SKILL_DIR / 'HTML-REPORT.md').read_text(encoding='utf-8')
        self.assertEqual([], mod.validate_skill_sources(skill, template))


if __name__ == '__main__':
    unittest.main()
