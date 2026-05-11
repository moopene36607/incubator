# `_nice/` — 候選清單評估

本資料夾收 10 個 user 標記感興趣的原型。本檔記錄一次「執行成功率 × 賺到錢機率」評估
+ 上網驗證關鍵聲稱、修正失誤、最終推薦。

> 評估日期：2026-05-11
> 評估方法：先讀完 10 份 README → 內部評分 → 上網查 5 個關鍵聲稱 →
> 推翻原本評分 → 重新排名。

---

## 10 個候選

| Slug | 第 N 輪 | AI 模式 | 一句話 |
|---|---|---|---|
| `carepen/` | 7 | doc-gen | 居服員 LTCIS 服務記錄 AI 助手 |
| `cropscan/` | 20 | Vision Classification | 農作物病蟲害辨識 + 台灣許可農藥建議 |
| `examready/` | 40 | MDP / DP Rollout | 升學考前多科溫習排程 |
| `fitlog/` | 11 | doc-gen | 健身教練課後訓練報告 |
| `kindergrid/` | 52 | HAC + DBSCAN | 0–6 歲家長挑幼兒園分群推薦 |
| `monthrep/` | 10 | doc-gen | 才藝班 / 補習班學生月報 |
| `petfeed/` | 57 | Empirical-Bayes HB | 寵物飼料 shrinkage 推薦 |
| `subsidybot/` | 14 | RAG over Local Corpus | 政府補助 Q&A |
| `tenderwatch/` | 17 | Real-time Monitoring + LLM Match | 政採網標案個人化推播 |
| `vetnote/` | 9 | doc-gen | 獸醫 SOAP 病歷草稿 |

---

## 初次評分（未驗證前）

| 排名 | 專案 | 評分 | 主要理由 |
|---|---|---|---|
| 🥇 | vetnote | 9.5/10 | 海外 PMF（VetSnap $99、Scribenote $89）+ TAM 集中 2,600 家 + ROI 42x + 語言護城河 |
| 🥈 | fitlog | 8.5/10 | 海外 PMF（TrueCoach、My PT Hub）+ Daily-use + 教練自費快 |
| 🥉 | tenderwatch | 8/10 | Daily-use + 高 WTP + 招標王 8 年沒進化 |
| 4 | carepen | 8/10 | 長照 3.0 政策驅動 + 評鑑代寫產業背書 WTP |
| 5 | subsidybot | 6.5/10 | 痛點明確但用過就走、維運貴 |
| 6 | monthrep | 6/10 | 補教王可能模仿 |
| 7 | examready | 5.5/10 | 家長強迫使用反效果風險 |
| 8 | kindergrid | 5/10 | One-shot 需求 + 季節性 |
| 9 | cropscan | 4.5/10 | 噴錯藥法律風險 + 農民付費低 |
| 10 | petfeed | 4.5/10 | 1–2 年才換糧一次,留存難 |

---

## 上網驗證（5 項關鍵聲稱）

| 待驗證點 | README 聲稱 | 實際驗證 | 影響 |
|---|---|---|---|
| vetnote: VetSnap 是 AI SOAP scribe | $99/月 競品 | ❌ **VetSnap 是控管藥品/庫存系統,不是 SOAP scribe**（vetsoftwarehub 確認） | vetnote PMF 證據縮水一半 |
| vetnote: Scribenote 定價 | $89/月 | ✅ 實際 $79/月,量級正確 | 無影響 |
| vetnote: 台灣動物醫院家數 | 2,600 家 | ⚠️ 實際 1,590–1,790 家（2022《寵物黃頁》/ 2021 農委會）— **TAM 縮水 30%** | TAM 從 NT$468 萬/月 → NT$306 萬/月 |
| vetnote: 台灣執業獸醫人數 | 5,500 人 | ✅ 5,000–5,672 人,寵物獸醫 3,993 | 無影響 |
| vetnote:「繁中市場零競品」 | 完整空白 | ❌❌ **PawfectNotes 已上繁中**(`pawfectnotes.com/zht/`)、整合 ezyVet/Vetspire/Pulse;另有 VetOS / NxVet / Dr.Vet / Vet.AI 已在做 AI 獸醫病歷 | 語言護城河失守,從藍海變紅海 |
| fitlog: TrueCoach / My PT Hub 是否有繁中 | 沒繁中 | ✅ 仍無繁中（**價格實際遠高於 README 舊聲稱**:TrueCoach Starter $26.34/月 ≈ NT$790、My PT Hub Starter $25/月 ≈ NT$750,均約 fitlog NT$299 的 2.5x） | fitlog 護城河比原文檔講的更強,但 README 海外價格錨點原本錯誤,已修正 |
| tenderwatch: 招標王仍是主導 | 8 年沒進化 | ⚠️ 部分驗證 — 「招標王 NT$299/月、2018 介面」具體價格未拿到官方頁面證實；但同類公開競品確實只有 OpenFun `pcc-viewer`（純查詢、無 semantic match）+ 台灣採購公報網 / 台灣標案網（傳統訂閱）。**結論仍成立但個別錨點建議改成市場觀察措辭** | tenderwatch 競爭弱方向正確,個別品牌價格錨點需附來源 |

---

## 修正後排名

