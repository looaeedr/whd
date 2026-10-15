from __future__ import annotations

from types import SimpleNamespace

import pytest
import phase6_project_file as project

from gui_modules.application import command_router


class AfterRoot:
    def __init__(self):
        self.jobs = {}
        self.cancelled = []
        self.bindings = []
        self.next_id = 0
        self.last_delay = None

    def after(self, delay, callback):
        self.next_id += 1
        job = f"job-{self.next_id}"
        self.last_delay = int(delay)
        self.jobs[job] = callback
        return job

    def after_cancel(self, job):
        self.cancelled.append(job)
        self.jobs.pop(job, None)

    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))

    def fire_latest(self):
        assert self.jobs
        job = sorted(self.jobs)[-1]
        callback = self.jobs.pop(job)
        return callback()


class Canvas:
    def __init__(self, events):
        self.events = events
        self.draw = lambda: self.events.append("draw")
        self.draw_idle = lambda: self.events.append("draw_idle")


def _owner(events, *, sync_ready=True, preview=True):
    return SimpleNamespace(
        root=AfterRoot(),
        renderer=SimpleNamespace(
            canvas=Canvas(events),
            render=lambda: events.append("renderer.render"),
        ),
        _phase6_sync_ready=sync_ready,
        _phase6_initializing=False,
        _phase6_external_apply_guard=False,
        _live_sync_callback=lambda payload=None: None,
        _phase6_force_sync_preview=False,
        _phase6_destroying=False,
        _phase6_switching_part=False,
        preview_3d_enabled=preview,
    )


def test_issue371_full_update_preserves_publish_then_render_order():
    events = []
    owner = _owner(events)

    command_router.execute_fold_designer_update_reasons(
        owner,
        {"geometry"},
        full_update=lambda: events.append("full"),
        render_committed=lambda: events.append("committed"),
        publish_if_changed=lambda: events.append("publish"),
    )

    assert events == ["publish", "full"]


def test_issue371_display_only_preserves_publish_then_committed_view_order():
    events = []
    owner = _owner(events)

    command_router.execute_fold_designer_update_reasons(
        owner,
        {"display", "camera"},
        full_update=lambda: events.append("full"),
        render_committed=lambda: events.append("committed"),
        publish_if_changed=lambda: events.append("publish"),
    )

    assert events == ["publish", "committed"]


def test_issue371_scheduler_coalesces_three_geometry_intents_at_75ms():
    events = []
    owner = _owner(events)
    scheduler = command_router._Phase6UpdateScheduler(
        owner,
        executor=lambda reasons: events.append(("execute", frozenset(reasons))),
    )

    scheduler.submit("geometry")
    scheduler.submit("geometry")
    scheduler.submit("geometry")

    assert owner.root.last_delay == 75
    assert events == []
    owner.root.fire_latest()
    assert events == [("execute", frozenset({"geometry"}))]


def test_issue371_immediate_submit_flushes_without_leaving_scheduled_job():
    events = []
    owner = _owner(events)

    result = command_router.submit_fold_designer_update_intent(
        owner,
        "geometry",
        commit=True,
        executor=lambda reasons: events.append(frozenset(reasons)),
    )

    assert result is True
    assert events == [frozenset({"geometry"})]
    assert owner.root.jobs == {}


class Transactions:
    def __init__(self, events):
        self.events = events

    def push_active_transaction(self, transaction_id):
        self.events.append(("push", transaction_id))
        return "previous"

    def restore_active_transaction(self, previous):
        self.events.append(("restore", previous))


def test_issue371_settings_delta_preserves_push_apply_restore_order():
    events = []
    transactions = Transactions(events)

    result = command_router.apply_fold_designer_settings_delta(
        {"w": 901},
        "tx-7",
        transactions=transactions,
        apply_updates=lambda updates: events.append(("apply", updates)) or "ok",
    )

    assert result == "ok"
    assert events == [
        ("push", "tx-7"),
        ("apply", {"w": 901}),
        ("restore", "previous"),
    ]


def test_issue371_keyboard_binding_install_is_idempotent():
    owner = SimpleNamespace(root=AfterRoot())

    first = command_router.install_fold_designer_keyboard_shortcuts(
        owner,
        on_save=lambda event: None,
        on_open=lambda event: None,
        on_fullscreen=lambda event: None,
    )
    second = command_router.install_fold_designer_keyboard_shortcuts(
        owner,
        on_save=lambda event: None,
        on_open=lambda event: None,
        on_fullscreen=lambda event: None,
    )

    assert first is True
    assert second is False
    assert [row[0] for row in owner.root.bindings] == [
        "<Control-s>",
        "<Control-S>",
        "<Control-o>",
        "<Control-O>",
        "<F11>",
    ]


