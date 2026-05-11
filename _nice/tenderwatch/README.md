# tenderwatch(標案監測)

**台灣中小企業政府標案 AI 即時警示 — 政採網每日新公告 → 個人化匹配 → LINE 推播只給「我能做、值得標」的標案。**

把每天 500-800 件政府標案公告中翻找適合自家的工作,從「老闆每天 1-2 小時刷政採網還可能漏」壓到「LINE 訊息看一眼即可」。

---

## 痛點

台灣政府電子採購網每年發 **20 萬件**招標公告,但中小企業承包商面對的現實是:

> **「政採網搜尋介面真的爛到爆,還要一頁一頁翻,常常截止前兩天才看到。」**
> — PTT Soft_Job 板(reformulated from common pattern)

具體痛點:

- 政府採購網每日 500-800 件新公告,**人工篩選成本 1-2 小時/日 × 22 工作日 = 月 22-44 小時**
- 老闆 / 業務員時薪 NT$500-1,000 = **月 NT$11K-44K 機會成本**只在「找標案」上
- 漏掉一件適合的 → 1 件中標 NT$30 萬-3,000 萬不等,**單次漏接損失極高**
- 純關鍵字搜尋(政採網 RSS / 招標王)噪音極大:「資訊」關鍵字會抓到「資訊清潔工程」「資訊系統機房空調」「資訊大樓警衛」全不適合
- ChatGPT 直接問:**不知道每日新公告 + 不知道你公司具體能力 + 沒推播**
- **海外工具不存在**:Bonfire / GovWin 服務美國 SAM.gov,不認識台灣政採格式

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **政採網 RSS / Open Data** | 純關鍵字訂閱,**無語意理解**,「資訊」關鍵字噪音極大 |
| **招標王** | NT$299/月,2018 年介面,純關鍵字,**無 AI 分類** |
| **TenderAlert.tw** | 已停服 |
| **ChatGPT 直接問** | 不知道每日新公告 + 不知道你公司能力 + 不會推播 |
| **海外工具** | Bonfire / GovWin 只在美國市場,不認識台灣政採網 |
| **公司內部行政人員手刷** | 現況。每日 1-2 小時人工成本 |

**Gap 結構性**:政府採購網 OpenData API 是公開可合法取用的(政府為了 open government 政策推),但**沒有人有動力把它做成「個人化 AI 助理」**。招標王走了 8 年沒進化,新進入者只要做出「semantic match」這個維度即可差異化。

## tenderwatch 在做什麼

```
政府電子採購網 OpenData(每日 500-800 件新公告)
        │
        ▼
  ┌──────────────────────────────────┐
  │ tender_filter.py 純函式硬條件過濾   │
  │  ✗ 投標廠商最低資本額 > 用戶資本額  │
  │  ✗ 預算 < 用戶最低門檻              │
  │  ✗ 截止日距今 < N 天 (來不及準備)    │
  │  ✗ 標案類別在用戶排除清單           │
  │  ✗ 缺必備認證 (ISO 27001 等)        │
  │  ⇒ 通常剩下 5-15% 標案進入 LLM       │
  └────────────────┬─────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────┐
  │ Claude 對通過標案做 semantic match │
  │  - 讀標案描述 vs 公司能力描述       │
  │  - 給 0-100 score + 匹配級別        │
  │  - 列 key match points + key gaps   │
  │  - recommendation:投/找夥伴/不投    │
  └────────────────┬─────────────────┘
                   │
                   ▼
        ① markdown 詳細報告(老闆審閱用)
        ② LINE 推播純文字版(只列 score >= 70 高匹配)
```

3 個關鍵架構決策:

1. **硬條件 100% 純函式**:資本額、預算、截止日、認證、排除類別這些黑白判斷不交給 LLM,避免 hallucination + 省 80%+ token cost(只把通過硬條件的送 LLM)。
2. **LLM 做 semantic match scoring,不做最終決策**:LLM 給 0-100 + match_level + key_match_points + key_gaps + recommendation,但**最終投不投標仍是老闆決定**。LLM 是「縮短候選清單」工具,不是「自動投標機器」。
3. **雙輸出**:老闆看 markdown 詳細報告,業務 LINE 收推播只列「score >= 70 + 截止日 + 案號」精簡版,直接看完一眼決定要不要進辦公室準備。

## 動作

### 純條件過濾(免 API key)

```bash
python3 tenderwatch.py \
    --tenders samples/sample_tenders.json \
    --profile samples/sample_user_profile.json \
    --today 2026-05-10 \
    --no-ai
```

`samples/sample_tenders.json` 是 15 件 mock 政府標案(涵蓋資訊服務 / 工程 / 印刷 / 餐飲 / 顧問 / 教育訓練 各類別 + 不同預算 / 截止日 / 資本額要求);`samples/sample_user_profile.json` 是雲鼎資訊(中型 IT 顧問,5M 資本、18 員工、ISO 27001/9001、不接前端 UI/工程/印刷)。

### 完整 AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 tenderwatch.py \
    --tenders samples/sample_tenders.json \
    --profile samples/sample_user_profile.json \
    --out report.md \
    --out-line line_alert.txt
