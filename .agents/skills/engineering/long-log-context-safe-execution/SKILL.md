---
name: long-log-context-safe-execution
description: Use when commands, tests, remote CI, pytest, Xvfb, Combined Acceptance, or other long-running jobs can produce logs large enough to overflow or repeatedly consume the execution/chat context.
whd_doc_role: CURRENT
whd_contract: long-log-context-safe-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Long-Log Handling / Context-Safe Execution

## LONG_LOG_CONTEXT_SAFE_EXECUTION_V1

超長 Log 的完整內容屬於**持久化證據**，不是日常監控 payload。核心原則：**raw log 落檔／artifact；context 只看結構化狀態、固定上限 tail、錯誤切片與 cursor 後的新內容。**

## 何時強制使用

- pytest / Xvfb / full-suite / Combined Acceptance 等輸出可能達數百到數千行。
- GitHub Actions / remote CI 長時間執行，需要多次 polling。
- 本機 command/process 持續輸出，而下一輪只需要新增輸出。
- Runtime、聊天或執行視窗可能被平台切斷，需要 checkpoint 續接。

## 強制規則

1. **禁止把完整超長 Log 灌進執行／聊天 context。** 完整 raw log 應寫入檔案、CI artifact、provider job log 或其他 durable storage；畫面與 context 只讀有限片段。
2. **正常執行只讀摘要 + bounded tail。** 每輪優先讀 process/run/job/step 狀態、iteration、PASS/FAIL/score、elapsed，以及最後固定上限 N 行。N 必須有上限，不能隨 log 成長；預設可從 80 行以下開始。
3. **FAIL 先定位、再切片。** 先搜尋 `FAILED`、`ERROR`、`Traceback`、`AssertionError`、exit code 或 provider failed-step annotation，只擷取命中點前後有限區段；不足才按 chunk 向外擴。
4. **分段反讀必須保留 offset/cursor。** 對 line/byte range、resource cursor、`next_read`、artifact offset 等記錄 `last_read_offset`；下一輪從 checkpoint 後續讀，禁止因 context 截斷就從第 1 行重讀。
5. **遠端 QA 優先結構化狀態。** polling 用 run → jobs → steps；失敗時優先 failed-job/failed-step log、搜尋或 bounded slice。若環境真的有 GitHub CLI，可用 `gh run view <run> --log-failed`；沒有 CLI 就用 connector/API 等價能力，不得假裝工具存在。
6. **provider 只能整包下載時，先落檔再搜尋。** 不得把整份下載內容直接回傳聊天；先保存 raw file，再以 grep/search/find/offset 取需要的片段。
7. **執行視窗被切斷 ≠ 工作失敗。** 恢復時先反查 durable `run_id/process_id + branch + HEAD + checkpoint + artifact/raw-log location + last_read_offset + last known state`，再續同一工作；禁止只因聊天中斷就重新跑整套測試。
8. **terminal 後才做完整 evidence 收斂。** 終態收 pass/fail counts、failed nodeids、invariants、head SHA、cleanup/drift evidence；完整 raw log 可作證據來源，但仍不必整份搬入 context。

## Checkpoint 最小欄位

長流程至少保存：`branch`、`head_sha`、`run_id/process_id`、`state`、`active_step`、`pass/fail/score`、`raw_log_path/artifact`、`last_read_offset/cursor`、`last_tail_range`、`known_failures`、`next_exact_action`。

## Context-safe 讀取策略

| 狀態 | 動作 |
|---|---|
| queued / running | structured status + bounded tail/new chunk；更新 cursor；依 owning cadence 回報 |
| failed | 搜 failure marker → bounded error slice → 必要時向外擴；raw log 留 durable storage |
| terminal success | 收 counts / invariants / HEAD / cleanup evidence；不重播整份 log |
| Runtime cut | 讀 checkpoint → 驗 branch/HEAD/run → 從 cursor 續讀；不重 trigger |

## 禁止事項

- 每次 polling 都重新 fetch / paste 整份 job log。
- 因 tool response 被截斷就從頭再抓一次超長 log。
- 用「log 太長看不到」當成重跑 full-suite 的理由。
- non-terminal 長流程等全部跑完才第一次回報；應依 owning monitoring/long-run cadence 回報狀態、iteration、score 或 bounded tail。
- 把 raw log 當成 production/domain authority；log 只提供 validation/evidence。

`monitoring-remote-qa` 擁有 remote run 的 active polling state machine；本 Skill 擁有**所有長輸出的 context-safe 讀取與續接策略**。兩者不得建立第二套互相衝突的 state machine。

## CI classifier / retry semantics bridge

`CLASSIFICATION_NOT_RUN != HANG/TIMEOUT`：classifier 尚未執行、沒有 terminal classifier record，不能推論成 hang 或 timeout。先確認 child process / job / step terminal state，再依 exact log evidence 分類。

`FLAKY_WARNING`：首次 unexpected RED、同一 exact scope retry GREEN，仍必須保留 `[FLAKY-WARNING]` 與 first-run evidence；retry GREEN 不得抹除第一次異常，也不得自動升格成 deterministic PASS 證據。
