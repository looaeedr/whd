---
name: issue-closure-gate
description: 完成工單後依原需求與真實驗收證據判定，GitHub close/readback，不需要狀態交易。
whd_doc_role: CURRENT
whd_contract: issue-closure-gate-independent
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# issue-closure-gate

當交付成果已確認、使用者要求結案或原工單明確達成時，直接更新／關閉 Issue，並重新讀取狀態以確認。禁止以完成測試冒充已關閉 Issue。不得依賴額外 execution record 或 transaction。

## 依原驗收範圍與實際證據結案，不以籠統人工 UAT 卡單

- **先核對需求，不憑空加前置**：以原 Issue 的必要驗收條件、使用者當次明確驗收決定及現行 CURRENT product/CI/release gate 為邊界，區分 `PASS / FAIL / NOT_RUN / NOT_APPLICABLE` 和測試所覆蓋的確切功能。原範圍已由可信證據充分證明、使用者接受交付且沒有未通過的必要硬閘門時，直接結案；不得事後用沒有指出具體操作、預期結果和缺少證據的「等人工 UAT」「全部重驗」籠統延後。
- **分段證據可合用，不能造假全綠**：同一功能的實機 GUI 手繪、原生資料讀回、WHD Session Confirm/Cancel/Undo、Save→Reload、2D/3D 和製造 DXF，可以逐項核對後共同支持原驗收範圍；必須註明設備、版本／HEAD、操作方式與各段實際結果。**分段 PASS 不等於從未通過的「同輪端到端 E2E PASS」**；對當次失敗、偶發失敗、未執行的追加測試，逐項如實揭露，不得改寫成 GREEN。
- **具體缺口才阻擋**：某個 FAIL / NOT_RUN 若屬原需求必要條件或明示不可替代的人工、安全、製造、CI 驗收，須留下具體失敗步驟、可重現條件或缺失證據，繼續修復／驗證，**不得僅因其他分段 PASS 就關單**。如果它只是額外擴張的同輪測試，先核對原需求是否真的要求此整段；非必要且已有足夠獨立證據時，說清失敗與不影響結案的理由，不得將它虛構為無期限的人工作業。
- **人工作業不冒名、驗收決定不蒸發**：AI 控制 Windows 滑鼠不是操作員本人手動 UAT；原 Issue 若明定不可替代的人為簽收，不能自行以自動化冒充。使用者當次依實際證據明確採納替代驗收時，在不違反更高優先級必要閘門的前提下按該決定收尾；仍有具體未完成條件則精確報告，不使用籠統「等人工」。
- **結案與發布分開**：完成後真正執行 GitHub `closed / completed`，並反讀 Issue 與必要 PR/CI；未完成 close 不得宣稱已關單。工單結案不等於產品已發布正式 `X=cleanup/2d-3d-sync`，沒有使用者當次 `/推推` 不得觸碰 X，也不因此取得 DC/RC 權限。

事故案例：[#1959 CADCraft GUI](https://github.com/looaeedr/whd/issues/1959) 的真實滑鼠手繪三種圖元、原生 inspect，以及另外驗證的 WHD 回傳／製造分段證據，可明確列入結案依據；同一輪手繪加回傳自動化未通過，必須同時如實註記，不能宣稱該額外單輪測試 PASS，也不能用籠統「等人工 UAT」取代實際判準。
