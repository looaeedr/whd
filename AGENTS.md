---
whd_doc_role: CURRENT
whd_contract: agent-startup-process
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
<!-- WHD_DOC_ROLE role=CURRENT contract=agent-startup-process -->
> **[CURRENT — PROCESS ONLY]** `AGENTS.md` 擁有 Agent 啟動、Knowledge Preflight、派工與驗收流程入口；不擁有製造公式或 ae_engine 架構真值。
> Current authority pointers：
- `個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md` — contract/role ownership map。
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md` — 現行 `ae_engine` 製造架構、公開 API 與 Certified Registry boundary。
- `AGENTS.md` — Agent 啟動、Preflight、派工與驗收流程入口。

# WHD 板金展開自動化系統

## AI 開發交接總覽

## -2. ENTRY_ROUTER_FIRST_HARD_GATE_V1：先找 canonical 入口，再做任何一般 discovery

<!-- ENTRY_ROUTER_FIRST_HARD_GATE_V1 -->

任何 WHD repository-content 任務、續作或修補，每個 invocation 的**第一個 routing sequence** 固定是：

`READ .agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json → READ .agents/skills/engineering/root-local-first/SKILL.md → ENTRY_ROUTER_READY`

`ENTRY_ROUTER_READY` 前只允許上述 bootstrap read。禁止 generic Drive/file search、Remote Desktop/local-machine search、GitHub content discovery、branch create、claim、Flow v2 discovery 或 mutation；聊天記憶、上一輪摘要、上一 invocation evidence 都不能代替 fresh read。

若已先走錯路，該段 discovery 不得算 execution evidence，固定 `FAIL_CLOSED_RETURN_TO_CANONICAL_ENTRY` 回本 executor 的 repo workspace 重新進場；不得因「已經查到了」就沿錯路續做。

machine owner=`tools/root_local_first_gate.py::assert_entry_router_action_allowed`；contract=`.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json`。

## -1. WORK_ROOT_BOOTSTRAP_HARD_GATE_V2：executor-local repo workspace

<!-- WORK_ROOT_BOOTSTRAP_HARD_GATE_V2 -->

任何 WHD repository-content task 的普通 execution root 是**該 executor 自己的 repo workspace**；不得硬編單一全域路徑。Codex 可是 `/workspace/whd`，ChatGPT/其他 runtime 使用各自 workspace。

共同 production baseline 固定 `cleanup/2d-3d-sync`。啟動只要求：

`WORKSPACE_ROOT_RESOLVED → WORKSPACE_GIT_IDENTITY_VERIFIED → PRODUCTION_BASELINE_CURRENT`

workspace 至少必須存在 `.git/.agents/.github/AGENTS.md/tools/tests/ae_engine/gui_modules`。普通 startup 不要求 Google Drive mount、`.unpushed` layout、generation/manifest 或 `workspace_canonical_sync.py`。

canonical contracts：
- `.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json`
- `.agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json`
- `.agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json`（HISTORICAL/SUPERSEDED data contract only）

machine owners：`tools/work_root_gate.py`、`tools/root_local_first_gate.py`。

## -0.75. WORKSPACE_BASELINE_BEFORE_WRITE_HARD_GATE_V1

<!-- ROOT_LOOKUP_BEFORE_REMOTE_HARD_GATE_V1 -->

普通 repository-content task 的 baseline 直接由 executor-local workspace 對齊 GitHub `cleanup/2d-3d-sync`。允許窄化 baseline actions：`READ / FETCH / COMPARE / BRANCH_READ / REPO_METADATA_READ`。

硬規則：
1. 修改與測試在 executor-local workspace 完成。
2. production target 禁止 direct push；只接受 exact tested delivery branch → PR → required checks → merge。
3. target 前進時 refresh baseline；碰到 touched path 就 retest，再 delivery。
4. GitHub baseline read 不等於一般 Issue/PR/Actions 或任意 remote authority；Skill 自動觸發也不會擴張 authority，非 baseline 動作仍走原 authority gate，未授權固定 `REMOTE_CONNECTION_DENIED`。
5. Google Drive / `.unpushed/{docs|body}/0` / shared-zero 全部退出 CURRENT repository-content routing；不得因其存在、缺失或 drift 改變施工 route。
## -0.5. ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1：workspace-only current route

<!-- ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1 -->

schema 名稱保留作相容入口；CURRENT repository-content route 永遠是 `WORKSPACE_DEFAULT`。

- `shared_zero_drift_present=false → WORKSPACE_DEFAULT`
- `shared_zero_drift_present=true → WORKSPACE_DEFAULT`；舊 drift 只記 historical evidence，不得切換 route。
- Drive mount、Drive mirror、舊 pointer、`.unpushed` 缺失都不是 blocker。
- executor-local repo workspace 不存在或不可執行 edit/test 時，才 `HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX`。
- 普通 CURRENT 流程：`fresh X baseline → workspace edit/test → exact diff → delivery branch → PR/checks → merge/readback`。

### N. Workspace-first Git delivery gate

- interactive/default content work 先在 executor-local workspace 對齊 `cleanup/2d-3d-sync`，再修改與測試。
- baseline `READ / FETCH / COMPARE / BRANCH_READ / REPO_METADATA_READ` 不需 `/推推` authority。
- 禁止直接修改/push `cleanup/2d-3d-sync`、`main` 或其他 production target；exact tested diff 只能進 delivery branch。
- delivery branch → PR → required checks → merge/readback 是普通主路。
- target drift 命中 touched paths 時必須 refresh/reconcile workspace、重測，再更新 delivery candidate。
- Drive/shared-zero 不再有 CURRENT delivery path；`/推推` 只是顯式 delivery alias，不得把流程導回 Drive。
- remote scheduler/control-plane scope 依 Flow v2 自己 authority，不得拿普通 workspace baseline read 擴張 control-plane mutation。

### 0.0.4 Authoritative View freshness 硬閘門

> **authoritative state 已更新，不代表操作員目前看到的 View 已刷新。兩者是不同 invariant。**

凡 Main GUI / Fold Designer / 2D / 3D 共用 authoritative state 的同步或入口收斂任務，必須同時驗證資料同源與可見 View freshness：

1. authoritative mutation / external sync 必須先完成 commit/apply/invalidate，再由 View 重新讀 authoritative projection / render data。
2. 若 `corner_data` / 截角資料 View 當下可見，每個新的 authoritative revision 套用成功後**剛好刷新一次**。
3. hidden View 不得 eager refresh；replayed / stale revision 必須 no-op，不得重刷。
4. repeated authoritative revisions 必須維持「一個 commit 對應一次 visible refresh」，不得漏刷或雙刷。
5. 禁止 widget-to-widget 抄值作同步；View refresh / destroy / recreate 不得寫回 manufacturing state、available parts、CornerType、Fold Profile、holes/features 或 persistence payload。
6. 驗 dual-view parity 不得只比 Final Material / DXF / Save→Reload；還必須有 visible refresh、hidden no-refresh、replayed revision no-op、repeated revisions、View recreate zero-mutation 的證據。
7. 發現「資料正確但畫面仍舊」時，先查 authoritative commit → invalidate/apply → visible View refresh orchestration，不得另建第二套 geometry/state 當 workaround。


### ISSUE100_LEGACY_2D_ENTRY_RETIREMENT_RULE

退役 UI 入口時，先切斷「使用者可達入口 / navigation authority / identity authority」，不得因名稱看似 legacy 就盲刪仍被新入口共用的 renderer/helper/callback state。若暫留 compatibility state，必須 user-unreachable、non-navigation、non-manufacturing-authority，並以 runtime navigation + capability preservation 驗收。