def test_issue372_main_root_destroy_cancels_pending_scheduler_job():
    events = []
    owner = _owner(events)
    scheduler = command_router._Phase6UpdateScheduler(
        owner,
        executor=lambda reasons: events.append(frozenset(reasons)),
    )
    owner._phase6_update_scheduler = scheduler

    installed = command_router.install_application_update_scheduler_lifecycle(owner)
    assert installed is True

    scheduler.submit("geometry")
    assert owner.root.jobs
    assert scheduler.dirty == {"geometry"}

    destroy_callbacks = [
        callback
        for sequence, callback, add in owner.root.bindings
        if sequence == "<Destroy>"
    ]
    assert len(destroy_callbacks) == 1
    destroy_callbacks[0](SimpleNamespace(widget=owner.root))

    assert owner.root.jobs == {}
    assert scheduler.dirty == set()
    assert scheduler._after_job is None
    assert events == []


def test_deferred_input_publish_keeps_final_manufacturing_publication_enabled():
    events = []
    owner = _owner(events)
    owner._phase6_defer_input_publish = True
    owner._live_sync_callback = lambda payload: events.append(payload)
    def full_update():
        events.append("full")
        owner._live_sync_callback("committed manufacturing")
    command_router.execute_fold_designer_update_reasons(
        owner, {"geometry"}, full_update=full_update,
        render_committed=lambda: events.append("view"),
        publish_if_changed=lambda: events.append("intermediate inputs"),
    )
    assert events == ["full", "committed manufacturing"]
    assert not getattr(owner, "_phase6_live_sync_guard", False)


# #1789: dirty intents raised by a running executor must not be lost.
def test_issue1789_reentrant_display_does_not_leave_save_flush_stale():
    events = []
    owner = _owner(events)
    scheduler = None

    def execute(reasons):
        events.append(frozenset(reasons))
        if reasons == {"geometry"}:
            # A trace fires while the full update is still executing.
            scheduler.submit("display")

    scheduler = command_router._Phase6UpdateScheduler(owner, executor=execute)
    owner._phase6_update_scheduler = scheduler
    scheduler.submit("geometry")  # a pending Tk callback must be cancelled
    assert owner.root.jobs

    # The same explicit boundary is used by Save / DXF Export.
    assert command_router._flush_phase6_authoritative_state(owner) is True
    assert events == [frozenset({"geometry"}), frozenset({"display"})]
    assert scheduler.dirty == set()
    assert owner.root.jobs == {}
    assert scheduler.metrics_snapshot()["calculation_flushes"] == 1
    assert scheduler.metrics_snapshot()["display_flushes"] == 1


def test_issue1789_nested_transaction_reentrant_immediate_final_intent():
    events = []
    owner = _owner(events)
    scheduler = None

    def execute(reasons):
        events.append(frozenset(reasons))
        if "geometry" in reasons:
            scheduler.begin()
            scheduler.submit("annotation", immediate=True)
            scheduler.submit("camera")
            scheduler.end()

    scheduler = command_router._Phase6UpdateScheduler(owner, executor=execute)
    scheduler.begin()
    scheduler.submit("geometry")
    scheduler.submit("assembly")
    assert events == []
    scheduler.end()
    assert owner.root.jobs
    owner.root.fire_latest()
    assert events == [
        frozenset({"geometry", "assembly"}),
        frozenset({"annotation", "camera"}),
    ]
    assert scheduler.dirty == set()
    assert owner.root.jobs == {}
    assert scheduler.metrics_snapshot()["calculation_flushes"] == 1


def test_issue1789_exception_preserves_new_intent_for_next_tk_flush():
    import pytest

    events = []
    owner = _owner(events)
    scheduler = None

    def execute(reasons):
        events.append(frozenset(reasons))
        if reasons == {"geometry"}:
            scheduler.submit("display")
            raise RuntimeError("simulated paint failure")

    scheduler = command_router._Phase6UpdateScheduler(owner, executor=execute)
    with pytest.raises(RuntimeError, match="simulated paint failure"):
        scheduler.submit("geometry", immediate=True)

    # The executor may fail, but a new committed user intent cannot disappear.
    assert scheduler.dirty == {"display"}
    assert owner.root.jobs
    owner.root.fire_latest()
    assert events == [frozenset({"geometry"}), frozenset({"display"})]
    assert scheduler.dirty == set()
    assert owner.root.jobs == {}


