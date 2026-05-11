# seatplan(座位計畫)

**台灣婚禮 / 喜宴座位編排 CSP 自動最佳化 — 200-300 賓客 + 多重 constraints(VIP / 不能同桌 / 必同桌 / 桌主題)→ 純函式 Simulated Annealing 求解 → AI 寫每桌 narrative + 風險點 + 最終調整建議。**

把婚禮顧問「**排桌 20+ 小時**」壓縮到「**1 分鐘自動編排 + 30 分鐘人工微調**」。

---

## 痛點

- 每對台灣新婚夫婦平均 **20-30 桌 × 10 人 = 200-300 賓客**
- 婚禮顧問收 NT$10-30K / 場,**排桌佔 40-50% 工時**(20+ 小時)
- PTT wedding「我家 20 桌排到崩潰」;Dcard 婚禮版「**WeddingDay / 喜恩**都是模板網站,**沒做 AI 自動排桌**」
- 約束複雜:VIP / 雙方家族 / 同事 / 同學 / 不能同桌的人(離婚夫婦 / 宿敵 / 不熟酗酒大叔)
- Excel 手排只能憑感覺,改一個 constraint 全部要重排
- 海外 wedding-seating tools(AllSeated / WeddingHappy) 不認識台灣婚禮文化(主桌 / 圓桌 10 人 / VIP 長輩)
- CSP / OR-tools 50 年成熟,**沒人做成台灣新婚夫婦可用 SaaS**

## 為什麼現在沒對的工具

| 既有工具 | 為什麼不行 |
|---|---|
| **WeddingDay / 喜恩 / Happy Wedding** | 模板網站做廣告;不做座位 |
| **AllSeated / WeddingHappy (海外)** | 英文 + 不認識台灣婚禮(主桌 / 10 人圓桌 / VIP 長輩) |
| **婚禮顧問人工** | NT$10-30K / 場;排桌 20+ 小時是顧問時間黑洞 |
| **Excel 手排** | 改 1 個 constraint 全部要重排;沒最佳化 |
| **OR-tools / Google CP-SAT** | 給研究員;新婚夫婦看不懂 |
| **ChatGPT 直接問** | 不能跑迭代優化;每次都 hallucination |

## seatplan 在做什麼

```
新婚夫婦 / 婚禮顧問上傳賓客 JSON
  (guests: 名字 + group + must_pair / avoid_pair + VIP +
   tables: 容量 + is_vip + preferred_groups)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ csp.py 100% 純函式 stdlib(random + math + dataclass):    │
  │   1. _greedy_initial: VIP → VIP 桌;同 group + preferred  │
  │      group 桌優先;從大 group 開始分配                       │
  │   2. simulated_annealing:                                  │
  │      - 隨機 swap 兩個 guest                                 │
  │      - cost 下降 → 接受;cost 上升 → 用 exp(-Δ/T) 機率接受  │
  │      - 溫度逐步冷卻(cooling_rate=0.9995)                   │
  │      - 5000-8000 iterations 後收斂                          │
  │   3. cost function:                                        │
  │      - HARD: avoid_pair +100 / must_pair +50 / VIP +30 /  │
  │        overflow +200                                        │
  │      - SOFT: group cohesion -1 / monopoly +10 /            │
  │        preferred mismatch +3                                │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 為每桌寫:                                            │
  │   - 60-100 字 narrative(主題 + VIP 介紹 + 預期氛圍)        │
  │   - 重點賓客提醒                                            │
  │   - 跨 group 安排的解釋                                     │
  │ + 潛在風險點(3-5 條)                                     │
  │ + 最終調整建議(2-3 條人工 swap / 加桌建議)                 │
  │ **LLM 永不重新分配座位 — CSP solver 的工作**                │
  └──────────────────────────────────────────────────────────┘
```

## 動作

### 純函式 CSP / SA(免 API key)

```bash
python3 seatplan.py samples/wedding.json --no-ai --out output.md
```

