# storehunt — 台灣小型創業店面承租 optimal stopping 決策助手

**「我看過 15 間店面了,當前這間該不該下訂?」** 用 secretary problem (1/e 法則) 算出 **觀察期門檻** + 時間壓力調整 + 多屬性加權分數,給創業老闆 6 種決策 verdict (STRONG_ACCEPT / ACCEPT / OBSERVE / WAIT / RELUCTANT / RECONSIDER)。Optimal stopping 在 OR / 機率論已成熟 60+ 年,**但沒人做成台灣中小餐飲 / 零售創業老闆能直接用的工具**。

## 痛點

台灣每年新開立餐飲業 + 零售業 + 服飾業 = ~50,000+ 家店面承租決策。一個新店成敗 70% 看選址 (餐飲教科書共識), 但個人創業 / 加盟 / 小型連鎖**完全沒選址工具**:

- 找店 1-3 個月,看 20-50 間,**每間印象越來越模糊** (decision fatigue)
- 房東「今天不簽就讓給別人」高頻話術
- 自己感覺 vs 配偶感覺 vs 員工感覺,**沒共同分數可比較**
- 已花的看店成本 (油錢 / 時間 / 機會成本) **變沈沒成本壓力**,容易倉促簽
- 簽錯一間,**月損失 NT$30-100K** (流量低 / 租金高 / 押金被坑 / 裝潢預算超支)

實際情境驗證 (PTT Entrepreneur / Salary / Restaurant / FB 餐飲老闆社群):
- 「找店 1 個月看 20 間,房東說今晚不簽就讓給隔壁店家,該怎麼辦」(每週重複)
- 「全家便利商店、星巴克都有 site selection team,我們個人創業只能靠感覺」
- 「上個月簽了一間結果隔壁開了同類型,生意被分掉一半」

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(storehunt 補的) |
|---|---|---|
| 591 / 樂屋網 | 店面 listing | 不做 stopping decision, 不算 secretary threshold |
| 鋪鋪通 / 591 商用 | 店面 listing 含商用 | 同上,沒有「該不該下訂」邏輯 |
| 房仲 (永慶 / 信義 商用) | 帶看 + 議價 | **利益衝突**: 仲介月底結業績必推你下訂 |
| 餐飲顧問 (NT$30-100K/次) | 訪談主觀建議 | 太貴,沒「秒回」決策能力,不能 24h 內回覆房東壓力 |
| Excel 自己列 | 列分數但不會 stopping | 沒有 1/e 門檻邏輯,易陷沈沒成本 |
| ChatGPT 直接問 | 一次性建議 | 沒記住已看 N 間,沒持續決策 state |
| Site selection AI (歐美) | 大型連鎖用 | 國際大廠等級工具,個人創業 access 不到 |

**Gap 結構性**: Optimal stopping 理論 1875 起源 (Cayley) → 1960 secretary problem 正式化 (Gardner) → 60 年數學成熟,**沒人做成台灣中小創業者可用 SaaS**。Google「台灣 店面 optimal stopping」零中文 SaaS 結果。

## 架構 — Secretary Problem / Optimal Stopping (32nd 條 AI pattern)

```
Observed history (N₁ stores)
    │
    ▼
┌──────────────────────────────────────┐
│ 1. Multi-attribute score 每間 0-100   │
│    location 0.30 + rent 0.25 +        │
│    size 0.20 + deposit 0.10 +         │
│    contract 0.15                      │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ 2. Observation phase = ⌊N/e⌋ ≈ 37%   │
│    threshold = max(scores in phase)   │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ 3. Time-pressure adjustment           │
│    (剩餘 < 20% / 已超預算週數 / 房東   │
│     deadline) → multiplier ∈ [0.7,1.0]│
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ 4. Verdict (6 classes):               │
│   STRONG_ACCEPT (score ≥ threshold×1.1)│
│   ACCEPT        (score ≥ threshold)   │
│   RELUCTANT     (low remaining + close)│
│   WAIT_FOR_BETTER                     │
│   RECONSIDER    (score way below)     │
│   CONTINUE_OBSERVATION (still in N/e) │
└──────────────────────────────────────┘
    │
    ▼
Theoretical P(picked best) ≈ 1/e ≈ 37%
```

**100% 純函式 stdlib** (math + statistics + dataclass + enum):
- `StoreAttributes`: 5 維屬性 (location / rent / size / deposit / contract)
- `composite_score`: weighted sum 0-100
- `observation_phase_size`: floor(N/e) Gardner 公式
- `observation_threshold`: max score during phase
- `time_pressure_adjustment`: pure function adjustment in [0.7, 1.0]
- `decide(state)`: 6-class verdict with reasoning signals
- `best_so_far`: highest-score store (for "you already missed it" warning)

