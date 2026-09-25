from pathlib import Path

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "tools/scheduled_resume_bridge.py"


def test_existing_continuity_engine_remains_present():
    assert continuity.ContinuityState.RUNNING.value == "RUNNING"
    assert continuity.ContinuityState.WAITING_REMOTE.value == "WAITING_REMOTE"
    assert callable(continuity.load_checkpoint)
    assert callable(continuity.transition_checkpoint)


def test_target_generic_scheduled_resume_bridge_exists():
    assert BRIDGE.is_file(), (
        "RED: no executable generic tools/scheduled_resume_bridge.py exists"
    )


def test_target_canonical_controller_exposes_scheduled_resume_delegation_api():
    assert callable(getattr(continuity, "scheduled_resume_action", None)), (
        "RED: canonical continuity controller has no scheduled-resume delegation API"
    )
