from __future__ import annotations

from types import SimpleNamespace

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
        if reasons == {"geometry"}:
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