```

每天的 API cost 通常 NT$5-20(全公司用),取決於通過硬條件的標案數。

### 預先產出的 demo

`examples/sample_output.md` + `examples/sample_line_alert.txt` 展示:
- **15 件 → 7 通過硬條件**(8 件因資本額/預算/截止/類別/認證被剔除,理由透明列出)
- **AI semantic match 排序**:
  - 🔥 [92/100] HIS FHIR 介接(過去做過 3 家公立醫院 HIS = 完美命中)
  - 🔥 [88/100] 外交部雲端遷移(雲端 + ISO 27001 直接命中)
  - 🔥 [85/100] 北市市民 App 重構(過去做過縣市政府 App 後端)
  - ✅ [72/100] 國科會 LLM 研究(主題符合但需找學術夥伴)
  - ✅ [68/100] 北市 LMS(教育產業熟,但 LMS 前端 UI 不在能力 → 找夥伴)
  - 🟡 [55/100] 國發會數位轉型顧問(找智庫主導)
  - 🟡 [42/100] 臺中 AI 培訓(培訓非公司主業 → 不建議)
- **LINE 推播只列 score >= 70 的 4 件**,簡潔到 1 分鐘可看完決定

## 已驗證 smoke test

- ✅ 投標廠商資本額過濾(用戶 5M < 標案 8M 要求)
- ✅ 截止日 < 14 天準備期 → 過濾(食藥署案剩 10 天)
- ✅ 缺必備認證(ISO 27001 等)→ 過濾
- ✅ 排除類別(印刷 / 工程 / 餐飲)→ 過濾
- ✅ 多重 fail 同時列出(告示牌標案:預算太低 + 排除類別)
- ✅ `_days_until` 日期計算正確(2026-05-25 vs 2026-05-10 = 15 天)

## 專案結構

```
tenderwatch/
├── README.md
├── tenderwatch.py        # CLI 主程式(硬條件過濾 + LLM semantic match + 雙輸出)
├── tender_filter.py      # 純函式硬條件過濾
├── samples/
│   ├── sample_tenders.json       # 15 件 mock 政府標案
│   └── sample_user_profile.json  # 雲鼎資訊 IT 顧問公司 profile
├── examples/
│   ├── sample_output.md          # 預先產出的詳細報告
│   └── sample_line_alert.txt     # LINE 推播純文字版
└── requirements.txt
```

總計約 450 行 Python。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **政府電子採購網 OpenData API 接入**:每日 cron 抓新公告 JSON、增量處理新進件、儲存歷史
- **embedding-based semantic match**(取代 LLM scoring):每件標案 embed 一次,公司 profile embed 一次,cosine sim threshold 觸發 LLM 詳細評估 — 大幅降低 token cost
- **得標廠商分析**:整合得標公告 API,顯示「過去 1 年同類標案誰得標 / 平均得標金額」
- **截止日倒數 calendar**:整合 Google Calendar / Outlook,自動建立準備提醒事件
- **多 profile 多公司**:同一 user 管多家公司的標案分流
- **歷史 win/loss 學習**:用戶標 win/loss 後系統學習什麼類型標案易中標
- **聯合投標媒合**:當 score 60-80(部分能力符合)時自動推薦合作夥伴
- **PDF 招標文件解析**:某些標案要看完整 PDF 才能完整評估,vision API 抽結構
- **國際標案**:政院公佈的國際援助 / WTO 政採案

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 5 件 / 日 | 試用 |
| **Solo** | **NT$799 / 月** | 1 公司 profile + 無限件 + LINE 推播 |
| **Pro** | NT$2,500 / 月 | 5 個 profile + 歷史得標分析 + 截止 calendar 整合 |
| **Enterprise** | 客製 | 顧問公司服務多客戶 |
| **API access** | NT$1.5/call | 第三方平台嵌入 |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 中小企業老闆 / 業務 每日刷政採網 1-2h × NT$500/hr × 22 天 = **月省 NT$11K-44K**
- vs Solo NT$799/月 = **14-55x ROI**
- 1 件中標通常 NT$30 萬以上 = **單次中標即回 1 個方案 30+ 年費用**

### TAM

- 全台中小型 IT / 顧問 / 設計 / 工程 / 教育訓練 公司估 30,000+ 家有承接政府標案需求
- 取 3% 滲透率 = 900 家 × NT$799 = **月 NT$72 萬 MRR / 年 NT$860 萬 ARR**
- 加 Pro / Enterprise / API + 橫移到醫院 / 學校 / 國營事業 採購監控 → 翻倍

## 早期 distribution

1. **PTT Soft_Job / SOHO 板**:「政採網好難用」抱怨貼文底下發 demo 影片
2. **FB 中小企業老闆社群**(「台灣 SI 廠商交流」「政府標案資訊分享」)
3. **政府採購網 SEO 競價**:「政府標案訂閱」「招標通知」關鍵字
4. **記帳士 / 會計師事務所 partner**:他們服務的客戶常問「我能標什麼案」,tenderwatch 嵌入記帳士官網
5. **公會 partner**(資訊服務工會 / 軟體協會)
6. **創業育成中心 / 政府推廣計畫**:配合 SBIR / 中小企業數位補助推廣

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **政採網改 API / 限流** | 中 | OpenData 是政院政策保證持續開放;備案 RSS / 爬蟲 |
| **AI semantic match 過度樂觀導致誤投** | 中 | LLM 給 score 但不下決策 + 列 key gaps + recommendation 只能是「建議」;歷史 win/loss feedback loop |
| **招標王推 AI 競品** | 中 | 招標王 8 年沒進化是 indicator;搶心占率 |
| **政院推官方版** | 低 | 政府工具開發慢、UX 差;商業 SaaS 仍有差異化空間 |
| **客戶覺得「我自己看也行」** | 中 | 提供 free tier 5 件/日 hook,讓老闆親身體會省下時間 |
| **個資 / 公司能力描述外洩** | 中 | stateless API call;企業版可走 self-host LLM |

---

*第十七輪在 2026-05-10 產出於 incubator(台灣優先,**第六個非 doc-gen 模式 — Real-time monitoring + alerting + LLM semantic match scoring**)。跟前 16 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B / 長照 / 法律 / 獸醫 / 月報 / 健身 / 機車估價 / LINE 整單 / 補助 RAG / 餐廳排班 / 婚攝媒合 都不同 vertical 也不同架構。*
