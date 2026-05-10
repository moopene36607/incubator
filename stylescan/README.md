# stylescan(文癖掃描)

**台灣國高中作文 AI 代筆風險偵測 — 用「書寫指紋」純函式抓出風格落差。**

收 5 篇學生過去作文 + 1 篇本次作文 → 純函式抽 20 個 stylometric 特徵 → cosine 比對 → 標出疑似 AI 代筆的作品供老師判讀。

**stylescan 永不下最終結論。AI 代筆判定權永遠在老師。**

---

## 痛點

108 課綱重視寫作,**國中會考國寫滿分 30 分、國寫題型佔考試成績 1/4**。學生用 AI 寫作文激增,但繁中市場 **零工具**:

> **「全班 30 個學生有 5 個寫得跟翻譯論文一樣,我憑直覺懷疑但沒證據。」** — 國中國文老師,Dcard 教師版

> **「上次直接問學生『是不是用 AI 寫的』,他完全否認,後來家長還來抗議我懷疑學生。」** — PTT C_Education

> **「Turnitin 只有英文,中文丟下去全部 0%,根本看不出來。」** — 高中作文老師,FB 教師社團

具體痛點:

- 國高中老師 **4-5 萬人** + 補習班作文老師 5,000+,每位每週改 30-200 篇作文
- GPT / Claude / Gemini 中文流暢度高,**人工很難一眼看穿**
- 直接質問學生 → 學生否認 → 老師沒證據 → 沒辦法處理
- GPTZero / Originality.ai / Turnitin 都偏英文,**繁中失效**(經多位老師實測 false negative 極高)
- 大型 LLM 自己當偵測工具不可信(它就是來源,有強烈動機說「不是 AI」)
- 中文作文評分標準裡「真情實感」「個人聲音」權重大,但**老師沒有客觀工具量化「個人聲音」**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **Turnitin / GPTZero / Originality.ai** | 全部偏英文,繁中作文 ROC-AUC 約 0.55(幾乎跟丟銅板一樣) |
| **ChatGPT / Claude / Gemini 直接問「這是不是 AI 寫的」** | LLM 自己就是來源,強烈動機說「人類寫的」;且不知學生過去風格 |
| **Originality.ai for 中文** | 沒繁中模型,只有簡中且效果差 |
| **老師人工抓** | 30 篇作文 × 5 分鐘判讀 = 2.5 小時 / 班 / 週,大規模班導不可能 |
| **直接質問學生** | 沒證據 → 學生否認 → 沒辦法處理 + 信任受損 |
| **學術 Plagiarism check** | 偵測「跟既存文章像不像」,**對 AI 即時生成的新內容無效** |

**Gap 結構性**:中文 stylometric 工具長年在學術圈被研究(中央研究院 / 政大 / 台師大 NLP 組都有 paper),但**沒人把它做成國高中老師易用的 SaaS**。Google 搜尋「中文 作文 AI 偵測 教師」零 SaaS 結果。

## stylescan 在做什麼

```
學生過去 5 篇作文 (JSON)         本次作文 (txt)              AI 範本 corpus (JSON)
        │                              │                           │
        ▼                              ▼                           ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ style_features.py 純函式抽 20 個 stylometric 特徵                       │
  │   ① 句長分布 4 個(均/std/短句比/長句比)                              │
  │   ② 標點密度 7 個(逗 / 頓 / 分 / 問 / 嘆 / 引 / 刪)                  │
  │   ③ 詞彙風格 5 個(連接詞 / 語氣詞 / 抒情比擬詞 / 抽象思辨詞 / 古文書面詞) │
  │   ④ 結構特徵 3 個(段落數 / 段落長 std / 起承轉合 keyword)            │
  │   ⑤ 雜訊 1 個(emoji / 顏文字密度)                                  │
  └────────────────┬─────────────────────────────────────────────────────┘
                   │
                   ▼
          ┌────────────────────────────────────────┐
          │ 純函式 cosine similarity (純 stdlib):    │
          │   cosine(本次, 學生過去平均) = 0.71      │
          │   cosine(本次, AI 範本平均)  = 0.94      │
          │   學生內部一致度 = 0.87                  │
          └────────────────┬───────────────────────┘
                           │
                           ▼
          ┌────────────────────────────────────────┐
          │ 純函式判定 (decide_verdict):              │
          │   CONSISTENT / MILD_DRIFT /              │
          │   STRONG_DRIFT / **LIKELY_AI**           │
          │   邏輯透明、可單元測試、可重現          │
          └────────────────┬───────────────────────┘
                           │
                           ▼
                    Top 6 偏離特徵 + verdict
                           │
                           ▼
          ┌────────────────────────────────────────┐
          │ Claude 為純函式發現的差異寫:              │
          │   - 風格分析(老師易讀,引用具體 feature) │
          │   - 給學生的文體建議 3 條               │
          │   - 給老師的 follow-up 3 條(訪談 / 現場寫作) │
          │ **嚴禁:LLM 不下「就是 AI 寫的」結論**     │
          │ **保留誠實可能性(學生可能臨時讀了散文)** │
          └────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **數字 100% 純函式**:句長、標點密度、cosine、verdict code 全部在 `style_features.py` + `stylescan.py:decide_verdict`,LLM **永不參與相似度計算**。
2. **三向比對**(本次 vs 學生過去 vs AI 範本) — 比僅有「本次 vs 學生」更可信。能區分「學生成熟」(只 vs 學生下降但 vs AI 也下降) vs 「AI 代筆」(vs 學生下降 + vs AI 上升)。
3. **stylescan 永不下最終結論**:LLM 寫風格分析,但措辭強制為「風格大幅偏離」「AI 主導度高」「建議老師訪談確認」。**最終 AI 代筆判定權永遠在老師**,因為:① stylometric 不是 100% 準 ② 學生有可能模仿散文 / 家長協助潤稿 ③ 老師需要保留信任空間給學生。

## 動作

### 純函式偵測(免 API key)

```bash
python3 stylescan.py \
    --history samples/student_history.json \
    --new-essay samples/new_essay.txt \
    --ai-corpus samples/ai_reference_corpus.json \
    --title "逆境中成長" \
    --no-ai \
    --out output.md
