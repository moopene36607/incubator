# growcurve — 陳小寶 (男嬰) 體重 Kalman filter 分析

**起始日期**: 2026-05-01  ·  **觀察天數**: 21
**起始月齡**: 4.0 月  ·  **目前月齡**: 4.7 月
**性別**: 男嬰

## 🎯 Kalman Filter 平滑結果

| 指標 | 起始 | 目前 | 變化 |
|---|---|---|---|
| Smoothed 體重 (kg) | 6.447 | **6.624** | +177 g |
| WHO 百分位 | P24 | **P19** (P15-50 (低標)) | — |
| Smoothed 增重速率 (g/day) | — | **8.4** | — |
| 平均增重 (g/day) | — | 8.8 | — |

## 📊 Raw vs Smoothed 體重 (最近 7 天)

| 日 | Raw (kg) | Smoothed (kg) | Velocity (g/day) | 變動 |
|---|---|---|---|---|
| Day 7 | 6.561 | **6.514** | +8.5 | 🟢 +47 g vs smoothed |
| Day 8 | 6.504 | **6.522** | +8.5 | 🟢 -19 g vs smoothed |
| Day 9 | 6.795 | **6.531** | +8.5 | 🔴 +264 g vs smoothed |
| Day 10 | 6.261 | **6.537** | +8.5 | 🔴 -276 g vs smoothed |
| Day 11 | 6.467 | **6.546** | +8.5 | 🟢 -79 g vs smoothed |
| Day 12 | 6.545 | **6.556** | +8.5 | 🟢 -11 g vs smoothed |
| Day 13 | 6.664 | **6.566** | +8.5 | 🟢 +98 g vs smoothed |
| Day 14 | 6.571 | **6.574** | +8.5 | 🟢 -3 g vs smoothed |
| Day 15 | 6.648 | **6.583** | +8.5 | 🟢 +65 g vs smoothed |
| Day 16 | 6.649 | **6.591** | +8.4 | 🟢 +58 g vs smoothed |
| Day 17 | 6.530 | **6.599** | +8.4 | 🟢 -69 g vs smoothed |
| Day 18 | 6.542 | **6.607** | +8.4 | 🟢 -65 g vs smoothed |
| Day 19 | 6.687 | **6.616** | +8.4 | 🟢 +71 g vs smoothed |
| Day 20 | 6.593 | **6.624** | +8.4 | 🟢 -31 g vs smoothed |

## 🔍 Raw noise vs smoothed signal

- **Raw min/max**: 6.26 - 6.79 kg (range 534 g — 量秤誤差 + 排便 + 餵奶前後)
- **Smoothed range**: 6.447 - 6.624 kg
- **Kalman 過濾掉 ~357 g 的 noise**

## ⚠️ 成長異常警示

### 🔴 URGENT: velocity_below_normal

- 近 5 天 smoothed 增重速率 8.4 g/day, 低於該年齡正常 18 g/day 的 50%

## WHO 0-24 月生長標準對照

| 月齡 | P50 體重 (kg) | 寶寶當時體重對照 |
|---|---|---|
| 0 mo | 3.3 | — |
| 1 mo | 4.5 | — |
| 2 mo | 5.6 | — |
| 3 mo | 6.4 | — |
| 4 mo | 7.0 | **6.45 (-7.9%)** |
| 6 mo | 7.9 | — |
| 9 mo | 8.9 | — |
| 12 mo | 9.6 | — |

## ⚠️ Kalman 模型假設與限制

- **Linear-Gaussian 假設**: state evolution + observation 都假設高斯,真實生長有 nonlinear 成分;Pro 版可用 EKF / UKF
- **Process noise σ² 是 prior**: 設定 0.001 kg² / 0.00001 kg/day² 是 conservative,個別寶寶可調
- **觀察 noise σ² = 0.04 kg² (0.2 kg std)**: 適合家用體重計, 醫院級電子秤可用 0.01
- **WHO 標準是全球**: 台灣寶寶平均體型較亞洲基準, 100% WHO 比對偶有偏差;Pro 版用 CDC / 台灣兒科 NHI 標準
- **不取代兒科醫師**: 工具用於監控進度 + 早期警示,確診 / 治療仍需專業評估
- **同一天多次量會誤導**: 餵奶前 vs 餵奶後可差 200-500 g, 建議每天固定時段 (e.g., 晨起空腹 / 餵奶前)

---
*growcurve = Kalman 1960 filter + RTS smoother × 台灣 0-24 月嬰幼兒生長監控 niche = 把 daily ±200g 噪音過濾, 還原真實 weight trajectory + 即時 percentile + 異常警示。*
