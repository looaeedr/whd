from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import gui


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class PerfCounters:
    calculation: int = 0
    manufacturing: int = 0
    scene_rebuild: int = 0
    render: int = 0
    publish: int = 0
    echo: int = 0
    dxf_disk_read: int = 0


class _BoolVar:
    def __init__(self, value: bool):
        self.value = value

    def get(self) -> bool:
        return self.value


class _Owner:
    def __init__(self):
        self.root = None
        self.counters = PerfCounters()

    def update_calculations(self):
        self.counters.calculation += 1
        self.counters.manufacturing += 1
        self.counters.scene_rebuild += 1
        self.counters.render += 1


def test_door_layout_single_mutation_has_at_most_one_calculation_and_render():
    app = object.__new__(gui.BoxCalculatorGUI)
    counters = PerfCounters()
    app.multi_door_enabled_var = _BoolVar(False)
    app.refresh_door_layout_status = lambda: None

    def draw_preview():
        counters.render += 1

    def update_calculations():
        counters.calculation += 1
        draw_preview()

    app.draw_preview = draw_preview
    app.update_calculations = update_calculations

    gui.BoxCalculatorGUI._on_door_layout_value_changed(app, recompute=True)

    assert counters.calculation <= 1
    assert counters.render <= 1


def test_scheduler_coalesces_three_geometry_mutations_in_one_transaction():
    owner = _Owner()
    scheduler = gui._Phase6UpdateScheduler(owner)

    scheduler.begin()
    scheduler.mark_dirty("geometry")
    scheduler.mark_dirty("geometry")
    scheduler.mark_dirty("geometry")
    scheduler.end()

    assert owner.counters.calculation == 1
    assert owner.counters.scene_rebuild == 1
    assert owner.counters.render == 1


def test_display_and_camera_dirty_reasons_never_run_calculation_or_manufacturing():
    for reason in ("display", "camera"):
        owner = _Owner()
        scheduler = gui._Phase6UpdateScheduler(owner)
        scheduler.mark_dirty(reason)
        assert owner.counters.calculation == 0, reason
        assert owner.counters.manufacturing == 0, reason


def _direct_update_callers(path: Path) -> set[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[tuple[str, str]] = set()

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.class_name = "<module>"
            self.function_name = "<module>"

        def visit_ClassDef(self, node: ast.ClassDef):
            previous = self.class_name
            self.class_name = node.name
            self.generic_visit(node)
            self.class_name = previous

        def visit_FunctionDef(self, node: ast.FunctionDef):
            previous = self.function_name
            self.function_name = node.name
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                fn = child.func
                if isinstance(fn, ast.Attribute) and fn.attr == "update_calculations":
                    found.add((self.class_name, node.name))
            self.function_name = previous

    Visitor().visit(tree)
    return found


def test_gui_direct_full_calculation_calls_are_confined_to_executor_or_bootstrap_allowlist():
    callers = _direct_update_callers(ROOT / "gui.py")
    allowed = {
        ("_Phase6UpdateScheduler", "flush_now"),
        ("BoxCalculatorGUI", "__init__"),
        ("BoxCalculatorGUI", "update_calculations"),
    }
    unexpected = sorted(callers - allowed)
    assert unexpected == [], f"direct executor bypasses: {unexpected}"

class _AfterRoot:
    def __init__(self):
        self.jobs = {}
        self.cancelled = []
        self.last_delay = None
        self._next = 0

    def after(self, delay_ms, callback):
        self._next += 1
        job = f"job-{self._next}"
        self.last_delay = int(delay_ms)
        self.jobs[job] = callback
        return job

    def after_cancel(self, job):
        self.cancelled.append(job)
        self.jobs.pop(job, None)

    def fire_latest(self):
        if not self.jobs:
            return
        job = sorted(self.jobs)[-1]
        callback = self.jobs.pop(job)
        callback()


class _OwnerWithAfter(_Owner):
    def __init__(self):
        super().__init__()
        self.root = _AfterRoot()


def test_scheduler_geometry_request_uses_75ms_trailing_debounce_by_default():
    owner = _OwnerWithAfter()
    scheduler = gui._Phase6UpdateScheduler(owner)

    scheduler.mark_dirty("geometry")

    assert owner.root.last_delay == 75
    assert owner.counters.calculation == 0
    owner.root.fire_latest()
    assert owner.counters.calculation == 1


def test_scheduler_flush_now_cancels_pending_debounce_and_commits_final_state_once():
    owner = _OwnerWithAfter()
    scheduler = gui._Phase6UpdateScheduler(owner)

    scheduler.mark_dirty("geometry")
    assert owner.counters.calculation == 0
    assert scheduler.flush_now() is True
    assert owner.counters.calculation == 1
    owner.root.fire_latest()
    assert owner.counters.calculation == 1


def test_scheduler_exposes_counter_snapshot_without_monkeypatching_private_functions():
    owner = _Owner()
    scheduler = gui._Phase6UpdateScheduler(owner)
    scheduler.mark_dirty("geometry")

    metrics = scheduler.metrics_snapshot()

    assert metrics["flushes"] == 1
    assert metrics["calculation_flushes"] == 1
    assert metrics["display_flushes"] == 0

class _FlushRecorder:
    def __init__(self):
        self.flush_calls = 0

    def flush_now(self):
        self.flush_calls += 1
        return True


class _ProjectControllerForSave:
    def __init__(self, scheduler):
        self.project_path = "project.p6fold"
        self.scheduler = scheduler
        self.saved_snapshot = None

    def save(self, path, snapshot_factory, active_part_hint=None):
        self.was_flushed_before_save = self.scheduler.flush_calls == 1
        self.saved_snapshot = snapshot_factory()
        return path


def test_save_project_flushes_pending_authoritative_state_before_snapshot():
    app = object.__new__(gui.BoxCalculatorGUI)
    scheduler = _FlushRecorder()
    app._phase6_update_scheduler = scheduler
    app.project_controller = _ProjectControllerForSave(scheduler)
    app.root = None
    app._compose_phase6_project_snapshot_from_main_gui = lambda: {"w": 901}

    result = gui.BoxCalculatorGUI.save_phase6_project(app)

    assert result == "project.p6fold"
    assert scheduler.flush_calls == 1
    assert app.project_controller.was_flushed_before_save is True
    assert app.project_controller.saved_snapshot == {"w": 901}


def test_dxf_export_flushes_authoritative_state_before_reading_inputs():
    import inspect

    source = inspect.getsource(gui.BoxCalculatorGUI.export_selected_dxf)
    flush_pos = source.find("_flush_phase6_authoritative_state")
    input_pos = source.find("get_float_values")
    assert flush_pos >= 0
    assert input_pos >= 0
    assert flush_pos < input_pos
