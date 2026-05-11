# lawmate(法律好夥伴)

**台灣民眾日常法律問題 BM25 + LLM rerank 條文檢索 — 自然語言問 → 適用法條 + 怎麼用 + 應對步驟。**

民眾遇加班費 / 房客糾紛 / 消費爭議 / 鄰居噪音 / 道交事故 → **不知道適用哪條法**。lawmate 用 BM25 sparse retrieval 從 30+ 條典型條文找候選 → LLM 法律相關性 rerank → 給人話解釋 + 應對步驟(存證信函 → 調解 → 申訴 → 訴訟)。

跟 caselens(找相似**判決**)不同 — lawmate 找適用**條文**(statute-based),角度互補。

---

## 痛點

民眾每年遇上**勞資爭議 / 房客糾紛 / 消費投訴 / 鄰居噪音 / 道交事故** 數百萬件,**最迫切想知道「我適用哪條法」**:

> **「我加班沒拿到加班費,該怎麼辦?可以告嗎?」** — Dcard 工作板真實案例

> **「房東不還押金,我可以走法律途徑嗎?要引用什麼條文?」** — PTT home-sale

> **「鄰居小孩半夜跑跳影響睡眠,有什麼法律可以管嗎?」** — Mobile01 居家版

具體痛點:

- 民眾**不知道適用哪條法** → 一般 Google 給「教科書式長文」沒對應你的個案
- **LegalBank / 法源網 NT$3K+/月** 偏律師專業工具
- **司法院 / 法務部全國法規資料庫** 條文 6,000+ 條,**搜尋介面糟糕**沒有 semantic
- 律師諮詢一次 NT$3-5K,**單純問「適用哪條法」太貴**
- **ChatGPT 直接問**:容易**幻覺編造條文**(實際律師驗證錯誤率約 30%+)
- 法扶基金會免費但要排隊 3-7 天
- **沒有針對民眾日常法律問題的 statute-level 智能搜尋**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **法務部全國法規資料庫** | 條文 6,000+ 條,搜尋介面糟,無 BM25 / semantic |
| **LegalBank / 法源** | 月費 NT$3K+ 給律師專業用;民眾單次查不到性價比 |
| **caselens(r28)** | 找相似**判決**,不找適用條文(角度不同) |
| **律師諮詢一次 NT$3-5K** | 只問「適用哪條」太貴;律師多半引導你委任他 |
| **法扶基金會免費諮詢** | 排隊 3-7 天 |
| **ChatGPT / Claude 直接問** | **幻覺嚴重編造條文**(高達 30%+ 錯誤率) |
| **網路法律 KOL 文章** | 偏教科書,不對應個案;沒有可搜尋的 corpus |

**Gap 結構性**:BM25 1976 年成熟,但**沒人做成台灣民眾可用的條文檢索 SaaS**。Google「台灣 法律 條文 搜尋 民眾」零中文 SaaS 結果。

## lawmate 在做什麼

