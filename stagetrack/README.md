# stagetrack(階段追蹤)

**台灣房地產 listing 銷售階段 HMM 自動追蹤 — 從每週活動觀察(詢問 / 帶看 / 議價)用 Forward-Backward + Viterbi 推測 Hot / Warm / Cold / Closed 狀態,給房仲行動建議。**

房仲一人帶 20-50 個 listing,過去全憑直覺判斷哪個還活著、哪個該介入。stagetrack 用**隱馬可夫模型**從原始活動資料自動解碼 hidden state,告訴你**「L002 連續 12 週 Warm 滯留 → 該調價」「L005 從 Warm 加熱到 Hot 96% → 把握黃金 7 天不要降價」**。

---

## 痛點

台灣房仲 **60,000+ 人**,信義 / 永慶 / 中信 / 台慶等大型房仲品牌每人平均帶 20-50 個 listing:

> **「我手上 30 個 listing,我不可能每個都記得『上週有多少人問、哪個進入議價』。」** — Dcard 房仲版

> **「591 / 永慶平台給我看詢問數 / 帶看數,但不告訴我『**這個 listing 現在是 hot 還是 cold**』」** — FB 房仲社群

> **「屋主每週問我『**還有人問嗎?**』,我都用感覺回。」** — PTT home-sale

具體痛點:

- 房仲一人帶 **20-50 個 listing**,**每個都需追蹤進度**但腦容量不夠
- 591 / 永慶 / 中信 / 台慶平台**只給原始事件**(詢問 / 帶看 / 議價),**不做 state 推測**
- 房仲憑直覺判斷常常誤判:看似 Cold 的可能還在 Warm 等時機;看似 Hot 的可能 buyer 在比價
- 屋主每週問「**還有人問嗎?**」,房仲沒有結構化答案
- 沒有「**何時該介入**」的明確 trigger:多久 Cold 該調價?多久 Warm 該重拍?
- **HMM / Viterbi 1960 年代成熟**,但**沒人做成房仲 SaaS**
- ChatGPT 無法跑 forward-backward iterations

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **591 / 永慶 / 中信 / 台慶 listing 平台** | 只給原始事件數,**不做 state 推測**;沒「該不該調價」建議 |
| **房仲 CRM(IKEAR / 房仲達人)** | 紀錄 / 排程工具,**沒做機率模型** |
| **Excel 自己追蹤** | 30 個 listing × 12 週 = 360 cells 手動更新太累 |
| **R / Python HMM 套件(hmmlearn)** | 給研究員用,**房仲看不懂 transition matrix** |
| **房仲顧問 / 行銷顧問** | 不做 listing 級別追蹤 |
| **ChatGPT 直接問** | 不能跑 forward-backward / Viterbi |

**Gap 結構性**:Hidden Markov Model 60 年成熟,**沒人做成房仲可用的 SaaS**。Google「台灣 房地產 listing 階段 HMM」零中文 SaaS。

## stagetrack 在做什麼

