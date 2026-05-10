# weddingmatch(婚攝媒合)

**台灣準新人婚攝風格 AI 配對 — 描述風格 + 預算 + 地區,30 秒拿到 Top 5 風格最像的婚攝師清單。**

把每對新人「刷 IG 滑 2-6 週才挑到一個風格對的婚攝」這個痛點,壓到一杯咖啡時間。

---

## 痛點

台灣每年 12-13 萬對新人,**婚攝挑選平均花 2-6 週**,卻是婚禮籌備裡風險最高的決定之一(預算 NT$5-15 萬、無法重來)。

> **「婚攝好難選,每個都說自己是 film 風,根本分不清楚 #婚禮籌備」**
> — Dcard 婚禮版

> **「有沒有婚攝推薦?風格是日系底片感預算 8 萬」**
> — PTT wedding 版,每週 5-10 則重複的詢問貼文

具體痛點:

- 每年 12-13 萬對新人 × 每對挑婚攝平均 2-6 週 × 滑 IG 50+ 個工作室 = **集體痛苦**
- 婚攝術語(film 風 / 底片感 / 電影感 / 日系)定義各家不同,新人**根本分不清誰是真的什麼風**
- 平均婚攝預算 NT$5-15 萬,選錯風險極高,但**沒有客觀比對工具**
- WeddingDay / 婚攝地圖 等台灣最大平台都是**廣告刊登模式**,沒有 AI 配對
- 全球無類似服務:The Knot (美) / Zankyou (歐) 都是廣告刊登,**沒有 CLIP-based 風格 embedding 配對**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **WeddingDay.com.tw** | 台灣最大婚禮媒合平台,但**純廣告刊登**,婚攝自行登錄無風格配對 |
| **婚攝地圖** | 人工瀏覽工具,無媒合演算法 |
| **PTT wedding / Dcard 婚禮版** | 用戶互推,**極度主觀 + 高度重複的詢問痛苦** |
| **滑 IG / FB hashtag** | 工作室自宣稱「日系底片感」「電影感」標準不一,**無法 cross-check** |
| **The Knot / Zankyou (歐美)** | 廣告刊登,且不在台灣;沒有風格 embedding |

**Gap 結構性**:WeddingDay 已有最大婚攝刊登庫,但它是**廣告主導商模**,不會做「主動配對」拉走自家流量。新進入者只要做出比 WeddingDay 更智慧的配對 + 雙邊都用 = 立即有差異化。

## weddingmatch 在做什麼

```
準新人輸入(自由文字或結構化)
  - 風格描述:「我喜歡日系底片感、不要太擺拍,有故事感像紀錄片」
  - 預算:NT$ 8-10 萬
  - 地區:北部
        │
        ▼
  Claude 解析 → 12 維 0/1 風格向量
   [film, digital, contrast, pastel, cinematic,
    posed, candid, journalistic,
    outdoor, indoor, studio, detail_focus]
        │
        ▼
  ┌──────────────────────────────────┐
  │ matching.py 純函式配對演算法       │
  │   1. cosine similarity vs 婚攝庫   │
  │   2. 預算過濾(below_budget 剔除) │
  │   3. 地區過濾(different 剔除)    │
  │   4. 排序(sim → price → region)  │
  └────────────────┬─────────────────┘
                   │
                   ▼
        Top N 婚攝師 + AI 寫的個人化推薦理由
        (cite 共同風格 tag + IG handle + 預算提醒)
```

3 個關鍵架構決策:

1. **`photographers_db.py` 結構化資料**:12 位 mock 婚攝師,每位附 12 維風格向量 + 預算 + 地區 + IG + 簡介。產品化後爬取 WeddingDay + IG + FB 婚禮社團 5,000+ 真實婚攝(需法律確認爬蟲合法性 + 婚攝師同意條款)。
2. **`matching.py` 100% 純函式**:cosine similarity + 預算/地區過濾 + 排序。LLM 永不介入排序計算 → 結果可重現、可單元測試、配對邏輯透明。
3. **AI 只負責兩件事**:① 把自由文字風格描述解析成 12 維 0/1 向量 ② 為配對結果寫人性化推薦理由(cite 共同 tag + IG)。**絕不**讓 AI 自己挑「Top 1 婚攝」 — 那是純函式工作。

## 動作

