from pathlib import Path


SKILL = Path('.agents/skills/engineering/截角資料入口收斂/SKILL.md')
PITFALLS = Path('個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md')


def test_issue119_corner_data_skill_keeps_lifecycle_refresh_and_readability_contract():
    text = SKILL.read_text(encoding='utf-8')
    required = (
        '對稱 enter/exit lifecycle',
        'post-commit available_parts',
        '一次且唯一的 refresh owner',
        'dedicated viewport',
        '不得重複 finished-dimension summary',
    )
    missing = [marker for marker in required if marker not in text]
    assert not missing, f'Issue119 durable Skill contract missing: {missing}'


def test_issue119_corner_data_pitfall_library_records_reusable_failure_modes():
    text = PITFALLS.read_text(encoding='utf-8')
    required = (
        'Issue119 Corner Data lifecycle/readability',
        '只藏右側 canvas、左側 panel 仍 managed',
        'authoritative topology commit 完成後才刷新 visible projection',
        '同一 transaction 只能有一次 refresh owner',
        '175px generic annotation gutter',
    )
    missing = [marker for marker in required if marker not in text]
    assert not missing, f'Issue119 AI pitfall contract missing: {missing}'
