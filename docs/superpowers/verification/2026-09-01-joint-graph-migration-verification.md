# 2026-09-01 Joint Graph Migration Verification

## Scope

依 `docs/superpowers/specs/2026-08-31-phase6-joint-graph-migration-spec.md`，把 Assembly preset、Resolved AssemblyJoint Graph、STANDARD/Certified Relief、blank/piece dimensions、Receiving BOTTOM WRAP、replay/diagnostics 收斂到單一可驗證資料鏈。

## Implemented contracts

- Assembly Intent Registry 提供 explicit TOP/BOTTOM/LEFT/RIGHT default Joint Map；WRAP 是 Joint relation，不是獨立 EndCap selector。
- Joint schema v2 保存 edge/direction/contact/preserve/clearance/relief/solver/source/revision；schema-1 side-only graph 可一次 migration 成四邊 graph，explicit/user data 優先。
- UI preset mirror 與 Joint Graph 分離；正常 redraw/load 不再用 Top CornerType 重寫 graph/corner state。
- Corner resolver 讀 nearby joints；Certified Registry runtime 支援 rule-owned multi-stage topology。
- `ENDCAP_TOP_OVERLAY_STANDARD_V1@3` 使用 STANDARD `40×41` + OVERLAY Semantic Delta，產生 `40×39 + 15×2`；formed FW=29 降級為 shadow/historical evidence。
- blank W×H 由 material segment chain / physical piece topology 決定，local relief 只改 area/material polygon。
- Receiving bottom assembly meaning 由 BOTTOM Joint 決定；Family 只提供 geometry/reserve，無 WRAP joint 時保持 STANDARD。
- replay signature 納入 Joint mechanical semantics、family structure、cabinet family、Fold Profile 與 registry revision，並正規化 legacy region alias/provenance。
- diagnostics 已 joint-local；BOTTOM WRAP 不再借用 TOP rule trace。

## Regression evidence

執行採單模組/逐 case，避免 GUI 長檔 timeout 被誤判。到 T8 收斂時，已覆蓋：Assembly/Joint/Registry、Receiving、blank/piece、Save/Reload、2D/單板3D/組合3D、DXF、Workspace/GUI presence、project file、settings、collision/replay/diagnostics。外部 `/mnt/data/自訂*.p6fold` 不存在時只 skip 專用 external-fixture case，不以其他 fixture 假冒。

正式 release 前仍必須重新執行 Skill preflight、release integrity、registry-driven Head/Tail/zero-penetration matrix，並從打包後重新解壓的 FULL 再跑正式 gate。

## Historical fixtures

2026-08-29 的 formed-FW 29、OVERLAY rule@2、replay v2 文件保留作歷史證據；2026-09-01 runtime specification 以 Joint Graph + STANDARD + Certified Semantic Delta 為準。

## Release constraints

- `config.ini` 不得修改。
- UPDATE 唯一基準：`PHASE6_FW_LINK_BUGFIX_FULL_20260823_212355(3).zip`。
- FULL/UPDATE 共用 Asia/Taipei `YYYYMMDD_HHMMSS`。
- UPDATE 強制包含 `個人AI檔案庫/**`，禁止 `config.ini` / BACKUP / cache。
- `skills/ → .agents/skills/` cleanup 依 `release_required_artifacts.json:update_cleanup_paths` 與 cleanup tool 執行。

## Final QA / Release Evidence — 2026-09-01

### Worktree QA

- Skill preflight / skill contracts: 11/11 passed.
- Release policy / integrity: 12/12 passed.
- Joint Graph / Registry mandatory matrix: 73/73 passed.
- Registry / Joint / diagnostics / Receiving WRAP high-risk matrix: 62/62 passed.
- Assembly GUI matrix: 3/3 passed.
- Blank / physical-piece topology: 6/6 passed.
- Single-source 3D renderer: 20/20 passed.
- Tail native orientation / save: 6/6 passed.
- Project Save/Reload: 19/19 passed.
- #126–#166 module QA finished without assertion failures; external user `.p6fold` cases only skip when the named `/mnt/data/自訂*.p6fold` fixture is absent.

### Packaging evidence

Canonical baseline library source is the original archive `PHASE6_FW_LINK_BUGFIX_FULL_20260823_212355.zip` from the same 2026-08-23 21:23:55 release. Its archive CRC is clean, archive root is project-root layout, and `config.ini` SHA256 is `5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`. The local `(3)` filename is treated only as the user's duplicate-download filename required by release policy; archive bytes are not modified.

Release collector validation proved:

- FULL and UPDATE use one Asia/Taipei timestamp.
- FULL includes current complete project tree and unchanged `config.ini`.
- UPDATE excludes `config.ini`, includes all mandatory artifacts and all `個人AI檔案庫/**` files.
- ZIP CRC passes; literal `#U` path count is zero.
- UTF-8 strict scan has no U+FFFD replacement characters in current text artifacts.
- Applying UPDATE onto fresh canonical baseline then running `tools/apply_phase6_update_cleanup.py` removes legacy `skills/` and preserves `.agents/skills/`.
- After UPDATE + cleanup: packaged current source files and updated baseline tree are identical by path and SHA256: missing=0, mismatch=0, extra=0.
- UPDATE-overlay core smoke: 60/60 passed.

### Packaged FULL fresh-extraction gate

From a fresh extraction of the generated FULL package:

- Registry / Joint / diagnostics / Receiving WRAP: 62/62 passed.
- Assembly GUI + single-source 3D + Tail save/orientation: 29/29 passed.
- Blank + Skill / release policy: 27/27 passed.
- T1–T7 rebuild / ownership regressions: 34/34 passed.
- Project Save/Reload: 19/19 passed.

Warnings observed are Linux test-environment font glyph warnings from DejaVu Sans and do not represent geometry, persistence, registry, or package failures.