```

`samples/` 包含:
- 5 篇陳小芸過去作文(七年級下 → 九年級上),口語化、句長 short variance、用「就」「結果」「超」、有 emoji
- 1 篇〈逆境中成長〉本次作文(刻意設計成 ChatGPT 風格 — 句長偏長、用「彼時」「然則」「不禁感慨」)
- AI corpus(3 篇 GPT/Claude/Gemini 中文範文,代表 AI 風格指紋)

預期輸出:`LIKELY_AI` verdict,cosine vs 本人 0.71、vs AI 0.94。

### 加 AI 寫風格分析(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 stylescan.py \
    --history samples/student_history.json \
    --new-essay samples/new_essay.txt \
    --ai-corpus samples/ai_reference_corpus.json \
    --title "逆境中成長" \
    --out output.md
```

加上:Claude 寫 150-250 字風格分析(挑 3-5 個關鍵 feature 差異說明)+ 給學生的文體建議 3 條 + 給老師的 follow-up 3 條(具體可執行,如「下週安排 30 分鐘現場寫作」)。

### 預先產出的 demo

`examples/sample_output.md` 是完整 AI 模式報告,展示對〈逆境中成長〉的 LIKELY_AI 判定 + 老師可採取的具體行動。

`examples/sample_output_no_ai.md` 是純函式模式輸出,證明 LLM down 也能用。

## 已驗證 smoke test

- ✅ 學生本人作文當作「新作文」交叉驗證 → CONSISTENT (cosine vs 本人 0.89, vs AI 0.73)
- ✅ AI 範文當作「新作文」 → LIKELY_AI (cosine vs 本人 0.81, vs AI 0.98, AI 主導度 +0.17)
- ✅ 預設樣本 (新作文 = AI-寫的〈逆境中成長〉) → LIKELY_AI (cosine vs 本人 0.71, vs AI 0.94)
- ✅ Identical input(學生平均 vs 學生平均) → 無 spurious diff
- ✅ 短文(< 50 字) → 全 0 features 不 crash
- ✅ Verdict 邏輯區分 LIKELY_AI 兩種觸發路徑(經典漂移 + AI 主導度)
- ✅ 純函式 deterministic,同樣輸入跑 N 次結果一致

## 專案結構

```
stylescan/
├── README.md
├── stylescan.py            # CLI(讀檔 + 跑純函式 + 呼叫 LLM)
├── style_features.py       # 100% 純函式 stylometric 抽取 + cosine + diff
├── samples/
│   ├── student_history.json     # 5 篇學生過去作文(陳小芸 七年級下 → 九年級上)
│   ├── new_essay.txt            # 本次作文(刻意 AI 風格)
│   └── ai_reference_corpus.json # AI 範本 corpus(3 篇 GPT/Claude/Gemini 範文)
├── examples/
│   ├── sample_output.md         # AI 模式完整報告
│   └── sample_output_no_ai.md   # 純函式模式報告
└── requirements.txt
```

依賴僅 `anthropic`(AI 模式才需要)。純函式部分零外部依賴(stdlib only)。

## 真正產品要有但 prototype 沒做

