# cabbrain -- 台灣計程車 / Uber 司機接單策略 RL with linear function approximation

**「凌晨 2 點收到一筆 NT$ 360 / 22km / 50min 訂單, 接還是不接?」** 用 Q-learning + linear function approximation 從歷史訂單 log 學 Q(s, a) ≈ w · φ(s), ε-greedy 平衡探索 / 利用, 學出來的策略在 replay 上跟 naive 全接比較淨利提升, 司機從「靠經驗 / 看心情」變「客觀 Q 值 + 預估淨利」決策, 對抗平台 algorithm 推爛單。

## 痛點

台灣計程車 / 網約車市場:
- **計程車**: ~80,000 司機 (含個人 + 大都會 / 台灣大車隊)
- **Uber / LINE Taxi / yoxi / 呼叫小黃**: ~30,000 司機
- **每日接單**: 每司機 30-80 通 / 天, 接 / 拒 決策 50-200 次
- **平均日營收**: NT$ 1,500-4,000 (扣抽成)

**司機痛點** (PTT taxi / Soft_Job / FB「Uber 司機交流」/「計程車自救會」5-10 萬人社群):
- 「平台一直推爛單 (長程低 surge / 凌晨偏遠 / 空車回程)」每天重複
- 「老司機說『時段 + 路況 + surge 看 5 秒決定接不接』, 新司機沒系統」
- 「拒太多會被平台降權, 接太多爛單時薪變低」
- 「沒工具客觀算: 接 vs 拒 哪個淨利期望高」
- gpscheck r45 是 GPS 申訴 (爭議事後), **這是策略事前**, 完全不同問題

**現有資源**:
- 平台 (Uber / LINE Taxi) algorithm 推薦的訂單 — **利益衝突, 平台要求高接受率**
- 老司機口耳相傳 ("凌晨 1-3 點不要接遠的")
- LINE 司機群分享當下訂單 — 主觀 + 沒系統化
- Excel / 筆記 — 飼料 driver 都太累不會做

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(cabbrain 補的) |
|---|---|---|
| Uber / LINE Taxi / yoxi 平台 | 推薦訂單 | **利益衝突**, 演算法要司機盡可能接 |
| 計程車 / Uber 司機 LINE 群 | 即時討論 | 主觀, 沒系統化 Q 值 |
| 老司機口耳相傳 | 經驗法則 | 落差大, 沒個人化 |
| ChatGPT 一次問 | 一次性建議 | 不能持續學習 + 不知道你的歷史接單 |
| Excel 自己算 | 純手動 | 沒 RL, 不會學 |
| 海外 RL ride-share 學術論文 | 學術為主 | 沒產品化, 一般司機用不到 |
| **gpscheck r45** (本 incubator) | GPS 申訴 (爭議事後) | 完全不同問題: 申訴 vs 策略 |

**Gap 結構性**: RL with linear function approximation (Q-learning 1989 + linear feature approx) 學術成熟 35+ 年, **沒人做成台灣繁中計程車 / Uber 司機可用 SaaS**。Google「台灣 計程車 接單 RL 中文」零本土 SaaS。

## 架構 -- Q-learning with Linear Function Approximation (56th 條 AI pattern)

