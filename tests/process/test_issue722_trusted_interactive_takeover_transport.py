from __future__ import annotations

import json
from pathlib import Path

WORKFLOW = Path(".github/workflows/whd-remote-execution-guard.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_interactive_authority_parser_uses_real_python_newlines():
    line = next(
        line.strip()
        for line in _text().splitlines()
        if "lines = body.replace" in line
    )
    assert line == r'lines = body.replace("\r\n", "\n").split("\n")'


def test_interactive_authority_json_handoff_is_single_valid_json_object(tmp_path):
    text = _text()
    line = next(
        line.strip()
        for line in text.splitlines()
        if 'Path("/tmp/user-authority.json").write_text' in line
    )
    assert line == (
        r'Path("/tmp/user-authority.json").write_text('
        r'json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")'
    )

    comment = {
        "id": 5845926910,
        "user": {"login": "looaeedr"},
        "created_at": "2026-09-26T11:34:55Z",
        "body": (
            "WHD_USER_DIRECTED_TAKEOVER_V1\n"
            "issue=687\n"
            "requesting_worker=chatgpt.sol260926.work2.687.1\n"
            "previous_worker=chatgpt.sol260926.stopgate.t1\n"
            "executor_source=chat"
        ),
    }
    authority = tmp_path / "user-authority.json"
    authority.write_text(json.dumps(comment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(authority.read_text(encoding="utf-8")) == comment


def test_interactive_authority_matching_remains_exact_and_owner_scoped():
    text = _text()
    assert 'user.get("login") != os.environ["GITHUB_REPOSITORY_OWNER"]' in text
    assert 'fields.get("issue") == os.environ["RG_ISSUE"]' in text
    assert 'fields.get("requesting_worker") == os.environ["RG_TAKEOVER_WORKER"]' in text
    assert 'fields.get("previous_worker") == os.environ["RG_WORKER"]' in text
    assert 'fields.get("executor_source") == "chat"' in text