```
使用者自然語言問題
("我加班沒拿到加班費,每月加班 60 小時")
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Stage 1: BM25 sparse retrieval(bm25.py 純函式)            │
  │   - 中文 char-bigram tokenization(無需 jieba)              │
  │   - Inverted index over 30+ 台灣常用條文                   │
  │   - Okapi BM25 公式(k1=1.5, b=0.75)                       │
  │   - 取 top 10 候選條文                                      │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Stage 2: Claude LLM Re-rank by 法律相關性                  │
  │   - BM25 抓 lexical match(字面),但法律需要 semantic       │
  │   - LLM 重新排序,過濾「字面相似但實質無關」                 │
  │     範例:加班費 query 不應 return「酒駕處罰」               │
  │     (BM25 因「處罰」字詞重疊會誤帶)                          │
  │   - 排出 top 3 真正適用的條文                                │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 為 top 3 條文寫:                                    │
  │   - 「為什麼適用你的情況」(引用具體事實)                    │
  │   - 「怎麼用」(50-100 字解釋)                              │
  │   - 「應對步驟」(具體可執行:存證信函 / 調解 / 申訴 / 訴訟)  │
  │ + 結果預估(順利 / 最壞 / 時程)                            │
  │ + 警示注意事項(時效 / 蒐證 / 何時必須請律師)               │
  │ **LLM 永不下「會贏 / 會輸」斷論**                           │
  │ **LLM 嚴禁編造條文**(只引用提供的候選)                     │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **BM25 純函式 stdlib**:中文 char-bigram tokenization,不需 jieba 等外部 dependencies;對 30-100 條短法律文字相當有效。
2. **Two-stage retrieval**:BM25(快速大量過濾)+ LLM(慢但準確的語意 rerank)= 經典 IR + LLM combo。Stage 1 為 Stage 2 縮小搜尋空間,Stage 2 為 Stage 1 矯正字面誤判。
3. **嚴格的 LLM 約束**:LLM 只引用提供的候選條文(避免幻覺)、不下「會贏」斷論(避免誤導法律建議)、不勸完全提告或完全不提告。

## 動作

### 純函式 BM25 檢索(免 API key)

```bash
python3 lawmate.py --query "我加班沒拿到加班費,每月加班 60 小時。公司不給加班費我該怎麼辦?" --no-ai --out output.md
```

輸出含 Stage 1 BM25 Top 10 候選 + Top 5 條文詳細 + query 拆解(高 IDF tokens)。

### 完整 Two-Stage AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 lawmate.py --query "..." --out output.md
```

加上 Claude Stage 2 法律 rerank + 為 Top 3 寫解釋與應對步驟 + 結果預估 + 警示。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示:
- 用戶問「加班費 + 每月加班 60 小時」
- BM25 Top 3 含 LSA-24(加班費)、LSA-32(加班上限)、**TRA-35(酒駕處罰 — 字面誤判)**
- LLM Stage 2 排除 TRA-35,改推 LSA-22(工資全額給付原則),正確抓到加班費 + 上限 + 工資保護三條
- 應對步驟:存證信函 → 14 天無回 → 勞工局申訴 → 必要時訴訟
- 結果預估:5 年內未付加班費約 NT$80-100 萬,3-6 月解決

`examples/sample_output_no_ai.md` 純函式模式,展示 BM25 字面誤判問題(TRA-35 進前 3)。

## 已驗證 smoke test

- ✅ Tokenize: 中文 char-bigram, 中英文混合, 單字邊界
- ✅ Build index: 29 條文, 1817 unique tokens
- ✅ 「加班費」query → LSA-24 排名第 1
- ✅ 「網購退貨」query → CPA-19 排名第 1
- ✅ 「鄰居噪音」query → APT-16 在 top 3
- ✅ 完全無關 query → 空結果不 crash
- ✅ Empty index 不 crash
- ✅ BM25 deterministic(同 input N 次相同結果)
- ✅ explain_query 找出高 IDF tokens(discriminative)
- ✅ IDF 計算正確(常見 token IDF 低,罕見 token IDF 高)
- ✅ 字面誤判 demo:加班費 query 在 BM25 中誤帶酒駕條文 → 證明需要 LLM rerank

## 專案結構

