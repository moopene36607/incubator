# examready — 台灣升學考前 MDP 多科溫習排程助手

**「考試倒數 N 天,今晚 3 小時讀哪幾科最划算」** 用 MDP rollout 替學生算出每晚的最佳分配。Markov Decision Process 50+ 年前在 OR 領域成熟,但**沒人把它做成國高中生家長能直接用的工具** — 因為 Anki / Quizlet 等 SRS 工具只解決「個別 flashcard 何時 review」,完全不考慮「考試日期 / 多科權重 / 每晚有限時間」這三個升學壓力家庭真正在乎的維度。

## 痛點

台灣每年:
- **學測 / 分科測驗**: 13 萬考生
- **國中會考**: 22 萬考生
- **統測**: 9 萬考生
- 加上 **30-50% 補習班學生** = **約 80-100 萬升學壓力家庭** 一年都在問:

> 「考前 30 天我家小孩每晚 3 小時,今晚到底該讀國文還是數學?」

實際情境(PTT C_Education / Dcard 高中 / 親子王國 / FB「108 課綱家長」社群):
- 「我女兒模考國文 75 數學 45,離學測一個月,她每晚一直讀國文(因為比較有成就感),數學擺爛我看了很急」
- 「補習班一週固定排表全班同一張,我家小孩 5 科進度根本天差地遠」
- 「ChatGPT 問每次要重貼資料,也記不住昨天讀過什麼」
- 「請家教 NT$800-2000/hr,一週 2-4 hr,我們也付不起天天請」

家長常見錯誤:
1. **過度補弱科**(可能 ROI 已飽和,加重時間反而邊際遞減)
2. **過度補強科**(成就感驅動,但無權重提升空間)
3. **均分時間**(忽略遺忘曲線 — 5 天沒練的數A 已 大幅衰退)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(examready 補的) |
|---|---|---|
| Anki / Quizlet | 個別 flashcard SRS | 不知道**考試日期 + 多科權重**,不規劃「今晚總共讀什麼」 |
| 學測倒數 App | 計算還剩幾天 | 不給今晚動作建議 |
| 均一 / PaGamO / Cool English | 練習題目平台 | 不做 next-action planning,不知道學生 5 科全貌 |
| 補習班排表 | 一週固定一張 | **全班同一張**,不個人化,不重新規劃 |
| 家教 (NT$800-2000/hr) | 1 對 1 視情況調 | 太貴,不可能每晚請,且家教也常憑經驗 |
| ChatGPT 直接問 | 一次性回答 | 沒有持續 state,每次重貼資料,無法持續規劃 |

**Gap 結構性**:MDP / rollout 50+ 年前 Bellman 就證了動態規劃最優性,**但只在 OR / 學術圈使用**。沒人做成台灣家長能直接用的工具。Google 搜「台灣 升學 MDP 排程」**零中文 SaaS 結果**。

## 架構 — Markov Decision Process / Dynamic Programming with Rollout

```
State (per night):
  ┌──────────────────────────────┐
  │ familiarity[CHI]  = 75       │
  │ familiarity[ENG]  = 60       │
  │ familiarity[MATH] = 45       │
  │ familiarity[PHYS] = 55       │
  │ familiarity[CHEM] = 50       │
  │ days_to_exam    = 30         │
  └──────────────────────────────┘

Action (tonight):           {CHI: 60, ENG: 60, PHYS: 60} minutes
                            ↓ apply_action
State (tomorrow):           f_new = decay(f, λ, 1) + (100-f)/100 × boost(t)
                            days_to_exam -= 1
                            ↓ default_future_policy (rollout)
                            ↓ ... 29 more days ...
Exam Day Reward:            Σ weight_s × f_s/100 × 100
                            = 311.9 / 500
```

**100% 純函式 stdlib**(math + statistics + dataclass + itertools):
- `boost(subject, minutes)`: saturating exp curve
- `decay(familiarity, λ, days)`: exponential forgetting curve
- `apply_action`: one-day MDP transition with **diminishing returns** (`(100-f)/100 × boost`) preventing trivial saturation
- `default_future_action`: rollout policy — top-K subjects by weighted gap
- `enumerate_candidate_actions`: ~145 candidate tonight allocations (combinations × block sizes)
- `rollout`: forward-simulate tonight's action + default policy until exam day → predicted score
- `find_optimal_tonight`: evaluate all candidates, sort by score
- `project_seven_day_plan`: re-plan each of next 7 nights using optimal-tonight + default-future

