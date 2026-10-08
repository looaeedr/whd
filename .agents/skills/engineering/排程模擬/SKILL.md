---
name: 排程模擬
description: WHD A/B recurring scheduler lane 與 /排程A、/排程B same-lane resume 入口。只透過 Flow v2 ExecutionRecord、lease/YIELD 與 structured next_action 執行。
whd_doc_role: MIRROR
whd_contract: scheduler-interactive-lane-resume
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 排程模擬

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並留下符合 runtime surface 的 startup communication evidence：interactive chat=user-visible；scheduler/Codex/headless=machine-visible。AI Library 只在實際具有 ChatGPT surface 時適用；缺 transport 不得成為 startup blocker。之後完成 project Phase6 Preflight；不得沿用前一 runtime declaration。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Lane identity
- A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`；entrypoints=`00/20/40`。
- B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`；entrypoints=`B15/B45`。
- entrypoint 不是 owner；scheduled 與 interactive resume 必須保存真實 invocation provenance。

### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1

新 scheduler invocation 尚不知道 exact owning Issue 時，先依 canonical Flow v2 執行 narrow `READ_ONLY_BOOTSTRAP_ONLY` 綁定 Issue/branch/HEAD；沒有 ChatGPT AI Library surface 時記 `NOT_APPLICABLE_NO_AI_LIBRARY_SURFACE` 並繼續，禁止回 `PROJECT_STARTUP_HARD_GATE_FAILED`。bootstrap 不是 execution authority，完成 trusted Phase6 admission 後必須 fresh-read canonical scheduler state再進 WAKE。

### RETIRED_SHARED_0_SCHEDULER_HISTORY_V1

- `.unpushed/docs/0`、`.unpushed/body/0`、shared-zero generation/freeze 與 Drive readback 已退出 CURRENT scheduler/content routing。
- 排程 A/B 與工作槽不得因 Drive/shared-zero 不可見、舊 drift、舊 lineage 或舊 pointer 改變 next_action。
- repository-content 只可 handoff 到 workspace-capable runtime，再固定走 `WORKSPACE_DEFAULT`。

scheduler invocation 在 project startup 階段還不知道 exact owning Issue，先依 canonical Flow v2 做 `READ_ONLY_BOOTSTRAP_ONLY`：只讀 `coord/execution-v2`、derived ready-index、`coord/monitor-v2:.dispatch/monitor/runtime/*.json` 的 NON_AUTHORITY runtime observations、`tools/execution_scheduler_view.py` scheduler projection 與 Issue/branch/HEAD identity；scheduler view 順序固定為 same-lane current → `TAKEOVER_CANDIDATE` → READY → explicit ingress。只有前三者都空時，才額外用 `tools/scheduler_ready_ingress.py` 掃 repository-owner-authored open Issue 第一個 nonblank marker `WHD_SCHEDULER_DISPATCH_REQUEST_V1`（可帶 `lane=ANY|A|B`），用來綁 trusted Phase6 Preflight request。A/B scheduler 綁定 exact Issue 後，先 fresh-read owning Issue 的 trusted Phase6 results：若存在同 lane、同 Issue/branch/HEAD、40 分鐘內的 push GREEN receipt，固定用 `WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1` 交給 trusted transaction ingress rebind；只有沒有 eligible receipt、receipt expired 或 exact branch/HEAD 已漂移時，才 existing-file CAS 到 `coord/preflight-requests-a|b:.dispatch/preflight-request.json` 發新 Preflight。**禁止 scheduler 自己建立 Issue request comment，也禁止有可 consume GREEN 時重複 mint Preflight**。普通 open Issue 不得推論成 work authority。此 bootstrap projection 不得授權 claim、ACQUIRE、transaction、Guard 或 repository mutation。host entrypoint observation 依 canonical fixed NON_AUTHORITY exception 可寫。

Preflight GREEN（包含 trusted bot receipt 被同 lane下一 invocation合法 rebind 的 GREEN）且 required Skill/reference 全部 fresh-read 後，必須丟棄 bootstrap projection，再 fresh-read canonical scheduler state，才進入下面的 Wake。receipt rebind 只重綁 invocation，不改 task/Issue/branch/HEAD/requirements，TTL 固定 40 分鐘；任何 identity drift fail closed。禁止建立永久 bootstrap Issue，也不得把這個 bridge 擴張成第二套 scheduler authority。

### ISSUE_COMMENT_10MIN_INTERVENTION_BRIDGE_V1

排程 A/B 的 foreign Issue 介入資格固定橋接到 `flow-v2-execution::ISSUE_COMMENT_10MIN_INTERVENTION_HARD_GATE_V1`：

