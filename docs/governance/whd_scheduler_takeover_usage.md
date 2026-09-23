---
whd_doc_role: REFERENCE
whd_contract: scheduler-takeover-operations
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 排程停滯接手使用手冊

本文件說明 recurring WHD scheduler 如何在無人互動時偵測停滯、接手既有 execution claim、消耗 Remote Guard authority，並在同一 execution cycle 繼續真正施工。它是操作手冊；ownership、closure、continuity 的 canonical authority 仍由對應 Skill 與 executable guard 擁有。

## 1. 核心模型

- scheduler lane 是 durable owner key，例如 `scheduler.<automation-id>`；每次喚醒都是新的 AI runtime，不是假設同一個背景程序一直活著。
- schedule 只負責 wake-up；真正狀態來自 GitHub durable authority：`coord/dispatch-claims`、checkpoint、Issue、branch、PR、exact Actions run。
- 每輪都要 dynamic discovery；禁止把 issue、child、branch、SHA、run_id 寫死在判斷流程。
- recurring lane 要長期保持 enabled。單輪 blocked、foreign owner active、WAITING_REMOTE、平台切斷，都只代表本輪可以結束，不代表 automation terminal。
- `:00` / `:30` sibling lanes 可以同時 enabled，但同一 executable leaf 同時只能有一個 claim owner。

## 2. 每輪標準流程

```text
wake
→ fresh-read coord/dispatch-claims
→ 排除 RELEASED/CLOSED/terminal/null-next_action/controller
→ 找 executable leaf
→ fresh-read Issue + claim + branch + checkpoint + exact run
→ 判斷 same-lane / foreign owner
→ 執行 next_action
→ 若需要 mutation：Remote Guard request
→ lock exact Guard run
→ machine GREEN receipt
→ 立即 consume 對應 mutation
→ fresh readback
→ 更新 claim/checkpoint
→ 同輪繼續下一步
```

狀態回報不是 exit condition。只要 same-lane 還有 executable `next_action`，就繼續。

## 3. Same-lane 與 foreign owner

### Same-lane

若 `claim.worker == scheduler.<本 lane>`：

- 不做 stale takeover；
- 不因 `ACTIVE_WITHIN_10M` 停工；
- 從 durable claim/checkpoint/exact run 直接 resume；
- 有 non-terminal exact run 就只 poll 同一 run；
- terminal success 立即 reconcile，再做下一個 action。

### Foreign owner

若 `claim.worker != 本 lane`：

- newest durable progress < 600 秒，或 exact run 為 queued / in_progress / waiting / pending / requested：分類 `FOREIGN_OWNER_ACTIVE`，本輪退讓，不 mutation、不 duplicate Guard。
- 只有沒有 active exact run 且 durable progress age >= 600 秒，才可走 canonical stale takeover。
- sibling scheduler 也是 foreign owner，沒有特權。

## 4. Stale takeover：request → GREEN → CAS → continue

合法 takeover 固定是：

1. fresh-read foreign claim、live branch HEAD、claim blob、authority；
2. 建立 owner-authored Issue top-level comment，第一行：
   `WHD_REMOTE_GUARD_REQUEST_V1`
3. `action=claim-takeover`，`executor_source=scheduler`，帶 exact old worker / claim H0 / live H1 / claim blob / authority；
4. 鎖定新產生的 `WHD Remote Execution Guard` exact run，poll 到 terminal；
5. job success 不等於 GREEN；必須讀 `WHD_REMOTE_GUARD_RESULT_V1` machine receipt；
6. receipt exact match 且未過期才做 claim CAS；
7. fresh-read claim 確認 scheduler 成為 owner；
8. **同一 cycle 立刻 fresh-read next_action 並繼續施工**。

禁止「拿到 GREEN 後只回報」、「CAS 後只說已接手」。

## 5. GREEN receipt 是 single-use mutation authority

Remote Guard GREEN 不是 session token。

- `claim-takeover` → claim CAS；
- `write` → exact path write/delete + verify；
- `commit` → exact changed-file set 的單一 atomic commit；
- `pr-write` → exact PR create/update/merge/close；
- `qa-dispatch/workflow-dispatch` → exact target dispatch + lock run。

新 invocation 開始時，要先找同 lane 尚未 consume 的 GREEN。identity、claim blob、HEAD、branch、changed_files 仍 exact match 就直接 consume；drift 或 expiry 才能重發。

