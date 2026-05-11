# gpscheck — 台灣外送員 / 計程車 / lalamove 司機 GPS 路徑 DTW 異常偵測 + 申訴工具

**「平台說我繞路扣分,但我沒有 — 怎麼自證?」** 用 Dynamic Time Warping (Sakoe & Chiba 1978) 比對司機**實際 GPS trace vs 平台建議路線**,給出 0-100 similarity score + 偏離點識別 + verdict (NORMAL / MINOR / SIGNIFICANT / MAJOR),作為司機向 Uber Eats / Foodpanda / lalamove 申訴的數學證據。

## 痛點

台灣外送 / 自由貨運 / 計程車生態:
- **Uber Eats / Foodpanda 外送員**: 30,000+ 人
- **lalamove / GoGoVan 貨運司機**: 30,000+ 人
- **計程車 / 多元計程車 (TaxiGo)**: 80,000+ 人
- **共計 ~140,000+ 跑單司機**

**平台處罰機制痛點** (PTT car / FoodPanda / Foodpanda司機 / Dcard 工作版):
- 平台 algorithm 判定「繞路」「超時」自動扣分扣錢 (NT$50-200/次)
- 司機**沒辦法看到 algorithm 邏輯**,也沒有自證工具
- 申訴介面是「自由文字框」,沒有客觀證據格式
- 多次累積扣分會被停權 (Uber 4.6 分以下 / Foodpanda 80 分以下)
- 一次停權月損 NT$30-60K (失業 1-2 週)

**司機常見申訴困境**:
- 「客戶投訴繞路,但我明明沒繞」(無法證明)
- 「平台估時 18 分但實際 25 分,系統說我超時」(無法解釋是塞車)
- 「客戶寫錯地址我跑了 2 個地點才送到」(平台不採信)

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(gpscheck 補的) |
|---|---|---|
| Uber Eats / Foodpanda 駕駛端 | 接單 / 導航 / 收入 | 不給司機自己路徑分析, 沒申訴證據格式 |
| Google Maps Timeline | 個人 GPS 歷史 | 不做與「平台建議路線」對比 |
| 行車紀錄器 | 影片證據 | 不分析 GPS 路徑 alignment |
| 律師 / 司機公會申訴 | 法律諮詢 | NT$3-5K/次 太貴, 不擅長 GPS 數學 |
| ChatGPT 直接問 | 一次性建議 | 不能跑 DTW, 不分析 GPS 數據 |

**Gap 結構性**: DTW (Sakoe & Chiba 1978) 學術界成熟 50+ 年,**沒人做成台灣司機可用 SaaS**。Google「外送員 GPS 申訴 DTW」零中文 SaaS 結果。司機自身有 GPS data (Google Timeline / 駕駛端 App 可匯出) + 平台建議路線可截圖,但**沒人把兩者用 DTW 比對**。

## 架構 — Dynamic Time Warping (35th 條 AI pattern)

```
Actual GPS trace [(lat, lon, t), ...]
                │
                ▼
┌──────────────────────────────────────┐
│ 1. Haversine distance per point pair │
│    (great-circle, accurate Earth      │
│     spheroid model)                   │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│ 2. DTW cost matrix C[n × m]           │
│    C[i][j] = d(a_i, b_j) +            │
│      min(C[i-1][j], C[i][j-1],        │
│          C[i-1][j-1])                 │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│ 3. Backtrace from (n-1, m-1) to (0,0)│
│    → alignment path                   │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│ 4. Similarity 0-100 = 100·exp(-avg/500)│
│    Verdict: NORMAL (≥85) / MINOR /    │
│    SIGNIFICANT (≥50) / MAJOR (<50)    │
└──────────────────────────────────────┘
                │
                ▼
Identify deviation points (> threshold m)
+ extra distance / time / speed metrics
```

**100% 純函式 stdlib** (math + dataclass + enum):
- `haversine`: great-circle distance, accurate to meters
- `dtw_cost_matrix`: O(n×m) DP cost matrix
- `dtw_backtrace`: argmin-of-3-neighbors path reconstruction
- `compute_dtw`: full pipeline → similarity score
- `identify_deviations`: list points exceeding threshold
- `classify_route`: 4-class verdict
- `route_total_distance / duration / avg_speed`: complementary metrics

**LLM 只負責**: 寫 200-280 字「司機申訴建議」(3 申訴步驟 + 3 合理解釋 + 風險)
**LLM 絕不負責**: 計算 DTW similarity / 偏離距離 / 路線距離 (數字 100% 來自純函式)

