from pathlib import Path


SKILL = Path('.agents/skills/engineering/deterministic-repo-migration/SKILL.md')
README = Path('.agents/skills/engineering/README.md')
PITFALL = Path('個人AI檔案庫/踩坑庫/deterministic_repo_migration_pitfalls.md')


def _text(path: Path) -> str:
    assert path.exists(), f'missing required governed artifact: {path}'
    return path.read_text(encoding='utf-8')


def test_issue250_skill_is_self_contained_and_authority_driven():
    text = _text(SKILL)
    required = [
        'authoritative matrix/registry',
        'scope inventory',
        'deterministic migration',
        'strict validation',
        'idempotence',
        'drift audit',
        'fail closed',
        'duplicate mapping',
        'missing mapping',
        'unknown role',
        'nonexistent target',
        'byte-for-byte',
        'zero diff',
    ]
    missing = [marker for marker in required if marker.lower() not in text.lower()]
    assert not missing, f'missing deterministic migration contract markers: {missing}'


def test_issue250_validator_is_not_authority_and_geometry_is_out_of_scope():
    text = _text(SKILL).lower()
    assert 'validator' in text and 'must not' in text and 'authority' in text
    assert 'production geometry' in text
    assert 'dxf' in text
    assert 'manufacturing truth' in text


def test_issue250_evidence_schema_and_applicability_are_explicit():
    text = _text(SKILL).lower()
    for marker in (
        'authority sha',
        'governed inventory count',
        'changed-file set',
        'idempotence result',
        'validator result',
        'drift audit',
        'positive applicability',
        'negative applicability',
    ):
        assert marker in text, f'missing evidence/applicability marker: {marker}'


def test_issue250_navigation_and_pitfall_writeback_exist():
    readme = _text(README).lower()
    assert 'deterministic-repo-migration' in readme
    pitfall = _text(PITFALL).lower()
    assert 'validator' in pitfall and 'authority' in pitfall
    assert 'same authority input' in pitfall
    assert 'second execution' in pitfall or 'zero diff' in pitfall


def test_issue250_preflight_route_discovers_skill():
    from tools.phase6_skill_preflight import required_skills_for

    routed = required_skills_for(
        task='deterministic repository migration from authoritative matrix registry',
        changed_files=(),
    )
    assert 'deterministic-repo-migration' in routed
