from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents/skills/engineering/派工/SKILL.md"
PITFALL = ROOT / "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md"


def test_dispatch_skill_requires_unique_execution_instance_identity() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for marker in (
        "EXECUTION_INSTANCE_IDENTITY_V1",
        "chatgpt.<instance-token>",
        "scheduler.<automation-id-or-token>",
        "[A-Za-z0-9_.-]{1,64}",
        "executor_source",
        "ownership identity",
        "user-visible",
        "legacy",
    ):
        assert marker in text


def test_global_pitfall_records_instance_identity_boundary() -> None:
    text = PITFALL.read_text(encoding="utf-8")
    for marker in (
        "EXECUTION_INSTANCE_IDENTITY_V1",
        "worker=chatgpt",
        "chatgpt.<instance-token>",
        "executor_source",
    ):
        assert marker in text
