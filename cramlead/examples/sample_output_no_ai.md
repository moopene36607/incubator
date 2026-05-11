# cramlead — 陽光補習班 (台北信義國高中部, 5 名講師, 約 80 學員) 招生 Lead Logistic Regression

**歷史 leads**: 180 件 (報名率 55.6%)
**Upcoming**: 15 個 leads 待 score
**Model**: Logistic Regression L2 λ=0.01, lr=0.3
**訓練收斂**: 393 iterations (converged)

## 🎯 模型表現

- **In-sample accuracy**: 81.1%
- **Log-loss**: 0.4379
- **AUC-ROC**: 0.876 (excellent)
- **Intercept (b)**: 0.322 (baseline logit)

## 📊 係數解釋 (β + odds ratio + 方向)

| 特徵 (one-hot) | β | odds_ratio | 方向 |
|---|---|---|---|
| attended_trial | +0.955 | ×2.60 | 正向 (預測報名) |
| distance_km | -0.819 | ×0.44 | 負向 (預測流失) |
| referral=朋友介紹 | +0.787 | ×2.20 | 正向 (預測報名) |
| contact_method=網站表單 | -0.761 | ×0.47 | 負向 (預測流失) |
| grade=高中1-3 | +0.736 | ×2.09 | 正向 (預測報名) |
| referral=FB廣告 | -0.593 | ×0.55 | 負向 (預測流失) |
| grade=國小1-3 | -0.569 | ×0.57 | 負向 (預測流失) |
| prev_cram_experience | +0.502 | ×1.65 | 正向 (預測報名) |
| referral=路過招生 | -0.424 | ×0.65 | 負向 (預測流失) |
| referral=親戚口碑 | +0.380 | ×1.46 | 正向 (預測報名) |
| contact_method=親自到店 | +0.360 | ×1.43 | 正向 (預測報名) |
| grade=國小4-6 | +0.353 | ×1.42 | 正向 (預測報名) |

> **odds ratio 解讀**: > 1 = 該 feature 使報名 odds 增加,< 1 = 降低。例如 odds=2.0 = 該 feature 出現時報名 odds 提升 2 倍。

## 🔮 未來 15 個 lead 報名機率預測

| Lead | 年級 | 試聽 | 推薦 | 距離 | 試聽過 | 上次聯絡 | P(報名) | 風險 | 建議動作 |
|---|---|---|---|---|---|---|---|---|---|
| L1010 | 高中1-3 | 數學 | 朋友介紹 | 0.8km | ✓ | 22d | **97.3%** | 🟢 高機率 | 今天就打 + 推方案 + 個別老師導覽 |
| L1014 | 高中1-3 | 理化 | 朋友介紹 | 4.7km | ✓ | 4d | **97.2%** | 🟢 高機率 | 今天就打 + 推方案 + 個別老師導覽 |
| L1004 | 國中1-3 | 數學 | FB廣告 | 1.5km | ✓ | 10d | **88.1%** | 🟢 高機率 | 今天就打 + 推方案 + 個別老師導覽 |
| L1002 | 高中1-3 | 英文 | 親戚口碑 | 4.2km | ✗ | 7d | **78.0%** | 🟢 高機率 | 今天就打 + 推方案 + 個別老師導覽 |
| L1015 | 國中1-3 | 數學 | 親戚口碑 | 7.2km | ✓ | 23d | **72.0%** | 🟢 高機率 | 今天就打 + 推方案 + 個別老師導覽 |
| L1003 | 國小1-3 | 國文 | 親戚口碑 | 1.6km | ✗ | 11d | **71.3%** | 🟢 高機率 | 今天就打 + 推方案 + 個別老師導覽 |
| L1005 | 高中1-3 | 理化 | FB廣告 | 4.7km | ✓ | 6d | **68.0%** | 🟡 中高 | 明天 LINE follow-up + 寄試聽優惠券 |
| L1007 | 國中1-3 | 理化 | 親戚口碑 | 3.5km | ✗ | 23d | **64.4%** | 🟡 中高 | 明天 LINE follow-up + 寄試聽優惠券 |
| L1011 | 國中1-3 | 數學 | Google廣告 | 3.2km | ✗ | 23d | **55.7%** | 🟡 中高 | 明天 LINE follow-up + 寄試聽優惠券 |
| L1006 | 高中1-3 | 國文 | Google廣告 | 7.2km | ✓ | 9d | **53.0%** | 🟡 中高 | 明天 LINE follow-up + 寄試聽優惠券 |
| L1008 | 國中1-3 | 多科套裝 | Google廣告 | 1.2km | ✗ | 6d | **45.3%** | 🟠 中 | 一週內 SMS 提醒 + 一般 follow-up |
| L1013 | 國小1-3 | 國文 | 親戚口碑 | 2.5km | ✗ | 5d | **44.3%** | 🟠 中 | 一週內 SMS 提醒 + 一般 follow-up |
| L1001 | 高中1-3 | 國文 | Cake/IG | 3.7km | ✗ | 25d | **38.0%** | 🟠 中 | 一週內 SMS 提醒 + 一般 follow-up |
| L1009 | 國中1-3 | 數學 | Google廣告 | 3.6km | ✗ | 16d | **13.0%** | 🔴 低 | 標準 nurture 流程 (月 1 次) |
| L1012 | 國小1-3 | 國文 | Google廣告 | 5.4km | ✗ | 30d | **5.3%** | 🔴 低 | 標準 nurture 流程 (月 1 次) |

