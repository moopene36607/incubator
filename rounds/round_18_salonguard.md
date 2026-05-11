### Round 18 — `salonguard/` (Taiwan 🇹🇼 — beauty salon churn prediction, **seventh non-doc-gen pattern**)

- **題目**: 台灣美髮 / 美甲 / 美睫沙龍 回頭客流失預測 + 個人化 LINE 挽回訊息
- **解決的問題**: 全台美業約 55,000 家,客戶 LTV NT$10K-30K/年,但 **99%+ 的沙龍沒有任何流失預測機制**。PTT BeautySalon:「客人都是來一次就消失,我也不知道哪裡出問題」;Dcard 美業:「等她不見了才發現」。iSalon / WACA / Booksy / MindBody 全部只做預約收款 **無 churn prediction**。架構:**Churn Prediction / Anomaly Detection** — `rfm.py` 100% 純函式 RFM + 個人化 avg_interval(不是粗糙的全店 60 天平均,而是**每位客戶自己的歷史回訪間隔**);ratio = recency / avg_interval 映射到 5 級風險(active/watch/warning/high/lost);加權 bonus(高客單 NT$2,500+ +5 分 / 高頻 6 次+/年 +5 分);AI 只為高風險客戶寫 80 字 LINE 挽回訊息(引用具體上次服務 / 不堆折扣 / 不批量自動發送)。
- **目標市場**: 55,000 家美業店。Solo NT$599/月(對標 iSalon NT$1,200 便宜 50% + 多 churn 功能)、Studio NT$1,299/月、Chain NT$3,500/月。WTP:1 客 LTV NT$10-30K,挽回 1 客 = 年費回本。TAM 3% 滲透 = 1,650 家 × NT$599 = **月 NT$99 萬 MRR / 年 NT$1,180 萬 ARR**。Distribution: FB 美業社群、PTT BeautySalon / Dcard 美業、iSalon / Beautix 既有用戶 add-on、美髮 / 美甲 KOL 合作、台北國際美容展、設計師 LINE 社群。
