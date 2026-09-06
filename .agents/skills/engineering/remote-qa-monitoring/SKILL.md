---
name: remote-qa-monitoring
description: Use whenever remote QA is synchronized or launched through GitHub Actions / another remote runner, especially when a workflow run must be followed through completion instead of merely being triggered.
---

# Remote QA Monitoring

## 核心原則

**啟動遠端 QA 不等於完成遠端 QA。**

只要 workflow run / remote QA job 已建立，本 Skill 立即接管到該 run 進入終態。禁止在 `queued`、`in_progress`、只完成部分 step，或「已觸發 workflow」時把回合停在進度回報。

## 觸發條件

任一成立即啟動本 Skill：
- 同步遠端 QA
- 啟動 GitHub Actions QA
- remote current-head QA
- 遠端 regression / integration / GUI gate
- 透過 GitHub Connector 建立或觸發 QA workflow

若同時命中 `git-remote-sync-fallback`，兩個 Skill 必須同時遵守：
- remote-sync Skill 管「如何安全同步內容」
- 本 Skill 管「同步後如何持續監控 QA 到終態」

## 固定監控流程

### 1. 取得唯一 run identity
建立/觸發 workflow 後，立即取得並 durable 記錄：
- repository
- branch / ref
- workflow name/path
- run_id
- head_sha
- job_id（可取得時）
- 啟動時間

禁止只記「最新 run」而沒有 run_id；後續監控必須鎖定本輪 run。

### 2. 立即進監控迴圈
反覆讀取該 run 的 jobs/steps，直到：
- `status=completed` 且 `conclusion=success`；或
- 出現明確 failed/cancelled/timed_out/action_required 等終態；或
- 遠端服務/權限/工具本身形成不可繼續的外部 blocker。

每次取得控制權後都應先更新該 run 狀態，再做其他可並行的文件/反讀工作。**不得用使用者是否追問作為下一次 poll 的觸發條件。**

### 3. 進度回報不是停工點
可依派工 Skill 做短進度回報，例如：
- run_id
- completed steps / total
- 最新 PASS 數
- 正在跑哪一批
- blocker 是否存在

但回報後必須繼續監控；禁止以「QA 已啟動」「目前正在跑」作為回合終點。

### 4. 紅燈立即抓 logs
任何 step/job 失敗：
1. 先抓該 job logs / step summary。
2. 分類：
   - production/test 真失敗
   - harness / dependency / import / DISPLAY / teardown / timeout
   - workflow 設定錯誤
3. 若屬可修正問題，直接修正、同步、重啟新的 remote QA run。
4. 新 run 取得新的 run_id 後，監控責任轉移到新 run；舊 run 保留 provenance。
5. 禁止只貼錯誤摘要後停止，除非確實存在外部 blocker。

### 5. 綠燈必須驗完整終態
只有全部成立才可宣告 remote QA GREEN：
- run status = completed
- run/job conclusion = success
- required steps 全部 success / 合法 skipped
- pytest 有完整 summary；不能只看點號或局部百分比
- 本工單要求的 config / fingerprint / invariant guard 已通過
- head_sha 是預期 current-head，不是舊 branch run
- 必要 temp workflow / trigger / probe 已清理
- durable state / journal / provenance 已更新

若 cleanup 本身會觸發另一個舊 workflow，需確認它不代表新的 acceptance run；不得被「最近一個 run」混淆。

### 6. 完成後才進工單關閉
順序固定：
1. remote QA 終態 GREEN
2. 抓完整 PASS 數與關鍵 log evidence
3. 清理 temp QA/probe files
4. 遠端反讀 production + state
5. 寫 durable checkpoint / journal / provenance
6. Issue/工單 acceptance 更新
7. 關單
8. 自動進下一張工單

不得把「關單」放在 remote QA 完成之前。

## Runtime / 回合中斷恢復

若工具回合或 Runtime 被不可抗力切斷：
- 下一次取得控制權後第一動作讀 durable state 裡的 `run_id`
- 直接查該 run，不重新觸發新的 QA
- 若原 run 已完成，直接抓結果/log；若仍在跑，續監控
- 只有原 run 明確無效或 production 已變更，才建立新 run

禁止因聊天中斷而把 remote QA 從頭重跑。

## Durable state 最低欄位

遠端 QA 進行中，工單 state/journal 至少記：
- `remote_qa_run_id`
- `remote_qa_head_sha`
- `remote_qa_status`
- `remote_qa_job_id`
- `completed_steps`
- `pending_steps`
- `last_log_evidence`
- `next_action`

QA 終態後追加：
- pass/fail/skipped summary
- config/fingerprint result
- temp workflow cleanup result
- accepted run URL/id

## Red Flags

| 錯誤想法 | 正確處理 |
|---|---|
| 「workflow 已 trigger，可以先回報」 | 回報可以，但必須繼續 poll。 |
| 「第一批測試綠了，剩下應該也沒問題」 | 不推測，監控到全部終態。 |
| 「使用者沒再問，等下次再查」 | 禁止；監控是本回合責任。 |
| 「最新 run 就是我要的 run」 | 用本輪固定 run_id + head_sha。 |
| 「Actions failure 就是 production failure」 | 先抓 logs 分類 harness / workflow / production。 |
| 「cleanup 後 workflow 又跑了，所以 QA 要重算」 | 以 accepted run_id / head_sha 判定，不混淆 cleanup side-run。 |

## Definition of Done

本 Skill 的完成不是「監控開始」，而是：

> **本輪遠端 QA 已取得明確終態、證據已落盤、需要的修正已閉環、temp remote QA 工具已清理，且工單可以安全進入 acceptance/下一張。**
