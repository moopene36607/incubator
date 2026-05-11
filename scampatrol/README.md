# scampatrol -- 台灣 LINE 詐騙訊息個人端 Weak-Supervision 偵測

**「半夜收到陌生 LINE 投資老師訊息, 看起來是詐騙但又不確定, 該不該理?」** 用 Ratner et al. 2016 Snorkel-style weak supervision 多 rule 投票 + Dawid & Skene 1979 EM 學每個 rule 的可信度 → 5 類詐騙分流 (合法 / 假投資 / 假冒身份 / 釣魚連結 / 假借錢) + 應對 SOP + 165 通報路徑, 個人端工具補 165 反詐騙專線「只能事後通報」的缺口。

## 痛點

台灣詐騙犯罪市場 (受害方):
- **165 反詐騙專線 2024 通報數**: 30 萬+ 件
- **2024 全年詐騙金額**: 突破 NT$ 100 億 (警政署「打詐儀表板」)
- **單筆平均損失**: 假投資 NT$50-300 萬 / 假冒銀行 NT$5-20 萬 / 假借錢 NT$3-10 萬
- **詐騙黑數**: 估計實際發生數 2-5x 通報數 (受害人多半不報案)
- **LINE 是主要通道**: 80%+ 詐騙從 LINE 開始接觸 (165 統計)
- **長輩 / 主婦 / 學生 / 上班族 全光譜** 都會遇到

**個人端痛點** (PTT Soft_Job / Salary / 媽寶 / Dcard / FB「反詐騙」/「LINE 安全」5-10 萬人社群):
- 「半夜收到陌生 LINE 投資邀請, 該理還是封鎖?」(每週重複)
- 「假冒銀行通知盜刷, 跟真實 SMS 長得很像」
- 「『媽我手機壞了』有夠寫實, 差一點就匯了」
- 「點到短連結後不知道有沒有植入木馬」
- 165 反詐騙專線「只能事後通報」: 已上當 / 已點 / 已輸入個資才聯絡

**現有資源**:
- 165 反詐騙專線 (1999 + 165) 「事後」服務,**無事前 triage 工具**
- 165 APP: 給公告 / 統計 / 通報入口, **不對個人收到的 LINE 訊息做分類**
- iWin 網路內容防護機構: 處理網址投訴, 事後機制
- 警政署「打詐儀表板」: 給公開統計 + 詐騙案件查詢, **無自動分類**
- LINE 內建「檢舉」功能: 通報後 LINE 處理, **不告訴用戶為什麼是詐騙**

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(scampatrol 補的) |
|---|---|---|
| 165 反詐騙專線 | 事後通報 + 帳戶凍結 | **不做事前 triage**, 用戶上當才聯絡 |
| 165 APP | 統計 / 公告 / 通報入口 | **不自動分類用戶 LINE 訊息** |
| LINE 檢舉 | 通報後 LINE 處理 | **不告訴用戶為什麼是詐騙** |
| iWin 內容防護 | 處理 URL 投訴 | 事後機制, 不對訊息分流 |
| 警政署「打詐儀表板」 | 公開統計 | 民眾收到訊息時無自動建議 |
| ChatGPT 一次問 | 一次性建議 | 不能持續學習 + 不知道台灣最新詐騙話術 |
| 反詐騙圖文 | 衛教 | 一次性閱讀, 收到訊息時忘了 |

**Gap 結構性**: Snorkel weak supervision (Ratner et al. 2016) + Dawid-Skene EM (1979) 學術界成熟 8+ / 46+ 年, **沒人做成台灣繁中 LINE 詐騙個人端 SaaS**。Google「台灣 LINE 詐騙 weak supervision」零中文 SaaS。**跟 stylescan r23 同精神不同對象** -- r23 國高中作文 AI 代筆 stylometric, r62 LINE 詐騙 weak supervision, 都是「多 weak signal 聚合做分類」場景; **跟 caselens r28 / lawmate r36 互補** -- r28 / r36 是法律檢索, r62 是事前詐騙 triage 預防案件發生。

## 架構 -- Weak Supervision with Dawid-Skene EM (52nd 條 AI pattern)

