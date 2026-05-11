# peakflow — 餐廳尖峰時段 agent-based 營運模擬器

**台灣中小餐廳老闆「該不該加人/擴廚/改菜單」的決策助手**。把店裡尖峰時段拍成模擬器跑 N 次,用 Customer / Server / Kitchen 三類 agent 算出**真實 ROI**,把「加 1 個服務員真的有用嗎?」「擴廚 vs 推快餐套餐哪個賺?」這類老闆每天問自己卻沒答案的問題,用 30 秒給出**數字證據**。

## 痛點

台灣餐飲業 17 萬家,7-8 成是 1-30 人小餐廳。**午餐尖峰 11:30-13:30 / 晚餐尖峰 18:00-20:30** 決定全月生死,但中小餐廳老闆做擴張決策**沒有任何工具**:

- 加 1 個外場服務員月 NT$32-38K — 真的能多服務多少客人?
- 擴廚採新設備月攤 NT$30-50K — 廚房真的是瓶頸嗎?
- 推快餐套餐 — 加快翻桌 vs 客單價下降,淨營收增還是減?
- 加桌位 — 但客人等不到桌就走,加桌真的有用?

PTT food / Dcard 餐飲業 / FB「餐飲老闆交流」社團每週都有人問:
- 「請了 3 個外場結果生意沒變好,是不是請錯了」
- 「廚房總是出不來菜,要不要再加 1 個師傅?但人事多 NT$45K 划算嗎」
- 「翻桌率拉不起來,午餐都把客人趕走」

**靠經驗 + Excel + 朋友建議** 是現況,完全沒有 **agent-based simulation** 工具。

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(peakflow 補的) |
|---|---|---|
| iCHEF / 雲端 POS / 沛點 | 點餐 / 收款 / 報表 | **不模擬**「如果加 1 個服務員會怎樣」,只有歷史數據 |
| Excel 預估表 | 老闆自己亂算 | 不會跑 Monte-Carlo,假設 100% 確定,結果嚴重失準 |
| 餐飲顧問 | 線下訪談 + 經驗判斷 | 1 次 NT$10K-50K + 訪談主觀 + 不能跑「假設情境」 |
| Restaurant Sim (歐美) | 教學用 | 不認識台灣餐廳尺寸 / 客單價 / 客人耐心度 / 翻桌文化 |
| AnyLogic / Simul8 | 重量級 BPM 工具 | 月費 USD$1,500+ + 學習曲線陡(顧問才用得起) |

**Gap 結構性**: 簡易、台灣化、餐廳老闆能直接用的 agent-based simulator 全球都沒有。

## 架構 — Agent-Based Discrete-Event Simulation

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  Customer   │────▶│   Server    │────▶│   Kitchen    │
│  (Agent)    │     │   (Agent)   │     │   (Agent)    │
└─────────────┘     └─────────────┘     └──────────────┘
   到達(Poisson)        IDLE/BUSY            CAPACITY=N
   桌位/耐心            點餐/上菜             FIFO cook queue
   用餐/離開
        │
        ▼
┌──────────────────────────────────────────┐
│  Event Queue (heapq priority by time)     │
│  arrival → seat → take_order →            │
│  send_to_kitchen → food_ready →           │
│  deliver → finish_meal → free_table       │
└──────────────────────────────────────────┘
```

- `sim.py` **100% 純函式**(stdlib only: `heapq` + `random` + `statistics` + `dataclass`)
  - `Customer` agent: arrival_time (Poisson) / party_size (1-4 加權) / patience (高斯分布) / state machine 8 狀態
  - `Server` agent: N 個服務員 each with `busy_until` 時間軸
  - `Kitchen` agent: capacity-bounded order queue, FIFO 出菜
  - Event-driven loop: 用 `heapq` 排序 events 依時間發生,處理事件可能觸發後續 events
  - `_find_table()`: smallest-fitting table 配位(避免 4 人坐 6 人桌浪費)
  - `run_scenarios()`: Monte-Carlo wrapper, 每個 scenario 跑 N 次 (預設 5-10) 平均
- `peakflow.py` CLI:
  - `--restaurant samples/restaurant.json` 載入餐廳設定 + 多情境
  - `--runs N` 每情境 N 次平均
  - `--no-ai` 純函式輸出(不呼叫 LLM)
  - `--seed` 隨機種子(可重現)

**AI 只負責**: 為已算好的 KPI/ROI 寫**老闆讀得懂的 5-7 行建議**(指出瓶頸 / 推薦方案 / 提醒風險)。
**AI 絕不負責**: 計算營收 / 流失率 / ROI(數字 100% 來自純函式 simulation)。

## 使用示例

### 純函式模式(無 API key)
```bash
python peakflow.py --restaurant samples/restaurant.json --no-ai --runs 10
```

### AI 模式(需 ANTHROPIC_API_KEY)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python peakflow.py --restaurant samples/restaurant.json --runs 10
```

