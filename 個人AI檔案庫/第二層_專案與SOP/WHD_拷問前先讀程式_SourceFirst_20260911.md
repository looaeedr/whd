# WHD 拷問／需求澄清 Source-first 規則

日期：2026-09-11

## 永久規則

只要進入「拷問」「深度質詢」「需求澄清」「寫規格前訪談」：

1. **先讀程式，再問使用者。**
   - current code / UI routing / current behavior
   - tests / regression contracts
   - 現有 specs / CONTEXT / ADR / AI Library
   - 使用者已確認的本輪與歷史規格
   - 使用者提到「原本就有」「以前是這樣」時，必要時查 Git history

2. **程式或既有資料能回答的 implementation fact，不得丟回使用者回答。**
   - 禁止程式已明確是 A，卻問「A 還是 B」。
   - 禁止把「AI 還沒讀程式」偽裝成需求澄清。
   - 禁止重問已在對話／規格／程式中有答案的問題。

3. **只有真正缺少 authority 才能問。**
   - current code/docs/tests 沒答案；或
   - authority 互相衝突，需要使用者裁決；或
   - 本質上是新的產品／設計偏好。

4. 使用者若指出「程式看清楚再來問」「不要假會」「本來就有」：
   - 立即停止後續質詢；
   - 先完成 source readback；
   - 根據 evidence 重算 design frontier；
   - 若 frontier 已空，不准為了形式硬湊問題，直接整理成規格。

## 本次觸發案例

WHD「截角資料」父／子箱身導覽需求中，AI 在未先讀現有 routing 前，詢問「點左側板時 3D 要只顯示單片還是保持完整箱身」。實際 current code 已定義「截角資料」為 view-only navigation，且 selection 不應修改 manufacturing workspace，因此該問題本來可以由程式直接回答，不應交給使用者。

後續已確認 current code 中：

- `深度質詢` 是 canonical grilling owner；
- `拷問邊建立文件` 是 composite skill；
- 兩者皆必須執行 Source-first hard gate。

## Source of Truth

- `.agents/skills/productivity/深度質詢/SKILL.md`
- `.agents/skills/engineering/拷問邊建立文件/SKILL.md`

此規則屬 WHD durable AI behavior，不是單次對話提醒。
