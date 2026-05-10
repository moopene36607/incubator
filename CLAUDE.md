# Incubator — AI Startup Prototype Index

This repository is an automated incubator. A scheduled `/loop` job fires
every 20 minutes and asks the model to:

1. Survey existing prototypes (this index + folder list) to avoid duplicates
2. Research a niche AI startup idea — **Asia-first markets prioritized**
   (台灣 / 日本 / 韓國 / 東南亞 / 中港); fall back to US/EU only when no
   Asian equivalent exists and the topic is unusually strong
3. Pick the highest-probability winner with evidence-backed competitive gap
4. Build a working prototype in a new folder
5. Commit + push to `origin/main` (one commit per round)

Each prototype has the same shape:
- `README.md` — pain, competitor analysis, pricing, distribution, risk
- single-file CLI(s) (Python, Anthropic SDK, prompt caching)
- `samples/` — realistic synthetic input
- `examples/` — pre-generated output (so demo works without API key)
- `requirements.txt`

---

## Active prototypes

### Round 1 — `scopescribe/` (US 🇺🇸)

- **題目**: AI scope-of-loss narrative generator for independent property insurance adjusters
- **解決的問題**: Independent (1099) US property insurance adjusters spend 3–4 hours per claim writing the narrative sections (Cause of Loss, Scope, Methodology). Per-claim income model means every saved hour = direct revenue. Existing tools (Xactimate, ClaimWizard, BuildArray) handle workflow but never auto-draft narrative text.
- **目標市場**: ~120,000 independent property adjusters in the US; concentrated in catastrophe deployments (hurricane / hail / wildfire / flood). $79–149/month or $15/report. Outlier — only English-market prototype in this incubator.

### Round 2 — `laobao/` (Taiwan 🇹🇼)

- **題目**: Taiwan SOHO 勞報單 + 二代健保補充保費 自動算 + 文件草稿產生
- **解決的問題**: Taiwanese freelancers don't know if they should be withheld 10% income tax + 2.11% NHI supplement on each gig payment. Multi-source pain validated on PTT soho 板, Medium, swap.work blog itself. swap.work locks payments behind a 9% platform fee; 健保署 site only calculates without producing documents. AI auto-classifies 9A / 9B / 50 from natural-language description.
- **目標市場**: TW SOHO 接案族 (年收 NT$15萬–150萬) + 10 人以下小公司. NT$99/月 Pro / NT$15/張 pay-as-you-go. Annual rate adjustments create subscription stickiness.

### Round 3 — `kosmelingo/` (Korea → Japan 🇰🇷→🇯🇵)

- **題目**: K-beauty 化妝品 韓→日 出口成分名 JCIA 標準化 + 標籤草稿 AI 生成
- **解決的問題**: Japan's 薬機法 mandates JCIA standardized Japanese ingredient names on labels — using English INCI names alone is illegal. Existing options are human代行 (50–200萬 KRW per product, 2–4 weeks). KCIA dictionary exists but isn't SaaS-ified; work-son.com is just a manually-maintained Google Sheet. Regulatory must-have, not nice-to-have — wrong name = can't ship.
- **目標市場**: Korean indie cosmetic brands (年商 1–30億 KRW) + ODM factories exporting to Japan. K-beauty 日本出口 +21.5% YoY (Q3 2024). 9,900 KRW per SKU pay-per-use, ~99,000 KRW/月 indie pro, 300–500萬 KRW/年 ODM plan.

### Round 4 — `mitsumori/` (Japan 🇯🇵 — domestic)

- **題目**: 日本町工場 小ロット見積書 AI 自動生成 (Japanese small machine shop quote auto-generation)
- **解決的問題**: Japan's 中小製造業 (~430,000 companies, ~60% with ≤5 employees) suffer from "Excel 属人化" — the quote spreadsheet only one veteran can edit. ITmedia 2025 survey + ESTman blog confirm. インボイス制度 (October 2023) broke every existing template (need 適格請求書登録番号 + 税抜/税込 dual display). CADDi/meviy serve enterprise; ESTman handles formatting but no AI prose; ARUM does NC code, not commercial documents.
- **目標市場**: 1–20 person 町工場 (machining / sheet metal / welding shops) in 大田区 / 東大阪 / 川崎. ¥3,980/月 Solo to ¥9,800/月 Standard. Distribution via 商工会議所 / MFG展示会 / 中小企業診断士.

### Round 5 — `settlekit/` (Korea 🇰🇷 — domestic)

- **題目**: 한국 1인 크리에이터 협찬 합의서 + 정산서 AI 자동 생성 (Korean solo creator brand-deal contract + settlement statement)
- **解決的問題**: Seoul city report: 56% of solo creators experienced unfair contract terms (still cited in 2025 policy work). National Tax Service auditing 4,000+ high-income YouTubers in 2025 for sponsorship income disclosure. 삼쩜삼 only handles tax filing; Modusign is enterprise e-sign at ₩50K-200K/month; no tool generates KFTC-compliant 협찬 합의서 + 사업소득 정산서 in one shot for solo creators. Numbers stay in pure functions, AI handles only contract prose.
- **目標市場**: Korean 1인 크리에이터 (1만–50만 subs mid-tier YouTubers / Instagram influencers / Threads operators), estimated 50,000–100,000 active. ₩9,900/월 Solo, ₩19,900/월 Pro (with e-sign + 종소세 report), ₩99,000/월 small MCN agency tier.

### Round 6 — `hoadon/` (Vietnam 🇻🇳 — SEA first appearance)

- **題目**: Vietnamese F&B household business daily e-invoice batch generator (越南 hộ kinh doanh F&B 業者每日批量電子發票 AI 自動產生器,符合 Nghị định 70/2025)
- **解決的問題**: Decree 70/2025/NĐ-CP took effect 2025-06-01: any household business with annual revenue over 1 tỷ VND (~USD 39K) must use e-invoices. F&B/retail can aggregate sub-50,000 VND transactions into a daily summary invoice — but the rules are complex (8% F&B vs 10% standard VAT; per-item threshold logic). Vietnamnet 2025: 42.7% of vendors don't fully understand tax types. MISA AMIS targets companies with accountants; VNPT only provides blank free forms; nobody offers AI-driven "daily voice memo → Decree 70 compliant batch invoice" SaaS. Numbers stay in pure functions; AI parses only the unstructured ledger text.
- **目標市場**: Vietnam ~2.2M hộ kinh doanh; F&B slice estimated 700K. Pho shops, cafes, street vendors, small bakeries. Solo plan 49,000 VND/月 (~USD 2), 399,000 VND/year, multi-shop 129,000 VND/月. WTP anchor: skip an accountant (1–2M VND/year saved) + avoid Decree 70 fines (4–10M VND).

### Round 7 — `carepen/` (Taiwan 🇹🇼 — long-term care, first TW non-tax)

