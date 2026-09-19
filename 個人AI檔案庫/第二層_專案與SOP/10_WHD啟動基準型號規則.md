---
whd_doc_role: CURRENT
whd_contract: phase6-startup-baseline-model
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 啟動基準型號規則

<!-- WHD_AUTHORITY contract=phase6-startup-baseline-model role=CURRENT path=個人AI檔案庫/第二層_專案與SOP/10_WHD啟動基準型號規則.md -->

## Canonical startup rule

WHD fresh startup 的基準型號固定為 **金庫型**。

Canonical state must be established before presentation widgets are built:

- `baseline_var = "金庫型"`
- `_active_cabinet_type = "金庫型"`
- fresh Fold Designer snapshot `model = "金庫型"`
- 3D 設定中心的基準型號初始值 = `金庫型`

## Ownership boundary

Fresh-start default belongs to the application state owner in
`gui_modules/application/state_sync.py`.

Do **not** rely on a legacy Combobox, menu `.current(...)`, or another optional UI widget to manufacture the startup default. Production `python gui.py` uses the direct `Phase6PrimaryApplication` path and may not construct legacy presentation widgets.

## Project/load boundary

This rule applies only to a **fresh application startup**.

- An explicitly loaded project remains authoritative for its saved model.
- User switching to `受電箱` remains supported.
- User switching to `自訂` remains supported.
- Known-family preset switching semantics remain unchanged.
- This rule does not change geometry, DXF authority, manufacturing formulas, or persistence schema.

## Regression contract

A permanent regression must cover both:

1. legacy compatibility host startup;
2. production direct-primary `python gui.py` startup.

Both must project `金庫型` consistently into the Fold Designer snapshot and 3D baseline selector.
