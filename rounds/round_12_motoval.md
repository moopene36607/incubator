### Round 12 — `motoval/` (Taiwan 🇹🇼 — used motorcycle valuation, **first non-doc-gen pattern**)

- **題目**: 台灣二手機車 AI 估價助手(自然語言車況描述 → 估值 + 議價建議)
- **解決的問題**: 台灣年交易二手機車 60 萬台,FB「台灣二手機車買賣」27 萬成員社團每天上百篇詢價,但**無客觀估價工具**。8891 / U-CAR 主打汽車 + 機車是 listing 沒估價;Yahoo / 露天只有 listing;Kelley Blue Book 等英美工具不認識台灣機車車款(光陽 Force / 三陽 DRG / Yamaha 新勁戰 / Gogoro)— 結構性 gap。前 11 輪 prototype 全是 document-gen,本輪刻意換成 **vertical pricing model + 自然語言解析** 架構。`pricing.py` 純函式 5 步驟估值(MSRP × 年折舊率^age × 里程 factor × 車況等級 × 細項加減分),所有數字計算 100% 純函式絕不交給 LLM;sanity cap 限制估值 ≤ MSRP × 0.95。AI 只負責解析自然語言「我的 Force 155 2021 跑了 7 萬...」→ 結構化 input。
- **目標市場**: 60 萬台年交易 + 2,000 家二手車行。B2C NT$49/次 估價、B2C 月會員 NT$199、B2B 車行 NT$799/月(無限批次)、B2B 連鎖 NT$2,499/月、API NT$0.5/call。WTP:B2C NT$49 vs 開錯價 NT$5K+ = 100x 保險;B2B 車行月 30 台估價省一台錯估 NT$2K = 月費回本。TAM B2C NT$147 萬/年 + B2B NT$192 萬 ARR + API enterprise = **總天花板 NT$1,000 萬 ARR**。Distribution: PTT biker / Dcard 機車版、FB 二手機車買賣社團、YouTube 機車 KOL(老吳 / Apex / 老查)、8891 / 露天 listing SEO、二手車行直接 BD。