- **題目**: 台灣長照居服員語音逐字稿 → LTCIS 服務記錄草稿 AI 助手
- **解決的問題**: 居服員每天 4–8 個個案,LTCIS (長照支付制度資訊系統) 規定欄位多、格式硬。報導者 2024 報導公聽會公開引述「**評鑑還是一場文書整理大賽**」,代寫評鑑文件市場規模「**數萬至數十萬元**」(居盟理事長確認)— 以真金白銀證明痛點存在。**長照 3.0 (2026 上路) 文書指標從 5 增至 7 項**。仁寶 i 照護主打派案不解決文書產出;Vocol.ai 不知 LTCIS 代碼;沒人做「30 秒語音 → LTCIS 結構化記錄」。架構:純函式渲染,AI 只做語意理解,生命徵象沒提到=null **絕不編造**(醫療紀錄硬規矩)。
- **目標市場**: 台灣 1,400+ 居服單位、40,000+ 居服員。Standard NT$4,900/月 (覆蓋 20-50 名居服員),WTP 錨點:督導改文書 60h/月 × NT$300 = NT$18K → 壓到 15h 一個月回本。TAM 1,400 × NT$4,900 = 月 NT$686 萬;取 5% 滲透 = 月 NT$34 萬 MRR。Distribution: 居家服務策略聯盟、衛福部數位部 AI 落地實證計畫補助、嘉義/屏東/雲林/台南社會處。

### Round 8 — `sudoc/` (Taiwan 🇹🇼 — legal vertical for small law firms)

- **題目**: 台灣 1–5 人小型律師事務所 民事起訴狀 AI 草稿產生器
- **解決的問題**: 台灣執業律師 14,000 人,**1–5 人事務所佔 75%+**(律師公會 2023)。PTT LAW 板直接引用「每次起訴狀都要從模板重打,要引條文又要改格式,一份要 2–3 小時」。Harvey AI USD 100+/user/月 + 全英文 + 不懂台灣司法院書狀格式;LawBank 法源只是法條搜尋不生成書狀;ChatGPT 直接問會幻覺條文。Gap 結構性:Harvey 不來、LawBank 不做、Word 太累。架構:純函式組裝書狀骨架(訴之聲明、中文大寫金額、民國紀年、狀末敬語、證物清單),AI 只負責「事實及理由」段落,RAG 限定 11 條最常引用民法/民事訴訟法。「協助起草」非「代擬」+ 律師審閱免責聲明,規避無律師資格代擬法律疑慮。
- **目標市場**: 14,000 律師中 10,500 位 1–5 人事務所;Standard NT$1,999/月(無限份 + 5 種書狀類型)。WTP 錨點:律師寫 1 份起訴狀 1.5h × NT$1,500/hr = NT$2,250 機會成本 → sudoc 壓到 15 分鐘,1 份回本一半月費。TAM 5% 滲透 = 月 NT$105 萬 MRR。Distribution: 律師公會在地分會、法律 podcast、PTT LAW、新進律師(司法官特考補習班)。

### Round 9 — `vetnote/` (Taiwan 🇹🇼 — veterinary SOAP)

- **題目**: 台灣獸醫診所中文 SOAP 病歷草稿 AI 助手
- **解決的問題**: 台灣 2,600 家動物醫院 / 診所,獸醫師每天 20-50 份 SOAP 病歷 = 每天 2.5-7.5 小時純文書(PTT VetMed: 「打 SOAP 打到手軟」、Dcard 獸醫系版: 「實習要寫到 10 點才能走」)。VetSnap (USD$99) + Scribenote (USD$89) 在英文市場已驗證 PMF。但繁中市場零 AI 競品 — 獸易通 / 毛孩管家等本土 PIMS 都是 record-keeper 沒 AI 生成。語言護城河 + 在地 PIMS 無 AI = 完整空白。架構:純函式渲染病患標頭 + 簽核欄,AI 只寫 SOAP 4 段。**System prompt 嚴禁開具體劑量 + 嚴禁下確定診斷**(獸醫師法規範診斷與處方為獸醫師專屬職責)。
- **目標市場**: 2,600 家動物醫院,診所版 NT$1,800/月(對標 VetSnap USD$99 ≈ NT$3,200,有 44% 價格優勢)。WTP:獸醫師時薪 NT$1,000 × 省 3.5 小時/天 = 月省 NT$77K,vs 月費 NT$1,800 = 42 倍 ROI。TAM 5% 滲透 = 月 NT$23 萬 MRR。Distribution: FB「台灣獸醫師社群」、獸醫系實習生 KOL、獸醫師公會、太僕 / 瑞鵬連鎖醫院、獸醫繼續教育學分課程贊助。

### Round 10 — `monthrep/` (Taiwan 🇹🇼 — cram-school / talent-class monthly report)

- **題目**: 台灣才藝班 / 補習班老師 學生月報自動產生器(月報先生)
- **解決的問題**: 全台才藝班 + 補習班約 50,000 家,1 位老師通常帶 20-30 位學生,每月底要寫 20-30 份個人化月報 ≈ 4 小時 admin/月。痛點 PTT C_Education / Dcard 教師版 / FB「台灣補習班主、才藝教室經營交流」社團多次出現:「每個月月底寫到懷疑人生」「打到半夜還沒寫完」。補教王 / EduBase / 補習達人 / ClassSwift / 均一 / PaGamO 全部是排課收費點名,**無一家**有 AI 文字生成。Gap:補教軟體商核心客戶是大型連鎖,沒動力做小型才藝工作室小功能 — 1-5 人才藝工作室是 VC 嫌小、補教軟體商嫌雜的縫隙。架構:純函式渲染標頭 + 出席統計 + LINE 友好版,AI 只寫 4 段月報內容。8 種科目 grounding(鋼琴 / 美術 / 英文 / 數學 / 舞蹈 / 小提琴 / 圍棋 / 作文)+ 4 個年齡 band(學齡前 / 國小 / 國中 / 高中) 自動切換口吻。**AI 嚴禁編造**(沒提到的進步 / 比賽 / 出席日數絕對不能補)。
- **目標市場**: 50,000 家才藝班 / 補習班,Solo NT$299/月、Studio NT$799/月、Chain NT$2,499/月。WTP 錨點:老師時薪 NT$600 × 月省 4 小時 = 月省 NT$2,400 vs Solo NT$299 = 8x ROI。TAM 2% 滲透 = 月 NT$30 萬 MRR / 年 NT$360 萬 ARR。Distribution: FB 補教交流社團、PTT C_Education / Dcard 教師版、才藝教育博覽會、新手老師 LINE 社群、教育部數位轉型補助配合推廣。

### Round 11 — `fitlog/` (Taiwan 🇹🇼 — personal trainer post-class report)

- **題目**: 台灣健身教練 (PT) / 瑜珈教練 課後訓練報告 AI 助手
- **解決的問題**: 台灣自由接案 PT 約 2-3 萬人,每天 6-8 節 1 對 1 課,每節結束後要寫課後紀錄維持留存與信任。Dcard 健身板:「一天 6 節課要寫 6 份,累死」。PTT FITNESS:「Word 模板還是很花時間」。每天 30-40 分鐘 admin × 教練時薪 NT$1,500 = 月省 NT$11K+ 機會成本。**TrueCoach (USD$19.99 月費) 在英文市場已驗證 PMF**;繁中市場零 AI 課後報告產生器,本土 MixFit / SportSoft 是課程預約點名沒 AI;ChatGPT 直接問每次要重打學員資料、沒結構化動作 grounding。架構:純函式渲染量化訓練表 + LINE 純文字版,AI 只寫 5 段(摘要 / 進步 / 觀察 / 下次重點 / 恢復飲食)。**AI 嚴禁編造**(體重 / 體脂 / 卡路里 / 心率沒提到不能補)+ **AI 不下醫療診斷**(學員主述不適時用「下次留意 / 視情況調整」措辭,規避 PT 與物治職業界線)。30 個動作 seed db 用台灣健身圈詞彙(槓鈴背蹲舉 / RPE / 超負荷 / TUT)。
- **目標市場**: 2-3 萬持照 PT,Solo NT$299/月(對標 TrueCoach NT$640 便宜 53%)、Solo+ Whisper NT$599/月、Studio NT$1,499/月。WTP 錨點:每天省 30-40 分鐘 × NT$1,500 時薪 = 月省 NT$11K+ vs Solo NT$299 = **37x ROI**。TAM 5% 滲透 = 月 NT$30 萬 MRR。Distribution: FB「健身教練交流」社團、體適能協會 (CTSCA / CSCS) 訓練營、YouTube 健身 KOL (肌肉爸爸 / 健人蓋伊 / 館長) 合作、Threads / IG 健身教練、World Gym / Anytime Fitness 駐店 PT BD。

