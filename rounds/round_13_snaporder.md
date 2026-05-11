### Round 13 — `snaporder/` (Taiwan 🇹🇼 — LINE group-buy order aggregation, **OCR/NLP non-doc-gen pattern**)

- **題目**: 台灣 LINE 團媽自動整單工具(群組對話 / 截圖 → 30 秒整出彙整表 + LINE 對帳訊息)
- **解決的問題**: 估計台灣活躍團媽 40-100 萬人,每月 8-15 次團 × 30-80 條訂購訊息 = 每月 240-1,200 條手工逐條判讀。Dcard 媽媽版:「整單 2-4 小時 / 次,算錯就自己賠」。揪好買 / 多多團走「電商平台」方向,不解決「群組截圖 → 整單」最後一哩痛點(自打嘴巴會把用戶留在 LINE)— 結構性 gap。架構:**LLM 解析非結構化 LINE 對話 → 結構化 OrderEvent (add/set/cancel),純函式聚合(`aggregator.py`)100% 算錢**。三種 action 區分精確處理「改成 N 個」「取消」這類團購群組常見模糊語言。Skipped events 透明列出避免靜默漏單。
- **目標市場**: 40-100 萬團媽,Pro NT$299/月、Business NT$699/月、年付折扣。WTP:每月 36 小時手工 × NT$200/hr = NT$7,200 機會成本 vs NT$299 = 24x ROI。TAM 1% 滲透 = 5,000 人 × NT$299 = **月 NT$150 萬 MRR / 年 NT$1,800 萬 ARR**;加 Business + 港澳 + 日韓繁中 → 翻倍。Distribution: FB 大型團購社團(「TAIWAN 媽媽團購交流」5-10 萬人)、Dcard 媽媽版 / WomenTalk、Threads / YouTube 主婦 KOL、LINE 官方 Bot Store。
