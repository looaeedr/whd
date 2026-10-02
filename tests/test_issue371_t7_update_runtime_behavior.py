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
