from pathlib import Path
import inspect

from phase6_project_controller import Phase6ProjectController


def _controller():
    return Phase6ProjectController(
        read_project=lambda path: {"schema": "phase6-project/v1", "snapshot": {"w": 321.0}},
        write_project=lambda path, payload: Path(path),
        schema="phase6-project/v1",
    )


def test_project_controller_keeps_session_internal_and_exposes_defensive_snapshots():
    controller = _controller()
    controller.capture_committed({"w": 400.0, "nested": {"value": 1}})

    assert not hasattr(controller, "session")
    committed = controller.committed_snapshot()
    assert committed["w"] == 400.0
    committed["nested"]["value"] = 99
    assert controller.committed_snapshot()["nested"]["value"] == 1
    assert controller.loaded_baseline_snapshot() is None
    assert controller.draft_snapshot() is None
    assert "session" not in inspect.signature(Phase6ProjectController).parameters


def test_production_project_session_caller_is_controller_only_and_gui_has_no_alias():
    production = []
    for path in Path(".").glob("*.py"):
        if path.name.startswith("test_"):
            continue
        source = path.read_text(encoding="utf-8")
        if "from phase6_project_session import ProjectSession" in source:
            production.append(path.name)
    assert production == ["phase6_project_controller.py"]

    gui_source = Path("gui.py").read_text(encoding="utf-8")
    assert "self.project_session =" not in gui_source
    assert "self.project_controller.session" not in gui_source