### Round 12 — `motoval/` (Taiwan 🇹🇼 — used motorcycle valuation, **first non-doc-gen pattern**)

- **題目**: 台灣二手機車 AI 估價助手(自然語言車況描述 → 估值 + 議價建議)
- **解決的問題**: 台灣年交易二手機車 60 萬台,FB「台灣二手機車買賣」27 萬成員社團每天上百篇詢價,但**無客觀估價工具**。8891 / U-CAR 主打汽車 + 機車是 listing 沒估價;Yahoo / 露天只有 listing;Kelley Blue Book 等英美工具不認識台灣機車車款(光陽 Force / 三陽 DRG / Yamaha 新勁戰 / Gogoro)— 結構性 gap。前 11 輪 prototype 全是 document-gen,本輪刻意換成 **vertical pricing model + 自然語言解析** 架構。`pricing.py` 純函式 5 步驟估值(MSRP × 年折舊率^age × 里程 factor × 車況等級 × 細項加減分),所有數字計算 100% 純函式絕不交給 LLM;sanity cap 限制估值 ≤ MSRP × 0.95。AI 只負責解析自然語言「我的 Force 155 2021 跑了 7 萬...」→ 結構化 input。
- **目標市場**: 60 萬台年交易 + 2,000 家二手車行。B2C NT$49/次 估價、B2C 月會員 NT$199、B2B 車行 NT$799/月(無限批次)、B2B 連鎖 NT$2,499/月、API NT$0.5/call。WTP:B2C NT$49 vs 開錯價 NT$5K+ = 100x 保險;B2B 車行月 30 台估價省一台錯估 NT$2K = 月費回本。TAM B2C NT$147 萬/年 + B2B NT$192 萬 ARR + API enterprise = **總天花板 NT$1,000 萬 ARR**。Distribution: PTT biker / Dcard 機車版、FB 二手機車買賣社團、YouTube 機車 KOL(老吳 / Apex / 老查)、8891 / 露天 listing SEO、二手車行直接 BD。

### Round 13 — `snaporder/` (Taiwan 🇹🇼 — LINE group-buy order aggregation, **OCR/NLP non-doc-gen pattern**)

- **題目**: 台灣 LINE 團媽自動整單工具(群組對話 / 截圖 → 30 秒整出彙整表 + LINE 對帳訊息)
- **解決的問題**: 估計台灣活躍團媽 40-100 萬人,每月 8-15 次團 × 30-80 條訂購訊息 = 每月 240-1,200 條手工逐條判讀。Dcard 媽媽版:「整單 2-4 小時 / 次,算錯就自己賠」。揪好買 / 多多團走「電商平台」方向,不解決「群組截圖 → 整單」最後一哩痛點(自打嘴巴會把用戶留在 LINE)— 結構性 gap。架構:**LLM 解析非結構化 LINE 對話 → 結構化 OrderEvent (add/set/cancel),純函式聚合(`aggregator.py`)100% 算錢**。三種 action 區分精確處理「改成 N 個」「取消」這類團購群組常見模糊語言。Skipped events 透明列出避免靜默漏單。
- **目標市場**: 40-100 萬團媽,Pro NT$299/月、Business NT$699/月、年付折扣。WTP:每月 36 小時手工 × NT$200/hr = NT$7,200 機會成本 vs NT$299 = 24x ROI。TAM 1% 滲透 = 5,000 人 × NT$299 = **月 NT$150 萬 MRR / 年 NT$1,800 萬 ARR**;加 Business + 港澳 + 日韓繁中 → 翻倍。Distribution: FB 大型團購社團(「TAIWAN 媽媽團購交流」5-10 萬人)、Dcard 媽媽版 / WomenTalk、Threads / YouTube 主婦 KOL、LINE 官方 Bot Store。

### Round 14 — `subsidybot/` (Taiwan 🇹🇼 — government subsidy RAG Q&A, **third non-doc-gen pattern**)

- **題目**: 台灣中小企業 / 創業 / 個人補助 RAG Q&A 助手(用戶條件 + 自由問題 → 30 秒比對符合方案)
- **解決的問題**: 台灣補助散在 N 個機關(經濟部 / 勞動部 / 農業部 / 數位部 / 各縣市),普通創業者每次自己 Google 2-3 小時還可能漏。PTT Entrepreneur:「請問台灣創業補助有哪些?每次都要自己去 N 個不同網站找資料」。SBIR 官網是靜態 FAQ;104 補助資料庫無法答「我符合嗎」;ChatGPT 直接問**幻覺嚴重**(常給已截止方案);律師諮詢一次 NT$3,000-5,000 小企業負擔不起。架構:**`subsidies_db.py` 結構化 corpus(8 個方案 metadata)+ `retrieval.py` 純函式硬條件比對(年齡 / 設立年限 / 員工 / 行業 / 性別)+ Claude 嚴格 RAG(只 cite 提供 corpus,絕不編造)**。Bug fix during testing: 性別 substring 比對誤判 25 男符合「男(45歲以上)」— 改 exact match。
- **目標市場**: 1-10 人微型企業主 ~150,000 人 + 自由工作者 + 個人創業者 = 200,000+ 潛在用戶。Pro NT$299/月、企業版 NT$799/月、API NT$0.5/call、Enterprise NT$5,000+/月。WTP:每月省 2-3 小時查補助 × 機會成本 = NT$600-1,800 vs Pro NT$299 = 2-6x ROI。TAM 1% 滲透 = 2,000 人 × NT$299 = **月 NT$60 萬 MRR / 年 NT$720 萬 ARR**;加 API + Enterprise + 橫移 RAG(勞基法/健保/農委會)→ 翻倍。Distribution: PTT Entrepreneur / Dcard 創業版、創業 podcast、會計師 / 記帳士事務所合作 partner、政府單位 partner、創業育成中心、長尾 SEO 關鍵字。

### Round 15 — `shiftsync/` (Taiwan 🇹🇼 — restaurant shift management LINE bot, **fourth non-doc-gen pattern**)

