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
    assert 'provider 原生 `delete_file`' in text
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


def test_negated_delete_words_do_not_trigger_destructive_discovery():
    from tools.phase6_skill_preflight import required_skills_for
    # Advisory skill routing must not interpret "do not" as an action request.
    denied = (
        "不要刪除", "不准刪掉", "不用清空", "別清 staging",
        "不要移除 0", "don't delete", "do not remove",
    )
    for task in denied:
        assert "刪除" not in required_skills_for(task=task), task


def test_explicit_delete_route_and_file_review_are_preserved():
    from tools.phase6_skill_preflight import required_skills_for
    for task in ("請刪除舊檔", "清空 staging", "刪掉暫存", "delete old files",
                 "remove staging", "清 active 0"):
        assert "刪除" in required_skills_for(task=task), task
    # Editing the deletion Skill still needs its contract review, even when
    # the user explicitly forbids deleting actual files.
    assert "刪除" in required_skills_for(
        task="不要刪除任何資料，只修改 Skill 的規範",
        changed_files=[".agents/skills/engineering/刪除/SKILL.md"],
    )
