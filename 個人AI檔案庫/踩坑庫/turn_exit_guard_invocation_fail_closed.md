---
whd_doc_role: REFERENCE
whd_contract: turn-exit-guard-invocation-pitfall
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Turn-exit guard invocation fail-closed pitfall

## Incident

只有「有 checkpoint」或「checkpoint JSON 合法」不足以證明 assistant turn 可以結束。若 worker 沒有載入正確 owner 的 checkpoint，或根本沒有實際呼叫 canonical turn-exit guard，仍可能在 `RUNNING / WAITING_REMOTE / RECOVERING` 狀態下提前停止。

## Root cause

把 durable state existence 與 executable guard execution 混成同一件事：

- checkpoint 可存在但屬於別的 issue / branch / head；
- checkpoint 可合法但已 stale；
- caller 可讀取 checkpoint 後自己重算 state，完全繞過 `assert_turn_exitable()`；
- 文件裡有 guard command 不代表本次 turn 真正執行過；
- 舊的 guard 結果在 checkpoint 改寫後不能再當授權。

## Permanent rule

Turn exit 必須同時具備三個條件：

1. **Valid owning checkpoint**：checkpoint 存在、可讀、schema 合法，而且 `issue + branch + head_sha` 與 active execution context 精確一致。
2. **Actual canonical guard invocation**：path-level boundary 必須真的呼叫 `assert_turn_exitable(checkpoint)`，不能複製 state logic 或只看 checkpoint 存在。
3. **Current guard invocation proof**：成功 guard invocation 必須產生綁定 owning identity 與 checkpoint content digest 的 machine-verifiable proof；外層 boundary 必須驗證 proof。

任何一項缺失都必須：

```text
FAIL_CLOSED
```

具體分類：

```text
NO_VALID_OWNING_CHECKPOINT => FAIL_CLOSED
NO_ACTUAL_GUARD_INVOCATION => FAIL_CLOSED
NO_CURRENT_GUARD_INVOCATION_PROOF => FAIL_CLOSED
STALE_OR_OWNER_MISMATCHED_PROOF => FAIL_CLOSED
```

Checkpoint 只要在 guard 後改寫，舊 proof 立即失效。

## Machine regression requirement

`tests/process/test_issue321_turn_exit_enforcement.py` 必須保護：

- missing / malformed checkpoint；
- valid JSON 但 foreign owner；
- autonomous non-terminal state 不得 mint proof；
- path boundary 必須實際呼叫 canonical guard；
- valid owning checkpoint 但無 proof 仍拒絕；
- successful guard invocation 才能 mint bound proof；
- checkpoint 改寫後 proof stale。

Canonical operational authority 仍是 `.agents/skills/engineering/executable-continuity-controller/SKILL.md`；本檔只保存事故與防錯經驗。