## 6. Remote QA 與 stale snapshot

claim/checkpoint 裡的 remote status 只是 snapshot。每次 resume 都以 GitHub live exact run 為準：

- snapshot 寫 queued，但 live run 已 success → 立即 reconcile、cleanup、drift audit、closure；
- snapshot 寫 waiting，但 live run failure → 立即讀 failed job/log，repair；
- active exact run → poll 同一 run，不 duplicate dispatch。

## 7. Post-commit claim HEAD reconciliation

合法 mutation 讓 work branch `H0 → H1`，claim 還停 H0 時：

- 不 stale-takeover 自己；
- 不直接手改 claim；
- 使用 current `POST_COMMIT_CLAIM_HEAD_RECONCILIATION_V1` 窄路徑；
- Remote Guard `action=write`，changed_file 唯一為 exact claim path，`head_sha=tested_target_sha=H1`；
- GREEN 後 CAS claim HEAD 到 H1，再 fresh-read。

## 8. Trusted finalization

terminal checkpoint 不能靠手寫 marker 關票。

目前 trusted executor：`.github/workflows/whd-remote-finalization.yml`。

若 workflow 支援 `issue_comment: created`，runtime 只要能建立 owning Issue top-level comment，就有 finalization trigger capability。固定 marker：

`WHD_REMOTE_FINALIZATION_REQUEST_V1`

只允許 fixed identity fields：issue、worker、branch、head_sha、checkpoint path/blob/fingerprint、claim blob、guard authority SHA。

必須取得：

- exact `WHD Remote Finalization` run terminal success；
- `WHD_REMOTE_FINALIZATION_RECEIPT_V1`；
- `reason=FINALIZATION_PROOF_VALID`；
- bound proof artifact；
- exact identity 全部吻合。

之後才 close Issue → fresh readback `closed/completed` → guarded claim release。

## 9. Reopened Issue + RELEASED claim

若 Issue 因 invalid finalization evidence 被 reopen，而舊 claim 已 RELEASED：

- RELEASED 只代表前一輪 process-state，不代表 reopened Issue 已完成；
- 不得用 same-lane stale takeover；
- 若 current guard 缺少合法 recovery capability，先完成 blocking governance repair child；
- repair integrated 後回原 Issue，重新執行 fresh trusted finalization；
- 舊 finalization receipt 若已被前一次 closure 消耗，不能跨 reopen 重用。

## 10. 手動操作方式

需要人工立即測試 scheduler 時，手動執行既有 automation 即可；不要另建一次性 automation，也不要把 Issue 編號寫進 prompt。

觀察順序：

1. `coord/dispatch-claims`：誰是 owner、phase、next_action、head；
2. owning Issue：Guard request/result 與 process evidence；
3. GitHub Actions：鎖 exact run，而不是只看最新一顆；
4. PR / target branch：確認真正 mutation 是否發生；
5. claim/checkpoint：確認 durable readback 已追上 live state。

## 11. 常見故障

- **只講狀態沒施工**：檢查 `NON_TERMINAL_CONTINUE` 與 GREEN 是否未 consume。
- **重複觸發 Guard**：先找上一輪未 consume GREEN 或同 lane active exact run。
- **誤判 stale**：600 秒只適用 foreign owner；same-lane 不做 takeover。
- **workflow_dispatch 不可用**：先 fresh-read finalization workflow；若支援 fixed Issue-comment transport，不是 capability blocker。
- **Guard job success 但不能 mutation**：machine receipt 可能 FAIL；一定讀 result/reason。
- **branch HEAD 已前進、claim 還舊**：走 post-commit claim-head reconciliation，不 self-takeover。
- **PR/QA 已完成但 claim 還寫舊 next_action**：live state 高於 snapshot，先 reconcile durable state再繼續。
- **某輪 fully blocked**：只結束該 invocation；recurring lane 保持 enabled。

## 12. 成功證據最低集合

每次重要 mutation 至少保存：

- issue / worker / executor_source；
- claim blob；
- work branch / base / head；
- Guard request/result comment IDs；
- exact Guard run_id、result、reason、expiry；
- mutation 後 commit/ref/PR/run identity；
- fresh readback；
- remote QA run + tested head + pass/fail；
- terminal checkpoint blob/fingerprint；
- finalization run + proof artifact；
- Issue close/readback + claim release。

歷史 run / issue 只能作 provenance，不能取代每輪 fresh identity。
