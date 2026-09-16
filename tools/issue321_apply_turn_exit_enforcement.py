# Temporary deterministic patch helper for issue #321; removed after GREEN.
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_controller() -> None:
    path = ROOT / "tools/continuity_controller.py"
    anchor = "\ndef _format_checkpoint(checkpoint: Checkpoint) -> str:\n"
    insertion = '''\ndef assert_turn_exitable_path(path: Path) -> Checkpoint:\n    """Load the authoritative checkpoint and enforce turn-exit eligibility in one call.\n\n    Missing or unreadable checkpoint state is a guard failure via ``load_checkpoint``;\n    callers must not treat the absence of durable state as permission to end the turn.\n    """\n\n    checkpoint = load_checkpoint(path)\n    assert_turn_exitable(checkpoint)\n    return checkpoint\n\n\ndef _format_checkpoint(checkpoint: Checkpoint) -> str:\n'''
    replace_once(path, anchor, insertion)

    old = '''        if args.command == "assert-turn-exitable":\n            assert_turn_exitable(checkpoint)\n            print(f"TURN_EXITABLE {checkpoint.state.value}")\n            return 0\n'''
    new = '''        if args.command == "assert-turn-exitable":\n            checkpoint = assert_turn_exitable_path(args.path)\n            print(f"TURN_EXITABLE {checkpoint.state.value}")\n            return 0\n'''
    replace_once(path, old, new)


def patch_controller_skill() -> None:
    path = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
    old = '''from tools.continuity_controller import load_checkpoint, assert_turn_exitable\n\ncheckpoint = load_checkpoint(path)\nassert_turn_exitable(checkpoint)\n'''
    new = '''from tools.continuity_controller import assert_turn_exitable_path\n\ncheckpoint = assert_turn_exitable_path(path)\n'''
    replace_once(path, old, new)

    cli = '''```bash\npython -m tools.continuity_controller assert-turn-exitable path/to/checkpoint.json\n```\n'''
    expanded = cli + '''\n`assert_turn_exitable_path(path)` 是 canonical path-level boundary：它把 checkpoint load/validation 與 turn-exit assertion 綁成同一個 executable operation。對已進入 long-flow / ticketed execution 的工作，**missing / unreadable checkpoint** 也是 guard failure，絕不是允許結束 turn；呼叫端必須先 recovery／持久化 owning checkpoint，再重跑同一 boundary，禁止直接略過 guard。\n'''
    replace_once(path, cli, expanded)


def patch_agents() -> None:
    path = ROOT / "AGENTS.md"
    anchor = "### 0.0.3.1 Executable Continuity finalization bridge\n"
    section = '''### 0.0.3.0 ASSISTANT_TURN_EXIT_HARD_GATE_V2\n\n<!-- ASSISTANT_TURN_EXIT_HARD_GATE_V2 -->\n對已進入 ticketed / long-running WHD execution、已建立 durable checkpoint、remote QA、recovery 或 closing chain 的工作，在任何 user-visible `final`／assistant turn exit 前都必須走同一個 executable boundary：\n\n```powershell\npython -m tools.continuity_controller assert-turn-exitable path/to/checkpoint.json\n```\n\n硬規則：\n\n1. 先定位本工作鏈唯一 owning durable checkpoint；不得用聊天文字、status update 或「下一續跑點」代替。\n2. `RUNNING / WAITING_REMOTE / RECOVERING` 被 guard 拒絕時，禁止結束 turn；立即執行 checkpoint 的 exact `next_action`。\n3. **missing / unreadable checkpoint** 一律 fail closed：先 recovery／建立或修復 authoritative checkpoint，再執行同一 guard；不存在「沒有 checkpoint 所以可以略過」。\n4. `BLOCKED` 只有符合 canonical controller Skill 的 genuine external authority/capability blocker才可 turn-exit；它仍不得通過 `assert-finalizable`。\n5. Remote run terminal 只解除 remote lock；若 cleanup / invariant / drift / closure 尚有工作，checkpoint 轉回 `RUNNING(next_action)`，本 gate 立即接手。\n6. 本節只建立最外層必經 hook；state semantics 與 executable authority 仍唯一屬於 `.agents/skills/engineering/executable-continuity-controller/SKILL.md` 與 `tools/continuity_controller.py`，不得建立第二套 controller。\n\n'''
    replace_once(path, anchor, section + anchor)


def main() -> None:
    patch_controller()
    patch_controller_skill()
    patch_agents()


if __name__ == "__main__":
    main()
