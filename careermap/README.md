# careermap -- 台灣高中 / 大學畢業生 個人職涯方向 SOM 2D map

**「資管系應屆畢業生我該選軟工還是顧問? 行銷企劃比較適合我嗎?」** 用 Kohonen 1982 Self-Organizing Map 把 12 維個性 / 技能 / 偏好向量投影到 2D 拓樸 map, 找到「跟你最像的人通常選什麼職涯」+ 鄰近 cells 提示相近選項。純函式 SOM 訓練 + min-max scaling + BMU + labeled-cell fallback, 80 個歷史 profile 訓練, 應屆 / 在學生 30 秒拿到 8 大職涯方向客觀 mapping。

## 痛點

台灣高中 / 大學畢業生職涯選擇:
- **大學畢業生**: ~15 萬/年 (教育部 113 學年資料)
- **高中 / 高職畢業生**: ~25 萬/年
- **總計**: ~40 萬人/年 在「選系 / 選工作」決策關鍵期
- **教育部 113 統計**: 大學畢業生 25% 第一份工作做的不是科系相關
- **1/3 在三年內換工作** -- 因為「念了才知道不適合」

**學生 / 應屆畢業生痛點** (PTT C_Education / Dcard 工作 / 大學 / FB「應屆畢業生交流」5-10 萬人社群):
- 「資管系該當軟工還是顧問?」「文組能轉產品經理嗎?」(每週重複)
- 「父母叫我考公務員, 但我喜歡寫程式」
- 「104 / 1111 / Cake 給我看一千個職位, 我不知道哪個適合我」
- **學校輔導室一對一輔導 1:200 比例, 一年只能輪到一次**
- 求職 KOL (大人學 / Mr. 6 / 矽谷阿雅) 內容導向, 沒個人化分析

**家長 / 老師 痛點**:
- 「我女兒分析能力強但口才不好, 適合什麼工作」(父母只能憑經驗)
- 「全班 30 個學生我只能整體建議, 沒法個別性向診斷」

**現有資源**:
- 大考中心 / 心測中心 性向測驗: 國中 / 高中時做過, 但結果 PDF 看過就忘
- 104 / 1111 / Cake 求職平台: Job listing 不做個人化 mapping
- 16PF / MBTI / Holland Code: 國外為主, 不對應台灣職涯生態
- 學校輔導室: 1:200 比例, 機會少
- 求職 KOL: 內容導向, 沒個人化

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(careermap 補的) |
|---|---|---|
| 大考 / 心測中心性向測驗 | 國中 / 高中時做 + PDF | 結果一次性, 沒延續, 不對應職涯 |
| 104 / 1111 / Cake | Job listing | **無個人化 mapping**, 不告訴你「跟你像的人選什麼」 |
| 16PF / MBTI / Holland | 海外性向測驗 | 不對應台灣職涯生態 + 不用 SOM 拓樸視覺化 |
| 學校輔導室 | 一對一諮詢 | 1:200 比例 + 人工 + 主觀 |
| 求職 KOL (大人學 / 矽谷阿雅) | 內容導向 | 沒個人化分析 |
| ChatGPT 一次問 | 一次性建議 | 不能持續學, 沒台灣畢業生 profile 資料 |
| **salaryci r41** (本 incubator) | 薪資談判 conformal CI | 完全不同問題: 議價 vs 性向 |
| **cramlead r56** | 補習招生 lead | 完全不同問題: 招生 vs 性向 |
| **examready r40** | 升學考前排程 | 完全不同問題: 排程 vs 性向 |

**Gap 結構性**: Self-Organizing Map (Kohonen 1982) 學術成熟 43+ 年, **沒人做成台灣繁中應屆畢業生可用 SaaS**。Google「台灣 SOM 職涯」零本土 SaaS。

## 架構 -- Self-Organizing Map (54th 條 AI pattern)