def test_issue1789_same_reason_trace_echo_is_coalesced_within_one_transaction():
    events = []
    owner = _owner(events)
    scheduler = None

    def execute(reasons):
        events.append(frozenset(reasons))
        # Canonical GUI computations may synchronously fire a Tk write trace
        # for the identical geometry reason while projecting calculated state.
        if reasons == {"geometry"}:
            scheduler.submit("geometry")

    scheduler = command_router._Phase6UpdateScheduler(owner, executor=execute)
    assert scheduler.submit("geometry", immediate=True)
    assert events == [frozenset({"geometry"})]
    assert scheduler.dirty == set()
    assert owner.root.jobs == {}
    assert scheduler.metrics_snapshot()["calculation_flushes"] == 1


# #1790: standalone designer persistence must not commit stale pending settings.
def _issue1790_standalone_save_owner(path, *, initial_width=400):
    from gui_modules.application import fold_designer_composition_state as state
    settings = {"w": initial_width}
    events = []
    errors = []
    app = SimpleNamespace(
        root=None,
        _phase6_pending_settings={"w": 500},
        _phase6_current_project_path=str(path),
        _project_save_callback=None,
        active_part_key="box_body",
        settings_status_var=SimpleNamespace(set=lambda value: events.append(("status", value))),
    )

    def flush():
        events.append(("flush", None))
        settings["w"] = app._phase6_pending_settings.pop("w")
        return {"w": settings["w"]}

    app.flush_pending_settings = flush

    class Composition:
        def __init__(self):
            self.app = app

        def _required(self, namespace, key):
            assert key == "_phase6_project_file"
            return project

        def build_project_snapshot(self, namespace):
            events.append(("snapshot", settings["w"]))
            return {
                "schema": project.PROJECT_SCHEMA,
                "snapshot": {
                    "model": "金庫型", "w": settings["w"],
                    "h": 600, "d": 200, "t": 2,
                },
                "final_geometry": {},
            }

    return state, Composition(), app, settings, events, errors


def test_issue1790_fallback_save_flush_failure_keeps_existing_file_bytes(tmp_path, monkeypatch):
    from tkinter import messagebox

    path = tmp_path / "existing.p6fold"
    original = b"existing committed project file must remain untouched"
    path.write_bytes(original)
    state, comp, app, settings, events, errors = _issue1790_standalone_save_owner(path)

    def fail_flush():
        events.append(("flush", None))
        raise RuntimeError("pending settings cannot be committed")

    app.flush_pending_settings = fail_flush
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: errors.append((title, message)))

    assert state.save_project_file(comp, {}) is None
    assert path.read_bytes() == original
    assert app._phase6_pending_settings == {"w": 500}
    assert events == [("flush", None)]
    assert errors and "pending settings cannot be committed" in errors[0][1]


def test_issue1790_fallback_save_flush_failure_does_not_create_new_file(tmp_path, monkeypatch):
    from tkinter import messagebox

    path = tmp_path / "new.p6fold"
    state, comp, app, settings, events, errors = _issue1790_standalone_save_owner(path)
    app._phase6_current_project_path = ""
    app.baseline_model_var = SimpleNamespace(get=lambda: "金庫型")

    def fail_flush():
        raise RuntimeError("settings transaction failed before Save As")

    app.flush_pending_settings = fail_flush
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: errors.append((title, message)))
    monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", lambda **kw: str(path))

    assert state.save_project_file(comp, {}, save_as=True) is None
    assert not path.exists()
    assert app._phase6_pending_settings == {"w": 500}
    assert errors and "settings transaction failed" in errors[0][1]
    assert events == []


def test_issue1790_fallback_success_flushes_last_settings_before_save_reload(tmp_path):
    path = tmp_path / "current.p6fold"
    state, comp, app, settings, events, errors = _issue1790_standalone_save_owner(path)
    saved = state.save_project_file(comp, {})

    assert saved == str(path)
    assert events[:2] == [("flush", None), ("snapshot", 500)]
    assert app._phase6_pending_settings == {}
    assert project.read_project(path)["snapshot"]["w"] == pytest.approx(500)


def test_issue1790_host_callback_save_preserves_existing_owner(tmp_path):
    path = tmp_path / "host-owned.p6fold"
    state, comp, app, settings, events, errors = _issue1790_standalone_save_owner(path)
    captured = []
    app._project_save_callback = lambda **kw: captured.append(kw) or "HOST_COMMITTED"

    assert state.save_project_file(comp, {}, save_as=True) == "HOST_COMMITTED"
    assert captured == [{"save_as": True, "active_part": "box_body"}]
    assert events == []
    assert not path.exists()