- native ACQUIRE 完成立即在 owning GitHub Issue 留目前 owner、lane、slot、HEAD、generation 的 `WHD_ISSUE_OWNER_PROGRESS_V1` 接取留言，執行中每 10 分鐘留一次具體的進度、阻礙與下一步；純 HEARTBEAT 不算進度。
- foreign Issue 的候選判定必須 fresh-read 該工單留言，再由 `tools/execution_scheduler_view.py::build_scheduler_view(issue_comments=..., trusted_comment_authors=...)` 投影。**<=600 秒禁止介入；>600 秒才可進正式 atomic HANDOFF/ACQUIRE**。missing comments、identity mismatch 都不得推論超時。
- 舊 parent/child lineage、lease、heartbeat、runtime END、QA run 判活一律退出**介入時間判斷**；正常 machine CAS/單寫者/QA fencing 不變。接手成功後立即留言新 `TAKEOVER` owner 並續跑 exact `next_action`，不要求人工二次確認。

## Wake
每次 host wake 先以 `tools/scheduler_entrypoint_observation.py` 寫 exact entrypoint NON_AUTHORITY WAKE，再 fresh-read `coord/execution-v2` 與 owner runtime observations。優先 same-lane nonterminal record；若沒有 current，`execution_scheduler_view.py` 必須先 fresh-read Issue comments 並套用 `ISSUE_COMMENT_10MIN_INTERVENTION_HARD_GATE_V1`，有 `TAKEOVER_CANDIDATE` 時立即對 deterministic `selected_issue` 做 HANDOFF 到本 scheduler lane，fresh-read 後 ACQUIRE，並同 invocation 續原 exact `next_action`。只有沒有 takeover candidate 才讀 READY；current/takeover/ready 都空才做 explicit marker discovery。只有 current/takeover/ready/explicit candidate 全空才可回 NO_EXECUTABLE_WORK。正常 return 前必須寫 exact entrypoint EXIT；不能再留下 SEED-only host occurrence。

`RESUME_CURRENT` 若先 ACQUIRE，ACQUIRE 後同一 invocation 必須立即 fresh-read並執行原 exact `next_action`；不得把拿到 lease 當 progress/停止點。`TAKEOVER_CANDIDATE` 必須使用 scheduler view 的 deterministic `selected_issue` 與 `build_takeover_handoff_effect(...)`，先 HANDOFF、fresh-read，再 ACQUIRE，然後立即續 HANDOFF 前保存的 exact `next_action`；HANDOFF/ACQUIRE 都不是停止點。`READY_CANDIDATES` 才是下一順位，使用 deterministic `selected_issue` 立即 ACQUIRE；`INGRESS_REQUIRED` 必須先建立 exact READY，再 fresh-read/ACQUIRE，且 `DISPATCH_READY` 不算 substantive progress。race/conflict後 fresh-read重選。

正常 return 前必須通過 canonical `SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1`：WAKE/讀取/回報/HEARTBEAT/單獨 ACQUIRE 都不算 substantive progress。只有 DONE、LANE_BUSY、合法 BLOCKED、active remote QA wait，或本 invocation 已完成 substantive transaction 後的合法 YIELD 可離開；`SCHEDULER_EXECUTION_NO_PROGRESS` 必須繼續施工，不得停止。

## REPOSITORY_CONTENT_ROUTING_HARD_GATE_V2

排程A/B 可以擁有 Flow v2 control-plane lease/next_action，但 **scheduler execution mode 不授予 repository-content authoring**，也不得把 handoff 綁死到 `/Google Drive/WHD`。

- 若 exact next_action 只需要 read/discovery、lease/coordination、trusted preflight、既有候選的 QA/merge/finalization，排程可直接執行。
- 若 next_action 需要新增、修改或刪除 repository content，固定 `HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX`；接手 runtime fresh 解析自己的 executor-local repo workspace，CURRENT route 固定 `WORKSPACE_DEFAULT`。
- **Drive mount、mirror、舊 shared-zero drift 都不是 scheduler content-handoff 的判定條件，也不得形成 blocker。**
- 任何 route 都不得在未測 GitHub branch 直接 author / patch / hotfix；GitHub 只承接已測 exact diff 與 post-push CI/QA/merge。
- handoff 不等於停止：scheduler 必須保存 exact structured next_action；candidate/delivery 出現後立即接回 post-push integration tail。

<!-- REPOSITORY_CONTENT_ROUTING_HARD_GATE_V2 -->

## Lifecycle

<!-- SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1 -->

