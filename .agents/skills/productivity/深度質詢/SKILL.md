---
name: 深度質詢
description: 對 plan、decision 或 idea 做高強度逐輪質詢，建立 design tree，直到所有可決策分支都被明確處理。事實由執行者查證、決策由使用者做；沒有真正 Subagent Runtime 時必須 inline 查證，不得虛構背景工作。
---

# 深度質詢

持續訪談直到雙方對問題形成共享理解。把整個問題建成 **design tree**：每個 decision 向下連到依賴它的後續 decisions。

## 0. Source-first 硬閘門：先讀程式，再問人

**任何拷問、需求澄清、規格訪談開始前，先反讀可取得的現況證據。** 不得先憑印象設計問題，再把本來可由程式回答的事實丟回使用者。

至少依任務範圍先查：

- current code / routing / UI behavior；
- tests / regression contracts；
- 現有 specs / ADR / CONTEXT / AI Library；
- 必要時 Git history，確認「原本就有的功能」是否仍存在、只是 routing 被改掉；
- 使用者本輪與既有已確認規則。

### 禁止事項

- **程式已有答案時，禁止再問使用者「A 還是 B」。** 直接回報查到的既有行為與真正待決策點。
- 禁止把「我還沒讀程式」包裝成需求澄清。
- 禁止要求使用者重新回答 current code、現有設定、既有流程、已在本輪/歷史對話確認過的事實。
- 禁止因為某功能目前畫面上看不到，就假設功能不存在；先查 current code / Git history / tests。
- 禁止在沒有 source evidence 前自行發明選項，讓使用者替執行者做 fact-finding。

### 只有這些情況才可以問

1. 現有 code/docs/tests **沒有答案**；或
2. 不同 authority 互相衝突，需要使用者指定哪個產品決策為準；或
3. 問題本質是新的 product/design preference，而不是 implementation fact。

如果使用者指出「程式看清楚再來問」「不要假會」「這本來程式就有」，立即停止後續質詢，先完成 source readback，再重新計算 frontier。

## 1. Frontier 規則

以 rounds 推進。**frontier** 是目前 prerequisites 已全部 settle、因此可以現在就問的所有 decisions。

每輪：

1. 重新計算 frontier。
2. 一次問完整 frontier，而不是只問第一題。
3. 每題編號，清楚寫問題、必要選項與 trade-off。
4. 每題提供你的 recommended answer 與理由。
5. 等使用者回答這些 decisions，再計算下一輪 frontier。

若 Q2 的答案依賴同一輪仍未解的 Q1，Q2 不屬於本輪 frontier，移到下一輪。不要用自己的猜測提前填答案。

## 2. Facts 是執行者的責任

需要 environment fact 才能問某個 frontier decision 時，先自行取得證據，不把可查事實丟給使用者。

優先使用目前實際存在的能力：repository/files、search、tests、logs、connected tools 等。

**Source-first Gate 優先於提問速度。** 就算使用者說「拷問我」，也不代表可以跳過程式反讀；「拷問」只針對真正未決策的 design/product frontier，不包含可自行查證的 implementation fact。

### Subagent 能力邊界

- 若目前環境有**真正、可觀測、可回收結果的 Subagent Runtime**，可以把純 fact-finding 委派出去；該 exploration 只會阻塞依賴它的 branch，不影響其他已 ready frontier questions。
- **沒有真正 Subagent Runtime** 時，由同一執行者 **inline** 查證該 fact，再繼續質詢。
- 不得假裝已 dispatch Subagent、不得等待不存在的背景回報、不得因缺 Subagent 就把整個質詢標成 blocked。
- 只有 fact 確實無法透過現有安全工具取得，且它是某個 decision 的必要 prerequisite，才向使用者說明缺口並請他提供那個無法自行取得的資訊。

## 3. Decisions 是使用者的責任

查到 facts 後，涉及產品、設計、取捨、偏好、authority 的 decision 必須交給使用者決定。不要因為某個選項在 current code 裡已存在，就把它冒充成使用者決策。

推薦答案可以強，但要清楚區分：

- 已查證 fact；
- 你的 recommendation；
- 使用者最後 decision。

若 current code 已明確實作某行為，而使用者只是要求「找回來／保持原本」，該行為優先視為 **implementation fact to recover/reuse**，不是重新拿來問使用者一次。

## 4. 每輪格式

```text
❓ Q1 — <問題標題>
<問題、已查證事實、選項與 trade-off>

➡️ 建議：<recommended answer + why>

---

❓ Q2 — <問題標題>
...
```

不要為了格式而拆成一堆無關小題；frontier 的每題應代表真正需要決策的節點。

如果 Source-first 查完後 frontier 為空，就不要硬湊問題；直接整理已查證事實與可執行規格。

## 5. 結束條件

當 frontier 為空，代表 design tree 的所有 branch 都已處理。此時：

- 列出已 settle 的核心 decisions；
- 列出仍因外部資訊不可得而 OPEN 的項目（若有）；
- 不自行進入實作，直到使用者確認已達共享理解或明確要求下一步。

若本 Skill 被 `拷問邊建立文件` 使用，settled domain terms / ADR-worthy decisions 依該 Skill 同步落盤。