```
房仲手上 5-50 個 listings × 12 週活動觀察 (JSON)
  每週活動值 0-4:
    0 = 無活動
    1 = 低活動(1-2 詢問 / 0 帶看)
    2 = 中活動(3-5 詢問 + 1 帶看)
    3 = 高活動(6+ 詢問 + 2+ 帶看)
    4 = 議價中(議價 + 帶看)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ hmm.py 100% 純函式 stdlib(只 math + dataclass):           │
  │   HMM 參數(domain knowledge 預設):                       │
  │     - 4 hidden states: Hot / Warm / Cold / Closed (absorbing) │
  │     - 5 observations: activity_level 0-4                   │
  │     - Transition matrix (4×4) + Emission matrix (4×5) +    │
  │       Initial distribution (4)                              │
  │                                                              │
  │   - forward: α_t(i) = P(obs_1..t, state_t=i)                 │
  │     (用 scaling 避免數值溢位)                                │
  │   - backward: β_t(i) = P(obs_{t+1..T} | state_t=i)          │
  │   - posterior: γ_t(i) = α × β / norm                        │
  │   - viterbi: 最可能 state sequence(用 log-space 避免溢位)  │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 每個 listing 輸出:                                          │
  │   - 12 週 Viterbi state sequence                            │
  │   - 當前 W12 posterior distribution (各 state 機率)         │
  │   - State transition history (W1 → Hot → W6 → Closed)       │
  │   - 連續在當前 state 的週數                                  │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 房仲顧問寫:                                          │
  │   - 每 listing 100-150 字故事化解讀(經歷什麼階段、為何 X)  │
  │   - 為當前 state 給 3-5 條立即可執行行動(調價 / 重拍照 /   │
  │     議價 / 撤回)                                            │
  │   - 早期警示信號(連續 N 週 Cold → 主動聯繫屋主)            │
  │   - Portfolio 整體建議(該集中時間在哪個 listing)            │
  │ **LLM 永不算 HMM 機率**                                     │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **HMM 用 hand-set 參數 (domain knowledge)**:60 年成熟的 transition / emission 在房仲 case 不需要訓練,房仲訪談得到的「**Hot → Cold 通常 4-6 週**」「**Cold 30% 機率撤回**」等可直接設定。未來如有充足資料可用 Baum-Welch 學習。
2. **數字 100% 純函式**:forward / backward / Viterbi / posterior 全在 `hmm.py`;LLM 永不參與機率計算。
3. **Closed 是 absorbing state**:成交或撤回的 listing 不會「復活」,模型正確處理「無活動」的雙義性(可能 Cold,也可能 Closed)。

## 動作

### 純函式 HMM 分析(免 API key)

```bash
python3 stagetrack.py samples/listings.json --no-ai --out output.md
```

`samples/listings.json` 是 5 個 listings × 12 週活動觀察,包含 4 種典型情境(成交 / Warm 滯留 / 衰退 / 始終 Cold / 加熱中)。

輸出含 portfolio 摘要表 + 每 listing 12 週 state sequence + posterior 分布。

### 完整 AI 房仲顧問模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 stagetrack.py samples/listings.json --out output.md
```

加上 Claude 寫故事化解讀 + 3-5 條立即行動 + 早期警示 + portfolio 建議。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示 5 個 listings 的不同 state 演變與對應建議:
- L001 (信義 28M) Hot → Closed 5 週成交
- L002 (板橋 14M) Warm 滯留 12 週 → 建議降價 3-5%
- L003 (新店 9M) Hot → Warm → Cold 三階段衰退 → 大幅調整
- L004 (中壢 18M) 始終 Cold → 結構性偏高建議重委託
- L005 (台中 12M) Warm → Hot 加熱中 → 把握黃金 7 天

`examples/sample_output_no_ai.md` 純函式模式輸出。

## 已驗證 smoke test

- ✅ Empty / single observation 邊界正確
- ✅ All-high obs → 全 Hot
- ✅ All-zero obs → Cold/Closed 收斂
- ✅ Posterior 每個 t sum to 1.0(±1e-3)
- ✅ Transition / Emission 矩陣 row sums = 1.0
- ✅ analyze_listing 結構完整
- ✅ Sample 5 listings 各自 state 符合預期(L001=Closed / L002=Warm / L004=Closed / L005=Hot)
- ✅ 純函式 deterministic
- ✅ Closed 是 absorbing state(進入後不離開)
- ✅ HMM 對「**5 週連續高活動**」正確判定為 Hot 5 週
- ✅ Viterbi 算法用 log-space 避免數值溢位

## 專案結構