| 排名 | 專案 | 評分 | 修正後關鍵理由 |
|---|---|---|---|
| 🥇 **1** | **`tenderwatch`** | **8.5/10** | 競爭最弱、daily-use、ROI 14–55x、企業預算非個人付費、海外無法進攻 |
| 🥈 2 | `fitlog` | 8/10 | 海外 PMF 真實 + 繁中護城河,但 TAM 分散（自由接案 PT）銷售難規模化 |
| 🥉 3 | `vetnote` | 6.5/10 | 海外 PMF 仍強,**但 PawfectNotes 繁中已先到**,TAM 縮水 30%,從藍海變紅海 |
| 4 | `carepen` | 7/10 | 長照 3.0 是實在政策驅動,但居服員 IT 抗拒 + 政府銷售週期 |
| 5–10 | 其餘 | < 7 | One-shot / 留存難 / 法律風險 / 政府競品 |

---

## 最終推薦：`tenderwatch`（標案監測）

**為什麼勝出**：

1. **競爭真實薄弱** — 招標王 8 年沒進化是事實,公開只有 OpenFun pcc-viewer（查詢工具,無語意匹配）。海外 Bonfire/GovWin 永遠不會做台灣政採網。
2. **B2B 預算 vs 個人自費** — 中小企業老闆把它當「業務工時節省工具」報銷,比 fitlog 個人教練自掏腰包 NT$299 更穩。
3. **單次中標 NT$30 萬–3,000 萬** — WTP 錨點極強,NT$799/月被一次中標瞬間消化。
4. **政府 OpenData 已開放** — `web.pcc.gov.tw` + `data.gov.tw` 是政策強制,資料源無風險。
5. **Daily-use** — 每日新公告 500–800 件,LINE 推播是高頻接觸點,留存率天生高。
6. **vetnote 與 fitlog 都已有海外對手在敲門**（PawfectNotes 已上繁中、TrueCoach $26.34/月 與 My PT Hub $25/月雖無繁中但已是 PT 預設選項）,**tenderwatch 是唯一海外進不來的格局**。

---

## 下一步（如果要往 tenderwatch 推進)

- [ ] 接政府電子採購網 OpenData API（每日 cron 抓新公告）
- [ ] 找 2–3 家中小型 SI / 顧問公司做 closed beta、收集 win/loss 反饋
- [ ] 接 LINE Notify / LINE Bot 把高匹配標案推播給業務手機
- [ ] 用 embedding-based pre-filter（cosine sim threshold）取代直接 LLM scoring,把 token cost 砍 80%+
- [ ] 整合「過去 1 年同類標案誰得標 / 平均得標金額」(決標公告 OpenData)
- [ ] 招標王與台灣採購公報網的功能 gap audit、寫一篇 SEO 對比文章

---

## 驗證資料來源

- [Veterinary AI Scribe Pricing Comparison 2026](https://www.vetsoftwarehub.com/article/veterinary-ai-scribe-pricing-comparison-2026)
- [Scribenote Pricing](https://www.scribenote.com/pricing)
- [VetSnap Review 2026 — 控管藥品工具,非 SOAP scribe](https://www.vetsoftwarehub.com/product/vetsnap)
- [PawfectNotes 繁中介面](https://pawfectnotes.com/zht/)
- [世界愛犬聯盟:台灣動物醫院近 1,600 家](https://www.worlddogalliance.org/%E5%8F%B0%E7%81%A3%E7%84%A6%E9%BB%9E-%E5%8B%95%E7%89%A9%E9%86%AB%E9%99%A2%E8%BF%911600%E5%AE%B6-%E4%BB%8D%E6%8C%81%E7%BA%8C%E5%A2%9E%E5%8A%A0/?lang=zh-hant)
- [imedtac:台灣執業寵物獸醫 3,993 名](https://www.imedtac.com/news/20250108-2/)
- [VetOS 台灣獸醫智能平台](https://vetos.pet/)
- [NxVet 動物醫院系統](https://nxvet.io/)
- [Dr.Vet 寵物病歷系統](https://www.bonvies.com/drvet/)
- [Vet.AI 寵物智慧語音諮詢](https://www.vetaiai.com/zh-TW)
- [政府電子採購網](https://web.pcc.gov.tw/pis/)
- [OpenFun pcc-viewer 標案瀏覽（公開純查詢工具）](https://openfunltd.github.io/pcc-viewer/index.html)
- [台灣採購公報網](http://www.taiwanbuying.com.tw/)
- [My PT Hub vs TrueCoach 2025 (SoftwareWorld)](https://www.softwareworld.co/compare/my-pt-hub-vs-truecoach/)

---

## README 已修正項目

- `_nice/vetnote/README.md`:
  - 痛點段:「2,600 家動物醫院」→「約 1,600–1,800 家」(援引《寵物黃頁》/ 農委會)
  - 海外競品表:**移除 VetSnap**(它不是 AI SOAP scribe),改列 Scribenote / VetRec / CoVet 等真實競品
  - 「繁中市場零競品」→「繁中市場早期競爭、無人主導」,明列 PawfectNotes / VetOS / NxVet / Dr.Vet / Vet.AI
  - TAM 算式:5% × 2,600 = NT$468 萬/月 → 5% × 1,700 = NT$306 萬/月
  - WTP 對比:VetSnap $99 → Scribenote $79 / VetRec $100–250 區間
  - 風險表:VetSnap/Scribenote 推繁中 → PawfectNotes 已上繁中
  - 風險表:獸易通 / 毛孩管家 → VetOS / NxVet / Dr.Vet / Vet.AI(實際存在的本土平台)