`samples/wedding.json` 是「陳大華 + 林惠美」48 賓客 × 6 桌(主桌 VIP + 新郎/新娘家族 + 新郎/新娘同事 + 同學桌),含 must_pair_with(夫妻 / 父母)+ avoid_pair_with(陳大叔 vs 陳二叔有過節 / 老趙 vs 老錢離職前舊怨)。

### 完整 AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 seatplan.py samples/wedding.json --out output.md
```

加上 Claude 為每桌寫 narrative + 風險點 + 最終調整建議。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示:
- 48 賓客 × 6 桌,0 violations 全滿足
- 陳大叔 ↔ 陳二叔 / 老趙 ↔ 老錢 全部成功分桌
- 8 位 VIP 全在主桌
- 每桌 narrative 含預期氛圍 + 桌長建議
- 5 個風險點 + 3 個最終 swap 建議(王經理 ↔ 阿強)

## Smoke test (10 cases passed)

- 48 賓客 × 6 桌:0 avoid violations / 0 must violations / 0 VIP misplaced / 0 overflow
- 陳大叔 (G011) ↔ 陳二叔 (G014) 成功分桌
- 必同桌的夫妻(G003-G004, G011-G012)正確同桌
- 所有 8 VIPs 在 VIP 桌
- SA 從 cost 103 → -55(改善 158)
- Empty inputs 不 crash
- Deterministic(same seed → same plan)
- preferred_groups bias 有效(T02 新郎家族桌:6/8 是新郎家族)
- 48 全部 assigned

## 商業模式

| 方案 | 費用 | 對象 |
|---|---|---|
| **Free** | 30 賓客 / 月 1 次 | 試用 |
| **Solo** | NT$799 / 場 | 新婚夫婦 single 婚禮(限 200 賓客) |
| **Pro** | **NT$1,499 / 月** | 婚禮顧問月 5-10 場(包含 400+ 賓客) |
| **Studio** | NT$4,999 / 月 | 婚紗 / 喜宴公司每月 20+ 場 |
| **B2B 飯店** | NT$30K+ / 月 | 圓山 / 君悅 / 喜來登 wedding hall white-label |

WTP:婚禮顧問人工排桌 20 小時 × NT$500/hr = **NT$10,000 機會成本** vs Pro NT$1,499 月費 = **6.7x ROI**。新婚夫婦 wedding 預算 NT$30-100 萬,排桌花 NT$799 (Solo) 是「小錢解決大頭痛」。

TAM:台灣每年 12-13 萬對結婚,婚禮顧問 5,000+。1% 滲透 = 1,300 對 × NT$799 + 100 顧問 × NT$1,499 × 12 = **年 NT$300 萬 ARR**;加 Pro / Studio / B2B 飯店 → 年 ARR **NT$1,500-3,000 萬**;橫移日韓港新 → 翻倍。

## Distribution

1. WeddingDay / 喜恩 / Happy Wedding listing integration
2. PTT wedding / Dcard 婚禮版 / FB 婚禮社團
3. 婚禮顧問公會 / 婚紗業協會 partner
4. 圓山 / 君悅 / 喜來登 wedding hall 配合
5. YouTube 婚禮 KOL(婚禮籌備家 等) demo
6. 婚禮博覽會攤位

## 風險評估

| 風險 | 評估 | 緩解 |
|---|---|---|
| **真實婚禮 constraints 超過 5 類** | 中 | Pro 版可定義自訂 constraint;UI 列已知 constraint 範本 |
| **CSP 結果與人類直覺不符** | 中 | 提供「最終調整」工具,允許手動 swap;LLM narrative 解釋 |
| **大型婚禮 200+ 賓客 SA 太慢** | 中 | iterations 可調;大型用 OR-tools CP-SAT(Pro 版) |
| **賓客個資隱私** | 高 | stateless;名單不上雲;企業版 self-host |
| **WeddingDay / 喜恩自己做** | 中 | 在地化 + CSP 技術深度是護城河;走 partner 路線 |

---

*第三十七輪 2026-05-11,**第二十七個 AI 架構模式 — Constraint Satisfaction / Simulated Annealing**。跟前 36 輪所有 pattern 都不同。*