**LLM 只負責**: 寫 150-200 字解釋「為什麼 MDP 挑這個分配」 + 學習建議 + 風險提醒。
**LLM 絕不負責**: 計算 familiarity / 預期分數 / candidate actions(數字 100% 來自純函式 MDP)。

## 使用示例

### 純函式模式(無 API key)
```bash
python examready.py --student samples/student.json --no-ai
```

### AI 模式(需 ANTHROPIC_API_KEY)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python examready.py --student samples/student.json
```

預期輸出 (詳見 `examples/sample_output.md` 與 `examples/sample_output_no_ai.md`):

樣本 (王小明 高三 / 二類組 / 學測倒數 30 天):

| 政策 | 預期考試總分 | vs 完全不讀 |
|---|---|---|
| **MDP 最佳** | **311.9** / 500 | **+183.4** |
| 一週固定排表 | 290.6 | +162.1 |
| 完全不讀 | 128.5 | 基準 |

→ **MDP 比固定排表多 21.3 分**(差不多多上一個志願 PR 值)

今晚建議:**國文 60分 + 英文 60分 + 物理 60分**
推薦邏輯:預設未來政策會每晚優先讀數A / 化學 / 物理(權重大且弱),今晚反而要補預設不會碰的國文 / 英文 — 避免它們衰退太多。

## 目標市場

- **TAM**: 升學壓力家庭 ~80-100 萬戶(學測 13 萬 + 會考 22 萬 + 統測 9 萬 + 補習班 30-50%)
- **WTP 錨點**:
  - 家教 NT$800-2000/hr × 8 hr/月 = NT$6,400-16,000/月 vs examready Solo NT$199/月 = **30-80x 便宜**
  - 補習班 NT$15-30K/月 vs Solo NT$199 = 1% 的補教預算搭配使用
  - 升學志願差 1 個 PR 值,大學選系決定一輩子 — NT$199/月 一年 NT$2,388 對家長太划算

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次計算/月 + 純函式輸出 | 試用 |
| **Solo** | NT$199/月 | 每天 1 次今晚規劃 + 7 天投影 + LINE 提醒 | 個人學生 |
| **Family** | NT$399/月 | 多孩家庭 / 多考試版本 + 家長 dashboard | 多孩家庭 |
| **Cram School** | NT$2,999/月 | 補習班一班 30 學生 + 老師 dashboard + 模考成績整合 | 中小型補習班 |
| **Enterprise** | NT$15,000+/月 | 連鎖補習班 + API + 與排課系統整合 | 大型補教集團 |

## Distribution

- **PTT C_Education / Dcard 高中 / 親子王國 / FB「108 課綱家長」** SEO + 案例分享
- **中小補習班** BD — 跟補教王 / 補習達人 等管理系統互補不衝突(他們做排課收費,我們做學生個人化規劃)
- **YouTube 升學 KOL**(葉丙成 / 王政忠 / 補教名師)合作宣傳
- **學測 / 會考倒數** 30 / 60 / 90 / 100 天節點 Google Ads
- **數位學伴 / 偏鄉教育** 公益合作(免費贊助偏鄉學生使用)拿 PR + Distribution
- **教育部 / 各縣市教育局** 數位轉型補助配合計畫

## TAM 估算

- 1% × 80 萬升學家庭 = 8,000 家庭 × Solo NT$199 = **月 NT$160 萬 MRR / 年 NT$1,900 萬 ARR**
- + Family + Cram School + Enterprise → 年 ARR NT$5,000 萬-1 億
- 橫移港新馬中文補教 + 日韓升學市場 → 翻倍

## 風險與限制

- **熟悉度自評不準** — 學生樂觀 / 悲觀都會偏 MDP 結果。緩解:用學校段考 / 模考分數矯正,每週重新自評一次
- **線性 reward 假設** — 真實考試分數非線性(尾段越來越難拉),Pro 版加 sigmoid reward 選項
- **不考慮校內進度** — 模型只看升學考,不考慮段考、學校老師臨時抽考。緩解:Family 版加段考 mode
- **學生不照計劃做** — MDP 算出 60+60+60,實際讀 180 分鐘國文。緩解:LINE 每晚提醒 + 隔天 ask「實際讀了什麼」自動更新 state
- **家長強迫使用反效果** — 升學壓力家庭已經很緊張,工具可能變成新壓力源。緩解:UI 上強調「建議」非「命令」,顯示信心區間而非單一數字

---
*examready = 升學考前 MDP 助手。Bellman 證的「最優子結構」終於走進台灣升學家庭。*
