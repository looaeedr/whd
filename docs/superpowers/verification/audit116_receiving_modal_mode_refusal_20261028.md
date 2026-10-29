---
whd_doc_role: CURRENT
whd_contract: audit116-receiving-modal-rejected-mode-no-orphan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Audit 116 — Receiving modal rejected-mode orphan / close NameError

## Windows evidence, 2026-10-28 Asia/Taipei

R5-2600, `Z:\\localX` on GitHub `localX@da949756`, original GUI `python gui.py` PID 18304 at 00:47; at 00:57 Windows reported it as Responding=true. Meanwhile a separate 116 UAT pytest process PID 18576 ran from 00:56; test finished 13 passed, 1 skipped. `logs/runtime_error.log` contained two consecutive `tk_callback` failures at 00:56:11 and 00:56:14:

- `NameError: cannot access free variable 'sketch_redraw' where it is not associated with a value in enclosing scope` at `receiving_multi_settings_window.py:299`, `close()`.
- Initial cause: `open_multi_settings` constructed a `tk.Toplevel`, installed a WM_DELETE_WINDOW close callback and stored it as `parent._receiving_multi_settings_window`, then performed a source mode switch that rejected or raised at line 378. The orphan Toplevel's close callback called cleanup closures before their definitions had been reached, so ordinary close left the modal on screen and could trap focus.

A separate 3D `NFB_QUANTITY_INHERITED_MODEL_NEEDS_RESELECTION` trace at 00:57:55 contains `tests/test_issue1463_receiving_modes.py::counted_resolve`, and therefore is *not proof* that the customer's separate GUI PID 18304 failed. Do not conflate these test logs with a live GUI crash.

## Root fix

Before constructing child widgets, registration of close callbacks or scheduling idle redraw, preflight the authoritative `active_mode` transition. For compatibility with mode switch event ownership, a `Toplevel` may be created and stored first, but any refusal or exception must **immediately destroy** it and clear the parent reference **before the close callback exists**. Do not bypass mode safety, auto-confirm unsaved changes, force switching or kill the customer's running GUI. On success, build the same form once.

## Acceptance and scope

1. `set_bay -> single(quantity)` returns False: raises the existing failure and preserves authoritative source mode; no extra Tk children, modal grab or retained parent pointer.
2. `quantity -> multi(set_bay)` return False and raises ValueError: same no-orphan behavior.
3. Existing legitimate mode switching, GUI cancel/confirm and 2D/3D regressions remain green.
4. Test added to canonical Product Regression. Windows user's `config.ini`, local LOG, open PID and production X must not be overwritten or force-closed.
5. This source fix takes effect only when a new GUI process loads the updated `localX`. It does not retroactively patch an already-running Tk modal.
