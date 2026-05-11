# stagetrack 房地產 listing HMM 銷售階段追蹤報告

**模式**: 純函式 Hidden Markov Model + Viterbi(免 API key)

## Portfolio 概況 — 5 個 listings

| Listing | 地址 | 當前 state | 信賴度 | 連續週數 | State 演變 |
|---|---|---|---|---|---|
| L001 | 台北市信義區某路 100 號 8F(28 坪 /  | 🔒 已結案 | 100% | 7 週 | W1 → Hot → W6 → Closed |
| L002 | 新北市板橋區某路 200 號 5F(22 坪 /  | 🟡 溫溫的 | 69% | 12 週 | W1 → Warm |
| L003 | 新北市新店區某路 300 號 4F(18 坪 /  | ❄️ 冷掉了 | 50% | 5 週 | W1 → Hot → W4 → Warm → W8 → Cold |
| L004 | 桃園市中壢區某路 400 號 12F(35 坪 / | 🔒 已結案 | 86% | 9 週 | W1 → Cold → W4 → Closed |
| L005 | 台中市西屯區某路 500 號 6F(25 坪 /  | 🔥 熱賣中 | 96% | 7 週 | W1 → Warm → W6 → Hot |

## L001 — 台北市信義區某路 100 號 8F(28 坪 / NT$ 28M)

**筆記**: 上市後第 1-3 週熱絡,第 4 週進入議價,第 6 週成交

### 12 週活動觀察 vs HMM 推測 state

| 週 | 觀察 (0-4) | 觀察描述 | Viterbi state |
|---|---|---|---|
| W1 | 3 | 高活動 | 🔥 Hot |
| W2 | 3 | 高活動 | 🔥 Hot |
| W3 | 4 | 議價中 | 🔥 Hot |
| W4 | 4 | 議價中 | 🔥 Hot |
| W5 | 4 | 議價中 | 🔥 Hot |
| W6 | 0 | 無活動 | 🔒 Closed |
| W7 | 0 | 無活動 | 🔒 Closed |
| W8 | 0 | 無活動 | 🔒 Closed |
| W9 | 0 | 無活動 | 🔒 Closed |
| W10 | 0 | 無活動 | 🔒 Closed |
| W11 | 0 | 無活動 | 🔒 Closed |
| W12 | 0 | 無活動 | 🔒 Closed |

### 當前 state 分布(W12 posterior)

- 🔥 **Hot**: 0.0% 
- 🟡 **Warm**: 0.0% 
- ❄️ **Cold**: 0.1% 
- 🔒 **Closed**: 99.9% █████████████████████████████

### State 演變

**W1 → Hot → W6 → Closed**

連續 **7 週**在 Closed

## L002 — 新北市板橋區某路 200 號 5F(22 坪 / NT$ 14M)

**筆記**: 穩定 warm — 持續中等興趣但未進入議價,可能要調整定價

### 12 週活動觀察 vs HMM 推測 state

| 週 | 觀察 (0-4) | 觀察描述 | Viterbi state |
|---|---|---|---|
| W1 | 2 | 中活動 | 🟡 Warm |
| W2 | 2 | 中活動 | 🟡 Warm |
| W3 | 1 | 低活動 | 🟡 Warm |
| W4 | 2 | 中活動 | 🟡 Warm |
| W5 | 2 | 中活動 | 🟡 Warm |
| W6 | 2 | 中活動 | 🟡 Warm |
| W7 | 1 | 低活動 | 🟡 Warm |
| W8 | 2 | 中活動 | 🟡 Warm |
| W9 | 2 | 中活動 | 🟡 Warm |
| W10 | 1 | 低活動 | 🟡 Warm |
| W11 | 2 | 中活動 | 🟡 Warm |
| W12 | 2 | 中活動 | 🟡 Warm |

### 當前 state 分布(W12 posterior)

- 🔥 **Hot**: 16.8% █████
- 🟡 **Warm**: 69.3% ████████████████████
- ❄️ **Cold**: 13.6% ████
- 🔒 **Closed**: 0.3% 

### State 演變

**W1 → Warm**

連續 **12 週**在 Warm

## L003 — 新北市新店區某路 300 號 4F(18 坪 / NT$ 9M)

**筆記**: 初期熱中後 cool down — 第 1-3 週 hot,4-7 週 warm,8-12 週 cold

### 12 週活動觀察 vs HMM 推測 state

| 週 | 觀察 (0-4) | 觀察描述 | Viterbi state |
|---|---|---|---|
| W1 | 3 | 高活動 | 🔥 Hot |
| W2 | 4 | 議價中 | 🔥 Hot |
| W3 | 3 | 高活動 | 🔥 Hot |
| W4 | 2 | 中活動 | 🟡 Warm |
| W5 | 2 | 中活動 | 🟡 Warm |
| W6 | 1 | 低活動 | 🟡 Warm |
| W7 | 2 | 中活動 | 🟡 Warm |
| W8 | 1 | 低活動 | ❄️ Cold |
| W9 | 0 | 無活動 | ❄️ Cold |
| W10 | 0 | 無活動 | ❄️ Cold |
| W11 | 1 | 低活動 | ❄️ Cold |
| W12 | 0 | 無活動 | ❄️ Cold |

### 當前 state 分布(W12 posterior)

- 🔥 **Hot**: 0.5% 
- 🟡 **Warm**: 3.8% █
- ❄️ **Cold**: 50.2% ███████████████
- 🔒 **Closed**: 45.6% █████████████

### State 演變

**W1 → Hot → W4 → Warm → W8 → Cold**

連續 **5 週**在 Cold

## L004 — 桃園市中壢區某路 400 號 12F(35 坪 / NT$ 18M)

**筆記**: 整個刊登期間都 Cold — 可能需要重拍照 + 降價或撤回

### 12 週活動觀察 vs HMM 推測 state

| 週 | 觀察 (0-4) | 觀察描述 | Viterbi state |
|---|---|---|---|
| W1 | 1 | 低活動 | ❄️ Cold |
| W2 | 0 | 無活動 | ❄️ Cold |
| W3 | 1 | 低活動 | ❄️ Cold |
| W4 | 0 | 無活動 | 🔒 Closed |
| W5 | 0 | 無活動 | 🔒 Closed |
| W6 | 0 | 無活動 | 🔒 Closed |
| W7 | 1 | 低活動 | 🔒 Closed |
| W8 | 0 | 無活動 | 🔒 Closed |
| W9 | 0 | 無活動 | 🔒 Closed |
| W10 | 0 | 無活動 | 🔒 Closed |
| W11 | 1 | 低活動 | 🔒 Closed |
| W12 | 0 | 無活動 | 🔒 Closed |

### 當前 state 分布(W12 posterior)

- 🔥 **Hot**: 0.1% 
- 🟡 **Warm**: 0.9% 
- ❄️ **Cold**: 12.8% ███
- 🔒 **Closed**: 86.2% █████████████████████████

### State 演變

**W1 → Cold → W4 → Closed**

連續 **9 週**在 Closed

## L005 — 台中市西屯區某路 500 號 6F(25 坪 / NT$ 12M)

**筆記**: slow heat up — 第 1-4 週 warm 起步,5-8 週 warm-to-hot,9-12 進入議價

### 12 週活動觀察 vs HMM 推測 state

| 週 | 觀察 (0-4) | 觀察描述 | Viterbi state |
|---|---|---|---|
| W1 | 1 | 低活動 | 🟡 Warm |
| W2 | 2 | 中活動 | 🟡 Warm |
| W3 | 2 | 中活動 | 🟡 Warm |
| W4 | 2 | 中活動 | 🟡 Warm |
| W5 | 2 | 中活動 | 🟡 Warm |
| W6 | 3 | 高活動 | 🔥 Hot |
| W7 | 3 | 高活動 | 🔥 Hot |
| W8 | 3 | 高活動 | 🔥 Hot |
| W9 | 3 | 高活動 | 🔥 Hot |
| W10 | 4 | 議價中 | 🔥 Hot |
| W11 | 3 | 高活動 | 🔥 Hot |
| W12 | 4 | 議價中 | 🔥 Hot |

### 當前 state 分布(W12 posterior)

- 🔥 **Hot**: 96.0% ████████████████████████████
- 🟡 **Warm**: 4.0% █
- ❄️ **Cold**: 0.0% 
- 🔒 **Closed**: 0.0% 

### State 演變

**W1 → Warm → W6 → Hot**

連續 **7 週**在 Hot

---
*純函式模式無 AI 故事化解讀與行動建議。AI 模式會為每個 listing 寫故事 + 3-5 條立即行動 + 預警信號 + portfolio 建議。*
*stagetrack 是分析工具,**最終決策**(調價 / 撤回)請依房仲經驗 + 屋主溝通。HMM 推測有不確定性。*