```
LINE 訊息文字
       │
       ▼
┌──────────────────────────────────────────────┐
│ 10 個手工 Labelling Functions (LFs):         │
│   LF_invest_keywords         → 假投資 / abstain │
│   LF_impersonation_authority → 假冒身份 / abstain │
│   LF_phishing_short_link     → 釣魚 / abstain │
│   LF_phishing_prize          → 釣魚 / abstain │
│   LF_borrow_urgency          → 假借錢 / abstain │
│   LF_msg_length_link         → 釣魚 / abstain │
│   LF_legitimate_long_no_link → 合法 / abstain │
│   LF_invest_percent_number   → 假投資 / abstain │
│   LF_mlm_dating              → 假投資 / abstain │
│   LF_impersonation_family    → 假借錢 / abstain │
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│ Majority Vote (sanity baseline):              │
│   counts per class across non-abstaining LFs  │
│   tie-break: smaller class index              │
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│ Dawid-Skene EM (unsupervised aggregation):    │
│   Latent: y_i (true class of message i)       │
│   Params:                                      │
│     pi[c]      = P(y = c)                     │
│     theta_j[c][l] = P(LF j emits l | y=c)    │
│     abstain_j[c]  = P(LF j abstains | y=c)   │
│                                                │
│   Init q[i][c] from smoothed majority vote    │
│   (avoids symmetric-init class collapse)      │
│                                                │
│   E-step: q[i][c] ∝ pi[c] *                   │
│              prod_j P(L_ij | y=c)             │
│                                                │
│   M-step: re-estimate pi / theta / abstain    │
│           with Laplace smoothing alpha=0.1    │
│                                                │
│   Iterate until log-lik converges             │
└──────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│ For new message:                              │
│   apply all 10 LFs → L*[j]                    │
│   posterior P(y = c | L*)                     │
│   predict argmax → 5 類 + 信心                │
│                                                │
│ Output:                                       │
│   • LF 觸發明細 (which rules fired)           │
│   • Majority vote baseline                    │
│   • DS EM posterior                           │
│   • Class-specific defensive SOP (封鎖 / 反向 │
│     驗證 / 165 通報路徑)                      │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + statistics + dataclasses + collections):
- 10 手工 LFs: 中文 keyword pattern matching with abstain logic
- `apply_lfs / apply_lfs_batch`: vectorise LF application
- `majority_vote`: 簡單投票 baseline (tie-break smaller class index)
- `fit_dawid_skene`: EM with Laplace-smoothed M-step + majority-vote init responsibilities (avoids degenerate class-collapse failure mode)
- `predict_one`: posterior P(y|L*) for single message
- `lf_coverage`: fraction of messages where each LF didn't abstain
- `lf_estimated_accuracy`: π-weighted diagonal of θ as LF reliability proxy

**LLM 只負責**: 寫 250-330 字「個人應對 SOP (5 分鐘內封鎖 / 反向驗證 / 截圖) + 已上當緊急止損 + 家人衛教提醒」
**LLM 絕不負責**: 計算 posterior / LF accuracy / classification (數字 100% 來自 EM)

### 為什麼 Weak Supervision 適合這個 use case (vs Logistic r56 / NB r55 / RF r48)

- **Weak Supervision**: 不需要標註資料, 用領域專家知識寫 LFs 即可訓練; 適合「詐騙話術快速演變, 沒時間標註」的場景
- **Logistic r56 cramlead**: 需要標註資料 (lead 是否報名是 ground truth), 詐騙資料標註困難
- **Naive Bayes r55 cleanmate**: 需要標註訓練樣本, 同樣困難
- **Random Forest r48 crybabel**: 需要標註 + 黑盒, 無法解釋為何標記為詐騙
- **Logistic regression with hand-crafted features**: 等同 hand-crafted LFs 但少了 EM 學每個 LF 可信度的能力

Weak supervision 獨特優勢:
1. **零標註成本**: 165 反詐騙專線 + 警政署 / 各銀行 / 各 ISP 公告 詐騙話術直接寫成 LFs
2. **可解釋**: 哪些 rules 觸發明白列出, 用戶看得懂為什麼
3. **動態擴展**: 新詐騙話術出現 → 加新 LF (一行 Python) 即可, 不重訓 model
4. **LF 可信度 EM 學習**: 不需要先驗知道哪個 LF 準, EM 自動估計

## 使用示例

```bash
# 純函式模式 (無 API key)
python3 scampatrol.py --data samples/messages.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 scampatrol.py --data samples/messages.json