```
lawmate/
├── README.md
├── lawmate.py             # CLI(BM25 + LLM rerank)
├── bm25.py                # 100% 純函式 BM25(Okapi formula)
├── articles_db.py         # 29 條台灣常用條文 corpus
├── examples/
│   ├── sample_output.md          # AI 完整報告
│   └── sample_output_no_ai.md    # 純函式 BM25 模式
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 math + re + dataclass)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **擴展 corpus**:目前 29 條,真實版需 200-500 條涵蓋大多數民眾法律問題(刑法 / 性別工作平等法 / 行政程序法 / 智慧財產 / 商標 ...)
- **接全國法規資料庫 API**:法務部開放 API 可即時抓最新法規(條文 / 函釋 / 解釋令)
- **jieba 中文分詞**:char-bigram 對中文有效但 jieba 更準確(尤其是專有名詞)
- **Dense embedding hybrid**:BM25(sparse)+ BGE/E5 中文 embedding(dense)hybrid retrieval 通常更好
- **判例聯動**:lawmate 找出條文 → 跳轉 caselens 找該條相關判決,二者協作
- **存證信函 / 申訴書草稿**:整合 sudoc r8 / leasecheck r24 doc-gen
- **LINE Bot**:民眾 LINE 直接問,30 秒回適用條文 + 應對
- **法律新聞訂閱**:大型法規變動主動推播相關用戶

## 商業模式

| 方案 | 月費 / 單次 | 對象 |
|------|--------------|------|
| **Free** | 月 3 次 BM25 only | 試用 |
| **Solo** | NT$99 / 次 | 一般民眾遇單一法律問題 |
| **Pro** | **NT$199 / 月** | 月內無限查詢 + 結果預估 |
| **Studio** | NT$1,499 / 月 | 法律事務所助理 / 記帳士 |
| **B2B 公益** | 免費 | 法扶基金會 / 消基會 / 縣市消保官 |
| **B2B 保險 / 銀行** | 客製 NT$30K+ / 月 | 客服處理糾紛時用 |

### WTP 計算

- 律師諮詢一次 NT$3-5K vs lawmate NT$99 = **30-50x 便宜**
- 一個正確的應對步驟省下「亂試」的時間 / 金錢 / 機會成本(NT$10-50K)vs NT$199 月費 = **50-250x ROI**
- 法律事務所助理用 lawmate 取代「**自己讀條文做研究**」,每個案省 1-3 小時 × NT$1,500 = NT$1.5-5K/案

### TAM

- 台灣每年遇法律問題的成年人估 **500 萬人**(法務部 2022)
- 取 0.5% 滲透 = 2.5 萬人 × 平均 NT$99/年 = **年 NT$250 萬 ARR (single-use)**
- 加 Pro 訂閱(預估 1,000 訂閱)+ Studio + B2B → 年 ARR **NT$2,000-4,000 萬**
- 横移日韓港新 → 翻倍(各國法規完全不同,在地化是護城河)

## 早期 distribution

1. **PTT Law / WomenTalk / 工作板 / Soft_Job** — 痛點來源(每天無數「我這情況該告嗎」貼文)
2. **Dcard 法律 / 工作 / 房地產 / 消費** 板
3. **法扶基金會 / 消基會 / 縣市消保官** partner — 公益合作
4. **YouTube 法律 KOL**(雷皓明 / 李怡慧 / 柯郁哲)case study
5. **Google Ads** — 「我加班沒加班費」「網購退貨」等長尾關鍵字
6. **保險業務員 / 銀行客服** 工具(B2B2C)
7. **房仲 / 仲介公會** partner — 仲介常被問法律問題
8. **法規 podcast / 法律專欄** 內容合作

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **被認定為「無律師資格代為法律意見」** | **極高** | 報告底部多次明確「不是法律意見」+「請洽律師 / 法扶」;與律師合作背書;避免「替您打官司」用語 |
| **法規即時更新滯後** | 中-高 | 接法務部 API + 至少每月同步;明確標示「資料截至 YYYY-MM-DD」 |
| **LLM 編造條文** | 高 | 嚴格約束 LLM 只引用提供候選;Two-stage 設計避免幻覺;報告底部顯示「條文編號 + 法源」可驗證 |
| **個資 / 使用者法律問題隱私** | 高 | stateless API call;對話不上雲;企業版 self-host LLM |
| **律師 / 法扶反感(搶生意)** | 中 | 走 partner 路線;**lawmate 是「諮詢前的快速分流」**,不取代律師;法扶會喜歡因為減少他們的負擔 |
| **錯誤建議導致使用者損失** | 高 | 不下「會贏」斷論;建議都是「先存證信函」這種低風險步驟;**重大決策強烈建議律師確認** |

---

*第三十六輪在 2026-05-11 產出於 incubator(台灣優先,**第二十六個 AI 架構模式 — Information Retrieval / BM25 + LLM Re-ranking**)。跟前 35 輪所有 pattern 都不同架構。*
