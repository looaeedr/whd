"""Application update routing extracted from gui.py.

This module owns scheduling/routing only; calculation/state authority remains on
the application owner and its existing controllers/services.
"""

class _Phase6UpdateScheduler:
    """Coalesce GUI work behind one authoritative update-executor seam."""

    DEFAULT_DEBOUNCE_MS = 75
    MIN_DEBOUNCE_MS = 50
    MAX_DEBOUNCE_MS = 100
    _DISPLAY_ONLY_REASONS = frozenset({"display", "annotation", "camera"})
    _FULL_REASONS = frozenset({"geometry", "assembly", "baseline"})

    def __init__(self, owner, *, executor=None):
        self.owner = owner
        self.executor = executor
        self.depth = 0
        self.dirty = set()
        self._flushing = False
        self._after_job = None
        self._metrics = {
            "flushes": 0,
            "calculation_flushes": 0,
            "display_flushes": 0,
        }

    def begin(self):
        self.depth += 1

    def end(self):
        if self.depth <= 0:
            self.depth = 0
            return
        self.depth -= 1
        if self.depth == 0:
            self.request_flush()

    def submit(self, reason="geometry", *, immediate=False, debounce_ms=None):
        self.dirty.add(str(reason or "geometry"))
        if immediate:
            return self.flush_now()
        if self.depth == 0:
            self.request_flush(debounce_ms=debounce_ms)
        return True

    def mark_dirty(self, reason="geometry"):
        return self.submit(reason)

    @classmethod
    def _normalize_debounce_ms(cls, debounce_ms):
        if debounce_ms is None:
            return cls.DEFAULT_DEBOUNCE_MS
        value = int(debounce_ms)
        if value <= 0:
            return 0
        return max(cls.MIN_DEBOUNCE_MS, min(cls.MAX_DEBOUNCE_MS, value))

    @classmethod
    def _requires_calculation(cls, reasons):
        for reason in reasons:
            text = str(reason or "geometry")
            if text in cls._DISPLAY_ONLY_REASONS:
                continue
            if text in cls._FULL_REASONS:
                return True
            # setting:*, legacy "settings", designer snapshots, and unknown
            # mutation reasons fail closed to a full authoritative calculation.
            return True
        return False

    def request_flush(self, *, debounce_ms=None):
        if self.depth > 0 or self._flushing or not self.dirty:
            return
        delay = self._normalize_debounce_ms(debounce_ms)
        root = getattr(self.owner, "root", None)
        if delay and root is not None and hasattr(root, "after"):
            if self._after_job is not None:
                try:
                    root.after_cancel(self._after_job)
                except Exception:
                    pass
            self._after_job = root.after(delay, self.flush_now)
            return
        self.flush_now()

    def flush_now(self):
        if self.depth > 0 or self._flushing or not self.dirty:
            return False
        if self._after_job is not None:
            root = getattr(self.owner, "root", None)
            try:
                if root is not None:
                    root.after_cancel(self._after_job)
            except Exception:
                pass
            self._after_job = None
        reasons = set(self.dirty)
        self.dirty.clear()
        self._flushing = True
        try:
            self._metrics["flushes"] += 1
            requires_calculation = self._requires_calculation(reasons)
            metric_key = (
                "calculation_flushes"
                if requires_calculation
                else "display_flushes"
            )
            self._metrics[metric_key] += 1
            if callable(self.executor):
                self.executor(reasons)
            elif requires_calculation:
                self.owner.update_calculations()
            else:
                render = getattr(self.owner, "draw_preview", None)
                if callable(render):
                    render()
        finally:
            self._flushing = False
        return bool(reasons)

    def cancel_pending(self):
        if self._after_job is not None:
            root = getattr(self.owner, "root", None)
            try:
                if root is not None:
                    root.after_cancel(self._after_job)
            except Exception:
                pass
            self._after_job = None
        self.dirty.clear()
        self.depth = 0
        return True

    def metrics_snapshot(self):
        return dict(self._metrics)


def cancel_application_update_scheduler(owner):
    scheduler = getattr(owner, "_phase6_update_scheduler", None)
    cancel = getattr(scheduler, "cancel_pending", None)
    if callable(cancel):
        return cancel()
    return False


def install_application_update_scheduler_lifecycle(owner):
    root = getattr(owner, "root", None)
    if root is None or bool(getattr(owner, "_phase6_update_scheduler_lifecycle_installed", False)):
        return False

    def _on_destroy(event):
        if getattr(event, "widget", None) is root:
            cancel_application_update_scheduler(owner)

    root.bind("<Destroy>", _on_destroy, add="+")
    owner._phase6_update_scheduler_lifecycle_installed = True
    return True


def execute_fold_designer_update_reasons(
    owner,
    reasons,
    *,
    full_update,
    render_committed,
    publish_if_changed,
):
    """Preserve Fold Designer mutation→publish→full/display render sequencing."""
    reasons = {str(reason or "geometry") for reason in set(reasons or ())}
    if not reasons:
        return None

    if (
        getattr(owner, "_phase6_sync_ready", False)
        and not getattr(owner, "_phase6_initializing", False)
        and not getattr(owner, "_phase6_external_apply_guard", False)
        and callable(getattr(owner, "_live_sync_callback", None))
    ):
        publish_if_changed()

    if _Phase6UpdateScheduler._requires_calculation(reasons):
        if getattr(owner, "preview_3d_enabled", True):
            canvas = owner.renderer.canvas
            draw = getattr(canvas, "draw", None)
            draw_idle = getattr(canvas, "draw_idle", None)
            if (
                callable(draw)
                and callable(draw_idle)
                and not getattr(owner, "_phase6_force_sync_preview", False)
            ):
                canvas.draw = draw_idle
                try:
                    return full_update()
                finally:
                    canvas.draw = draw
            return full_update()

        render = owner.renderer.render
        owner.renderer.render = lambda: None
        try:
            return full_update()
        finally:
            owner.renderer.render = render

    return render_committed()


