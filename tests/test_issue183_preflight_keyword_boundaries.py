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


def test_fix_keyword_does_not_misroute_pytest_fixture_or_prefix_edits():
    for task in (
        "pytest fixture 隔離測試",
        "prefix table naming",
        "suffix label formatting",
        "fixture monkeypatch 範例",
    ):
        skills = set(required_skills_for(task=task))
        assert "diagnosing-bugs" not in skills, task
        assert "tdd" not in skills, task

    for task in ("fix invalid project save", "修正錯誤", "debug crash"):
        skills = set(required_skills_for(task=task))
        assert "diagnosing-bugs" in skills, task
        assert "tdd" in skills, task


def test_release_packaging_requires_packaging_intent_or_actual_release_artifacts():
    non_release = (
        ("UPDATE AGENTS.md wording", ()),
        ("FULL suite feedback", ()),
        ("update README documentation", ()),
        ("修改技能路由診斷工具", ("tools/phase6_skill_preflight.py",)),
    )
    for task, files in non_release:
        selected = set(required_skills_for(task=task, changed_files=files))
        refs = set(required_references_for(task=task, changed_files=files))
        assert "phase6-release-packaging" not in selected, task
        assert "release_required_artifacts.json" not in refs, task

    for task in ("FULL 出包", "UPDATE 出包", "UPDATE package", "正式出包"):
        assert "phase6-release-packaging" in required_skills_for(task=task), task
        assert "release_required_artifacts.json" in required_references_for(task=task), task

    for path in ("tools/phase6_release.py", "release_required_artifacts.json"):
        assert "phase6-release-packaging" in required_skills_for(changed_files=(path,)), path


def test_delete_route_requires_actual_delete_verb_not_undelete_or_history():
    for task in (
        "undelete accidentally removed file",
        "show deleted file history",
        "removable drive settings",
    ):
        assert "刪除" not in required_skills_for(task=task), task
        assert ".agents/skills/engineering/刪除/SKILL.md" not in required_references_for(task=task), task

    for task in ("delete tracked file", "remove staging files", "清空 active 0"):
        assert "刪除" in required_skills_for(task=task), task
        assert ".agents/skills/engineering/刪除/SKILL.md" in required_references_for(task=task), task


def test_git_sync_fallback_needs_transport_intent_not_generic_connector_or_dns():
    for task in (
        "GitHub Connector 讀取 API 規範",
        "DNS 設定與域名解析",
        "JSON 無法解析資料",
    ):
        assert "git-remote-sync-fallback" not in required_skills_for(task=task), task

    for task in (
        "git push 因 DNS 失敗",
        "GitHub Connector 同步遠端分支",
        "Could not resolve host for git remote",
        "git DNS troubleshooting",
    ):
        assert "git-remote-sync-fallback" in required_skills_for(task=task), task


def test_gui_performance_route_needs_gui_trace_or_scheduler_context():
    for task in (
        "traceability requirements audit",
        "scheduler prompt wording",
        "GitHub Actions Scheduler 設定",
    ):
        assert "phase6-gui-performance-integrity" not in required_skills_for(task=task), task

    for task in (
        "Tk trace callback update",
        "GUI Scheduler dirty storm",
        "3D designer freeze",
    ):
        assert "phase6-gui-performance-integrity" in required_skills_for(task=task), task
