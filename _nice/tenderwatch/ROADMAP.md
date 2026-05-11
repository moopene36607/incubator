# tenderwatch — 一人公司 12 個月 Roadmap

> 規劃日期：2026-05-11
> 規劃前提：Approach A（內容 SEO PLG）
> 創辦人限制：10hr/週、預算 NT$10,000 / 6 個月、零寫程式（Claude Code 代勞）、軟工背景但不認識 SI 老闆

---

## 0. 規劃前提與硬限制

| 變數 | 設定 |
|---|---|
| 個人投入 | 10 小時/週（**非寫程式**） |
| 預算 | NT$10,000 / 前 6 個月（含底層維運） |
| 開發 | 100% 委由 Claude Code |
| 創辦人技能 | 軟體工程師 |
| 創辦人人脈 | 不認識 SI / 顧問 / 工程顧問 老闆 |
| 起點資產 | 原型已可運作（`tenderwatch.py` + `tender_filter.py` + 範例輸出） |

### Approach A 為什麼是唯一可行解

1. **沒人脈** → 不能跑 high-touch B2B sales
2. **沒預算** → 不能跑 paid ads
3. **有工程能力** → 寫深度技術內容、做產品自助化是 realistic
4. **時間有限** → 內容是「投入一次、被動產出半永久」的資產，10hr/週唯一能 compound 的就是它

---

## 1. 時間 / 預算分配

### 每週 10 小時分配

| 項目 | 時數 |
|---|---|
| 內容寫作（每週 1 篇 2,500–3,500 字） | 4 |
| 與 Claude Code 寫規格 + 驗收 | 2 |
| 客服 + 社群留言互動 | 2 |
| 分析 KPI + 週報 | 1 |
| 雜事（發票、合約、法務模板） | 1 |

### 前 6 個月預算 NT$10,000 分配

| 項目 | 金額 | 備註 |
|---|---|---|
| 行號設立規費 | NT$1,000 | 一次性 |
| `tenderwatch.tw` 域名 × 1 年 | NT$500 | Gandi / Cloudflare Registrar |
| Hosting（Zeabur Hobby） | NT$1,200 | Month 3 起付費 NT$200×6 |
| Anthropic API | NT$3,000 | 6 個月，靠 embedding pre-filter 砍 80% |
| OpenAI Embedding API | NT$300 | text-embedding-3-small |
| 商標登記 | NT$2,800 | 選做，第 4 個月再辦 |
| iubenda / 法務模板 | NT$0 | 免費 tier |
| LINE Messaging API | NT$0 | 500 則/月免費 tier |
| 綠界開戶手續費 | NT$0 | 抽 2.x% 交易 |
| 雜支緩衝 | NT$1,200 | 設計小費、Buffer 排程、email 服務 |

---

## 2. Phase 0 — Week 1-2：法務 + 基礎設施

### 公司形式：行號（獨資商號）

| 形式 | 設立成本 | 月維運 | 結論 |
|---|---|---|---|
| 個人接案 (5+6 報稅) | NT$0 | NT$0 | ❌ 收入超 NT$83K/月會被嚴查 |
| **行號（獨資商號）** | NT$1,200 規費 | NT$0–2K/季 | ✅ **採用** |
| 有限公司 | NT$1 萬 + 25 萬資本額 | NT$2-3K/月記帳 | ❌ 等 MRR 過 NT$10 萬再升 |

**行號 setup checklist**：