- **題目**: 台灣餐廳外場排班 LINE Bot 助手(員工自然語言請求 → 純函式規則檢查 → 自動回覆批准/建議/拒絕)
- **解決的問題**: 5-30 員工中小餐廳店長每週花 2-3 小時排班 + 處理 6-90 條 LINE 群組換班 / 請假 / 加班訊息。Dcard 餐飲業 / PTT restaurant 高頻討論:「LINE 訊息一片混亂、店長還要查工時防超時、有時排重了沒發現」。海外工具(Schedulefly USD$25 / 7shifts)全英文 + 員工要另下 app,**台灣 LINE-native 文化下幾乎沒人用**;Excel + LINE 群組是現況但易出錯。**架構:Scheduling 最佳化 + LINE bot 對話流程**(雙重新模式)— `schedule_rules.py` 100% 純函式驗證(衝突檢查 / 工時上限 / 勞基法 40h+48h hard limit / 角色相容 / 找代班候選人);AI 只解析自然語言「我跟小明換週五晚班」→ 結構化請求 + 把 ApprovalResult 翻成人性化 LINE 回覆。三類請求統一介面(swap / leave / extra),都帶 ApprovalResult 標準輸出(approved / approved_with_warning / needs_replacement / rejected)。Bug fix during testing: 重疊偵測訊息原本 dup 兩次 — 改用 set + 帶 shift_id 細節。
- **目標市場**: 全台餐飲業 ~17 萬家,5-30 員工佔 50% = 85,000 家。Solo NT$499/月、Pro NT$1,499/月、Enterprise 客製。WTP 錨點:店長排班 + 處理變更 2-3h × NT$300 × 4 週 = 月省 NT$2,400-3,600 機會成本 + 1 次排班漏算晚班缺人損失 NT$5K-15K 營收 vs NT$499 = **5-7x ROI**。TAM 2% 滲透 = 1,700 家 × NT$499 = **月 NT$85 萬 MRR / 年 NT$1,020 萬 ARR**。Distribution: FB 餐飲老闆社群、PTT restaurant / Dcard 餐飲業、LINE Bot Marketplace、連鎖餐飲集團 BD、iCHEF / 沛點 partner、餐飲 KOL。

### Round 16 — `weddingmatch/` (Taiwan 🇹🇼 — wedding photographer style matching, **fifth non-doc-gen pattern**)

- **題目**: 台灣準新人婚攝風格 AI 配對(自由文字風格描述 → 12 維風格向量 → 純函式 cosine similarity → Top 5 婚攝)
- **解決的問題**: 台灣每年 12-13 萬對新人籌備婚禮,**婚攝挑選平均花 2-6 週** — 因為每家工作室都自稱 film 風 / 日系 / 電影感,新人**根本分不清誰是真的什麼風**。婚攝預算 NT$5-15 萬選錯成本高,但無客觀比對工具。WeddingDay (台灣最大平台) 是純廣告刊登模式 + 婚攝地圖只是人工瀏覽,**全球 (The Knot / Zankyou) 也都沒有 CLIP-based 風格 embedding 配對**。**架構:Matching with embedding similarity** — `photographers_db.py` 12 位 mock 婚攝師,每位附 12 維 0/1 風格 tag(film_emulation / candid / cinematic / outdoor 等);`matching.py` 100% 純函式 cosine similarity + 預算 / 地區過濾 + 排序;AI 只在兩個地方介入(① 解析自由文字「日系底片感不要太擺拍」→ 12 維 0/1 向量 ② 為配對結果寫人性化推薦理由)。**LLM 永不挑 Top 1** — 那是純函式工作。
- **目標市場**: 5,000-8,000 位專業婚攝 + 12-13 萬對新人/年。Pro 婚攝師 NT$800/月(對標 WeddingDay 廣告位 NT$1,500-3,000 便宜 + 多 AI 配對)、Studio Pro NT$2,500/月、成交佣金 NT$1-2K/對(1-2%)。TAM 10% 滲透 = 500-800 婚攝 × NT$800 = **月 NT$40-64 萬 MRR**;加成交佣金 + 海外港新馬 → x2。Distribution: PTT wedding / Dcard 婚禮版、FB 婚禮社團、IG 婚禮 KOL、Google Ads 競價 WeddingDay 關鍵字、婚禮顧問 partner。

### Round 17 — `tenderwatch/` (Taiwan 🇹🇼 — government tender real-time monitoring, **sixth non-doc-gen pattern**)

- **題目**: 台灣中小企業政府標案 AI 即時警示(政採網每日新公告 → 個人化匹配 → LINE 推播)
- **解決的問題**: 台灣政府電子採購網每年發 20 萬件招標公告,中小企業老闆 / 業務員每日刷 1-2 小時還可能漏。PTT Soft_Job 板:「政採網搜尋介面真的爛到爆」。招標王 NT$299/月 是 2018 年介面 + 純關鍵字 + **無 AI 分類**;TenderAlert.tw 已停服;ChatGPT 不知道每日新公告 + 不知道你公司能力 + 沒推播。海外工具(Bonfire / GovWin)只服務美國 SAM.gov 不認識台灣政採。**Gap 結構性**:政府採購 OpenData API 公開可合法取用,但沒人有動力做「個人化 AI 助理」。**架構:Real-time monitoring + alerting + LLM semantic match scoring** — `tender_filter.py` 100% 純函式硬條件過濾(投標廠商資本額 / 預算 / 截止日 / 排除類別 / 必備認證,**通常剩下 5-15% 標案進入 LLM**)+ Claude 對通過件做 0-100 semantic match scoring(列 key_match_points + key_gaps + recommendation,但**最終投不投仍是老闆決定**)。雙輸出(markdown 詳細報告 + LINE 純文字推播只列 score >= 70)。
- **目標市場**: 全台中小型 IT / 顧問 / 設計 / 工程 / 教育訓練 公司估 30,000+ 家承接政府標案。Solo NT$799/月、Pro NT$2,500/月、Enterprise 客製、API NT$1.5/call。WTP 錨點:每日刷 1-2h × NT$500 × 22 天 = 月省 NT$11-44K vs NT$799 = **14-55x ROI**;1 件中標 NT$30 萬+ = 單次回本 30+ 年費。TAM 3% 滲透 = 900 家 × NT$799 = **月 NT$72 萬 MRR / 年 NT$860 萬 ARR**。Distribution: PTT Soft_Job / SOHO 板、FB SI 廠商社群、政採網 SEO 競價、記帳士 partner、公會、創業育成中心。

### Round 18 — `salonguard/` (Taiwan 🇹🇼 — beauty salon churn prediction, **seventh non-doc-gen pattern**)

- **題目**: 台灣美髮 / 美甲 / 美睫沙龍 回頭客流失預測 + 個人化 LINE 挽回訊息
- **解決的問題**: 全台美業約 55,000 家,客戶 LTV NT$10K-30K/年,但 **99%+ 的沙龍沒有任何流失預測機制**。PTT BeautySalon:「客人都是來一次就消失,我也不知道哪裡出問題」;Dcard 美業:「等她不見了才發現」。iSalon / WACA / Booksy / MindBody 全部只做預約收款 **無 churn prediction**。架構:**Churn Prediction / Anomaly Detection** — `rfm.py` 100% 純函式 RFM + 個人化 avg_interval(不是粗糙的全店 60 天平均,而是**每位客戶自己的歷史回訪間隔**);ratio = recency / avg_interval 映射到 5 級風險(active/watch/warning/high/lost);加權 bonus(高客單 NT$2,500+ +5 分 / 高頻 6 次+/年 +5 分);AI 只為高風險客戶寫 80 字 LINE 挽回訊息(引用具體上次服務 / 不堆折扣 / 不批量自動發送)。
- **目標市場**: 55,000 家美業店。Solo NT$599/月(對標 iSalon NT$1,200 便宜 50% + 多 churn 功能)、Studio NT$1,299/月、Chain NT$3,500/月。WTP:1 客 LTV NT$10-30K,挽回 1 客 = 年費回本。TAM 3% 滲透 = 1,650 家 × NT$599 = **月 NT$99 萬 MRR / 年 NT$1,180 萬 ARR**。Distribution: FB 美業社群、PTT BeautySalon / Dcard 美業、iSalon / Beautix 既有用戶 add-on、美髮 / 美甲 KOL 合作、台北國際美容展、設計師 LINE 社群。

