from tools.phase6_skill_preflight import required_skills_for


def test_short_ascii_route_keywords_do_not_match_inside_longer_words():
    for task in (
        "DM7 navigation durable guidance",
        "build regression evidence",
        "suite cleanup notes",
    ):
        required = set(required_skills_for(task=task))
        assert "UI設計與去AI味" not in required, task


def test_short_ascii_route_keywords_still_match_as_explicit_tokens():
    cases = (
        ("UI design review", "UI設計與去AI味"),
        ("UX review", "UI設計與去AI味"),
        ("3D geometry review", "phase6-corner-3d-model-integrity"),
    )
    for task, expected_skill in cases:
        required = set(required_skills_for(task=task))
        assert expected_skill in required, task