```
stagetrack/
├── README.md
├── stagetrack.py          # CLI(讀 JSON + 純函式 HMM + LLM 房仲顧問)
├── hmm.py                 # 100% 純函式 HMM (forward / backward / Viterbi)
├── samples/
│   └── listings.json      # 5 listings × 12 週 (4 種典型情境)
├── examples/
│   ├── sample_output.md          # AI 完整報告
│   └── sample_output_no_ai.md    # 純函式模式
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 math + dataclass)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **接 591 / 永慶 / 中信 / 台慶 / 信義 API**:每週自動拉每個 listing 的詢問 / 帶看 / 議價數
- **Baum-Welch learning**:有 1,000+ 已成交 listing 後可以**自動學 transition / emission**
- **多 observation streams**:把詢問 / 帶看 / 議價分開觀察(用 multivariate HMM)
- **個別 listing 客製 HMM**:豪宅 / 公寓 / 套房等不同物件用不同模型參數
- **LINE Bot 警示**:某 listing state 變 Cold → 立即推播房仲
- **Portfolio dashboard**:房仲一鍵看 30 個 listings 的 state 分布
- **Cohort 分析**:看「某地段 / 某價位區間」的 HMM transition 差異
- **房仲協作版**:店長看店內所有業務員的 listings 狀態

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 5 listings 分析 | 試用 |
| **Solo** | **NT$499 / 月** | 個人房仲 30 listings + LINE 警示 |
| **Pro** | NT$1,499 / 月 | 5-10 人小型房仲店 + portfolio 視覺化 |
| **Enterprise** | NT$5,999 / 月 | 連鎖房仲分店 30+ 業務員 + API 整合 |
| **B2B 房仲總部** | 客製 NT$50K+ / 月 | 信義 / 永慶 / 中信總部 white-label |

### WTP 計算

- 房仲每月帶 3-10 個 listing 成交,**每筆收 1-3% = NT$15-100K**;一次擋下「白費 3 個月在 Cold listing」可以省 NT$30-60K 機會成本 vs Solo NT$499 = **60-120x ROI**
- 房仲對「**減少屋主追問次數**」高度敏感,週度報告省 1 小時 × 4 週 × NT$500 = NT$2,000/月 vs NT$499 = 4x ROI

### TAM

- 台灣房仲約 60,000 人,5-10 人小型房仲店約 3,000 家
- 取 1% 滲透 = 600 個房仲 × NT$499 + 30 店 × NT$1,499 = **月 NT$34 萬 MRR / 年 NT$410 萬 ARR**
- 加 Enterprise 連鎖店 + 總部 white-label → 年 ARR **NT$2,000-4,000 萬**
- 横移日韓港新 → 翻倍

## 早期 distribution

1. **PTT home-sale / Dcard 房地產 / FB 房仲社群** — 痛點來源
2. **591 / 永慶 / 中信 / 台慶 / 信義 房仲品牌訓練課程** partner
3. **大型房仲店長 / 主任 BD** — 一間店 = 5-10 個業務員授權
4. **房仲教育機構 / 房屋仲介公會** 推廣
5. **YouTube 房地產 KOL**(田大偉 / 帥過頭 / Sway)合作 case study
6. **591 / 樂屋網 listing 平台 integration partner**(若開放)
7. **房仲技術年會 / 房地產 expo** 攤位

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **591 / 永慶等平台不開放 API** | 高 | 先做手動 / CSV 上傳;後期談 integration |
| **HMM 預設參數不符各地市場** | 中-高 | Pro 版可調 transition / emission;Enterprise 版可用屬地化參數 |
| **房仲覺得太技術** | 中 | UI 完全避免「Hidden Markov」「Viterbi」術語;只說「銷售階段追蹤」 |
| **大型房仲品牌 (信義 / 永慶) 自己做** | 中 | 在地化 + 跨平台(不依賴單一品牌)+ 多年技術積累是護城河 |
| **屋主資訊隱私** | 中 | listing 是公開資料;只追蹤活動次數不追蹤具體 buyer 個資 |
| **HMM 預測錯誤導致房仲誤判** | 中 | UI 顯示信賴度 + 多次強調「不取代房仲判斷」 |

---

*第三十五輪在 2026-05-11 產出於 incubator(台灣優先,**第二十五個 AI 架構模式 — Hidden Markov Models / Sequence Labeling**)。跟前 34 輪所有 pattern 都不同架構。*