### Round 19 — `propvision/` (Taiwan 🇹🇼 — real-estate vision-aided valuation, **eighth non-doc-gen pattern**)

- **題目**: 台灣房屋室內照片 Vision AI 估價(物件資料 + 3-5 張照片 → 純函式 6 步驟估值 + 加減分透明)
- **解決的問題**: 台灣每年 30 萬棟交易、60,000 房仲業務員,Dcard 房地產版:「仲介帶看說老屋但裝潢還新,報價比周邊高 15%,後來查實價發現完全灌水」。591 / 樂居 / 信義 AI 估價 **完全不看照片屋況**,只看交易歷史數字;Opendoor / HouseCanary 不在台灣;ChatGPT 不知道你家照片。實價登錄 2.0 open data 公開可用但**沒人把照片屋況與成交價連結**。**架構:Vertical pricing model + Vision identification 組合** — `pricing_model.py` 100% 純函式 6 步驟(base × 屋齡 × 樓層 × 朝向 × 裝修評分 × 加減分);AI 只負責 ① 從照片描述抽 renovation_score 1-10 + concerns ② 為估值寫人性化說明。**金額計算永不交給 LLM**;加減分透明列出 + 細項上限 ±15%。
- **目標市場**: 60,000 房仲業務員 + 30 萬棟年交易屋主 / 買方。B2C NT$1,500/份(衝動消費)、B2B 個人業務員 NT$3,000/月、B2B 事務所 NT$8,000/月、Enterprise 客製(信義 / 永慶連鎖)。WTP:房仲一月成交 1-2 件抽 NT$10-30 萬,NT$1,500/份小錢;屋主自售開價錯 5% = NT$50-100K 損失 vs NT$1,500 = 完美保險。TAM 5% 滲透 = 3,000 業務員 × NT$3,000 = **月 NT$900 萬 MRR / 年 NT$1.08 億 ARR**;加 B2C pay-per-use + Enterprise → 翻倍。Distribution: PTT home-sale / Dcard 房地產、永慶 / 信義 / 中信 業務員 LINE 社群、YouTube 房產 KOL、裝修平台 partner、銀行貸款業務員 partner。

### Round 20 — `cropscan/` (Taiwan 🇹🇼 — crop disease vision classification, **ninth non-doc-gen pattern**)

- **題目**: 台灣作物 AI 病蟲害辨識 + 台灣許可農藥建議(作物 + 病徵描述 → Top 3 候選病害 + 防治建議 + 農改場聯絡)
- **解決的問題**: 台灣 77 萬農家,中小型 1-5 公頃蔬果農遇病蟲害時:農改場推廣員每位覆蓋上百戶,LINE 回覆 3-5 天;農藥誤噴每次損失 NT$3,000-8,000;錯過黃金 24 小時處理期損失差 10x。PlantVillage / Plantix 訓練集偏歐美印,**台灣本土作物(蓮霧 / 鳳梨釋迦 / 火龍果 / 芒果炭疽)覆蓋極低**;農委會「農業易」App 只有圖鑑無 AI;iPlant(中國)用大陸農藥不符台灣法規。**架構:Pure Vision Classification**(prototype 用文字描述代替真實照片)— `pest_db.py` 25+ 條台灣本土病蟲害 corpus(每筆完整 metadata:典型症狀關鍵字 / 嚴重度判斷 / 台灣許可農藥 / 採收安全期 / 預防 / 何時必聯絡農改場);Claude 比對使用者症狀描述 vs corpus → Top 3 候選 + 0-100 confidence + 命中症狀明細 + 嚴重度推估。**LLM 永不編造農藥名**(所有用藥建議來自 corpus 預存的台灣許可清單)。Low confidence 自動建議聯絡農改場。
- **目標市場**: 30 萬戶中小型農家 + 各區農改場 6 處 + 鄉鎮農會 + 農藥行。農民 Pro NT$299/月、農會 / 農資行白標 NT$5,000/月、農改場授權 NT$15,000/月、農藥行 sponsored NT$5/click。WTP:1 次農藥誤噴 NT$3-8K vs Pro NT$299 = 單次回本年費。TAM 3% 滲透 = 9,000 戶 × NT$299 = **月 NT$270 萬 MRR / 年 NT$3,240 萬 ARR**;加 B2B + 農藥 sponsored → 翻倍。Distribution: 農業易 FB 社團 5 萬人、PTT Agriculture、各區農改場 partner、鄉鎮農會 LINE 白標、農藥行 partner、農委會數位推動補助。

### Round 21 — `trailmatch/` (Taiwan 🇹🇼 — personalized hiking-trail matching for beginners, **eleventh AI pattern — Behavioral Personalization**)

- **題目**: 台灣登山路線個人化媒合(經驗 / 體能 / 天數 / 出發地 / 季節 / 裝備 → 純函式硬條件過濾 25 座台灣山岳 → AI 為合格山岳寫個人化 why_match / 裝備提醒 / 安全警告 / 隊伍建議)
- **解決的問題**: 台灣 200 萬登山人口,FB 「登山補給站」「百岳台灣」社團「新手該從哪座山開始?」每週重複出現上百則;PTT Hiking 板「我體能普通沒裝備能爬合歡山嗎?」永遠在問同樣問題。健行筆記 / AllTrails 只有「路線資料」沒個人化推薦;LINE 山友群「等別人回」品質參差;山難每年 100+ 件,**73% 是「選錯山」(超過能力)** — 林務局統計。架構:**Behavioral Personalization with Hard-Filter Pre-screening** — `mountains_db.py` 25 座台灣山岳完整 metadata(難度 1-5 / 天數 / 海拔爬升 / 入山證 / 適合季節 / 高山症風險 / 地形特徵 / 出發城市 / 是否百岳);`trailmatch.py` 純函式 `filter_mountain` 硬條件(經驗→最高難度 / 體能→最高爬升 / 季節 / 高山症史 / 怕地形 / 雪季裝備),通過的山才進 LLM;AI 只為合格山岳寫個人化解釋(必須引用使用者具體欄位 / 不講罐頭安全話)。**LLM 永不放行被硬條件刷掉的山**(避免「AI 建議新手爬中央尖山」這種致命錯誤)。
- **目標市場**: 200 萬登山人口 + 200 家戶外品牌(山林賣店 / 歐都納 / Mont-bell 台灣)+ 旅行社 300 家 + 政府機關。C2C Free 3/月、Pro NT$149/月、Plus 即時路況 NT$299/月、B2B 旅行社 NT$2,000/月、戶外品牌 affiliate NT$50/單。WTP:1 次救難隊出勤 NT$30-100 萬 vs Pro NT$149 = 安全保險。TAM 5% × 200 萬 = 10 萬人 × Pro NT$149 = **月 NT$220-370 萬 MRR / 年 NT$2,640-4,440 萬 ARR**;加 B2B + affiliate → 翻倍。Distribution: PTT Hiking、健行筆記 partner、登山補給站 FB 5 萬粉、登山 YouTube KOL(山行者 / TaiwanHiker)、戶外品牌結帳 add-on、林務局合作宣導(山難防治)。

