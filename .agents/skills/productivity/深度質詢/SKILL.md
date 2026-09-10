---
name: 深度質詢
description: 對 plan、decision 或 idea 做高強度逐輪質詢，建立 design tree，直到所有可決策分支都被明確處理。事實由執行者查證、決策由使用者做；沒有真正 Subagent Runtime 時必須 inline 查證，不得虛構背景工作。
---

# 深度質詢

持續訪談直到雙方對問題形成共享理解。把整個問題建成 **design tree**：每個 decision 向下連到依賴它的後續 decisions。

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

## 5. 結束條件

當 frontier 為空，代表 design tree 的所有 branch 都已處理。此時：

- 列出已 settle 的核心 decisions；
- 列出仍因外部資訊不可得而 OPEN 的項目（若有）；
- 不自行進入實作，直到使用者確認已達共享理解或明確要求下一步。

若本 Skill 被 `拷問邊建立文件` 使用，settled domain terms / ADR-worthy decisions 依該 Skill 同步落盤。
