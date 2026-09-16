from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "tools/continuity_controller.py"
SKILL = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"


TURN_EXIT_FUNCTIONS = r'''

def _checkpoint_digest(path: Path) -> str:
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError as exc:
        raise CheckpointError(f"checkpoint file not found: {path}") from exc
    except OSError as exc:
        raise CheckpointError(f"cannot read checkpoint file: {path}") from exc
    return hashlib.sha256(data).hexdigest()


def _assert_checkpoint_owner(
    checkpoint: Checkpoint,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
) -> None:
    expected = (
        _require_text("expected_issue", expected_issue),
        _require_text("expected_branch", expected_branch),
        _require_text("expected_head_sha", expected_head_sha),
    )
    actual = (checkpoint.issue, checkpoint.branch, checkpoint.head_sha)
    if actual != expected:
        raise CheckpointError(
            "checkpoint owner mismatch: "
            f"expected issue={expected[0]!r} branch={expected[1]!r} head_sha={expected[2]!r}; "
            f"got issue={actual[0]!r} branch={actual[1]!r} head_sha={actual[2]!r}"
        )


def _turn_exit_proof_payload(
    checkpoint: Checkpoint,
    *,
    checkpoint_digest: str,
) -> dict[str, object]:
    return {
        "version": TURN_EXIT_PROOF_VERSION,
        "issue": checkpoint.issue,
        "branch": checkpoint.branch,
        "head_sha": checkpoint.head_sha,
        "checkpoint_digest": checkpoint_digest,
        "guard": "assert_turn_exitable",
    }


def assert_turn_exitable_path(
    path: Path,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
    receipt_path: Path,
) -> Checkpoint:
    """Load the owning checkpoint, invoke the canonical guard, and mint proof.

    The proof is written only after ``assert_turn_exitable`` returns successfully.
    """

    path = Path(path)
    receipt_path = Path(receipt_path)
    checkpoint = load_checkpoint(path)
    _assert_checkpoint_owner(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    assert_turn_exitable(checkpoint)
    digest = _checkpoint_digest(path)
    proof = json.dumps(
        _turn_exit_proof_payload(checkpoint, checkpoint_digest=digest),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    _atomic_write_text(receipt_path, proof)
    return checkpoint


def assert_turn_exit_permitted(
    checkpoint_path: Path,
    receipt_path: Path,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
) -> Checkpoint:
    """Verify current owning checkpoint has current proof from actual guard invocation."""

    checkpoint_path = Path(checkpoint_path)
    receipt_path = Path(receipt_path)
    checkpoint = load_checkpoint(checkpoint_path)
    _assert_checkpoint_owner(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )

    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TurnExitBlocked(f"guard invocation proof missing: {receipt_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise TurnExitBlocked(f"guard invocation proof invalid: {receipt_path}") from exc

    if not isinstance(payload, dict):
        raise TurnExitBlocked("guard invocation proof invalid: payload must be an object")
    if payload.get("version") != TURN_EXIT_PROOF_VERSION:
        raise TurnExitBlocked("guard invocation proof invalid: unsupported version")
    if payload.get("guard") != "assert_turn_exitable":
        raise TurnExitBlocked("guard invocation proof invalid: canonical guard identity mismatch")

    owner = (payload.get("issue"), payload.get("branch"), payload.get("head_sha"))
    expected_owner = (checkpoint.issue, checkpoint.branch, checkpoint.head_sha)
    if owner != expected_owner:
        raise TurnExitBlocked("guard invocation proof stale: owner mismatch")

    current_digest = _checkpoint_digest(checkpoint_path)
    if payload.get("checkpoint_digest") != current_digest:
        raise TurnExitBlocked("guard invocation proof stale: checkpoint digest mismatch")

    return checkpoint
'''


SKILL_V2 = r'''

## ASSISTANT_TURN_EXIT_HARD_GATE_V2

V1 的 state guard 不足以證明「這次 turn 真的跑過 guard」。V2 把 owning checkpoint 與 actual guard invocation 都變成必要條件。

### Valid owning checkpoint

Turn-exit boundary 不得只接受「有 checkpoint」或「JSON 可讀」。它必須驗證 active execution context 的 exact owner：

- `issue`
- `branch`
- `head_sha`

缺檔、壞檔、owner 不符、stale branch/head 都視為 **missing / unreadable checkpoint** 的同一 fail-closed 類別；foreign/stale checkpoint 絕不是可退出授權。

### Actual guard invocation

Canonical path boundary `assert_turn_exitable_path(...)` 必須在載入與 ownership 驗證後，**實際呼叫** canonical `assert_turn_exitable(checkpoint)`。禁止：

- 只讀 state 後自行複製判斷；
- 只看到 checkpoint valid 就放行；
- 只靠文件 marker 或聊天文字宣稱 guard 已執行。

成功 guard invocation 必須產生 machine-verifiable **guard invocation proof**，綁定 owning identity 與該次 checkpoint 內容 digest。外層 boundary 再以 `assert_turn_exit_permitted(...)` 驗證 proof。

以下任何一項都必須 fail closed：

```text
NO_VALID_OWNING_CHECKPOINT
NO_ACTUAL_GUARD_INVOCATION
NO_CURRENT_GUARD_INVOCATION_PROOF
STALE_OR_OWNER_MISMATCHED_PROOF
```

checkpoint 在 guard 後只要被改寫，先前 proof 立即失效。`BLOCKED` 或 terminal state 也不能因 state 本身而繞過 owning-checkpoint / proof gate。

### Required behavior tests

`tests/process/test_issue321_turn_exit_enforcement.py` 必須至少證明：

- missing / malformed checkpoint fail closed；
- valid JSON 但 non-owning checkpoint fail closed；
- `RUNNING` 不 mint proof；
- path boundary 確實呼叫 canonical `assert_turn_exitable`；
- valid owning checkpoint 但沒有 guard invocation proof 仍 fail closed；
- successful guard invocation 產生 bound proof；
- checkpoint 改寫後 proof stale 並 fail closed。
'''


def patch_controller() -> None:
    text = CONTROLLER.read_text(encoding="utf-8")

    if "TURN_EXIT_PROOF_VERSION = 1" not in text:
        anchor = "FINALIZATION_PROOF_VERSION = 1\n"
        if anchor not in text:
            raise SystemExit("current-production finalization constant anchor missing")
        text = text.replace(anchor, anchor + "TURN_EXIT_PROOF_VERSION = 1\n", 1)

    if "def assert_turn_exitable_path(" not in text:
        anchor = "\ndef _format_checkpoint(checkpoint: Checkpoint) -> str:\n"
        if anchor not in text:
            raise SystemExit("controller format anchor missing")
        text = text.replace(anchor, TURN_EXIT_FUNCTIONS + anchor, 1)

    if "def authorize_finalization(" not in text or "def assert_finalization_proof(" not in text:
        raise SystemExit("refusing patch: current-production finalization owner guard disappeared")

    CONTROLLER.write_text(text, encoding="utf-8")


def patch_skill() -> None:
    text = SKILL.read_text(encoding="utf-8")
    if "OWNING_FINALIZATION_GUARD_V2" not in text:
        raise SystemExit("refusing patch: current-production finalization Skill contract disappeared")
    if "## ASSISTANT_TURN_EXIT_HARD_GATE_V2" not in text:
        text = text.rstrip() + SKILL_V2 + "\n"
    SKILL.write_text(text, encoding="utf-8")


def main() -> None:
    patch_controller()
    patch_skill()


if __name__ == "__main__":
    main()