**LLM 只負責**: 寫 180-250 字「給創業老闆讀的決策建議」+ 具體下一步 + 風險提醒
**LLM 絕不負責**: 計算 score / threshold / verdict (數字 100% 來自純函式)

## 使用示例

```bash
# 純函式模式 (無 API key)
python storehunt.py --search samples/store_search.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python storehunt.py --search samples/store_search.json
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本: 陳老闆 30 歲離職創業, 30 坪日式定食, 找店 4 週看了 15 間, 房東 P 要求 24h 內回覆

| 指標 | 值 | 解讀 |
|---|---|---|
| 觀察期 (N/e) | 11 間 | 已過,進入決策階段 |
| Observation threshold | 76.5 | 觀察期最高分 (內湖店 H) |
| 時間壓力調整 | × 0.95 → 72.7 | 房東 deadline + 半過搜尋週期 |
| 當前店 (松菸店 P) | **80.4** | 顯著高於門檻 |
| **Verdict** | **🟢 STRONG_ACCEPT** | 強烈建議簽 |
| Theoretical P(best) | ~36.8% | 在 i.i.d. 假設下 |

## 目標市場

- **TAM**: 每年新開立餐飲業 + 零售業 + 服飾業 + 補習班 + 美業 + 烘焙 ≈ **50,000+ 家店面承租決策**
- **WTP 錨點**:
  - 簽錯一間月損 NT$30-100K × 6 月 (撐到結業) = NT$18-60 萬損失 vs Solo NT$199/月 = **900-3000x 防損保險**
  - 餐飲顧問 1 次 NT$30-100K vs 1 個月 Solo + Pro 試用 = **300-1000x 便宜**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 5 間/月,基礎 verdict | 試用 |
| **Solo** | NT$199/月 (一次性 NT$799 找店一輪) | 無限店 + 自訂權重 + 7 種產業 preset | 個人創業 |
| **Pro** | NT$499/月 | + 多人(配偶/合夥人)共評 + 圖片上傳 + LINE 提醒 | 多人決策 |
| **Franchise** | NT$2,999/月 | 加盟主總部用,批量比對 10-50 候選 + API | 中小型加盟 |
| **Brokerage** | NT$15,000+/月 | 房仲公司白標,給客戶用建立 trust | 永慶 / 信義 商用部 |

## Distribution

- **PTT Entrepreneur / Restaurant / 餐飲 / Salary** 板長尾 SEO
- **Dcard 創業 / 餐飲 / 家**
- **FB「台灣餐飲老闆交流」** 5-10 萬人社群 + **加盟主社群** + 「商業地產投資」社群
- **餐飲展 / 加盟展** booth (台北烘焙展每年 3 月, 餐飲展 6 月, 加盟展 8 月)
- **YouTube 創業 KOL** (王秋香 / Wendy 阿姨 / 創業學院 / Mr. 6) 案例合作
- **連鎖加盟總部 (路易莎 / 五十嵐 / Cama / Sukiya) B2B BD** 給加盟主用作篩選工具
- **房仲公司 商用部** B2B 白標
- **創業育成中心 / 中小企業協會** 配合計畫

## TAM

- 1% × 50,000 家年承租決策 = 500 家 × NT$799 = **年 NT$40 萬一次性收入**
- + Solo 月訂閱(平均 2-3 月 search 持續) 1,000 用戶 × NT$199 × 2.5 = NT$50 萬/月
- + Pro + Franchise + Brokerage → 年 ARR NT$2,000-4,000 萬
- 橫移港新馬 / 日本商店街(日本商家對選址工具尤重)→ 翻倍至 NT$8,000 萬 ARR

## 風險與限制

- **N (預估總共看) 不準** — 用戶估 30 間但實際只看到 20 間 → 門檻設過高;Pro 版加 dynamic N 修正
- **i.i.d. 假設違反** — 仲介可能先帶你看爛的,實際 adversarial sequence → 加入 "店面來源類型" feature 修正
- **不可回頭規則** — 現實 70% 情況房東給別人是真的,但 30% 是話術;UI 上強調 hold money 機制
- **多屬性權重產業差異大** — 餐飲 (location 40% rent 20%) vs 服飾 (location 50% size 15%) vs 烘焙 (location 30% rent 25% deposit 20%);Pro 版加 8 種產業 preset
- **裝潢成本未計入** — 月租低但要砸 NT$100 萬整修, 跟月租高但 turn-key 差很多;Pro 版加 amortization

---
*storehunt = secretary problem × 台灣店面承租 niche = 給創業老闆 24h 房東壓力下「秒回」的數學依據,而非靠感覺賭運氣。*
