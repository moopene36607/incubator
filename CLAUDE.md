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

---

## Conventions for future rounds

- **Geography diversification target** — already covered: US, TW, KR→JP cross-border, JP domestic, KR domestic. Strongly prefer SEA (VN/TH/ID/PH) / HK / mainland China / fresh JP non-manufacturing / fresh TW non-tax in upcoming rounds.
- **Vertical diversification** — already covered: insurance, freelance tax, cosmetic regulatory, manufacturing quoting, creator contracts. Avoid further insurance / payroll / cosmetic / quote / contract topics unless evidence is *extraordinarily* strong.
- **Architecture** — every prototype keeps numbers in pure Python functions and uses LLM only for prose / classification. Never let AI calculate money.
- **Demo without API key** — every project ships pre-generated examples in `examples/` so reviewers can see output without setting `ANTHROPIC_API_KEY`.
- **Commit format** — one commit per round, message explains pain + competitor gap + verified test cases. Push to `origin/main` after each round.
- **Update this file** — every new round must add a `### Round N — ...` block above and update the geography/vertical "covered" list in this section.

---

*Last updated: round 5 (2026-05-10). Loop job ID: `6901dad6` (every 20 min at :08/:28/:48).*
