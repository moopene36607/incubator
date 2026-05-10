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

---

## Conventions for future rounds

- **Geography priority (updated 2026-05-10)** — user is Taiwanese, so **Taiwan first** when evidence is comparable. Then other Asia (JP / KR / SEA / HK / mainland China). US / EU only when no Asian equivalent exists. Already covered: US (scopescribe), TW tax/freelancer (laobao), KR→JP (kosmelingo), JP domestic (mitsumori), KR domestic (settlekit), Vietnam (hoadon), TW long-term care (carepen), TW legal (sudoc), TW veterinary (vetnote), TW cram-school / talent-class monthly report (monthrep). For Taiwan, pick *fresh verticals* (F&B / non-vet healthcare clinic admin / real estate / logistics / HR / wedding / agriculture / construction / 自媒體 ops / 美髮美容 / 健身 / 二手 / 托嬰幼兒園 / 宮廟) — `laobao` tax, `carepen` long-term care, `sudoc` legal, `vetnote` veterinary, `monthrep` 補教 / 才藝 月報.
- **Vertical diversification** — already covered: insurance, freelance tax, cosmetic regulatory, manufacturing quoting, creator contracts, F&B retail tax compliance, long-term care service records, civil litigation drafting, veterinary SOAP records, cram-school monthly report. Avoid further insurance / payroll / cosmetic / quote / contract / e-invoice / care record / legal-document / vet-record / clinical-SOAP / cram-school-report topics unless evidence is *extraordinarily* strong.
- **Architecture** — every prototype keeps numbers in pure Python functions and uses LLM only for prose / classification. Never let AI calculate money.
- **Demo without API key** — every project ships pre-generated examples in `examples/` so reviewers can see output without setting `ANTHROPIC_API_KEY`.
- **Commit format** — one commit per round, message explains pain + competitor gap + verified test cases. Push to `origin/main` after each round.
- **Update this file** — every new round must add a `### Round N — ...` block above and update the geography/vertical "covered" list in this section.

---

*Last updated: round 10 (2026-05-10). Loop job ID: `6901dad6` (every 20 min at :08/:28/:48).*
