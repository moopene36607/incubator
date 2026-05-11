### Round 11 — `fitlog/` (Taiwan 🇹🇼 — personal trainer post-class report)

- **題目**: 台灣健身教練 (PT) / 瑜珈教練 課後訓練報告 AI 助手
- **解決的問題**: 台灣自由接案 PT 約 2-3 萬人,每天 6-8 節 1 對 1 課,每節結束後要寫課後紀錄維持留存與信任。Dcard 健身板:「一天 6 節課要寫 6 份,累死」。PTT FITNESS:「Word 模板還是很花時間」。每天 30-40 分鐘 admin × 教練時薪 NT$1,500 = 月省 NT$11K+ 機會成本。**TrueCoach (USD$19.99 月費) 在英文市場已驗證 PMF**;繁中市場零 AI 課後報告產生器,本土 MixFit / SportSoft 是課程預約點名沒 AI;ChatGPT 直接問每次要重打學員資料、沒結構化動作 grounding。架構:純函式渲染量化訓練表 + LINE 純文字版,AI 只寫 5 段(摘要 / 進步 / 觀察 / 下次重點 / 恢復飲食)。**AI 嚴禁編造**(體重 / 體脂 / 卡路里 / 心率沒提到不能補)+ **AI 不下醫療診斷**(學員主述不適時用「下次留意 / 視情況調整」措辭,規避 PT 與物治職業界線)。30 個動作 seed db 用台灣健身圈詞彙(槓鈴背蹲舉 / RPE / 超負荷 / TUT)。
- **目標市場**: 2-3 萬持照 PT,Solo NT$299/月(對標 TrueCoach NT$640 便宜 53%)、Solo+ Whisper NT$599/月、Studio NT$1,499/月。WTP 錨點:每天省 30-40 分鐘 × NT$1,500 時薪 = 月省 NT$11K+ vs Solo NT$299 = **37x ROI**。TAM 5% 滲透 = 月 NT$30 萬 MRR。Distribution: FB「健身教練交流」社團、體適能協會 (CTSCA / CSCS) 訓練營、YouTube 健身 KOL (肌肉爸爸 / 健人蓋伊 / 館長) 合作、Threads / IG 健身教練、World Gym / Anytime Fitness 駐店 PT BD。