### 結構化 JSON 輸入(免 API key)

```bash
python3 weddingmatch.py samples/sample_query.json --no-ai
```

`samples/sample_query.json` 是模擬準新人查詢:北部、預算 8-10 萬、底片+紀錄片+戶外+隨拍 4 風格 = 1。

### 自由文字描述(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 weddingmatch.py --freetext samples/sample_query_freetext.txt --out output.md
```

Claude 解析「我跟未婚夫在台北籌備婚禮,喜歡日系底片感...」→ 12 維 0/1 向量,然後走同一套純函式配對。

### 預先產出的 demo

`examples/sample_output.md` 是完整配對報告。可看到:
- **Top 1**:阿杰 Jay (@jayphoto.tw) 100% 風格匹配(film_emulation + candid + journalistic + outdoor 4/4 全中)
- **Top 2**:阿哲 Z-Studio 75%(film_emulation + candid + journalistic 3/4)
- **Top 3**:Lulu Studio 75%(film_emulation + candid + outdoor 3/4)
- **Top 4**:小綠 Lin 50%(candid + outdoor 2/4)
- **Top 5**:阿丹 Dan 50%(candid + journalistic 2/4)

數學計算可重現(cosine_similarity 純函式)。

## 已驗證 smoke test

- ✅ Cosine similarity 數學:`(1,0,1,0)` vs `(1,1,1,0)` = 2/sqrt(6) = 0.8165 精確
- ✅ Zero vector → similarity = 0(不會 div by zero)
- ✅ 全 0 用戶 query → 0 matches(不勉強配對)
- ✅ 預算極低(NT$10K) → 0 matches(全部 below_budget 剔除)
- ✅ 北部 region 過濾:6 matches 全是北部 + 全台(中南部全剔除)
- ✅ Sample 結果可重現:Top 1 永遠是阿杰 Jay 100% 匹配

## 12 維風格 tag

| 維度 | 中文 |
|------|------|
| film_emulation | 底片感 / 真實底片相機 |
| digital_clean | 數位乾淨銳利 |
| contrast_high | 高對比 / 暗調 / 戲劇性 |
| pastel_soft | 粉嫩柔和 / 清新淡雅 |
| cinematic | 電影感 / 電影色彩 |
| posed | 擺拍 / 經典 portrait |
| candid | 隨拍 / 抓拍自然瞬間 |
| journalistic | 新聞紀錄式 / 故事感 |
| outdoor | 戶外 / 自然光 |
| indoor_ceremony | 室內儀式 / 教堂 / 飯店 |
| studio_glamour | 棚拍 / glamour |
| detail_focus | 細節控 / 飾品 / 場佈特寫 |

(可擴展至 30+ 維,涵蓋 black_white、aerial_drone、underwater、family_focused、couple_only 等更細風格。)

## 專案結構

```
weddingmatch/
├── README.md
├── weddingmatch.py        # CLI 主程式(LLM 解析 + 純函式配對 + AI 推薦理由)
├── matching.py            # 純函式 cosine similarity + 過濾 + 排序
├── photographers_db.py    # 12 位 mock 婚攝 seed + 12 維風格 tag 定義
├── samples/
│   ├── sample_query.json          # 結構化查詢
│   └── sample_query_freetext.txt  # 自然語言查詢
├── examples/
│   └── sample_output.md           # 預先產出配對結果
└── requirements.txt
```

總計約 450 行 Python。依賴僅 `anthropic`(自由文字 / AI 推薦理由模式才需要)。

## 真正產品要有但 prototype 沒做

- **真實 CLIP image embedding**:準新人上傳「喜歡的風格參考圖」→ CLIP / GPT-4o vision 抽 embedding → 與婚攝作品集 embedding 比對。Prototype 用 12 維 0/1 是簡化版,真實版用 768 維 dense embedding。
- **5,000+ 婚攝師資料庫**:爬 WeddingDay + IG 公開作品,需處理婚攝授權同意條款 + 著作權問題
- **婚攝端 dashboard**:婚攝可看「本月被多少新人匹配到 / 風格詞被搜尋次數」+ 自己更新作品集
- **新人端比較功能**:Top 3 並排對比 / 收藏 / 約見面預約
- **真實成交追蹤**:配對 → 約見 → 簽約 → 成交 全流程,佣金抽成
- **多預算層 / 多場景**(婚紗外拍、求婚、迎娶、宴客、結婚週年)
- **雙邊評價系統**:成交後新人可給星等回饋,影響日後配對排序
- **婚攝風格自動標記**:從新婚攝上傳的作品集 → AI 自動歸類風格 tag,不需要手動勾選
- **季節性流量管理**:春秋是婚攝旺季,系統提早提示「3 個月後檔期會緊」

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free**(婚攝端) | 基本曝光,3 個關鍵字 | 試用婚攝師 |
| **Pro 婚攝師** | **NT$ 800 / 月** | 個人婚攝(專業曝光 + AI 配對 + 1 行 IG 連結) |
| **Studio Pro** | NT$ 2,500 / 月 | 工作室(多攝影師帳號 + 作品集數量無限) |
| **成交佣金** | NT$ 1,000-2,000 / 對 | 透過平台簽約成交,平台抽佣 |
| **新人端** | 免費 | 流量引入 |

### WTP 計算

- **婚攝師端**:WeddingDay 廣告位約 NT$ 1,500-3,000/月,但**無主動配對**;weddingmatch NT$ 800/月便宜 + 多了 AI 主動曝光 = 直接搶流量
- **成交佣金**:婚攝平均單場 NT$ 8-15 萬,平台佣金 NT$ 1-2K = 1-2% 抽成,合理
- 100 位婚攝師上架 → 月 NT$80K MRR;1,000 位 → 月 NT$80 萬 MRR

### TAM

- 全台專業婚攝估 5,000-8,000 位
- 取 10% 滲透率 = 500-800 位 × NT$800 = **月 NT$ 40-64 萬 MRR**(核心訂閱)
- 加上 12-13 萬對新人/年 × 平台佣金 = 額外 NT$ 數百萬/年成交收入
- 海外橫移 香港 / 馬新 繁中市場 → x2

## 早期 distribution

1. **PTT wedding / Dcard 婚禮版** — 痛點來源即 distribution 來源,在「找婚攝」討論串底下發 demo 影片
2. **FB 婚禮社團**(「婚禮籌備分享」「結婚 Q&A」「婚攝交流」5-10 萬人社團)
3. **Instagram 婚禮 / 婚攝 KOL 合作 demo** — 一位網美 KOL 推薦能帶上千新人試用
4. **WeddingDay 競品策略**:在 Google Ads 競價「WeddingDay」「婚攝推薦」關鍵字,搶 SEO/SEM 流量
5. **婚禮顧問公司 partner**:幫新人媒合 → 顧問拿介紹費 + 平台得到客
6. **IG / 蝦皮婚紗外拍社群** — 配套蜜月 / 婚紗 / 求婚 KOL 一起做

最初 100 位 paying Pro 婚攝師 = 月 NT$80,000 MRR,3-6 個月內可達成代表 PMF 訊號到位。

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **WeddingDay 自己加 AI 配對** | 中~高 | 他們廣告商模有結構性衝突,動作會慢;搶心占率 |
| **婚攝肖像權 / 作品集授權** | 高 | day-1 就要簽訂使用條款;爬蟲僅取公開縮圖 + 連回原 IG;若爭議,撤下作品集 |
| **冷啟動雙邊市場(沒新人 / 沒婚攝)** | 高 | 婚攝端先 onboard(白名單前 50 位免費 6 個月);累積到 200+ 婚攝再開新人端 |
| **AI 解析自由文字錯誤** | 中 | 使用者可手動勾選 12 個 tag 校正;Prompt few-shot 大量真實 PTT/Dcard 文字訓練 |
| **婚攝風格主觀性大,新人覺得配對不準** | 中 | Top N(不是 Top 1)+ 互相對比 + 約見面 = 工具是「縮短候選清單」非「自動拍板」 |
| **海外 The Knot / Zankyou 進入台灣** | 低 | 婚禮在地化極強,海外品牌過去 10 年都進不來 |

---

*第十六輪在 2026-05-10 產出於 incubator(台灣優先,**第五個非 doc-gen 模式 — Matching with embedding similarity**)。跟前 15 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B / 長照 / 法律 / 獸醫 / 月報 / 健身 / 機車估價 / LINE 整單 / 補助 RAG / 餐廳排班 都不同 vertical 也不同架構。*
