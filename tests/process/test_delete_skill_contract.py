import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/engineering/刪除/SKILL.md'
REGISTRY = ROOT / '.agents/skills/skill_registry.json'


def _registry_route():
    data = json.loads(REGISTRY.read_text(encoding='utf-8'))
    return next(route for route in data['routes'] if route.get('id') == '刪除')


def test_delete_skill_identity_and_semantics():
    text = SKILL.read_text(encoding='utf-8')
    assert 'name: 刪除' in text
    assert '# 刪除' in text
    assert 'PHYSICALLY_DELETED' in text
    assert 'ARCHIVED_NOT_DELETED' in text
    assert 'MOVED_OUT_OF_ACTIVE_SCOPE' in text
    assert 'DELETE_UNSUPPORTED' in text
    assert 'Google Drive `delete_file`' in text
    assert '不得把 archive/move 說成 delete' in text


def test_active_zero_cleanup_requires_namespace_readback():
    text = SKILL.read_text(encoding='utf-8')
    assert 'ACTIVE_ZERO_PHYSICAL_CLEANUP_HARD_GATE_V1' in text
    assert '只改 `CURRENT.json` / manifest 為 `EMPTY` 不算清乾淨' in text
    assert 'active `0`' in text
    assert '舊 `files/` staging tree' in text
    assert '重新建立乾淨的 active `0`' in text


def test_delete_skill_registry_route_is_narrow_and_canonical():
    route = _registry_route()
    assert route['required_skills'] == ['刪除']
    assert '.agents/skills/engineering/刪除/**' in route['file_globs']
    assert '刪除' in route['keywords']
    assert '清空' in route['keywords']
    assert route['required_references'] == ['.agents/skills/engineering/刪除/SKILL.md']
