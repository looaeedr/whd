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
