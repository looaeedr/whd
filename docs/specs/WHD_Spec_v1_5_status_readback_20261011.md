---
whd_doc_role: REFERENCE
whd_contract: common-parts-quantity-2d-settings-status-readback
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD v1.5 規格進度補充（2026-10-11）

> **REFERENCE / 狀態回讀，不是第二套產品規格。** 此文只澄清已鎖定的 `docs/specs/WHD_Spec_v1_5.md` 前言所述「尚未施工、尚未驗收、尚未寫入 GitHub 倉庫」為 **2026-10-09 定稿當時**的狀態。該句不是 2026-10-11 的即時狀態，也不得據此把已存在的產品程式視為不存在。

- **原規格嚴格保留**：`docs/superpowers/verification/issue1469-v15-acceptance-matrix.json` 綁定原規格 SHA-256 `7b2f69e684cffa62a2dbb06aa944aff629bc2dcbae54694465ccd7a1d7663697`，覆蓋 CPR-01～20、AC-01～32 共 52 條。**任何修改原規格文字均須正式重審需求映射及重新驗收，不能為了修日期敘述改寫原檔或放寬驗證器。**
- **既有施工證據**：本倉庫已有 `phase6_quantity_model.py`、`ae_engine/receiving_quantity_box.py`、`ae_engine/manufacturing_quantity.py`、`ae_engine/manufacturing_equivalence.py` 等產品模組，以及 `tests/test_receiving_quantity_allocation_20261011.py` 等回歸測試。是否正式通過，只看當次指定提交的必要 CI／驗收收據及整合狀態。
- **入口與交付**：本補充不可創造新需求或取代原 CPR/AC；產品變更依 `AGENTS.md` 與 CURRENT Canonical Authority Map 所載 `localX` 路線，正式 X 發布仍需當次 `/推推`。
- **保護歷史**：原規格所有定義、提案時點和定稿時狀態一律維持原樣；本補充僅避免將舊進度誤解為今天的實作現況。