def _fold_designer_scheduler(owner, *, executor):
    scheduler = getattr(owner, "_phase6_update_scheduler", None)
    if not isinstance(scheduler, _Phase6UpdateScheduler):
        scheduler = _Phase6UpdateScheduler(owner, executor=executor)
        owner._phase6_update_scheduler = scheduler
    else:
        scheduler.executor = executor
    return scheduler


def submit_fold_designer_update_intent(
    owner,
    reason,
    *,
    commit=False,
    executor,
):
    if getattr(owner, "_phase6_destroying", False):
        return None
    return _fold_designer_scheduler(
        owner, executor=executor
    ).submit(reason, immediate=bool(commit))


def flush_fold_designer_update_intents(owner, *, executor):
    scheduler = _fold_designer_scheduler(owner, executor=executor)
    return scheduler.flush_now()


def cancel_fold_designer_update_intents(owner):
    scheduler = getattr(owner, "_phase6_update_scheduler", None)
    cancel = getattr(scheduler, "cancel_pending", None)
    if callable(cancel):
        return cancel()
    return False


def queue_fold_designer_update(owner, *, executor):
    if (
        getattr(owner, "_phase6_destroying", False)
        or getattr(owner, "_phase6_switching_part", False)
    ):
        return None
    return submit_fold_designer_update_intent(
        owner,
        "geometry",
        commit=False,
        executor=executor,
    )


def apply_fold_designer_settings_delta(
    delta,
    transaction_id,
    *,
    transactions,
    apply_updates,
):
    previous = transactions.push_active_transaction(transaction_id)
    try:
        return apply_updates(dict(delta or {}))
    finally:
        transactions.restore_active_transaction(previous)


def install_fold_designer_keyboard_shortcuts(
    owner,
    *,
    on_save,
    on_open,
    on_fullscreen,
):
    """Install one Fold Designer shortcut layer without creating action owners."""
    if bool(getattr(owner, "_phase6_keyboard_shortcuts_installed", False)):
        return False
    root = owner.root
    for sequence in ("<Control-s>", "<Control-S>"):
        root.bind(sequence, on_save, add="+")
    for sequence in ("<Control-o>", "<Control-O>"):
        root.bind(sequence, on_open, add="+")
    root.bind("<F11>", on_fullscreen, add="+")
    owner._phase6_keyboard_shortcuts_installed = True
    return True


def _request_phase6_update(self, reason="geometry", *, immediate=False, debounce_ms=None):
    """Route a GUI mutation through the one authoritative update scheduler."""
    owner = getattr(self, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate(reason)
    scheduler = getattr(self, "_phase6_update_scheduler", None)
    if scheduler is None:
        scheduler = self._phase6_update_scheduler = _Phase6UpdateScheduler(self)

    submit = getattr(scheduler, "submit", None)
    if callable(submit):
        submit(reason, immediate=bool(immediate), debounce_ms=debounce_ms)
        return True

    # Compatibility seam for legacy/test schedulers that implement the
    # pre-T7 mark_dirty/flush_now/request_flush protocol.
    mark_dirty = getattr(scheduler, "mark_dirty", None)
    if not callable(mark_dirty):
        raise AttributeError("update scheduler provides neither submit nor mark_dirty")
    mark_dirty(reason)
    if immediate:
        flush_now = getattr(scheduler, "flush_now", None)
        return flush_now() if callable(flush_now) else True
    if debounce_ms is not None:
        request_flush = getattr(scheduler, "request_flush", None)
        if callable(request_flush):
            request_flush(debounce_ms=debounce_ms)
    return True


def _flush_phase6_authoritative_state(self):
    """Commit pending GUI mutations before persistence/manufacturing boundaries."""
    scheduler = getattr(self, "_phase6_update_scheduler", None)
    if scheduler is None:
        return False
    return scheduler.flush_now()


def bind_live_updates(self):
    # W/H 同時是 Door layout 的總尺寸；變更時要重算自動餘數。
    self.w_var.trace_add("write", lambda *args: self._on_total_door_dimension_changed())
    self.h_var.trace_add("write", lambda *args: self._on_total_door_dimension_changed())

    # 主 GUI 中仍存在的設定欄位與 3D 設定中心雙向連動。
    for key, var in self._setting_var_map().items():
        var.trace_add("write", lambda *_args, k=key, v=var: self._on_main_setting_var_changed(k, v))

    # 非 SettingsService 擁有的輸入也只送 dirty event；完整重算只能由 Scheduler 執行。
    for var in [self.base_plate_all_same_var, self.base_plate_shrink_same_var,
                self.indicator_g_var, self.indicator_l_var] + self.indicator_layer_g_vars:
        var.trace_add(
            "write",
            lambda *_args: self._on_main_geometry_var_changed("legacy_input"),
        )
