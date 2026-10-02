---
whd_doc_role: REFERENCE
whd_contract: pitfall-ledger
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# 超長 Log / Context-Safe Execution 踩坑

## LONG_LOG_CONTEXT_SAFE_EXECUTION_V1

### 事故模式

長 pytest / Xvfb / Combined Acceptance 或 GitHub Actions 產生數千行輸出時，若每輪監控都把完整 Log 重新抓進執行／聊天視窗，會快速耗盡 context、造成 tool response 截斷，甚至讓 Runtime 被切斷。切斷後若又從頭重讀或重跑 full-suite，就形成「越查越長、越長越重跑」循環。

### 根因

- 把 raw log 當成監控畫面，而不是 durable evidence source。
- 沒有 tail 上限與 offset/cursor，導致每次都從頭讀。
- FAIL 後不先定位 failure marker，直接下載／貼整包 log。
- 把聊天 Runtime 誤當 remote process lifecycle owner；視窗一斷就重 trigger。

### 永久規則

- 完整 raw log 落檔、artifact 或 provider job log；context 禁止整包灌入。
- running 期間只讀 structured state、進度、PASS/FAIL/score 與 bounded tail；固定上限，不因 log 變長而擴張。
- FAIL 先找 `FAILED/ERROR/Traceback/AssertionError` 或 failed step，再讀前後有限區段；不足才分段向外擴。
- 每次 chunk read 保存 line/byte offset 或 cursor；context 被裁切也從 checkpoint 續讀，不從頭重讀。
- GitHub Actions polling 優先 run/jobs/steps；有 `gh` 才用 `gh run view ... --log-failed`，沒有就用 connector/API 的 failed-job/bounded-search 等價路徑。
- provider 只能整包下載時，先保存 raw file，再在檔案上 search/tail；禁止把整包回傳聊天。
- 執行視窗被切斷不等於工作失敗。恢復順序：反查 run/process → branch/HEAD → durable evidence/artifact → cursor → latest state → next exact action；禁止先重跑。
- terminal 後才收斂完整 evidence；raw log 是證據來源，不是每次監控都要搬進 context 的內容。

Canonical execution rule：`.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`。Remote QA state machine 仍由 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 擁有。

<!-- QA_PIPELINE_FAIL_CLOSED_V1 -->
## QA pipeline 假綠 / movable baseline 踩坑（2026-09-14）

### 事故模式

T5 GUI modularization 曾出現 `pytest ... | tee` 與 `python validator.py | tee` 左側已 FAIL，但 GitHub step/job 因 `tee` exit 0 顯示 SUCCESS。另一個 Move-Only validator 同時使用 movable branch ref、並把可繼承呼叫 symbol 的 public subclass 誤認成真正 owner，造成驗證結果不可信。

### 根因

- shell pipeline 未啟用 `pipefail`，wrapper 的成功遮蔽真正 validator/test failure。
- 把 CI 綠燈顏色當 acceptance authority，沒有反讀 pytest/validator terminal summary。
- baseline 用 branch name 而非 immutable accepted SHA，驗證基準可在執行途中漂移。
- 由 public API surface 猜 class owner，沒有用 AST/原始碼確認實際定義位置。

### 永久規則

- fail-significant command 只要經過 pipe/`tee`，必須 `set -o pipefail`（或等價取得左側 exit status）；沒有這條的舊 GREEN evidence 一律不得沿用。
- Acceptance 同時要求：workflow terminal + 實際 test/validator terminal summary + exact tested `head_sha`。
- Characterization / Move-Only 比較基準固定寫 immutable accepted commit SHA；禁止 movable branch ref。
- owner/class 由 AST dependency inventory 或 exact source reread 確認；繼承可見性不等於 ownership。
- 發現假綠後要回溯原 log 重新分類，不能為了維持 GREEN 去改 production 配合 stale test。

## CI classification addendum
`CLASSIFICATION_NOT_RUN != HANG/TIMEOUT`：看到 step 長時間不換畫面，只能說 classifier 尚未完成或尚無新 observation；必須讀 terminal state / bounded log evidence 後才能判 hang/timeout。

`FLAKY_WARNING`：unexpected RED 若同 scope retry GREEN，保留首次 RED 的 node/reason/log evidence並標記 `[FLAKY-WARNING]`，不得用 retry GREEN 覆蓋第一次異常。