### Round 22 — `wattmon/` (Taiwan 🇹🇼 — SMB AMI smart-meter anomaly detection, **twelfth AI pattern — Time-Series Anomaly Detection**)

- **題目**: 台灣中小企業 / 餐飲店 / 早餐店 AMI 智慧電表 30 分鐘讀值用電異常偵測 + AI 節電建議(夜間漏電 / 時段尖峰 / 單日異常 / baseline 漂移)
- **解決的問題**: 台灣中小企業 1.5M 家、餐飲業 17 萬家、美業 5.5 萬家,每月電費 NT$5K-30 萬,但 99%+ 老闆拿到台電帳單只能哀嚎,**沒有工具看出哪邊燒掉**。台電 AMI 30 分鐘智慧電表已開放 API **5 年**,小型用戶根本沒人去下載分析。Schneider EcoStruxure / Siemens 走 enterprise BD 合約數十萬起;iSensor IoT 賣硬體 + 安裝 NT$5-30K 老闆覺得貴 + 麻煩;台電官網提供 PDF 帳單但**完全沒有 AI 解釋 + 沒有異常偵測**;ChatGPT 不知道你電表讀值且不持續分析。**Gap 結構性**:能源 SaaS 廠商認為 SMB 客單價低沒動力做小型 SaaS,但台電 API 公開可合法取用,Google「台灣 中小企業 AMI 用電 異常 偵測」零 SaaS 結果。架構:**Time-Series Anomaly Detection** — `analyzer.py` 100% 純函式偵測 4 類異常(NIGHT_LEAK 23:00-06:00 > base × 2.5;HOUR_BURST 同 DOW × hour 4 週中位數 ×1.5+;DAILY_HIGH 單日 vs 同 DOW 中位數 +30%+;BASELINE_DRIFT 前後半段日均 ±10%+);LLM 只為純函式發現的 anomaly 寫人性化成因 + 3 條具體可執行行動建議 + 月省金額預估。**Multi-rule cross-validation**(同事件雙觸發 → 證據強度提升)、**LLM 永不重算 kWh**、**行動建議嚴禁泛泛「節能」**(必須具體如「叫維修廠商檢查 R134a 冷媒壓力」)、**嚴禁推銷換新設備**。
- **目標市場**: 1.5M 中小企業 + 工廠 + 連鎖店。Solo NT$199/月(單店餐飲 / 美業 / 早餐店)、Studio NT$799/月(3-10 店連鎖)、Chain NT$2,499/月(10-50 店)、Enterprise NT$5,000+/月(工廠)、年付 ×10 月折扣。WTP 錨點:餐飲店 1 次冷凍故障 NT$30-80K + 食材損失 vs Solo NT$199 → **單次預警 12+ 個月回本**;工廠月電費 NT$30-100 萬,1% 優化 = NT$3-10K/月直接回本。TAM 1% 滲透 = 6,000 家 × NT$199 = **月 NT$120 萬 MRR / 年 NT$1,440 萬 ARR**;加連鎖 + 工廠 → 年 ARR 3-5 千萬。Distribution: PTT Soft_Job / restaurant、餐飲老闆 FB 社群、商工會議所 / 中小企業協會、台電節電獎勵 / 經濟部能源局 ESCO 配合計畫、記帳士 / 會計師 partner、iCHEF / 沛點 integration partner、冷凍 / 冷氣維修廠商介紹費。

### Round 23 — `stylescan/` (Taiwan 🇹🇼 — junior/senior high essay AI-ghostwriting detection, **thirteenth AI pattern — Stylometric Matching**)

- **題目**: 台灣國高中作文 AI 代筆風險偵測(學生過去 5 篇作文 + 本次作文 + AI 範本 corpus → 純函式 20 個 stylometric 特徵 cosine 比對 → 標出疑似 AI 代筆給老師判讀)
- **解決的問題**: 108 課綱重視寫作,**國中會考國寫滿分 30 分**;學生用 ChatGPT / Claude / Gemini 寫作文激增,但繁中市場**零工具**(GPTZero / Originality.ai / Turnitin 都偏英文,中文 ROC-AUC 約 0.55)。國中國文老師 4-5 萬人,每位每週改 30-200 篇作文,**人工判讀 5 分鐘 / 篇 = 2.5 hr / 班 / 週機會成本**;直接質問學生 → 學生否認 → 沒辦法處理 + 信任受損 + 家長抗議。痛點:Dcard 教師版「全班 30 個有 5 個寫得跟翻譯論文一樣憑直覺懷疑沒證據」;PTT C_Education「上次直接質疑學生家長還來抗議」。中文 stylometric 學術圈研究多年(中研院 / 政大 / 台師大 NLP 組都有 paper),但**沒人做成國高中老師易用 SaaS**。架構:**Stylometric Matching** — `style_features.py` 100% 純函式抽 20 個書寫指紋特徵(句長分布 4 / 標點密度 7 / 詞彙風格 5 / 結構特徵 3 / 雜訊 1),純 stdlib 不依賴 numpy;`stylescan.py:decide_verdict` 純函式 4 類判定(CONSISTENT / MILD_DRIFT / STRONG_DRIFT / **LIKELY_AI**);**三向比對**(本次 vs 學生過去 vs AI 範本)區分「學生成熟」vs「AI 代筆」;LLM 只寫風格分析(150-250 字)+ 學生文體建議 3 條 + 老師 follow-up 3 條(現場寫作 + 訪談)。**LLM 嚴禁下「就是 AI 寫」斷論**(措辭強制為「風格大幅偏離」「建議老師訪談確認」),**最終判定權永遠在老師**(避免 false positive 親師衝突 + 保留學生誠實可能性如模仿散文 / 家長協助潤稿)。
- **目標市場**: 5 萬國高中 / 補習班國文老師。Free 5 篇/月、Solo NT$199/月(老師個人)、Department NT$1,499/月(一科 5-10 老師)、School NT$4,999/月(整校 + Google Classroom 整合)、City Edu 客製 NT$50K+/年(教育局採購)。WTP 錨點:老師月省 10 hr × NT$500/hr = NT$5,000 機會成本 vs Solo NT$199 = **25x ROI**。TAM 5% 滲透 = 2,500 老師 × NT$199 = **月 NT$50 萬 MRR / 年 NT$600 萬 ARR**;加 Department + School + City Edu → 年 ARR 1,500-3,000 萬;橫移大學課程 + 港澳新馬中文教育 → 翻倍。Distribution: 教師 FB 社群、PTT C_Education / Dcard 教師版、教師研習工作坊、補習班分校 BD、教育部 / 縣市教育局 partner(108 課綱「AI 負責任使用」配套)、教師 KOL(葉丙成 等)、大學師培系。

### Round 24 — `leasecheck/` (Taiwan 🇹🇼 — residential lease contract clause-extraction & risk audit, **fourteenth AI pattern — Structured-Output Extraction from Messy Real-World Docs**)

