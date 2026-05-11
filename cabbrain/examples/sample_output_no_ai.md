# cabbrain -- 大都會 #88452 (10 年資 / 自有車) 接單策略 RL 訓練

**訓練 orders**: 54 筆歷史訂單
**Q-learning**: 線性函數逼近 Q(s, a) = w_a · φ(s), 9 維 features × 2 actions = 18 weights
**訓練 episodes**: 200 次 (epsilon 從 0.5 線性降到 0.05)
**Episode return**: 前半平均 6969 → 後半平均 8131 (越大越好)
**訓練接 / 拒比**: 8161 / 2639 (探索 + 學習中)

## 📈 學習到的策略 vs 全部接單 (replay on log)

| 指標 | 學習策略 | 全部接 (naive) | 差異 |
|---|---|---|---|
| 總淨利 (NT$) | 8930 | 8734 | **+196** |
| 接單數 | 38 / 54 | 54 / 54 | -- |

> 學習策略學會挑單, 差異 NT$ +196 per shift.

## 🎯 待決策訂單

_陳大哥週六凌晨 02:30 收到一筆 LINE Taxi 訂單: 信義區 → 新店捷運站 (約 22km, 預估 50min), 估價 NT$ 360 但 surge x1.1 + 路況 2/5 (凌晨無塞車). 司機猶豫: 路途長但凌晨無客可挑, 該接還是繼續等?_

| 屬性 | 值 |
|---|---|
| 估價 | NT$ 360 |
| 距離 | 22.0 km |
| 預估時間 | 50 分鐘 |
| Surge 倍率 | x1.10 |
| 上車區密度 | 0.40 |
| 路況 | 2/5 |
| 時段 | 02:00 |
| 週末 | 是 |

## ✅ RL 策略建議: **接單**

### 建議接單 -- Q 微優

| 指標 | 值 |
|---|---|
| Q(s, accept) | 1270.1 |
| Q(s, decline) | 1091.7 |
| Margin (accept - decline) | **+178.4** |
| 接受預估淨利 | NT$ 41 |

## 🔬 學到的權重 (top 5 by |w| per action)

### 接單 (a=1)

| Feature | 權重 | 物理意義 |
|---|---|---|
| bias | +763.736 | 常數項 |
| zone_density | +428.164 | 上車區商業密度 |
| fare_norm | +368.023 | 估價 / NT$600 ratio |
| hour | +348.805 | 時段 (晚上 / 凌晨 一般較虧) |
| traffic_norm | -218.577 | 路況差度 (1=順 5=塞) |

### 拒接 (a=0)

| Feature | 權重 | 物理意義 |
|---|---|---|
| bias | +721.645 | 常數項 |
| zone_density | +375.964 | 上車區商業密度 |
| distance_norm | +214.791 | 距離 / 30 km ratio |
| duration_norm | +158.811 | 時長 / 60 min ratio |
| is_weekend | -149.671 | 週末 = 1 |

## ⚠️ RL with linear function approximation 模型假設與限制

- **Linear approximation 假設**: Q(s,a) = w·φ(s) 假設 Q 是 features 的線性函數;真實有非線性 (e.g. 距離平方項 / 時段交互), Pro 版加多項式 features 或 neural network
- **Off-policy 偏差**: 歷史訂單是司機過去策略下產生, 並非完全 IID 樣本;若舊策略偏向只接「短程訂單」, Q-learning 會 underestimate 長程訂單價值 (covariate shift), Pro 版加 importance sampling
- **Reward 工程主觀**: fuel_cost / opportunity_cost 是預設值, 不同車型 / 油價 / 司機機會成本不同; 真實 launch 要讓司機自訂
- **不含關鍵 features**: 客戶評分 / 取消歷史 / 訂單 metadata, prototype 簡化 8 維; Pro 版加 20-30 維
- **不取代司機判斷**: RL 給「策略建議」, 安全 / 心情 / 直覺 / 同行情報 仍是司機決定; 工具僅輔助
- **episode 假設**: 訓練用 shuffled 順序, 真實一天訂單有時序相關 (e.g. 通勤尖峰), Pro 版用 ordered episodes
- **沒考慮競爭**: 多司機搶單 game-theoretic 均衡需 multi-agent RL
- **隱私敏感**: 訂單資料涉司機個資 + 乘客上車地點, 本地版完全在司機手機;雲端版需匿名化

---
*cabbrain = Q-learning + linear function approximation × 台灣計程車 / Uber 司機 接單策略 niche = 從歷史訂單 log 學 Q(s, a) ≈ w · φ(s), ε-greedy 平衡探索 / 利用, 學到的策略 vs naive 全接 比較淨利提升, 司機從「靠經驗 / 看心情」變「客觀 Q 值」, 對抗平台 algorithm 推爛單。*
