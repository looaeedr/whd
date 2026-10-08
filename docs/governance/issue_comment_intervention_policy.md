# Issue #1412 — 工單留言接取、10 分鐘進度與介入唯一判定

> CURRENT。Authority：`.agents/skills/engineering/flow-v2-execution/SKILL.md::ISSUE_COMMENT_10MIN_INTERVENTION_HARD_GATE_V1`。本文件只說明 Issue-plane protocol，不另建 owner／claim state machine。

## 發文時機與責任

- **ACQUIRE 成功即發文**：現任 owner 使用授權的 GitHub Issue-comment API，在 exact owning Issue 發佈 `WHD_ISSUE_OWNER_PROGRESS_V1`，並 readback GitHub server `created_at`。單純宣稱「已接取」或寫到聊天室不合格。
- **每 10 分鐘**：owner 持續施工，最遲 600 秒補發真實進度；即使還在測試，也要填「目前做什麼、障礙與下一步」。空泛的 heartbeat/ping 不續時。不得臆造已完成的測試。
- **HANDOFF/TAKEOVER 成功**：新 owner 立即發 `event=TAKEOVER`，這則建立新的 10 分鐘時鐘；舊 owner 的舊代次留言無法替新 owner 續命。
- **完成／釋放**：可以追加 `RELEASED/DONE` 交接留言，但這不算有效活躍進度，不更動可介入時鐘。
- 未成功取得 native claim 的執行者不得冒稱 ACQUIRED；GitHub 留言不產生 claim、lease 或修改 authority。

## 有效留言格式

GitHub Issue comment body 的第一行必須是 `WHD_ISSUE_OWNER_PROGRESS_V1`，之後每行 `key=value`：

```text
WHD_ISSUE_OWNER_PROGRESS_V1
issue=1412
generation=4
owner_kind=SCHEDULER
owner_id=scheduler.6ab13fa557fc8191935c671214b865e2
lane_id=scheduler.6ab13fa557fc8191935c671214b865e2
slot_id=NONE
work_branch=work/issue-1412
head_sha=<exact 40-char Git SHA>
event=PROGRESS
done=已完成的具體工作
work=正在執行的具體工作
blocker=無或具體障礙
next=下一步
```

上例是格式示意，非真實 #1412 claim。可呼叫 `tools/issue_comment_progress.py::build_owner_progress_comment` 生成格式，再透過有 `ISSUE_COMMENT` authority 的 GitHub transporter 發佈到 exact Issue。每次 progress 使用 fresh record generation/HEAD，不能沿用舊範本。留言時間以 GitHub **server created_at** 為唯一時鐘；不得由使用者輸入、留言中的時間或 GitHub edited_at 替代。

## 後來者介入

1. fresh-read exact Issue 的 comments + current `WHD_EXECUTION_RECORD_V2`，根據 exact issue/generation/owner/branch/head 與可信 GitHub 發文身份過濾。未取得可信 comments、發文作者不可信、欄位缺失、時間不是帶時區 ISO、時間在未來 → `NO_INTERVENTION`。
2. 取最大有效 `created_at`；若最後有效留言距現在 **0–600 秒（含 600）**，不得介入、搶單或提早改 owner。
3. 只有距今 **超過 600 秒**，才得到候選 `ISSUE_COMMENT_STALE_OVER_600S`。此為 eligibility，不是授權寫入；原有單一寫者 CAS、Flow v2 HANDOFF/ACQUIRE、generation、HEAD、QA/merge gates 不變。
4. **正式接手成功**後立即在同 Issue 留下新身份，並直接接續原 `next_action`；不得另外叫使用者或舊接取者確認。
5. 舊觀測法：heartbeat freshness（300/420）、runtime END、lease expiry、600-second durable progress、Actions active run、issue-family delegated/active writer 推斷，**全部退出介入時鐘的決定路徑**；如有交易鎖與安全防線仍保留於獨立原用途。非可信工單留言不能用來替代。

## 失敗與回歸矩陣

- 0、599、600 秒：`NO_INTERVENTION`；601 秒：候選。
- 兩筆留言（舊、近）：取最新合格留言。
- 缺 comments、異代次、不同 owner/branch/HEAD、冒名作者、generic heartbeat、edited-only 更新：不得授權介入。
- 排程 A/B 與互動工作槽同一協定，不改 recurring cadence，不用第二套機器狀態。
- tests：`tests/process/test_issue1412_comment_takeover.py`；scheduler projection：`tests/process/test_flow_v2_execution_scheduler_view.py`。

## 導入／遷移

新規則生效後，舊的只含 monitoring heartbeat 而沒有合法 Issue 進度留言的 ongoing claim **不得被推定為失聯**。現任 owner 下次合法執行時需先補發自己的 ACQUIRED/PROGRESS（須與當前 record 完全匹配）才有有效的 10 分鐘時鐘；失敗按正常 Issue-comment API/capability 錯誤處理，不能以另一種超時門檻偷做接手。
