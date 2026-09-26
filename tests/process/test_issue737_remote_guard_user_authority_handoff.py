from pathlib import Path

WORKFLOW = Path(".github/workflows/whd-remote-execution-guard.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _guard_block() -> str:
    text = _text()
    start = text.index("            guard_args=(")
    end = text.index('            "${guard_args[@]}"', start)
    return text[start:end]


def test_chat_claim_takeover_forwards_selected_authority_to_execution_guard() -> None:
    block = _guard_block()
    expected = (
        '              if [ "$RG_EXECUTOR_SOURCE" = "chat" ]; then\n'
        "                guard_args+=(--user-authority-evidence /tmp/user-authority.json)\n"
        "              fi"
    )
    assert expected in block


def test_user_authority_evidence_is_only_forwarded_inside_claim_takeover_guard_path() -> None:
    block = _guard_block()
    assert block.count("--user-authority-evidence /tmp/user-authority.json") == 1
    claim_takeover = block.index('if [ "$RG_ACTION" = "claim-takeover" ]; then')
    chat_gate = block.index('if [ "$RG_EXECUTOR_SOURCE" = "chat" ]; then', claim_takeover)
    evidence = block.index("--user-authority-evidence /tmp/user-authority.json")
    else_branch = block.index("            else", claim_takeover)
    assert claim_takeover < chat_gate < evidence < else_branch