- [ ] 想 3 個商號名，到 [全國商業司](https://gcis.nat.gov.tw) 線上預查
- [ ] 戶籍縣市政府商業課辦設立（NT$1,000 規費，1 日完成）
- [ ] 線上申請電子發票字軌（財政部 e-tax）
- [ ] 開獨立銀行帳戶（玉山 / 國泰）

### 域名

- 首選 `tenderwatch.tw`（NT$500/年）
- 備案 `biaoan.tw` + `tenderwatch.com.tw`
- **不買 `.com`**

### 法務模板

| 文件 | 來源 |
|---|---|
| 服務條款 | 抄 Notion / Linear 中文 ToS 改寫 |
| 隱私權政策 | iubenda 免費 tier |
| 個資告知聲明 | 國發會範本 |
| 退費政策 | 月費先付 / 14 天試用免費 / 不退費 |

### 信箱與品牌

- Cloudflare Email Routing 免費轉發 `hi@tenderwatch.tw` 到 Gmail
- 不開 Google Workspace

### Phase 0 出口判準

- [ ] 行號統編到手
- [ ] 域名 + Cloudflare DNS 接好
- [ ] LINE Bot Channel 開好
- [ ] 銀行帳戶開好、綠界商家審核**送出**（Week 1 就送）
- [ ] ToS + 隱私 + 個資告知 + 退費政策 4 份 PDF 放官網

**Phase 0 總花費：NT$2,200**

---

## 3. Phase 1 — Month 1-2：Production MVP

由 Claude Code 開發；你每週 2hr 寫規格 + 驗收。

### Sprint 1 (Week 1-2) — 資料抽取 + 持久化

```
Task 1.1  接政府電子採購網 OpenData API
          - 每日 06:00 / 14:00 cron 抓增量
          - 重試 / 限流 / 失敗 Discord webhook 告警
Task 1.2  Postgres schema：tenders / users / profiles / matches / subscriptions
Task 1.3  原型 lib 化（供 worker 呼叫）
Task 1.4  Embedding pre-filter
          - text-embedding-3-small embed 標案 + profile
          - cosine sim < 0.3 直接丟、0.3-0.6 才送 LLM
          - 預期 token cost 砍 70-80%
```

### Sprint 2 (Week 3-4) — 使用者 + 訂閱

```
Task 2.1  LINE Login（不做 email/密碼）
Task 2.2  Onboarding wizard：profile 填空式 + 範例選單
Task 2.3  綠界定期定額（authcode）
          - Free / Solo NT$799 / Pro NT$2,500
          - 自動續訂 + 卡片失敗 retry + 自動開發票
```

### Sprint 3 (Week 5-6) — 推播 + 報表

```
Task 3.1  LINE Bot 推播
          - 每日 09:00 推播 score >= 70
          - rich menu：今日報告 / 修改 profile / 暫停
Task 3.2  Web dashboard
          - 今日報告 markdown render
          - 30 天歷史搜尋
          - profile 編輯
          - 訂閱 / 發票管理
Task 3.3  Email digest
```

### Sprint 4 (Week 7-8) — Ops + Soft Launch 準備

```
Task 4.1  Monitoring：Better Stack 免費 + Discord 告警
Task 4.2  Sentry 免費 tier（5K event/月）
Task 4.3  Plausible / Umami 自架分析（不上 GA）
Task 4.4  Marketing site：landing + ToS + Privacy + Pricing + FAQ
Task 4.5  Smoke test：你親自跑「註冊→收推播→付款→收發票」一輪
```

### 開發風險與緩衝

| 風險 | 緩衝 |
|---|---|
| 政採網 OpenData 格式變更 / 限流 | 第一週做 graceful degrade + 告警 |
| 綠界商家審核被退件 | Phase 0 Week 1 就送、備案 Stripe |
| LINE Bot 綁定 UX 差 | 至少 3 個朋友通過 onboarding 才上線 |
| Embedding 過度激進剔除 | sim threshold 設保守 0.25 + 抽樣 100 件 audit |

### Phase 1 出口判準

- [ ] 你跑完「註冊 → 推播 → 付款 → 發票」全流程
- [ ] 連續 7 天推播觸發成功
- [ ] Anthropic API 月成本實測 < NT$500（10 demo profile）
- [ ] 4 份法務頁到位
- [ ] Discord 告警 channel 有訊號

**Phase 1 花費：NT$700**

---

## 4. Phase 2 — Month 3：Soft Launch

目標：Month 3 月底 20-50 個免費註冊 + 1-2 個付費。

### 定價（**lock-in 半年不亂改**）

| 方案 | 月費 | 年付（×10） | 限制 |
|---|---|---|---|
| Free | NT$0 | — | 1 profile / 每日推播上限 3 件 / 14 天歷史 |
| **Solo** | **NT$799** | NT$7,990 | 1 profile / 不限件數 / 90 天歷史 / LINE + Email |
| Pro | NT$2,500 | NT$25,000 | 5 profile / 得標分析 / Calendar 整合 / 優先客服 |
| Enterprise | 客製（標「聯絡我們」） | — | 不限 profile / 客製欄位 / SSO |

**3 個刻意決定**：
1. Free 不限時間（不寫 14 天試用）= PLG 漏斗底
2. Free 限「每日推播 3 件」不限總件數 = 自然升級觸發
3. 年付折 2 個月 = 提早鎖現金流

### Soft Launch 第一週節奏

| Day | 動作 | 你的時間 |
|---|---|---|
| D1 | 寄 email 給 5 個朋友 → 拜託試用 + 給 5 個回饋 | 2hr |
| D2 | 改完 critical bugs | 2hr |
| D3 | PTT Soft_Job 發 1 篇「我做了一個免費政採網 AI 篩選工具」 | 1hr 寫 + 4hr 回留言 |
| D4-7 | 留言 / DM / LINE 接待 | 5hr 散落 |

### Soft Launch 內容彈藥（**Month 3 第一天就要在官網**）

1. 「政府電子採購網搜尋為什麼那麼難用 — 一個工程師的拆解」
2. 「2026 公部門資安標案完整指南：從 ISO 27001 到投標金額分布」
3. 「中小型 SI 廠商一年到底接到幾個政府案？我們爬了 3 年資料」
4. 「招標王 vs 政採網 RSS vs tenderwatch：3 種訂閱方式優缺點」
5. 「免費版可以做什麼 / 為什麼不做 14 天試用 / 怎麼退費」

### 不該做（黑名單）

- ❌ Product Hunt（受眾錯）
- ❌ FB / IG 廣告（預算不足）
- ❌ KOL 業配（垂直無對的 KOL）
- ❌ iThome 鐵人賽 30 天（綁太死）

### Soft Launch KPI（Month 3 月底）

| 指標 | 警告 | 健康 | 超預期 |
|---|---|---|---|
| Free 註冊 | < 10 | 20-50 | > 80 |
| Day 7 retention | < 20% | 30-50% | > 60% |
| LINE 打開率 | < 30% | 40-60% | > 70% |
| 付費轉換 | 0 | 1-2 | 3+ |
| PTT 推噓比 | -3 以下 | 推 > 5 | 推 > 30 |

### Soft Launch 失敗 trigger（註冊 < 10）

→ 不是繼續 Approach A，是去找 3 個 SI 老闆**面對面 30 分鐘**（LinkedIn DM、創業聚會、咖啡廳）
→ 如果都說「不需要」，ICP 假設錯，pivot 或 sunset

---

## 5. Phase 3 — 內容 SEO 引擎（Month 1-9 ongoing）

每週 4hr，9 個月 = 36 篇深度文。

### 週節奏

| 週時段 | 時數 | 動作 |
|---|---|---|
| 週一 | 1hr | 選題 + 大綱（Claude 助攻） |
| 週三 | 1.5hr | 初稿（Claude 寫 1500 字 → 你 polish 到 2500-3500） |
| 週五 | 1hr | 圖表 + 截圖 + 案例 + 內鏈 + meta |
| 週日 | 0.5hr | 發佈 + 跨平台 |

### 內容支柱：3 cluster × 12 篇

#### Cluster A — 標案類別投標完整指南（SEO 主力 15 篇）

公部門資安、雲端遷移、SI 系統、APP 開發、LMS、HIS、政府網站改版、資料庫遷移、AI/LLM 服務、設計外包、軟體授權、影片製作、教育訓練、雲端託管、機房維護

每篇格式：痛點 → 案件數 + 預算分布 → 必備認證 / 資本額 → 得標廠商側寫 → 老司機建議 → CTA

#### Cluster B — 工具比較與替代（competitor hijack 10 篇）

招標王 vs tenderwatch、政採網 RSS 訂閱、TenderAlert.tw 停服替代、OpenFun pcc-viewer 用法、Excel 整理 5 招、Google Alert 行嗎、ChatGPT 找標案、自架爬蟲 vs SaaS、招標公報網付費值嗎、代標公司 vs 自己投

#### Cluster C — 產業 data story（PR + backlink 11 篇）

2025 政府標案總金額 / 流標率、AI/LLM 標案爆發、北中南縣市 IT 採購差異、各部會發包習慣、中小企業得標率變化、女性 / 青年得標比、ESG 採購滲透、共同供應契約 vs 個案、跨年度框約佔比、原民 / 中小企業優惠採購法定比例落實

### 一稿多用通路

| 通路 | 形式 |
|---|---|
| 官網 blog | 完整 2500-3500 字 |
| Medium 中文 | 同稿 |
| Threads | 5 則 thread |
| iThome 鐵人賽選文（不參賽） | 重點段落 |
| LINE OA 月報 | 5 篇精選 |
| Reddit r/Taiwan | 偶爾 1 篇 |

### SEO 技術底層（Phase 1 Marketing site 就要對）

- Astro / Next.js static, Lighthouse > 95
- schema.org Article + BreadcrumbList
- sitemap.xml + RSS 自動
- 中文 slug 英文化
- Search Console + Bing Webmaster 第一天提交
- 每篇至少 3 內鏈

### SEO 流量曲線預估

| 月 | 累積文章 | Google 月流量 | 註冊轉換 |
|---|---|---|---|
| Month 3 | 8 | 50-200 | 1-3% |
| Month 6 | 20 | 500-1,500 | 1-3% |
| Month 9 | 36 | 2,000-5,000 | 1-3% |
| Month 12 | 50 | 5,000-15,000 | 2-4% |

Month 9 預估 **20-150 自然註冊 / 月**、**1-5 付費 / 月**。

### 警示燈

- 連續 4 週寫不出 1 篇 → 時間預算被吃，重排
- 半年累積 < 15 篇 → 不會 compound
- Search Console 6 個月後 0 indexed → 技術 SEO 出包
- 文章像 ChatGPT 通稿 → Google 2026 直接降權

---

## 6. Phase 4 — 通路冷啟動（Month 3-9，每週 2hr）

| 通路 | 受眾 | 你的成本 | Action |
|---|---|---|---|
| PTT Soft_Job / SOHO 板 | 中 | 0 | 月 1 篇純分享文，3 個月 build karma |
| FB 軟體開發者交流 / 政府標案社群 | 高 | 0 | 週 1 則有用回答 + 月底 1 次自介 |
| Threads 個人帳號 | 中 | 0 | 日 1-2 則「政採網日常觀察」短內容 |
| LINE OA「政府標案訊息站」 | 高 | 500 則/月免費 | Month 4 開，月精選 + 亮點得標案例 |
| Inside / 數位時代 / iThome 投稿 | 中 | 0 | 投 1-2 篇 Cluster C data story |
| 記帳士 / 會計師 partner | 高 | 拆 20% | Month 6 開始 DM 3-5 家 |
| 工會 / 公會 partner | 中 | 拆分潤 | Month 9 後才考慮（需 case study） |
| Google Ads SKAG | 高 | NT$1,200 試 4 天 | 只在 Month 6 後試 1 次 |

### Cold DM 模板（Month 4 起，每週 5 人）

對象：FB「台灣 SI 廠商交流」發過「找 [類別] 案」的老闆

```
您好，我是 tenderwatch 的開發者，看到您 [日期] 發文找 [類別] 標案。
我做了一個工具：每天政採網新公告 → AI 篩出符合您公司能力的 → LINE 推播。

不是要您買，先送一個月免費讓您試試（不用信用卡）。
試完不喜歡直接刪 LINE Bot 就好。

如果您願意，回我「OK」或公司名稱，我手動幫您開通。
— [你的名字]
```

成功率現實預期：寄 50 → 開 25 → 5 註冊 → 1-2 付費。

### Partner（Month 6+）

記帳士事務所 affiliate：每帶 1 付費客戶拆 20% × 12 月 ≈ NT$1,918 (Solo)
第一年目標：3 家事務所、共 10 個 referred 付費。

### 失敗訊號

- Month 6 PTT / FB 0 自然詢問 → ICP 假設錯
- Month 9 partner 0 簽約 → 切 outbound 找 5 家會計師
- Month 12 累計 < 5 付費 → 進 Phase 6 決策

---

## 7. Phase 5 — Month 6-9：Pricing / Retention 微調

**Month 6 第一次 review，只動一次**。

### 量測指標

| 指標 | 目標 | Trigger |
|---|---|---|
| Free → Solo 轉換 | 5-8% | < 3% = free tier 給太多 |
| Solo Day 30 retention | > 80% | < 70% = 推播品質不夠 |
| Solo MRR churn | < 5%/月 | > 10% = onboarding 出問題、exit 訪談 |
| ARPU | NT$799-1,200 | < NT$799 = 沒人升級 Pro |
| API cost / 付費用戶 | < NT$80/月 | > NT$150 = pre-filter 沒收效 |
| CAC | < NT$1,200 | > NT$2,000 = 通路效率差 |

### Pricing 試驗（三選一，不同時動）

- A. Free tier 加嚴（推播 3 → 2 件/日）→ 推升轉換
- B. Solo 微漲（799 → 899）→ 拉客單價
- C. Annual ×10 → ×9（年付折更多）→ 拉年付率

### Retention 工程（Month 7-9）

- 週推播加「上週看 N 件、開 M 件」mini stats
- 連續 7 天 0 開信 → trigger「需要協助嗎？」
- 月度 email「本月得標統計」
- 「找夥伴」功能（score 60-79）= **Pro 升級鉤子**

---

## 8. Phase 6 — Month 9-12：決策點

### Month 9 健康檢查

| 訊號 | Continue | Pivot | Sunset |
|---|---|---|---|
| MRR | NT$5K+ | NT$1-5K | < NT$1K |
| 付費客戶數 | 8+ | 3-7 | 0-2 |
| 月新付費 | 1-3 | 0-1 | 0 / 3 月 |
| Day 30 retention | > 70% | 50-70% | < 50% |
| 你的精力 | 仍想做 | 累但有信號 | 放棄 |

### Continue Path（>= 4 項綠燈）

- Month 10-12：擴 Pro 功能（得標廠商分析、Calendar、PDF 解析）
- Year 2 Q1：找 part-time partner（業務 / 內容）
- Year 2 Q2：考慮微外部資金 friend round NT$200-500 萬

### Pivot Path

- 候選 1：擴成「補助 + 標案」雙合一（整合 subsidybot）
- 候選 2：B2B → B2B2C 記帳士白標
- 候選 3：橫移醫院 / 學校 / 國營事業採購監控

### Sunset Path

- 公告付費客戶 60 天前
- 退剩餘月份比例款
- Open source codebase → 個人作品集
- 行號保留（可重啟下個專案）

---

## 9. 12 個月一張表

| Month | 法務 / 設施 | 產品 | 內容 | 通路 | 時數重點 |
|---|---|---|---|---|---|
| 1 | 行號 + 域名 + Cloudflare | Sprint 1+2 | 4 篇打底 | — | 70% 規格 |
| 2 | 綠界商家審核完成 | Sprint 3+4 | 4 篇 | 朋友圈試水 | 50/50 |
| 3 | iubenda 法務頁 | Soft launch | 累積 8 + PTT 1 | PTT + FB | 30/70 |
| 4 | — | bug fix + UX 優化 | 累積 12 | Cold DM 5/週 | 20/80 |
| 5 | — | 「找夥伴」初版 | 累積 16 | partner 試水 | 同上 |
| 6 | LINE OA 開 | Pricing review | 累積 20 | DM 累計 100 | 同上 |
| 7-9 | — | Retention 工程 | 累積 32 | 進 SEO 收成期 | 同上 |
| 10-12 | — | Continue / Pivot / Sunset 決策 | 累積 50 | — | — |

---

## 10. 關鍵風險與退場觸發

| 風險 | 觸發 | 行動 |
|---|---|---|
| 政採網 OpenData 格式變更 | 任 1 次抓取連續 24h 失敗 | 切備案 RSS / 爬蟲 |
| 招標王推 AI 競品 | 看到他們發新版 | 砍價或加 LINE Bot 特色 |
| LLM 過度樂觀致誤投 | 第 1 個客訴 | 加 key_gaps 強制顯示 |
| 你寫不出內容 | 連續 4 週 0 篇 | 降 free tier 自動化 = 不再做 SaaS，pivot 顧問 |
| 自然流量 0 | Month 6 GSC 0 indexed | 找朋友審 SEO，1 次性 NT$5K 預算 |
| ICP 假設錯 | Month 3 註冊 < 10 | 找 3 SI 老闆 30 分鐘 face-to-face |

---

## 11. 不要做的事

- ❌ 一開始就辦有限公司（資本額卡死、月維運高）
- ❌ Product Hunt / FB ads / KOL 業配
- ❌ Stripe（要美國公司繞道）
- ❌ Google Analytics（速度差 + cookie 同意彈窗麻煩）
- ❌ 用 email / 密碼 auth（LINE Login 對 TW SMB 最順）
- ❌ 同時動多個 pricing 試驗
- ❌ 提早做 enterprise 客製
- ❌ 半年內亂改價格
- ❌ 文章寫得像 ChatGPT 通稿

---

*由 brainstorming session 在 2026-05-11 與創辦人對齊產出。下一步：依本文件展開 implementation plan（writing-plans skill）。*
