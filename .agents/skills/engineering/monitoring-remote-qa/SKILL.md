---
name: monitoring-remote-qa
description: 讀取 GitHub Actions 測試結果並處理失敗，不使用控制交易。
whd_doc_role: CURRENT
whd_contract: monitoring-remote-qa-independent
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# monitoring-remote-qa
追蹤指定 PR 的 exact workflow run、commit 和測試結果；失敗時直接修程式並重測，不得將 pending 當 GREEN。普通產品 QA 不會自動發布正式 X；產品發布權限只來自使用者 /推推。純治理文檔/技能透過 tools/change_lane_gate.py 驗證，可不經一般產品 QA，直接治理分支 PR 合併 X。
