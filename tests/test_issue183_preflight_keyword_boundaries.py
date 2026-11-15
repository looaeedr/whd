from tools.phase6_skill_preflight import required_references_for, required_skills_for


UI_SKILL = "UI設計與去AI味"
UI_REFERENCE = "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md"


def test_short_ascii_route_keywords_do_not_match_inside_longer_words():
    for task in (
        "DM7 navigation durable guidance",
        "build regression evidence",
        "suite cleanup notes",
    ):
        required_skills = set(required_skills_for(task=task))
        required_references = set(required_references_for(task=task))
        assert UI_SKILL not in required_skills, task
        assert UI_REFERENCE not in required_references, task


def test_short_ascii_route_keywords_still_match_as_explicit_tokens():
    cases = (
        ("UI design review", UI_SKILL),
        ("UX review", UI_SKILL),
        ("3D geometry review", "phase6-corner-3d-model-integrity"),
    )
    for task, expected_skill in cases:
        required = set(required_skills_for(task=task))
        assert expected_skill in required, task

    for task in ("UI design review", "UX review"):
        required_references = set(required_references_for(task=task))
        assert UI_REFERENCE in required_references, task

def test_python_mock_keyword_does_not_capture_visual_mockups():
    # Visual mockups are not pytest mocks. The policy is route-local, not global.
    from tools.phase6_skill_preflight import required_skills_for

    for task in ("UI mockup 視覺設計", "design mockups", "mockup 色彩版面"):
        assert "Python測試實務" not in required_skills_for(task=task), task


def test_python_mock_keyword_routes_actual_test_double_work():
    from tools.phase6_skill_preflight import required_skills_for, required_references_for

    task = "用 mock 隔離 pytest 外部依賴"
    assert "Python測試實務" in required_skills_for(task=task)
    assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in required_references_for(task=task)