本入口不複製 host recovery state machine；startup 前的 host-layer recovery 唯一服從 `flow-v2-execution::SCHEDULER_HOST_RECOVERY_BOOTSTRAP_V1`。正常 Flow v2 execution 仍不得管理 host lifecycle。任何 task-level結果都只是 physical cycle return，固定保留 `CYCLE_END — KEEP_SCHEDULE_ENABLED` 語意。

相容 hard gate 保留原 literal：`不得自行 disable/delete/complete/reschedule自己或 sibling`；此限制適用於正常 Flow v2 execution，canonical host-recovery micro-bootstrap 不擴張 execution authority。

### HOST_LIFECYCLE_WATCHDOG_V1 bridge

scheduler invocation 在 project startup hard gate 完成後、寫 WAKE 前，可且應執行 **read-only host lifecycle inspection**，取得 A00/A20/A40/B15/B45 的 task `enabled / last_run_time`，並以 NON_AUTHORITY snapshot CAS 更新 `coord/monitor-v2:.dispatch/monitor/host/chatgpt-automations.json`。此為唯一 read-only automation introspection 例外；禁止任何 lifecycle mutation API。

每個 entrypoint 必須把自己的 WAKE/HEARTBEAT/PROGRESS/EXIT 同步 mirror 到 exact entrypoint observation file，固定由 `tools/scheduler_entrypoint_observation.py` 建立 canonical `WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1`。WAKE 可在 project startup 前寫入 fixed host-layer path；每個正常 return 都要有 EXIT，所以 host run 不得停在 SEED-only。host snapshot 與 entrypoint mirror 都只是 observability，不可當 claim/lease/transaction authority。

獨立 GitHub watchdog workflow 已退役並移除。需要判讀 host occurrence 時，由當次 scheduler invocation 或 explicit diagnostic 直接呼叫 canonical `tools/scheduler_host_watchdog.py` 讀 NON_AUTHORITY snapshot；不得另建 recurring GitHub Actions watchdog。120 秒 grace 的 `HOST_ENTRY_FAILURE / HOST_AUTO_PAUSE / HOST_STATE_UNKNOWN` 分類語意仍由 evaluator 擁有。


## REPORT_HANDLER_IDENTITY_PREFIX_V1

所有 `/排程A`、`/排程B`、A00/A20/A40/B15/B45 的 **user-visible** progress / CHECKPOINT / terminal / exit 回報，**第一行**固定為：

`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>｜slot=<worker.slot.N|NONE|UNBOUND>｜invocation_identity=<exact invocation_identity>】`

- machine owner 固定為 `tools/runtime_report_identity.py`；所有 progress / CHECKPOINT / terminal / exit 必須先經 `build_runtime_report_identity(...)` 驗完整 identity，再由 `format_runtime_report_prefix(..., event=...)` 產生第一行。`TERMINAL/EXIT` 必須帶 current `WHD_FLOW_V2_HOST_EXIT_PROOF_V1`，由 `build_host_exit_proof(...)` mint、formatter 以 `validate_host_exit_proof(...)` 對 fresh ExecutionRecord 重驗；`may_return=false`、缺 proof、stale proof 一律禁止正常 return。progress/CHECKPOINT 不是 exit authority。缺欄、空白或 invocation_identity=`NONE/UNBOUND/UNAVAILABLE` 一律 fail closed；不得手工拼 prefix 冒充合法回報。

相容核心模板：`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>】`。

- handler 只可為 `排程A` 或 `排程B`（或 exact interactive work-slot handler），不得把 entrypoint、foreign lane 或其他 runtime 冒充處理者。
- scheduler 回報必須 fresh-read `lane_owner`、`claim_issue`、`claim_worker`；owner 必須是 real claim owner，不得因目前由排程A/B喚醒就改寫 ownership。
- 沒有 active Issue 時工單=`NONE`；有 bootstrap projection 但尚未 durable bind 時=`UNBOUND`。slot 沒有 exact binding 時=`NONE/UNBOUND`，不得猜。
- foreign owner / foreign lane 只能明確標示 foreign，不得偽裝成本 lane owner。
- `invocation_identity` 必須取本輪 exact scheduler host/runtime observation；不得省略、不得用 entrypoint 名稱或 `last_run_time` 猜。
- 此 prefix 只提供 provenance，**不建立 execution authority**；ownership authority 仍是 canonical ExecutionRecord + lease。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。


## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。

對 `SCHEDULER_LANE`，startup declaration 必須先於任何 claim 或 mutation，並明確保留本 invocation 的 lane/entrypoint provenance；若沒有已成立的 durable resume authority，`resume_authority=NONE`。
