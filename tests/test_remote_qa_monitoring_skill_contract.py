from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_remote_qa_monitoring_skill_is_registered_and_required_by_dispatch():
    skill = ROOT / '.agents/skills/engineering/monitoring-remote-qa/SKILL.md'
    assert skill.exists(), 'remote QA monitoring skill must exist'
    skill_text = skill.read_text(encoding='utf-8')
    assert 'name: monitoring-remote-qa' in skill_text
    assert 'workflow run' in skill_text
    assert 'job' in skill_text
    assert 'step' in skill_text
    assert 'durable state' in skill_text
    assert '不得' in skill_text and '觸發' in skill_text and '停止' in skill_text

    registry = json.loads((ROOT / '.agents/skills/skill_registry.json').read_text(encoding='utf-8'))
    route = next((item for item in registry['routes'] if item.get('id') == 'remote-qa-monitoring'), None)
    assert route is not None, 'remote QA monitoring route must exist'
    assert 'monitoring-remote-qa' in route.get('required_skills', [])
    keywords = set(route.get('keywords', []))
    assert {'遠端 QA', '同步遠端QA', 'GitHub Actions', 'workflow run'} <= keywords

    dispatch = (ROOT / '.agents/skills/engineering/派工/SKILL.md').read_text(encoding='utf-8')
    assert '**REQUIRED SUB-SKILL:** monitoring-remote-qa' in dispatch
    assert 'remote QA' in dispatch or '遠端 QA' in dispatch