- **接 Google Classroom / 均一 / iLearn 等學習平台**:作文上傳即自動分析,免老師手動匯整 JSON
- **班級 dashboard**:一次掃 30 篇作文,直接列出 verdict = LIKELY_AI 的學生
- **校園版多學科**:擴展到歷史 / 公民申論題 / 跨校國寫測驗
- **歷史指紋更新**:學生交一篇就自動加進 history,書寫指紋會「跟著學生成長」(避免一年前 vs 現在誤報)
- **AI 範本 corpus 持續更新**:GPT-5 / Claude-Opus-5 / Gemini-3 上線時,需要重新 sample 範文 + recompute reference vector
- **多模型 ensemble**:加上「AI 代筆 likelihood」classifier(如 BERT 微調),跟 stylometric 結果 ensemble
- **教師訪談腳本生成器**:依據 LIKELY_AI 的具體偏離特徵,自動產出 5 句訪談引導問題
- **學生自評工具**:讓學生自己上傳作文看「我的書寫指紋」(不評斷 AI,而是讓學生看見「自己的聲音」)

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 5 篇分析 | 試用 |
| **Solo** | **NT$199 / 月** | 1 位老師,無限次分析 + 班級 dashboard |
| **Department** | NT$1,499 / 月 | 一個科 (5-10 老師),共享題庫與班級資料 |
| **School** | NT$4,999 / 月 | 整校 (30-100 老師),整合 Google Classroom |
| **City Edu** | 客製 NT$50,000+ | 教育局統一採購(覆蓋全縣國中) |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 老師每週改 30 篇 × 5 分鐘 / 篇判讀「是不是 AI」 = **2.5 小時 / 週機會成本**;月省 10 小時 × 老師時薪 NT$500 = NT$5,000
- vs Solo NT$199/月 = **25x ROI**
- 補習班 / 私校 老師薪資更高,WTP 可拉到 NT$300-500/月
- City Edu 採購一個縣市 30-50 萬 / 年是合理區間(已對標其他教育 SaaS 採購)

### TAM

- 全台國中 + 高中 + 補習班 國文 / 作文老師約 **5 萬人**
- 取 5% 滲透 = 2,500 人 × NT$199 = **月 NT$50 萬 MRR / 年 NT$600 萬 ARR**
- 加 Department + School + City Edu = 年 ARR **NT$1,500-3,000 萬**
- 橫移到大學(課程作業 / 期末報告)+ 港澳新馬中文教育市場 → 翻倍

## 早期 distribution

1. **教師 FB 社群**(「親師生交流園地」「中學國文老師」5-10 萬人)— 痛點來源 + 第一波種子
2. **PTT C_Education / Dcard 教師版** — 每週都有「學生用 AI 寫作」抱怨貼文,直接附 demo
3. **教師研習工作坊**(縣市教育局舉辦)— 30-50 位老師現場示範 + 課程贈送 1 個月 Free
4. **補習班分校 BD**(行動補習班 / 翰林 / 康軒)— 1 個分校決策 = 5-10 老師導入
5. **教育部 / 各縣市教育局 partner** — 108 課綱倡議「AI 工具負責任使用」,stylescan 是配套工具
6. **YouTube / Threads 教師 KOL**(雙語老爸 / 葉丙成 / 各國文 KOL)合作
7. **大學師培系** — 預備老師訓練時導入工具熟悉度,畢業後帶到第一線

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **學生 AI 模型升級導致 false negative 提升** | 高 | AI corpus 每季更新 sample;加多模態(段落結構 + 標點 pattern)避免單軸失效 |
| **學生反過來用 AI 模仿自己風格** | 中 | 暫時性風險(prompt-engineering 門檻高);長期靠多次點檢測累積一致性 |
| **老師誤用工具質問學生 → 親師衝突** | 高 | 工具措辭嚴控「不下結論」+ follow-up 建議都先溫和訪談;附使用指南影片 |
| **GPTZero / Originality 推中文版** | 中 | 在地化 + 教師 onboarding + 國中升學脈絡是護城河 |
| **Turnitin 推中文版** | 中 | 同上;且 Turnitin 走學術抄襲不擅長 stylometric |
| **學生個資 / GDPR** | 高 | 作文存校內 server / self-host LLM 選項;不上雲;只比對該學生本人歷史 |
| **stylometric 對短作文 (< 200 字) 不準** | 中 | UI 警告 + 短作文不下 LIKELY_AI 結論,只列 feature 比較 |

---

*第二十三輪在 2026-05-10 產出於 incubator(台灣優先,**第十三個 AI 架構模式 — Stylometric Matching**)。跟前 22 輪 doc-gen / pricing / OCR-aggregation / RAG / scheduling+LINE / matching-similarity / monitoring+alerting / churn / vision-pricing / vision-classification / personalization / time-series-anomaly 都不同架構。*