預期輸出 (詳見 `examples/sample_output.md` 與 `examples/sample_output_no_ai.md`):

| 情境 | 流失率 | 月增成本 | 月淨增益 | ROI |
|---|---|---|---|---|
| 現況 | 36.5% | 基準 | — | — |
| 加 2 桌 | 28.9% | NT$8,000 | NT$+48,280 | +604% |
| **推快餐套餐** | **21.2%** | **NT$12,000** | **NT$+135,000** | **+1125%** |
| 全升級 | 10.3% | NT$58,000 | NT$+199,880 | +345% |

→ 用 simulation **找出真正瓶頸是廚房(84.7% 滿載)**, 加服務員是把錢花錯地方,**推快餐套餐才是最划算的單一動作**。

## 目標市場

- **TAM**: 全台餐飲業 17 萬家,5-30 人小餐廳佔 50% = **85,000 家**潛在客戶
- **WTP 錨點**: 1 次餐飲顧問訪談 NT$10-50K vs peakflow Solo NT$799/月 = **5-50x cost saver**
- **單一決策價值**: 老闆做錯 1 次「擴廚 vs 加人」決策,沉沒成本 NT$30-100K → peakflow 1 個月年費就回本

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Solo** | NT$799/月 | 1 家店,3 種情境/月,10 runs/sim | 個人老闆試用 |
| **Pro** | NT$1,999/月 | 5 家店,無限情境,50 runs/sim, 真實 POS 數據匯入 | 小型連鎖 (2-5 店) |
| **Enterprise** | NT$8,000+/月 | 大型連鎖客製,API 接 iCHEF/沛點,顧問支援 | 連鎖品牌 |

## Distribution

- **PTT food / restaurant 板** + **Dcard 餐飲業** SEO 長尾關鍵字「擴店該不該」「請外場 vs 加廚師」
- **FB「餐飲老闆交流」** 5-10 萬人社群,案例分享文(數字驅動最容易瘋傳)
- **iCHEF / 沛點 / Foodland POS** partner — 作為其報表附加功能(20% 拆帳)
- **餐飲顧問公司** 白標 — 顧問用 peakflow 當訪談工具(月 NT$5K 白標費)
- **商業周刊 / 食力 foodNEXT** 撰文「用 simulation 救餐廳尖峰營收」
- **餐飲博覽會** 攤位(台北國際食品展每年 6 月)

## 5% 滲透率 = 月 MRR

- 5% × 85,000 家 = 4,250 家 × Solo NT$799 = **月 NT$340 萬 MRR / 年 NT$4,080 萬 ARR**
- 加 Pro / Enterprise / 白標 → **翻倍至年 NT$8,000 萬 ARR 天花板**

## 風險與限制

- **模擬參數靠老闆主觀填**(平均烹飪時間 / 客人耐心) — 第一週用「全國中位數」, 之後用真實 POS 數據自動校準
- **沒考慮天氣 / 節慶 / 競爭店開幕** — Pro 版加 holiday-aware mode
- **單店 ROI 可能高估**(用 ×30 天假設天天滿座)— 報告自帶 warning 提醒打 7 折保守看
- **客單價變動** — 推快餐套餐時客單可能下降,模型用 fixed 客單,需老闆自己抓 15-20% 緩衝

---
*peakflow = peak-hour flow simulator. 給老闆每天問自己卻沒答案的問題,用 30 秒給出數字證據。*