```
歷史訂單 logs (fare / dist / dur / surge / hour / zone / traffic)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Feature engineering φ(s):                     │
│   hour / 24                                   │
│   is_weekend (0/1)                            │
│   fare_norm (NT$/600 clipped 2.0)            │
│   distance_norm (km/30 clipped 2.0)          │
│   duration_norm (min/60 clipped 2.0)         │
│   surge_norm ((x-1)/2)                        │
│   pickup_zone_density (0..1)                  │
│   traffic_norm ((x-1)/4)                      │
│   bias = 1                                    │
│ Total 9 features                              │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Linear Q-value:                               │
│   Q(s, a) = w_a · φ(s)                        │
│   2 actions (accept / decline)                │
│   18 learnable weights total                  │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Reward function:                              │
│   Accept: fare * surge                        │
│          - fuel_cost_per_km * distance        │
│          - opportunity_cost_per_min * dur     │
│   Decline: -decline_penalty                   │
│ Defaults: fuel=2.5 NT$/km, opp=6 NT$/min,    │
│           decline=10 NT$                      │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Episode training (n_episodes = 200):          │
│   For each ep:                                │
│     ε = linear decay 0.5 → 0.05               │
│     Shuffle orders                            │
│     For each order in sequence:               │
│       a = ε-greedy(Q, s)                      │
│       r = compute_reward(order, a)            │
│       s' = next order features                │
│       TD-target: r + γ · max_a' Q(s', a')    │
│       TD-error: target - Q(s, a)              │
│       w_a += α · TD-error · φ(s)              │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Inference on new order:                       │
│   recommend = argmax_a Q(s_query, a)          │
│   margin = Q(s, 1) - Q(s, 0)                  │
│   rationale based on margin magnitude         │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Replay on log:                                │
│   Compare learned vs naive (always-accept)    │
│   Reports net delta NT$ per shift             │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + random + statistics + dataclasses):
- `Order`: dataclass with 8 attributes
- `normalise_features`: bounded 9-dim feature vector
- `compute_reward`: realised reward with configurable cost structure
- `LinearQ`: linear function approx with per-action weight vectors
- `train_q_learning`: ε-greedy + TD(0) updates + epsilon decay
- `recommend`: argmax + margin rationale
- `replay_policy_on_log`: learned-vs-naive comparison
- `policy_summary`: top-feature weights per action for interpretability

**LLM 只負責**: 寫 250-330 字「司機接單前 5 秒判斷 SOP + 何時違反 RL + 新司機長期策略」
**LLM 絕不負責**: 計算 Q 值 / TD-error / reward (數字 100% 來自 RL 純函式)

### 為什麼 RL with linear FA 適合這個 use case (vs MCMC r61 / Bandit r38)

- **RL with FA**: 學 *long-horizon* policy (Q 估未來折扣 return, 不是當下 immediate reward), 適合「司機一天 N 個訂單 sequence 的累積收益」
- **MCMC r61 staypulse**: 學 *demand elasticity*, 適合 cross-section (民宿一晚定價), 不適合 sequence policy
- **Multi-armed Bandit r38 quotelab**: 單回合決策, 不考慮 state transition (司機接 / 拒影響下一單的時間 / 位置)

RL 獨特優勢:
1. **State-aware**: 同一訂單在不同 state (時段 / 位置 / 路況) 的 Q 不同, 動態調整
2. **Long-horizon**: γ=0.9 折扣 8-10 個未來訂單, 學會「拒這單為了等更好的」
3. **Linear FA tractable**: 18 weights 即可學 8 維 state × 2 action, 純 stdlib SGD 可訓

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 cabbrain.py --data samples/shifts.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 cabbrain.py --data samples/shifts.json

# 自訂訓練 hyperparameters
python3 cabbrain.py --episodes 500 --alpha 0.005 --gamma 0.95
```

預期輸出 (詳見 `examples/sample_output.md`):

大都會 #88452 (54 歷史訂單) 接單策略:
- **訓練收斂**: episode return 從 6,969 提升到 8,131 (+16.6%)
- **Replay 比較**: 學習策略 NT$ 8,930 vs naive 全接 NT$ 8,734 (+196 per shift, 拒掉 16/54 爛單)
- **Top features 學到**: 接單偏向 zone_density + fare_norm + surge, 拒單偏向 distance + duration 長 + zone 密度低

陳大哥 凌晨 02:30 收到 NT$ 360 / 22km / 50min / surge 1.1:
- **預估淨利**: NT$ 41
- **Q margin**: +178 (接 vs 拒)
- **建議**: 接 (邊際好單, 凌晨等不到下一單)

## 目標市場

- **TAM**:
  - 計程車司機 80,000 + Uber / LINE Taxi / yoxi 30,000 = 110,000 司機
  - 大都會 / 台灣大車隊 / 全國等車行 (B2B white-label)
  - 計程車公會 / 司機工會
  - Uber / 平台公司 (driver retention)