- **題目**: 台灣住宅租賃合約 AI 審約助手(房客上傳合約 → LLM 從原文精確抽出每條條款 → 純函式比對 corpus 20+ 條典型違法 / 危險 / 合理條款 → 純函式算 risk_score 0-100 → AI 寫房客易讀解釋與談判話術)
- **解決的問題**: 全台 200+ 萬租屋族,每年新合約 50-80 萬份,99% 簽約者**不會看條款**。房東給的「自製合約」常抄自 5 年前舊版,完全不符合內政部 2017 應記載 / 不得記載事項。常見坑:押金 3-6 個月(違法,法定上限 2 個月)、違約金 2 個月(違法,上限 1 個月)、修繕全推房客(違法)、強制續約(違法)、不得申報所得稅(違法)、房東隨時進入(違法)。律師審約 NT$3-5K **小資族負擔不起**;DoNotPay / Robinhood 海外工具不認識台灣租賃條例 + 民法 + 應記載事項;ChatGPT 直接問**幻覺嚴重**(編造條文);LegalBank 是法條搜尋不審契約;崔媽媽 / 法扶免費但要排隊。**Gap 結構性**:中文租賃法規開放、租屋族痛點明確、律師太貴、海外工具不在地化,Google「台灣 租屋合約 AI 審約」零 SaaS 結果。架構:**Structured-Output Extraction from Messy Real-World Docs** — `clauses_db.py` 預設 20+ 條典型租屋條款 corpus(每條附 risk_level red/yellow/green、severity_score 0-30、legal_basis 內政部 / 民法 / 條例、common_phrasing、negotiation_tip);LLM 精確抽出合約原文中的對應條款句子(structured extraction);純函式 `analyzer.py:assess_risk` 加總 severity_score 切檔 LOW / MEDIUM / HIGH / **CRITICAL**;LLM 寫每條 red/yellow 的房客易讀解釋 + 談判話術 + 整體建議優先談 3 件事。**LLM 永不算 risk_score**、**嚴禁編造合約沒寫的條款**、**嚴禁勸放棄 / 提告**(只給修約建議,重大爭議引導法扶 / 崔媽媽);純函式 fallback (keyword extract) 提供免 API key 模式 + 中文空白容差。
- **目標市場**: 200 萬租屋族 + 房仲 60,000 + 政府 / 公益 partner。Free 1 份/月、Solo NT$99/月(學生 / 租屋族)、Pay-per-use NT$199/份、Pro NT$299/月(LINE Bot + 修約建議 + 法扶預約)、B2B 房仲 NT$1,999/月、B2B 公益免費(政府 / 基金會贊助)。WTP 錨點:律師審約 NT$3-5K vs leasecheck NT$199 = **15-25x 便宜**;一條霸王條款擋下(押金 1 月 NT$15K + 違約金 1 月 NT$15K)= 直接省 NT$30K。TAM C2C 5% 滲透 = 25K-40K 人 × NT$199 = **年 NT$500-800 萬 ARR**;加 Pro + B2B 房仲 + 政府合作 → 年 ARR 2,000-4,000 萬;橫移日韓新中港 → 翻倍。Distribution: PTT home-rent / Dcard 租屋板、崔媽媽 / 法扶基金會 partner、大學新生季 (8-9 月)、591 / 樂屋網 listing 整合、YouTube 法律 KOL(雷皓明 等)、房地產 podcast、內政部地政司 / 縣市租賃服務站 partner。

### Round 25 — `retiremate/` (Taiwan 🇹🇼 — retirement planning AI advisor for 50-60yo, **fifteenth AI pattern — Conversational Agent with Tools**)

- **題目**: 台灣 50-60 歲族群退休規劃 AI 顧問(profile JSON → Claude tool-use API 自主調用 8 個純函式 tool[勞退新制 / 勞保 / 國保 / 個人儲蓄 / 月支出 / 健保 / 缺口 / 補足]→ 組合中立第三方退休規劃報告)
- **解決的問題**: 台灣已進入超高齡社會,**50-60 歲族群超過 600 萬人**,每月 ~10 萬人退休。但退休規劃工具現況極差:勞退新制 + 勞保老年年金 + 國民年金 + 個人儲蓄 + 健保 = **5 個獨立系統零整合**;勞動部勞退試算 / 勞保試算 UI 是 2005 年水準且分開試算;銀行 robo-advisor 偏「銷售投資 / 保險商品」(球員兼裁判);獨立 CFP 在台稀有且收費 NT$10-30K/次;ChatGPT 直接問**會幻覺編造勞退公式 / 弄錯月投保薪資上限**。痛點驗證:FB 退休理財社團「年金改革吵 10 年我還是看不懂月領多少」;Dcard 25-up「跑去問銀行理專一直推終身險」;PTT Salary「勞動部試算頁面像 2005 年的網站」。**Gap 結構性**:5 系統合一試算 + 中立立場 + 易用介面銀行不做(壓縮銷售)、政府不做(各部會不整合)、CFP 不做(產業分散)。架構:**Conversational Agent with Tools** — `tools.py` 100% 純函式 8 個 tool(estimate_labor_pension_new / estimate_labor_insurance_pension / estimate_national_pension / project_personal_savings / estimate_monthly_living_cost / estimate_post_retirement_nhi / compute_retirement_gap / required_savings_for_gap),每個 tool 帶 TOOL_DEFINITIONS schema(JSON);Claude 用 Anthropic tool-use API **自主決定**何時調用哪個 tool、傳什麼參數、收到結果後決定下一步;最後組合成完整報告(執行摘要 / 各項月領 / 月支出缺口 / 儲蓄成長 vs 需要儲蓄 / Top 3-5 具體建議 / 重要提醒)。**LLM 永不算 NT$**、**嚴禁推銷特定保險 / 投資商品**、**建議聚焦政策 lever**(自願提繳 6% 節稅 / 延後退休 1-2 年影響 / 勞保展延請領 +4%/年)。Tool 調用紀錄全透明列出供審計重現。
- **目標市場**: 600 萬 50-60 歲族群 + 200 萬 55-60 歲核心(退休前 5 年)。Free 1 次/月、Solo NT$199/月、Pro NT$499/月(配偶合併 + LINE Bot)、Pay-per-use NT$499/次、B2B 銀行白標 NT$50-200K/月(retain 高資產客戶)、B2B 政府 / 公益免費。WTP 錨點:CFP 諮詢一次 NT$10-30K vs retiremate Solo NT$199/月 = **50-150x 便宜**;延後退休 1 年的試算決策影響可達 NT$50-150 萬。TAM 1% 滲透 = 2 萬人 × NT$199 = **月 NT$400 萬 MRR / 年 NT$4,800 萬 ARR**;加 Pro + B2B 銀行 + 政府合作 → 年 ARR NT$1-2 億;橫移 60-70 歲已退休族群 → 翻倍。Distribution: 退休前公務員 / 軍教 / 國營員工社團、企業 HR 員工福利、FB 退休理財社團、PTT Salary / 中年板、Threads 中年理財 KOL(夏韻芬 等)、退休 podcast、勞動部 / 勞保局 partner、第二人生 / 退休學校 / 樂齡學習中心。

### Round 26 — `cashpilot/` (Taiwan 🇹🇼 — SME cash-flow Monte-Carlo risk simulator, **sixteenth AI pattern — Simulation / Monte-Carlo**)