## 使用示例

```bash
# 純函式模式 (無 API key)
python gpscheck.py --trip samples/trip.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python gpscheck.py --trip samples/trip.json

# 自訂偏離閾值
python gpscheck.py --threshold 300
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳大華 Uber Eats 外送員, 信義 W 飯店 → 松山機場捷運站):

| 指標 | 平台建議 | 實際 | 解讀 |
|---|---|---|---|
| 路線距離 | 4,890 m | 4,982 m | +91 m (GPS 誤差等級) |
| 耗時 | 18 分 | 25 分 | +7 分 (塞車信號) |
| 車速 | 16.3 km/h | 12.0 km/h | -26% |
| **DTW similarity** | **67.8 / 100** | — | **SIGNIFICANT DEVIATION** |
| 偏離點 (>200m) | 4 個 | — | 350-633 m 各處 |

→ 司機可用此報告申訴: **「實際距離僅多 91m (在 GPS 誤差內),延誤原因為塞車 (車速降 26%),非繞路」**

## 目標市場

- **TAM**:
  - Uber Eats / Foodpanda 外送員: 30,000+
  - lalamove / GoGoVan 貨運司機: 30,000+
  - 計程車 / 多元計程車: 80,000+
  - **共計 ~140,000+ 跑單司機**
- **WTP 錨點**:
  - 一次成功申訴撤銷 NT$50-200 罰款 vs gpscheck Solo NT$199/月 = 月省 1-2 次罰款回本
  - 避免停權 (月損 NT$30-60K) → 高 WTP 司機願意付

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 trip/月 + 純函式 verdict | 試用 |
| **Solo** | NT$199/月 | 無限 trips + 申訴模板 + LINE 推播 | 個人司機 |
| **Pro** | NT$499/月 | + Google Timeline 自動匯入 + 多平台 (Uber/FP/lalamove) + 月度報告 | 全職司機 |
| **Fleet** | NT$2,999/月 | 車隊 5-30 司機 + 老闆 dashboard + 異常 trip 警示 | 計程車隊 / 物流行 |
| **Union** | NT$15,000+/月 | 司機公會 / 工會聯合採購 + 法律支援整合 | 公會集體申訴 |

## Distribution

- **PTT car / Foodpanda / FoodPanda司機 / Soft_Job** 板長尾 SEO
- **Dcard 工作版** 案例分享
- **FB「Uber Eats 司機交流」 / 「Foodpanda 外送員自救會」** 5-10K 社群案例
- **YouTube 司機 KOL** (老吳 / Apex / 阿凱 / 外送員的日常) 案例合作
- **計程車隊老闆 BD** (大都會 / 台灣大車隊) 給司機用作工會員工福利
- **司機公會 / 自由職業工會** B2B 聯採
- **車行 / 駕訓班** partner 推廣
- **法律扶助基金會** 公益版 — 免費贊助申訴困難司機

## TAM

- 1% × 140,000 司機 = 1,400 × NT$199 = **月 MRR NT$28 萬**
- + Pro 300 × NT$499 = NT$15 萬/月
- + Fleet 50 × NT$2,999 = NT$15 萬/月
- + Union 5 × NT$15,000 = NT$8 萬/月
- 總計 **月 MRR NT$66 萬 / 年 ARR NT$790 萬**
- 加滲透率提升 + 橫移港新馬 / 日本物流 / 韓國代駕 → 翻倍至 **NT$2,000-4,000 萬 ARR**

## 風險與限制

- **DTW 為點對點 alignment 不理解道路網路** — 兩條路偏 100m 但都在 main road 上也會被算成 100m 偏離;Pro 版加 road-network snap 預處理
- **GPS 誤差 5-20m 是正常的** — 城市區 building shadow 更糟;設 threshold ≥ 100m 才有意義
- **無 monotonic warp constraint** — Sakoe-Chiba 帶沒實作,可能對劇烈不同步序列 over-alignment;Pro 版加 warp window
- **平台不一定承認此分析** — Uber Eats / Foodpanda 申訴決定權仍在平台;但作為司機自證證據能提高採信率
- **僅單一指標** — DTW similarity 不能取代速度 / 暫停時間分析,Pro 版聯合 metric

---
*gpscheck = Sakoe & Chiba 1978 DTW × 台灣外送員 / 司機 niche = 用數學替司機申訴,而不是平台 algorithm 說了算。*