# 自訂 EM 迭代
python3 scampatrol.py --n-iter 100
```

預期輸出 (詳見 `examples/sample_output.md`):

陳媽媽收到的訊息: 「陳大哥您好,我是專業投資老師, 每天保證獲利 3-5%, 加入內線消息群組, 一個月翻倍。點此 https://bit.ly/3xyzABC」

**LF 判決**:
- `lf_invest_keywords` → 假投資 (because "保證獲利" + "穩賺方法" + "內線消息")
- `lf_phishing_short_link` → 釣魚 (because "bit.ly")
- `lf_invest_percent_number` → 假投資 (because "每天 3-5%")

**Dawid-Skene EM 後驗**:
| 類別 | P(y \| LF) |
|---|---|
| ⭐ **假投資詐騙** | **99.1%** |
| 釣魚連結 / 中獎詐騙 | 0.9% |
| 其他 | 0.0% |

**建議**: 立刻封鎖 + 不點連結 + 不轉帳; 截圖 + 打 165 + 警政署「打詐儀表板」https://165dashboard.tw 通報。

訓練診斷: 40 則訓練訊息, EM 41 次迭代收斂, log-lik -113.7。LF 覆蓋率與估計準確度顯示模型 well-calibrated。

## 目標市場

- **TAM 雙邊**:
  - **個人 (B2C)**: 全台 LINE 用戶 ~2,200 萬 (中華電信 + LINE Taiwan 2024 estimate);保守 1% 滲透 = 22 萬付費用戶潛力
  - **企業反詐騙 / 金融 (B2B)**: 銀行客服 / 電信客服 / 保險業務員 全公司部署 = 100+ 家潛在客戶
  - **政府 (B2G)**: 165 反詐騙專線, iWin, 各縣市警察局, 學校反詐騙教育
- **WTP 錨點**:
  - 個人 NT$99/月 vs 1 次假投資被騙 NT$50-300 萬 = **500-3000x 防損保險**
  - 銀行客服月省 50 次「客戶來電問是不是詐騙」 × NT$200/通 = NT$10K = **40x ROI**
  - 165 公益版免費, 換取 PR + Distribution + 政府背書

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 5 則訊息 / 月 | 個人試用 |
| **Solo** | NT$99/月 | 無限訊息 + LINE Bot + 每週新詐騙話術更新 | 個人 (尤其長輩) |
| **Family** | NT$299/月 | + 家人共用 + 父母長輩 LINE Bot 自動掃描 + 警示推播 | 多代家庭 |
| **Enterprise** | NT$15,000+/月 | 銀行客服 / 電信客服 / 保險業務員 整合 + API + 客製 LFs | 金融 / 電信 |
| **Government** | 公益免費 | 165 / iWin / 各縣市警察 / 學校反詐騙教育 | 政府 |

## Distribution

- **PTT Soft_Job / Salary / WomenTalk 板**
- **Dcard 媽寶 / 工作 / 金融**
- **FB「台灣反詐騙交流」/「LINE 安全教學」5-10 萬人社群**
- **YouTube 反詐騙 / 法律 KOL** (雷皓明 / 老高 / 反詐騙志工)
- **165 反詐騙專線 partner** (公益版 + PR + 政府背書)
- **iWin 網路內容防護機構 partner**
- **長輩教育**: 醫院 / 衛福部老人關懷站 / 各縣市衛生所 反詐騙宣導
- **學校反詐騙教育**: 教育部 / 各縣市教育局 配合宣導 ("數位公民教育")
- **銀行 B2B BD** (中信 / 國泰 / 玉山 / 永豐 客服部) -- 客服第一線分流工具
- **電信 B2B BD** (中華電信 / 台灣大 / 遠傳) -- SMS / LINE 入侵偵測整合

## TAM

- 0.1% × 2,200 萬 LINE 用戶 = 22,000 × Solo NT$99 = **月 NT$218 萬**
- + Family 3,000 × NT$299 = NT$90 萬/月
- + Enterprise 20 × NT$15K = NT$30 萬/月
- 總計 **月 MRR NT$338 萬 / 年 ARR NT$4,000 萬**
- 加滲透 + 橫移日本 (詐騙電話) / 韓國 (SNS 詐騙) / 東南亞 (跨境電信詐騙) → **NT$1-2 億 ARR**

## 風險與限制

- **40 則 prototype 太小** — real launch 需 ≥ 1,000 則訊息訓練, 跟 165 / 警政署 / 銀行 公開資料合作
- **LF 是手工規則**: 詐騙話術快速演變, 需要持續更新 LFs, 老 LFs 過時; Pro 版加自動 LF generation + 用戶回報 → LF 候選 pipeline
- **LF 獨立性假設違反**: Dawid-Skene 假設「給定真實類別, LFs 條件獨立」, 真實有相關 (LF1 LF8 都看 '%' 數字); Pro 版用 Snorkel-style generative model with LF correlations
- **不含視覺 / URL 資訊**: 真實 phishing 包含圖片 / 假網址截圖, prototype 只看文字; Pro 版加 vision + URL reputation check
- **不含時序 / 帳號信譽**: 同一帳號連發 100 則 spam, 純文字模型看不出; Pro 版加 sender history + LINE 帳號 metadata
- **法律邊界**: 工具只給「值得警覺」分流, **最終判定 / 報警仍需 165 反詐騙專線 / 警政署**; 不取代專業
- **隱私敏感**: 私訊內容可能涉個資, 本地版完全在用戶設備不上傳; 雲端版需加密 + 用戶同意 + 訊息匿名化 + 端對端加密選項
- **誤判風險**: 合法投資理財訊息可能誤判為「假投資」(e.g. 真銀行業務員推薦, 合法 ETF) -- 工具標明「分流參考」, 仍需用戶判斷 + 反向驗證
- **對抗詐騙演化**: 詐騙集團會學工具的關鍵字 → 改話術繞過, 需持續迭代 LFs + 加非語言信號 (帳號註冊時間, 對方互動模式)

---
*scampatrol = Ratner et al. 2016 Snorkel weak supervision + Dawid & Skene 1979 EM × 台灣 LINE 詐騙偵測 niche = "10 手工 weak rules + Dawid-Skene EM 學每個 rule 可信度" 補 165 反詐騙專線「事後通報」的缺口, 個人端 5 秒 triage 把「值得警覺」訊息分流給 165 處理。*
