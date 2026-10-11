---
name: git-remote-sync-fallback
description: Use when Git remote synchronization is blocked by DNS, network, authentication transport, or harness limitations; when git push/fetch/pull cannot reach GitHub; or when an authorized GitHub Connector may be available as a fallback.
whd_doc_role: CURRENT
whd_contract: git-remote-sync-fallback
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Git Remote Sync Fallback

## 核心原則

**GitHub Connector 內容同步 ≠ git push。** Connector 可以把內容安全同步到遠端，但可能建立新的遠端 commit SHA；若任務要求保留本機 commit identity / 原始 commit graph，就不能把 Connector 同步宣稱成 `git push` 成功。

任何 fallback 都必須 **fail closed、非強制、可追溯、遠端二次驗證**。

## 現行遠端操作與公開上傳邊界

本 Skill 只處理已授權工作分支的 Git 運輸／失敗備援，**不自行授權施工或 DC 存取**，也不恢復舊 remote token／receipt／unlock。`/派工` 的產品 BUILD／TEST／COMMIT 必須在 GitHub／排程／雲端執行器；`/接手` 僅在使用者當次明確指示後才能於 RC `whd-dev:/workspace/whd` 施工。兩者依現行流程將產品 PR 交付至 `localX`，正式 X 的產品發布仍只接受當次 `/推推`。純治理走受信任 `tools/change_lane_gate.py` 白名單的 GitHub／雲端治理分支直送 X。

實際平台安全審查仍然有效：若 Git/Connector/Remote Desktop 因公開上傳要求更精確批准或拒絕，不可換工具規避、偽稱已獲批准、重建不同 commit 冒充原提交；保留本機 SHA、回報原始拒絕操作與使用者可行動的步驟。

## 固定流程

1. **先確認合法執行器的 Git 真值（不可藉此探測本機）**
   ```bash
   git status --short --branch
   git rev-parse HEAD
   git branch --show-current
   git remote -v
   ```
   僅在當次已授權且有真實 Git 工作區的執行器上檢查；`/派工` 的施工階段不得連線或讀取使用者本機。工作樹有未提交內容時，不得用遠端同步掩蓋 dirty state；只能在原合法施工環境安全保存與核對。

2. **重現並分類傳輸失敗**
    先確認操作落在本輪 repo/Issue/工作分支的既有授權與實際工具權限範圍；不再要求已退役的內部遠端批准才能進行讀取或已核准工作分支的正常交付。
   - `Could not resolve host`、DNS/network unreachable、容器網路受限：屬 transport/environment blocker，可考慮 Connector fallback。
   - non-fast-forward、branch protection、權限拒絕、內容衝突：不是 DNS fallback 問題，禁止繞過。
   - 禁止因 push 失敗改用 `--force` / `push --force`。

3. **Connector 寫入前先鎖定遠端 HEAD**
   用已授權 GitHub Connector 讀目標 branch / commit，記錄 remote HEAD SHA，並確認它仍是預期 parent/base。遠端若已移動且不是預期 fast-forward 基礎，停止寫入並重新比較差異。

4. **只做非強制同步**
   - 多檔同步且工具支援時，優先 `blob → tree → commit → update_ref(force=false)`，讓一次遠端 commit 原子承載完整內容變更。
   - 少量文字檔可使用 Contents API 的 create/update；update 必須帶目前遠端 blob SHA。
   - `update_ref` 一律 `force=false`；任何要求 force 才能前進的情況都視為阻塞。
   - 若要保留本機 commit SHA/history，而 Connector 無法精確重建，停止並回報「Git transport 仍阻塞」，不要改口說已 push。

5. **工具錯誤視為可能部分成功**
   Connector 批次若超過 tool-call limit、timeout、UNKNOWN 或中途報錯，必須假設前面操作可能已成功。**先重新讀取遠端** HEAD / 檔案 / compare，再只補缺少的變更；**不得盲目重送**整批，避免重複 journal、重複 commit 或覆蓋新遠端內容。

6. **遠端二次驗證後才可宣告同步**
   至少驗：
   - remote branch HEAD 已改變且 ancestry/compare 符合預期；
   - 關鍵 state/evidence 檔從 GitHub 遠端重新讀回，內容與本輪驗證一致；
   - 必要 binary / ZIP / raw journal 是否真的存在於遠端；未同步者必須逐項列出；
   - Issue/PR 只有在依賴證據已確認存在遠端後才能關閉。

## 回報用語

- 真正 Git transport 成功：可以說「`git push` 成功」。
- Connector fallback：只能說「已透過 GitHub Connector 同步遠端內容」。
- 只同步部分檔案：明確列出「已同步 / 未同步」，禁止說「整個 branch 已 push」。

## Red Flags

| 想法 | 正確處理 |
|---|---|
| 「DNS 壞了，force push 也許可以」 | DNS 與 force 無關；禁止 force。 |
| 「Connector call 報錯，所以一定什麼都沒寫」 | 可能部分成功；先重讀遠端。 |
| 「文字檔都上去了，所以 ZIP 應該也算上去了」 | 未遠端讀回或列檔驗證就不算。 |
| 「remote 有內容就等於 local commits 都 push 了」 | 內容同步與 commit identity 是兩回事。 |

## GitHub transport and execution-location boundary

- `/派工`：BUILD／TEST／COMMIT 只由 GitHub／排程／雲端施工環境擁有；DC 僅於 exact CI SUCCESS 的 `LOCALX_INTEGRATION` 才能執行本機最終合併與回讀，不能藉 Git transport fallback 在本機施工。
- `/接手`：只有使用者當次明確授權，才可於 CoreELEC `whd-dev:/workspace/whd` 進行產品施工；不能將先前授權或普通「繼續」當成 DC 許可。
- 治理／文件變更：依 `tools/change_lane_gate.py` 的白名單，從最新 X 的 GitHub／雲端治理分支 PR／CI／合併 X；未經當次明確授權不得接觸本機／DC。
- Connector 備援僅同步合法執行器已測試的 exact diff，不能把新遠端 SHA 假稱原始本機 git push；平台安全拒絕、commit 身分不可保存或目標衝突均須 fail closed，不 force、不更換工具繞過。

## Connector target-write hard gate

Before every GitHub Connector write, bind the **intent** to the exact action and target ref. This is a hard gate, not a reminder:

- `create_branch` is for creating a branch. Never substitute `create_file` / `update_file` because the desired branch does not yet exist.
- `create_file` / `update_file` / `delete_file` are content mutations and must **fail closed** if their `branch` is an authoritative target such as `cleanup/2d-3d-sync` or `main`.
- Connector create_file/update_file/delete_file/update_ref 僅限本輪指定的工作分支及 exact tested diff，禁止直接修改 X、main、localX；遇平台拒絕必須停下回報。

If a direct target write happens accidentally:

1. **STOP_PRODUCTION_WRITES** — do not send a compensating direct write and do not force-reset history.
2. Re-read the live target SHA and the accidental commit contents.
3. Create a fresh repair branch from the **current accidental target HEAD**.
4. On that repair branch, remove accidental files and restore the previously verified content/tree.
5. Prove the repair tree SHA equals the intended verified tree whenever an accepted tree already exists.
6. Re-run acceptance needed for the repaired state.
8. Run post-merge production readback/invariants and clean temporary refs.
9. Record the failure mode in `個人AI檔案庫/踩坑庫/git_connector_target_write_pitfall.md` so future workers do not repeat it.
