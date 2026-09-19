from pathlib import Path


MONITOR = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
CONTINUITY = Path(".agents/skills/engineering/executable-continuity-controller/SKILL.md")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_watchdog_is_fallback_only_and_never_permission_to_stop_active_work():
    monitor = _text(MONITOR)
    continuity = _text(CONTINUITY)

    assert "WATCHDOG_FALLBACK_ONLY_CONTRACT" in monitor
    assert "watchdog/schedule presence != permission to stop" in monitor
    assert "當前 Runtime 仍可執行時，必須繼續目前施工／polling" in monitor

    assert "WATCHDOG_FALLBACK_ONLY_CONTRACT" in continuity
    assert "watchdog/schedule presence != permission to stop" in continuity
    assert "Schedule cadence is wake-up cadence, not execution cadence" in continuity


def test_watchdog_closes_only_after_owning_chain_is_really_complete():
    monitor = _text(MONITOR)
    continuity = _text(CONTINUITY)

    required = "owning chain COMPLETE/closed + final acceptance/cleanup finished"
    assert required in monitor
    assert required in continuity
    assert "disable the watchdog" in monitor
    assert "disable the watchdog" in continuity


def test_watchdog_wakeup_resumes_execution_not_status_only_reporting():
    monitor = _text(MONITOR)
    continuity = _text(CONTINUITY)

    assert "watchdog wake-up → restore owner → continue exact next action" in monitor
    assert "watchdog wake-up → restore owner → continue exact next action" in continuity
    assert "status-only watchdog response" in monitor
    assert "status-only watchdog response" in continuity
