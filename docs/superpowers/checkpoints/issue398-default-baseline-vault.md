---
whd_doc_role: REFERENCE
whd_contract: issue398-default-baseline-vault
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# #398 — 啟動基準型號預設為金庫型

## Accepted rule

Fresh application startup must use `金庫型` as the canonical baseline model.

This must already be true in application state before any optional/legacy widget presentation runs:

```
baseline_var == "金庫型"
_active_cabinet_type == "金庫型"
Fold Designer snapshot["model"] == "金庫型"
3D baseline_model_var == "金庫型"
```

Saved project load remains authoritative when an explicit project model exists. User switching to 受電箱 or 自訂 remains unchanged.

## Root cause

The legacy `BoxCalculatorGUI` path happened to select 金庫型 later through the old baseline Combobox. The production direct-3D `Phase6PrimaryApplication` path does not build that widget, so relying on `Combobox.current(...)` left the canonical `baseline_var` blank.

Startup defaults therefore belong in the application state owner, not in an optional presentation widget.

## Implementation

`gui_modules/application/state_sync.py` initializes `baseline_var` to `"金庫型"`.

No family geometry, baseline DXF, manufacturing formula, project persistence schema, or user switching semantics are changed.

## Evidence

- Intended RED: RUN `35453790280` — direct-primary path failed with `assert '' == '金庫型'`, legacy path passed.
- GREEN: RUN `35453943729`
  - fresh startup: 2 PASS
  - family switching: 4 PASS
  - project/ownership: 9 PASS
  - protected drift: 0