- **WTP 錨點**:
  - 司機 NT$ 199/月 vs 月省 1-2 個爛單 (每單虧 NT$ 100-300) = 月省 NT$ 1-3K = **5-15x ROI**
  - 大都會 NT$ 5,000+ 月費白標 vs 司機留任率提升 5% → 平台抽成增加

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次/天 推薦 | 試用 |
| **Solo** | NT$199/月 | 無限推薦 + LINE Bot + 個人 Q 學習 | 個別司機 |
| **Pro** | NT$499/月 | + 每日報表 + 同行匿名比較 + 爛單 alert | 全職司機 |
| **Fleet** | NT$2,999/月 | 車隊 5-30 司機 + 老闆 dashboard + API | 計程車行 |
| **Enterprise** | NT$15,000+/月 | 大車隊 + 平台 integration + 司機留任分析 | 大都會 / 台灣大 |
| **Platform** | NT$50,000+/月 | Uber / LINE Taxi / yoxi 平台 white-label | 網約車平台 |

## Distribution

- **PTT taxi / Soft_Job 板** 長尾 SEO
- **Dcard 工作 / 計程車** 版
- **FB「Uber 司機交流 / 計程車自救會 / yoxi 司機」5-10 萬人社群** 案例分享
- **大都會 / 台灣大車隊 B2B BD** (車行月會宣傳)
- **計程車公會 / 司機工會 partner** (全台 24 個地方公會)
- **YouTube 司機 KOL** (老吳 / Apex / 計程車人生 / 外送員的日常)
- **Uber Driver 認證合作 (若可申)**
- **大樓 / 機場 / 飯店 司機休息室 海報**

## TAM

- 1% × 110,000 = 1,100 × Solo NT$199 = **月 NT$22 萬**
- + Pro 500 × NT$499 = NT$25 萬/月
- + Fleet 50 × NT$2,999 = NT$15 萬/月
- + Enterprise 10 × NT$15,000 = NT$15 萬/月
- + Platform 3 × NT$50,000 = NT$15 萬/月
- 總計 **月 MRR NT$92 萬 / 年 ARR NT$1,100 萬**
- 加滲透 + 橫移日本計程車 (法人車 30 萬) / 韓國 카카오택시 / 港新馬 → **NT$5,000 萬-1 億 ARR**

## 風險與限制

- **Linear approximation 假設**: Q(s,a) = w·φ(s) 假設 Q 是 features 的線性函數, 真實有非線性 (e.g. 距離平方項 / 時段交互), Pro 版加多項式 features 或 neural network
- **Off-policy 偏差**: 歷史訂單是司機過去策略下產生, 並非完全 IID 樣本; 若舊策略偏向只接「短程訂單」, Q-learning 會 underestimate 長程訂單價值 (covariate shift), Pro 版加 importance sampling
- **Reward 工程主觀**: fuel_cost / opportunity_cost 是預設值, 不同車型 / 油價 / 司機機會成本不同; 真實 launch 要讓司機自訂
- **不含關鍵 features**: 客戶評分 / 取消歷史 / 訂單 metadata, prototype 簡化 8 維; Pro 版加 20-30 維
- **不取代司機判斷**: RL 給「策略建議」, 安全 / 心情 / 直覺 / 同行情報 仍是司機決定; 工具僅輔助, 安全永遠優先
- **episode 假設**: 訓練用 shuffled 順序, 真實一天訂單有時序相關 (e.g. 通勤尖峰 + 散場潮), Pro 版用 ordered episodes
- **沒考慮競爭**: 多司機搶單 game-theoretic 均衡需 multi-agent RL
- **平台政策變動**: Uber / LINE Taxi 抽成比例改變 / 接受率懲罰調整 → 模型失效需重訓
- **隱私敏感**: 訂單資料涉司機 GPS + 乘客上車地點, 本地版完全在司機手機; 雲端版需匿名化 + 用戶同意
- **不適用初級司機**: 0-3 個月新司機建議「全接 + 累積 Q 學歷史」, RL 才能學出個性化 policy
- **避免被平台針對**: 若所有司機都用 cabbrain, 平台會調整 algorithm 推爛單給某些司機; 集體博弈問題

---
*cabbrain = Q-learning + linear function approximation × 台灣計程車 / Uber 司機接單策略 niche = "從歷史訂單 log 學 Q(s, a) ≈ w · φ(s), ε-greedy 平衡探索 / 利用", 學習策略 vs naive 全接 比較淨利提升, 司機從「靠經驗 / 看心情」變「客觀 Q 值」, 對抗平台 algorithm 推爛單。*