```
80+ 各職涯歷史 profile (12-dim 個性 + 技能 + 偏好)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 1. Min-max scaler (per feature):              │
│    x_scaled = (x - min) / (max - min)         │
│    Constant-feature safeguard -> 0.5          │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 2. Initialize 8 × 8 SOM grid:                 │
│    Each neuron has 12-dim weight vector       │
│    Uniform [0.2, 0.8] random init             │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 3. Online competitive training (80 epochs):   │
│    For each input x in shuffled order:        │
│      BMU c = argmin_i ||w_i - x||²            │
│      For each neuron j:                       │
│        h(c,j,t) = exp(-||pos(c)-pos(j)||²    │
│                       / (2 sigma(t)²))        │
│        w_j <- w_j + eta(t) * h(c,j,t)         │
│                       * (x - w_j)             │
│    eta(t)   = eta_0 * exp(-t / tau_eta)       │
│    sigma(t) = sigma_0 * exp(-t / tau_sigma)   │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 4. Label assignment (majority vote):          │
│    For each training (x, career_label):       │
│      Find BMU                                 │
│      Increment counter[BMU][career_label]     │
│    label_grid[r][c] = argmax counter[r][c]    │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 5. Predict new x:                             │
│    BMU = closest cell in weight space         │
│    If BMU has label -> recommend that career  │
│    Else -> recommend nearest labeled cell    │
│           (SOM dead-cell fallback, canonical) │
│    Adjacent cells = "相近但不同的選項"        │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Diagnostics:                                  │
│   • Quantisation error (mean ||x - w_BMU||)   │
│   • Topographic error (1st vs 2nd BMU adj)    │
│   • 2D label-grid map (text visualisation)    │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + random + statistics + dataclasses + collections):
- `init_som / find_bmu / fit_som`: 標準 Kohonen 在線競爭學習
- `_neighbourhood`: Gaussian h(c, j, sigma) on 2D grid distance
- `assign_labels`: 每 cell majority vote 訓練樣本標籤
- `predict`: BMU + 自然回退至最近 labeled cell (cells between trained zones)
- `quantisation_error / topographic_error`: SOM 品質診斷
- `fit_minmax_scaler / apply_minmax`: 特徵縮放 [0, 1]

**LLM 只負責**: 寫 280-340 字「給應屆 / 在學生的職涯探索行動 + 真喜歡 vs 父母推薦訊號 + 風險」
**LLM 絕不負責**: 計算 BMU / distance / clustering (數字 100% 來自 SOM)

### 為什麼 SOM 適合這個 use case (vs HAC r52 / DBSCAN r52 / EM r34 / Spectral r63)

- **SOM**: 給**拓樸保持的 2D 視覺化** + 個性「梯度」清楚 (e.g. 軟工 → 顧問 是漸進不是斷裂), 鄰近 cells 自然提示「相近但不同」選項
- **HAC r52 kindergrid**: 樹狀分群, 不給 2D 拓樸視覺化, 不易說「你像 X 但離 Y 很近」
- **Spectral r63 topiclens**: 圖譜社群檢測, 適合 graph-defined 物件 (共錯題目), 不適合連續向量
- **EM r34 daypart**: 假設高斯分布, 適合 prob 分群, 不給 2D map
- **DBSCAN r52**: 適合 noise 多 + 密度差大的 case, 不給拓樸

SOM 的獨特優勢:
1. **拓樸保持**: 個性相近的職涯在 2D map 上相鄰 (e.g. 顧問 ↔ 創業 ↔ 業務 是連續區域), 自然給「探索選項」
2. **可視化 friendly**: 8×8 grid 直接 print 成 ASCII, 適合 CLI / web
3. **Dead-cell 自然回退**: 樣本不足的 cell 用最近 labeled cell, 系統化處理冷啟動

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 careermap.py --data samples/profiles.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 careermap.py --data samples/profiles.json

# 調整 SOM 大小 / 訓練 epoch
python3 careermap.py --grid-h 10 --grid-w 10 --epochs 150
```

預期輸出 (詳見 `examples/sample_output.md`):

陳同學 22 歲資管系應屆畢業生 (analytical 8 / tech 7 / social 6 / structure 5 / learning_speed 8):

**2D SOM map** (8 個職涯各自佔據區域):
```
    |  0  |  1  |  2  |  3  |  4  |  5  |  6  |  7  |
  0 |業務 |業務 |  .  |  .  |創業 |  .  |顧問 |顧問 |
  1 |業務 |  .  |  .  |創業 |  .  |  .  |  .  |顧問 |
  3 |行銷 |行銷 |  .  |  .  |  .  |  .  |軟工 |軟工 |
  ...
  7 |老師 |老師 |  .  |  .  |研究 |研究 |  .  |研究 |
```

→ BMU = [3][5] 沒有訓練樣本對應 (位於軟工 / 顧問 zone 中間), **自然回退至最近 labeled cell [3][6] = 軟體工程師** (距離 0.566)
→ 訓練診斷: QE 0.218, TE 7.5% — well-fit SOM

## 目標市場

- **TAM**:
  - 大學 / 高中 / 高職畢業生: 40 萬/年
  - 在校大學生 / 高三生 / 高二生: 100 萬+ (考慮重複)
  - 學校輔導室 / 學生諮商處: 4,500 所學校
  - 企業 HR / 招募部 (B2B 性向比對): 中大型 ~5,000 家