- **題目**: 台灣中小企業現金流 Monte-Carlo 風險試算(profile JSON → 純函式跑 2000 次 12 月模擬,抽月營收 / 應收延遲 / 倒帳事件 / 變動成本 → 算現金破洞機率 + P10/P50/P90 餘額 + 接大單情境對照 → LLM 解釋 + 給接 / 不接 / 條件式建議)
- **解決的問題**: 台灣中小企業 150 萬家,5-30 人規模 30 萬家。**70% 倒閉是「現金流問題」非「不賺錢」**。痛點驗證:FB 中小企業老闆「上市公司大單 200 萬 90 天票期接還是不接」;PTT Salary「明明 P&L 賺錢但每個月底發薪水都心臟亂跳因為錢都卡在應收」;Dcard 創業板「想找會計師做 cash flow projection 開價 30 萬說要做 3 個月」。會計師事務所看「過去 P&L」**不做前瞻 cash flow simulation**;Xero / QuickBooks / Float / Pulse 都是**簡單線性預估**沒做不確定性;銀行貸款專員偏「線性 best case」評信用;iCHEF / Cashier 是 POS / 開票完全沒 cash flow;ChatGPT 不能跑模擬只能講概念。**Gap 結構性**:中文 + Monte-Carlo + 在地化(中信 / 兆豐 / 應收承購)= 大型會計事務所做不到輕量、海外 SaaS 不在地化、Excel 太複雜。Google「台灣 中小企業 現金流 模擬」零 SaaS 結果。架構:**Simulation / Monte-Carlo** — `simulator.py` 100% 純函式 stdlib 只用 random + statistics;2000 次 12 月模擬每次抽月營收 ~ Normal(μ, σ)、應收回收 60d ± 15d、大客戶倒帳 Bernoulli、變動成本 × ratio;統計 prob_cash_negative_any_month + 逐月累積 + P10/P50/P90 最低 / 年底餘額 + worst_month_distribution;classify_risk 純函式 4 檔 LOW/MEDIUM/HIGH/CRITICAL;若 profile 有 big_deal_amount > 0 跑第二次「接大單後」模擬 + compare_scenarios 對照差異。LLM 寫 baseline 解釋 + 大單決策(推薦 / 條件式 / 不推薦)+ 3-5 條具體可執行建議(應收拆款 / SME LOC / 應收承購 / 砍變動成本)+ 警覺訊號。**LLM 永不算機率 / NT$**、**嚴禁推銷特定銀行 / 保險 / SaaS 商品**、**不建議 IPO / VC 募資**(中小企業可立即執行的 lever)、純函式 deterministic 可審計。
- **目標市場**: 150 萬 SME + 30 萬 5-30 人核心。Free 1 次/月、Solo NT$399/月(1-5 人)、Pro NT$999/月(5-30 人 + 多情境 + LINE 警示)、Enterprise NT$2,999/月(30+ 人 + API + 會計軟體整合)、B2B 銀行 / 會計師 客製 NT$50K+/月。WTP 錨點:會計師客製 cash flow projection NT$5-30 萬 vs Pro NT$999 = **5-30x 便宜 + 即時更新**;一次「接錯大單」破洞損失難估,NT$999/月 預防。TAM 1% 滲透 = 3,000 家 × NT$999 = **月 NT$300 萬 MRR / 年 NT$3,600 萬 ARR**;加 Enterprise + B2B 銀行 / 會計師 → 年 ARR NT$1-2 億;橫移日韓港新 SME → 翻倍。Distribution: PTT Salary / 中小企業板、FB 老闆社群、記帳士 / 會計師事務所 partner、中信銀 / 兆豐 SME LOC partner、創業育成中心 / 商總、YouTube 中小企業 KOL、iCHEF / Cashier integration partner。

---

## Conventions for future rounds

- **Geography priority (updated 2026-05-10)** — user is Taiwanese, so **Taiwan first** when evidence is comparable. Then other Asia. Already covered: US (scopescribe), TW tax/freelancer (laobao), KR→JP (kosmelingo), JP domestic (mitsumori), KR domestic (settlekit), Vietnam (hoadon), TW long-term care (carepen), TW legal (sudoc), TW veterinary (vetnote), TW 補教月報 (monthrep), TW 健身 (fitlog), TW 二手機車 (motoval), TW LINE 團購 (snaporder), TW 政府補助 RAG (subsidybot), TW 餐廳排班 LINE bot (shiftsync), TW 婚攝媒合 (weddingmatch), TW 政府標案 monitoring (tenderwatch), TW 美業 churn (salonguard), TW 房屋 vision 估價 (propvision), TW 作物病蟲害 vision (cropscan), TW 登山媒合 personalization (trailmatch), TW 中小企業 AMI 用電 anomaly (wattmon), TW 國高中作文 AI 代筆 stylometric (stylescan), TW 住宅租賃合約審約 extraction (leasecheck), TW 50-60 歲退休規劃 agent (retiremate), TW SME 現金流 Monte-Carlo (cashpilot). For Taiwan, pick *fresh verticals* (logistics / HR / construction / 自媒體 / 托嬰幼兒園 / 宮廟 / 家政 / dating / pet vision-or-voice / non-vet clinic 預約 / 二手家具 / 殯葬 / 嬰幼兒哭聲 / 語言發音 voice-signal / 補習班招生 / 婚禮策劃 / 葬禮 / 中藥房 / 物流司機).
- **Architecture diversification rule** — covered AI patterns: doc-gen (rounds 1-11), vertical pricing model (motoval r12), NLP/OCR multi-message aggregation (snaporder r13), RAG over local-knowledge corpus (subsidybot r14), scheduling + LINE bot (shiftsync r15), matching with embedding similarity (weddingmatch r16), real-time monitoring + LLM semantic-match scoring (tenderwatch r17), churn prediction / anomaly detection on customer events (salonguard r18), vertical pricing + vision identification combo (propvision r19), pure vision classification (cropscan r20), behavioral personalization with hard-filter pre-screening (trailmatch r21), time-series anomaly detection on metered signals (wattmon r22), stylometric matching for AI-ghostwriting detection (stylescan r23), structured-output extraction from messy real-world docs (leasecheck r24), conversational agent with tool-use API (retiremate r25), Monte-Carlo simulation with scenario comparison (cashpilot r26). Future rounds: prefer **voice signal analysis** / **multi-modal fusion** / **graph / network analysis** / **vector retrieval with re-ranking** / **A/B counterfactual estimation**. Avoid doc-gen / OCR-aggregation / RAG-Q&A / scheduling+LINE-bot / matching-similarity / monitoring+alerting / churn-prediction / pricing-with-vision / pure-vision-classification / hard-filter-personalization / time-series-anomaly / stylometric-matching / structured-extraction / conversational-agent-with-tools / monte-carlo patterns unless extraordinary evidence.
- **Vertical diversification** — already covered: insurance, freelance tax, cosmetic regulatory, manufacturing quoting, creator contracts, F&B retail tax compliance, long-term care service records, civil litigation drafting, veterinary SOAP records, cram-school monthly report, fitness-trainer post-class report, used-motorcycle valuation, LINE group-buy aggregation, government subsidy RAG, restaurant shift management, wedding photographer matching, government tender monitoring, beauty salon churn, real-estate vision pricing, crop disease vision classification, hiking-trail personalized matching, SMB energy / AMI metering, junior/senior high essay AI-ghostwriting detection, residential lease contract auditing, retirement planning for pre-retirees, SME cash-flow risk modeling.
- **Architecture** — every prototype keeps numbers in pure Python functions and uses LLM only for prose / classification. Never let AI calculate money.
- **Demo without API key** — every project ships pre-generated examples in `examples/` so reviewers can see output without setting `ANTHROPIC_API_KEY`.
- **Commit format** — one commit per round, message explains pain + competitor gap + verified test cases. Push to `origin/main` after each round.
- **Update this file** — every new round must add a `### Round N — ...` block above and update the geography/vertical "covered" list in this section.

---

*Last updated: round 26 (2026-05-10). Loop job ID: `6901dad6` (every 20 min at :08/:28/:48).*
