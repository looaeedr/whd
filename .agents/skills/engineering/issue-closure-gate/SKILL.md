---
name: issue-closure-gate
description: 完成工單後 GitHub close/readback，不需要狀態交易。
whd_doc_role: CURRENT
whd_contract: issue-closure-gate-independent
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# issue-closure-gate
當交付成果已確認、使用者要求結案或原工單明確達成時，直接更新／關閉 Issue，並重新讀取狀態以確認。禁止以完成測試冒充已關閉 Issue。不得依賴額外 execution record 或 transaction。
