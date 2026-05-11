# groupbuzz — 台灣 LINE 群組 / 社群成員 PageRank 影響力排行 + 沈默召回工具

**「我經營這個 100 人 LINE 群已經 8 個月,但不知道哪些成員影響力最大、哪些人快流失」** 用 Brin & Page (1998) PageRank 從 reply / mention / reaction 構成 directed graph 算 stationary distribution → 找出 top influencers + 識別 lurker → AI 寫「利用 top 3 + 救活沈默成員」具體腳本。

## 痛點

台灣 LINE 群組生態:
- **團媽 / 團爸**: 40-100 萬人活躍管理 2-10 個團購群 (每群 50-500 成員)
- **行銷社群經營者 / FB 社團主**: 20-30 萬人經營興趣群 (寵物 / 育兒 / 運動 / 學習)
- **企業內部 LINE 群**: 中小企業 ~30 萬個 active group (HR / 工作協作)
- **總計 ~100 萬+ active group admins**

**核心痛點** (PTT WomenTalk / Dcard 媽媽版 / FB「團媽交流」5-10 萬人社群):
- 「群組 200 人但只有 20 人有在發言, 80% 是 ghost member」(每週問)
- 「我想推新團, 不知道該先私訊誰 (high-influence members)」
- 「新加入 5 個成員過去 2 週都沒講話, 是不是準備退群?」
- 「成員 A 訊息很多但是沒人回, 是 spammer 還是邊緣人?」
- 「LINE 後台只給總訊息數 — 不分析誰影響力大」

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(groupbuzz 補的) |
|---|---|---|
| LINE 群組原生 | 訊息 / 通知 | 不做成員影響力分析 |
| LINE@ 商家帳號 | broadcast + 數據 | 只給 LINE@ 訊息送達率, 不分析 group 內社交動態 |
| Slack Analytics / Discord bots | 英文 / 工作群為主 | 不認識台灣團媽文化 + LINE 沒類似 bot 接口 |
| 自己用 Excel 標註 | 純手動 | 100 人 × 200 訊息 → 主觀記錯 |
| ChatGPT 一次貼 | 一次性回答 | 不能跑 PageRank power iteration |

**Gap 結構性**: PageRank (Brin & Page 1998) 學術成熟 27 年,**沒人做成台灣 LINE 群組 admin 可用 SaaS**。Google「LINE 群組 PageRank 影響力」零中文 SaaS 結果。

## 架構 — PageRank Power Iteration (40th 條 AI pattern)

```
Messages (reply / mention / reactions)
                │
                ▼
┌──────────────────────────────────────────┐
│ 1. Build directed graph                   │
│    Edge i → j when i replies to / mentions│
│    / reacts to j's message                │
│    Weight: reply 1.0 / mention 0.7 /      │
│           reaction 0.3                    │
└──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│ 2. Power iteration:                       │
│    Init: pr[i] = 1/n                      │
│    Repeat:                                │
│      new_pr[j] = (1-d)/n + dangling_pr/n │
│                + d × Σ_{i→j} pr[i] × w/W │
│    Until ‖new_pr - pr‖_∞ < 1e-6           │
│    Handle dangling (no out-edge) nodes    │
└──────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│ 3. Per-member stats:                      │
│    PR, in_weight, out_weight, msg_count   │
│    Role: core_influencer / connector /    │
│          active / regular / silent / lurker│
└──────────────────────────────────────────┘
                │
                ▼
       Group health: PR concentration,
       activity skew, lurker rate
```

**100% 純函式 stdlib** (math + collections + dataclass):
- `build_influence_graph`: reply (1.0) + mention (0.7) + reaction (0.3) → directed edges
- `pagerank`: power iteration with dangling node handling + convergence check
- `degree_centrality`: in_weight + out_weight per node
- `classify_role`: 6-class heuristic (core_influencer / connector / active / regular / silent / lurker)
- `compute_member_stats`: aggregate per-member metrics
- `compute_group_health`: top-5 PR concentration, activity_skew (80/20 measure), lurker rate

**LLM 只負責**: 寫 250-320 字「利用 top 3 + 救活沈默成員具體腳本 + 風險」
**LLM 絕不負責**: 計算 PageRank / centrality / role classification (數字 100% 來自純函式)

## 使用示例