- **WTP 錨點**:
  - 選錯系第一年休學損失 NT$12 萬學費 + 一年機會成本 NT$50 萬+ = NT$60 萬+ vs Solo NT$199/月 = **3000x 防錯**
  - 應屆畢業生選錯第一份工作浪費 1-2 年 = NT$60-120 萬機會成本

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 次性向 mapping | 試用 |
| **Solo** | NT$199/月 | 無限次更新 + 4 種職涯深度報告 + LINE 推播職涯活動 | 個別學生 |
| **Family** | NT$399/月 | 父母共讀模式 + 1 對 1 通話建議 | 全家共用 |
| **School** | NT$4,999/月 | 整校 + 輔導室 dashboard + 班級對比 + 學期追蹤 | 高中 / 大學輔導室 |
| **District** | NT$15,000+/月 | 縣市教育局 + 跨校 anonymized 比較 + 政策制定 | 教育局 |
| **HR** | NT$30,000+/月 | 企業招募 性向比對 + API + 客製職涯 schema | 大型企業 HR |

## Distribution

- **PTT C_Education / SeniorHigh / Salary / Soft_Job 板** 長尾 SEO
- **Dcard 大學 / 工作 / 申請季 / 升學專版**
- **FB「應屆畢業生交流」/「大學申請與選系」/「面試經驗分享」5-10 萬人社群**
- **YouTube 求職 / 職涯 KOL** (大人學 / Mr. 6 / 矽谷阿雅 / 啟點文教 / 啾啾鞋)
- **學校輔導室 partner** (高中 + 大學, 約 1,500 所重點校)
- **教育部 / 各縣市教育局 partner** (公益版 + 個人化 108 課綱)
- **大學 / 高中升學博覽會** (每年 1-2 月 + 7-8 月)
- **104 / 1111 / Cake 求職平台 integration** (新鮮人專區附 SOM)
- **大型企業 HR B2B BD** (聯發科 / 台積電 / 鴻海 / 國泰 / 中信 / 富邦) -- 校招性向比對

## TAM

- 0.5% × 40 萬畢業生 = 2,000 × Solo NT$199 = 月 NT$40 萬
- + Family 500 × NT$399 = NT$20 萬/月
- + School 200 × NT$4,999 = NT$100 萬/月 (4,500 所學校 4%)
- + District 20 × NT$15K = NT$30 萬/月
- + HR 50 × NT$30K = NT$150 萬/月
- 總計 **月 MRR NT$340 萬 / 年 ARR NT$4,000 萬**
- 加滲透 + 橫移日本 / 韓國 (高中 / 大學畢業生 + 終身學習) → **NT$1-2 億 ARR**

## 風險與限制

- **80 profile prototype 太小** -- real launch 需 ≥ 500 個各職涯實際工作 1-3 年滿意人士的 profile;鼓勵畢業生 contribute 換取免費 Solo 月
- **2D 拓樸壓縮損失**: SOM 把 12 維壓到 2D, 真實人格可能多維, 邊界職涯可能不準
- **Feature 主觀**: 12 個自評 score 受心情 / 自信影響, Pro 版加客觀指標 (學測級分 / 程式作業 / 實習評價 / 性向測驗結果)
- **Cold-start**: 新職涯類型 (e.g. AI 訓練師 / Vibe coder) 沒訓練樣本就找不到對應 cell, Pro 版持續加新 profile
- **個性 ≠ 命運**: SOM 給「目前 profile 最像哪群人」, **不代表只能走那條路**; 鄰近 cells 是合理的相近選項, 探索 mindset 比 dogmatic 更重要
- **不取代深度諮詢**: 大型決定 (轉行 / 換系 / 出國) 仍需學校輔導室 / 職涯顧問 / 業界 mentor 一對一輔導
- **隱私敏感**: 個人 profile 涉個資, 雲端版需匿名化 + 用戶同意 + 不販售給雇主
- **避免標籤化**: 切勿告訴學生「你是業務型」, 應強調這是「目前性向最像哪群人」的可變 state
- **18-22 歲 profile 變化快**: SOM 結果隨個人成長 / 接觸新領域而變, 每年重做 1 次比較好

---
*careermap = Kohonen 1982 Self-Organizing Map × 台灣高中 / 大學畢業生 niche = "12 維個性向量 → 8×8 SOM 拓樸 map → BMU + 鄰近 cells 探索" 比 104 / 1111 職位列表多一層個人化, 比 16PF / MBTI 更具拓樸視覺化, 比輔導室 1:200 比例可及性高。*
