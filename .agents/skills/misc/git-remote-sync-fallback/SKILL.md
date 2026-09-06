---
name: git-remote-sync-fallback
description: Use when Git remote synchronization is blocked by DNS, network, authentication transport, or harness limitations; when git push/fetch/pull cannot reach GitHub; or when an authorized GitHub Connector may be available as a fallback.
---

# Git Remote Sync Fallback

## 核心原則

**GitHub Connector 內容同步 ≠ git push。** Connector 可以把內容安全同步到遠端，但可能建立新的遠端 commit SHA；若任務要求保留本機 commit identity / 原始 commit graph，就不能把 Connector 同步宣稱成 `git push` 成功。

任何 fallback 都必須 **fail closed、非強制、可追溯、遠端二次驗證**。

## 固定流程

1. **先確認本機 Git 真值**
   ```bash
   git status --short --branch
   git rev-parse HEAD
   git branch --show-current
   git remote -v
   ```
   工作樹有未提交內容時，先依專案 Git 備份規則落 commit / backup tag；禁止用遠端同步掩蓋本機 dirty state。

2. **重現並分類傳輸失敗**
   優先用 `git ls-remote origin`；必要時再用 `getent hosts github.com`/等價 DNS probe。
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
