---
name: 派工
description: 建立或選定 WHD GitHub 工單，直接派交開發，不使用原生執行交易管理。
whd_doc_role: CURRENT
whd_contract: direct-issue-dispatch
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# /派工
依使用者需求建立或讀取既有 Issue，確認 scope、工作分支及責任人。
能直接完成時直接修改、測試並整合至 localX；不可虛構已派出的代理人或未發生的提交。
若使用者下達 `/接手`，使用 RC → whd-dev → `/workspace/whd` 施工。
產品施工不得自動將 localX 發布至 X；必須使用者當次 `/推推`。純文檔／治理／技能工作不必派工，也不經 localX，可由本地治理分支直接 PR 合併 X，但必須通過 `tools/change_lane_gate.py` 的白名單硬檢查。