## 📈 群體預測總覽

- **預期報名數**: 8.9 / 15 (59.4%)
- **高機率 (≥ 70%)**: 6 個 — 今天就要 outreach
- **中高 (50-70%)**: 4 個 — 一週內 follow-up

## 🔍 Top 例: 高機率 lead 為何被預測

### #1 L1010 (P = 97.3%, logit = 3.59)

Top contributing features (β × value):
  - `distance_km` = -1.532 → +1.255
  - `attended_trial` = 0.965 → +0.921
  - `referral=朋友介紹` = 1.0 → +0.787
  - `grade=高中1-3` = 1.0 → +0.736
  - `prev_cram_experience` = -1.102 → -0.554

### #2 L1014 (P = 97.2%, logit = 3.56)

Top contributing features (β × value):
  - `attended_trial` = 0.965 → +0.921
  - `referral=朋友介紹` = 1.0 → +0.787
  - `grade=高中1-3` = 1.0 → +0.736
  - `prev_cram_experience` = 0.902 → +0.453
  - `contact_method=親自到店` = 1.0 → +0.360

### #3 L1004 (P = 88.1%, logit = 2.00)

Top contributing features (β × value):
  - `distance_km` = -1.212 → +0.993
  - `attended_trial` = 0.965 → +0.921
  - `referral=FB廣告` = 1.0 → -0.593
  - `prev_cram_experience` = 0.902 → +0.453
  - `contact_method=電話來電` = 1.0 → -0.348

## ⚠️ Logistic Regression 模型假設與限制

- **線性假設**: P(報名) 通過 logit 跟 features 線性,真實有 nonlinear 交互 (e.g. 年級 × 距離) — Pro 版加交互項
- **180 件樣本不大**: 真實 launch 需 ≥ 500 件多季 / 多年資料訓練, 避免 overfit
- **L2 正則化 λ=0.01 是 mild**: 過大 → underfit, 過小 → overfit;Pro 版用 cross-validation 自動選 λ
- **In-sample accuracy 高 ≠ 真實預測力**: 需 train/test split + temporal validation (用 t-1 季訓練, 預測 t 季)
- **季節性未捕捉**: 暑假前 vs 開學後 conversion 差異, Pro 版加 month/seasonality 特徵
- **隱私敏感**: lead 資料涉個資, 雲端版需加密 + 客戶同意 + 資料留存政策

---
*cramlead = Logistic Regression with L2 regularization × 台灣補習班招生季 lead conversion niche = 從 180 件歷史學報名模式, 對未來 15 leads 標 P(報名), 老闆 / 櫃台優先 outreach 高機率 lead, conversion 從 30% → 50%。*