```bash
# 純函式模式 (無 API key)
python groupbuzz.py --group samples/group_messages.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python groupbuzz.py --group samples/group_messages.json

# 自訂 damping factor
python groupbuzz.py --damping 0.9
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (中和媽咪愛買團 50 人 LINE 團購群 / 7 天 181 訊息):

| # | 成員 | PageRank | 角色 | 訊息數 |
|---|---|---|---|---|
| 1 | 阿美團媽 | **0.4260** | ⭐ 核心影響者 | 9 |
| 2 | 麗華團長 | **0.3391** | ⭐ 核心影響者 | 9 |
| 3 | 美月學姐 | **0.0890** | 🔗 連接者 | 10 |

**群組健康度**:Top 5 PR 集中度 **86%** (🔴 過度集中), 潛水率 6% (OK), activity_skew 40.3% (中等)。

3 名「新加入 1-3」7 天 0 訊息 → 潛水召回候選。

## 目標市場

- **TAM**:
  - 團媽 / 團爸 active managers ~40-100 萬人 (2-10 群/人)
  - FB 社團主 / 興趣群管理者 ~20-30 萬
  - SME 內部 LINE 群 admin ~30 萬
  - **總計 ~100 萬+ active group admins**
- **WTP 錨點**:
  - 一次成功推新團多賺 NT$3-15K (受 influencer 帶動)
  - LINE@ 月費 NT$500-3,000, groupbuzz Solo NT$199 = **2.5-15x 便宜 + 補後台缺口**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 1 群 + Top 5 影響力 | 試用 |
| **Solo** | NT$199/月 | 3 群 + Top 20 + 月度報告 + LINE 推播 | 個人團媽 |
| **Pro** | NT$499/月 | 10 群 + sentiment-aware + 時間衰減 + API | 多群媽媽 / 大型團媽 |
| **Studio** | NT$1,999/月 | 50 群 + 多管理員 + 跨群比較 | 行銷代理 / 中型 KOL |
| **Enterprise** | NT$8,000+/月 | 企業內部 LINE 群 + EHR / Slack API | 中大型企業 HR |

## Distribution

- **FB「團媽交流」5-10 萬人社群** SEO + 案例分享
- **PTT WomenTalk / Salary / Salary** 板長尾關鍵字
- **Dcard 媽媽 / 創業 / 工作版**
- **YouTube 團媽 / KOL 經營 KOL** (Wendy 阿姨 / 神老師 / 親子作家) 案例
- **行銷代理 / SOHO 創業課程** B2B BD
- **LINE@ 認證合作伙伴**(若可申請)
- **PMA / WeShare / Facebook for Business** 整合 partner

## TAM

- 1% × 100 萬 = 10,000 × NT$199 = **月 MRR NT$200 萬**
- + Pro 1,000 × NT$499 = NT$50 萬/月
- + Studio 200 × NT$1,999 = NT$40 萬/月
- + Enterprise 50 × NT$8K = NT$40 萬/月
- 總計 **月 MRR NT$330 萬 / 年 ARR NT$4,000 萬**
- 加滲透 + 橫移港新馬 LINE 用戶 + 東南亞 WhatsApp / Telegram → 翻倍至 **NT$8,000 萬-1 億 ARR**

## 風險與限制

- **LINE 沒提供 official 訊息 dump** — 真實 launch 需要用戶手動截圖 + OCR 或第三方 export 工具,**有 ToS 風險**;Pro 版改用 LINE@ 商家後台 API (用戶轉 LINE@ 才能用)
- **隱私敏感** — 訊息含個資,UI 必須**透明告知 + 群主同意 + 預設 anonymize 成員姓名**
- **Mention 可能是 spam, reply 可能是 sarcasm** — Pro 版加 sentiment-aware weighting
- **時間衰減未處理** — Pro 版加 exponential time decay (半年前 reply 權重 0.3)
- **群組規模**: 50 人 OK, 500+ 人需 sparse matrix 優化, 1000+ 需 distributed power iteration
- **不取代社群經營經驗** — PageRank 給訊號, 但群組氣氛 / 個別成員心理需要人類經營者判斷

---
*groupbuzz = Brin & Page 1998 PageRank × 台灣 LINE 群組管理 niche = 從 200 條訊息 5 秒找出 top 5 influencers + 沈默成員召回名單 + 健康度警示。*
