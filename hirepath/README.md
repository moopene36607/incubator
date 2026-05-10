# hirepath(招募路徑)

**台灣 SME 老闆「招專員 vs 外包」12/24/36 個月全週期 ROI 對照 — 純函式精算所有 hidden cost,LLM 評估 4 個 non-cost factors + 給最終決策建議。**

把「**月薪 NT$50K 看起來便宜**」變成「**effective NT$80,811/月 vs 外包 NT$40,800/月,差 50%,但機密性 / 速度 / 品質 3 維度招專員勝**」。

---

## 痛點

5-30 人 SME 老闆每年面臨 **3-5 次「招專員 vs 外包」決策**(行銷 / 設計 / 內容 / 客服 / 業務 / IT 維運...),憑直覺決定常常事後懊悔:

> **「招了一個 Marketing 月薪 5 萬,我以為一年 60 萬就結束了。結果加上勞健保 + 三節 + 年終 + 設備,根本不止。**而且他做 6 個月就走了還要重招,等於那一年我花了 100 萬什麼都沒留下。」 — Dcard 創業板真實貼文

> **「**外包代操**月費 3.5 萬看起來便宜很多,但每週要花 1 小時跟廠商開會 + 廠商**同時做 10 家同行**,我們最大的競爭對手就是他們客戶。」 — PTT Soft_Job

> **「**會計師看「過去 P&L」**不做未來 12-36 個月全週期 ROI 對照**;HR 顧問偏大公司不接 5-30 人 SME。」 — FB 中小企業老闆社群

具體痛點:

- **雇主隱性成本**(健保 5.17% + 勞保 10.5% + 勞退提繳 6% + 三節 + 年終 + 招聘 + 培訓 + 設備)= 月薪 × 1.6-1.8 倍,SME 老闆**常常只算月薪**
- **外包隱性成本**(老闆對接時間 + 廠商切換風險 + 知識遺失)= 月費 × 1.2-1.5 倍,老闆常忽略
- **重招風險**:SME 1 年離職率 25-35%,每次重招成本 = 1-2 月薪 + 招聘廣告,評估期內常發生 1-2 次
- **長期 vs 短期**:1 年 horizon 通常外包贏;5+ 年若內化成本攤平 + 累積 IP / 品牌資產可能反轉
- **non-cost factors**:品質 / 速度 / 機密性 / 規模化能力 — 純數字無法衡量但決策關鍵
- **沒人做這類決策助手**:會計師、HR 顧問、Mercer/KPMG 報告 NT$50K+ 一份;ChatGPT 算不出健保勞保提撥 / 三節獎金 / 重招風險

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **會計師事務所** | 看「過去 P&L」**不做未來 12-36 個月全週期 ROI**;custom analysis NT$5-30 萬 |
| **HR 顧問公司** | 偏服務大公司(50+ 人);SME 客單低不接 |
| **Mercer / KPMG 薪酬報告** | NT$50K+ 一份;研究薪資水準不評估「招 vs 外包」 |
| **ChatGPT / Claude 直接問** | 算不出健保 / 勞保 / 勞退提撥(各 cap 不同);無法評估離職率 / 切換風險 |
| **Excel 自己算** | 雇主健保 cap NT$182K / 勞保 cap NT$45.8K / 勞退 cap NT$150K 各不同,公式繁雜;每年公告值更新麻煩 |
| **104 薪酬數據** | 只給薪資中位數,**不算 effective total cost**;不做外包對照 |

**Gap 結構性**:中小企業每年面臨 3-5 次 hire-vs-outsource 決策,但**沒有任何在地化、輕量、整合「成本 + non-cost factors」的決策工具**。Google「台灣 中小企業 招專員 外包 決策」零中文 SaaS 結果。

## hirepath 在做什麼

```
公司 + role + 兩方案參數 JSON
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compute_hire_total_cost (comparator.py):           │
  │   - base salary × 12 × years                              │
  │   - 雇主健保 5.17% × min(salary, 182K)                    │
  │   - 雇主勞保 10.5% × min(salary, 45.8K)                   │
  │   - 勞退提繳 6% × min(salary, 150K)                       │
  │   - 三節 + 年終 (~月薪 × 2.5/年)                          │
  │   - 招聘 + 培訓 (1.5 月薪)                                │
  │   - 設備 / 工位 (~NT$4K/月)                               │
  │   - 預估重招風險(離職率 × 重招成本)                       │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compute_outsource_total_cost:                      │
  │   - base monthly fee × 12 × years                         │
  │   - 老闆對接機會成本(時數 × 老闆時薪)                     │
  │   - 預估切換廠商風險(年機率 × 切換成本)                   │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 純函式 compare:                                            │
  │   - 較便宜方案 + 差距 NT$ + %                              │
  │   - 月化節省                                               │
  │   - Breakeven horizon(若有)                              │
  │   - qualitative_signals(高薪 / 高 mgmt 時間 / 高離職率)   │
  │ 純函式 horizon_sensitivity:                                │
  │   - 1 / 2 / 3 / 5 年 horizon 各跑一次                      │
  │   - 顯示「短期 vs 長期」是否會 cross-over                  │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude fractional COO 顧問解釋:                           │
  │   - 為什麼月薪 NT$X 變 effective NT$Y(<150 字)             │
  │   - 4 個 non-cost factors 評分(1-5 分):                  │
  │       · 品質控制                                           │
  │       · 速度 / 響應                                         │
  │       · 機密性 / IP                                         │
  │       · 規模化能力                                         │
  │   - 最終建議:招專員 / 外包 / **混合**(短期外包驗證 +     │
  │     長期內化)                                             │
  │   - 決策觸發條件(未來若 X 發生則重新評估)                 │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **數字 100% 純函式**:NHI / LI / 勞退費率 + cap 全在 `comparator.py` 常數區,LLM 永不重算金額。
2. **2 維度評估(cost + non-cost)**:純成本不夠 — 機密性 / 速度 / 規模化能力都會 swing 決策。LLM 角色就是把這 4 個 non-cost factors 給 1-5 分並權衡。
3. **3 個 ending(招專員 / 外包 / 混合)**:很多 case 答案是「**短期外包驗證需求 + 第 13-18 個月內化**」 — 既不純招也不純外包。LLM 必須能識別這種混合策略。

## 動作

### 純函式試算(免 API key)

```bash
python3 hirepath.py samples/profile.json --no-ai --out output.md
```

`samples/profile.json` 是「鼎峰科技 8 人軟體外包公司」考慮招 Marketing 月薪 NT$50K vs 外包代操 NT$35K/月,評估期 2 年。

輸出含:雇用 / 外包成本拆解、純函式對照、1/2/3/5 年敏感度。

### 完整 AI fractional COO 顧問模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 hirepath.py samples/profile.json --out output.md
```

加上 Claude 的 4 維 non-cost evaluation + 最終建議(招 / 外包 / 混合)+ 決策觸發條件。

### 預先產出的 demo

`examples/sample_output.md` 是完整 AI 報告,展示:
- effective NT$80,811/月 vs NT$40,800/月,**外包便宜 50%**
- non-cost: 招專員 16/20 vs 外包 12/20(機密性 + 速度 + 品質贏)
- 最終建議「混合」— Phase 1(0-12 月)外包驗證 + Phase 2(13-18 月)內化
- 5 條決策觸發條件

`examples/sample_output_no_ai.md` 是純函式模式輸出。

## 已驗證 smoke test

- ✅ Cost 隨月薪 monotone(40K < 80K)
- ✅ LI cap NT$45,800 正確生效(月薪 30 萬不會被多算)
- ✅ 外包月費 << 月薪 → 外包較便宜
- ✅ 外包月費 >> 月薪 → 招專員較便宜
- ✅ Horizon sensitivity 列表回傳正確結構
- ✅ Zero salary 邊界案不 crash
- ✅ 高薪 signal trigger(NT$60K+ 月薪)
- ✅ 高 mgmt hours signal trigger(8 hr/月+)
- ✅ 純函式 deterministic
- ✅ 5 年 / 1 年 ratio 在 4-5.5 倍合理區間

## 專案結構

```
hirepath/
├── README.md
├── hirepath.py            # CLI(讀 profile + 純函式試算 + LLM COO 顧問)
├── comparator.py          # 100% 純函式:NHI / LI / 勞退 / hire / outsource / 對照
├── samples/
│   └── profile.json       # 8 人軟體外包公司 Marketing role 招 vs 外包
├── examples/
│   ├── sample_output.md          # AI 完整報告
│   └── sample_output_no_ai.md    # 純函式試算
└── requirements.txt
```

純函式部分零外部依賴(stdlib 只用 dataclass + math)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **公告費率自動更新**:每年 1 月 / 4 月健保 / 勞保 / 勞退費率公告值更新
- **加薪情境模擬**:招專員 12 個月後加薪 5% / 10% 對 2 年總成本的影響
- **多人團隊試算**:不只 1 個 role,而是「招 1 個 senior + 2 個 junior」vs「外包 1 個整套」對比
- **產業 benchmark**:行銷 / 設計 / 工程 / 客服 各產業典型外包 vs 內化 ratio
- **HR 法規警示**:雇用 1 人 SME 不需保勞退;但 5 人以上必須投保
- **LINE Bot**:用 LINE 對話介面引導老闆填參數
- **B2B 會計師 / 顧問 white-label**:會計師事務所幫客戶做決策時用 hirepath 出報告

## 商業模式

| 方案 | 費用 | 對象 |
|------|------|------|
| **Free** | 月 1 次純函式試算(無 AI 建議) | 試用 |
| **Solo** | **NT$299 / 月**(3 次完整 AI 試算 + 比較記錄) | 個人老闆 / 創業者 |
| **Pro** | NT$999 / 月(無限試算 + 多人團隊 + 加薪情境) | 5-30 人 SME |
| **Pay-per-use** | NT$499 / 次 | 不訂閱單次重大決策 |
| **B2B 會計師 / 顧問** | NT$3,999 / 月(white-label + 批量 100 客戶) | 記帳士 / 會計師事務所 |
| **B2B 創投 / FA** | 客製 NT$30K+/月 | 評估 portfolio company HR strategy |

### WTP 計算

- 會計師客製 hire vs outsource 試算 NT$5-30 萬 vs hirepath Pro NT$999 = **5-30x 便宜 + 即時**
- 一個「錯招」帶來的損失(招到不適合 + 6 個月離職 + 失去 6 個月銷售機會) = **NT$50-100 萬**;NT$299 預防即可
- B2B 會計師事務所:每年幫客戶做 50-100 次「招人 vs 外包」討論,Pro NT$999/月 自己手算 50-100 hr × NT$1,500 = **75-150x ROI**

### TAM

- 台灣 SME 約 150 萬家;5-30 人核心約 30 萬家
- 每家每年 3-5 次招募決策 → 100 萬次決策 / 年
- 取 1% 滲透(每年至少 1 次完整試算)= 3,000 家 × NT$999 = **月 NT$300 萬 MRR / 年 NT$3,600 萬 ARR**
- 加 Pay-per-use + B2B 會計師 + 創投 → 年 ARR NT$1-2 億
- 横移日韓港新 SME → 翻倍

## 早期 distribution

1. **PTT Soft_Job / 中小企業板 / Salary** — 痛點來源 + 種子(每週「招還是外包」貼文)
2. **FB 中小企業老闆社群** — 5-10 萬人 SME 老闆集中
3. **記帳士 / 會計師事務所 partner** — white-label 給他們服務 SME 客戶
4. **創業育成中心 / 商總 / 商工會議所**
5. **YouTube 中小企業 KOL** demo case study
6. **LinkedIn 中小企業 HR 同好** B2B 開發
7. **HR 顧問公司 partner** — 大公司導向的 HR 顧問,SME 案件他們接不來可轉介
8. **iCHEF / Cashier integration partner** — 餐飲零售 SME 整合

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **公告費率變動 / 法規修法** | 中 | constants 集中在 comparator.py,每年 1 月 / 4 月可定期更新 |
| **使用者高估離職率 / 低估管理時間** | 中 | UI 提示產業 benchmark;Pro 版自動匹配同產業歷史數據 |
| **HR 顧問 / 會計師反感(搶生意)** | 中 | 走 B2B partner 路線 white-label,反而幫他們做 SME 客戶 |
| **複雜雇用形態(派遣 / 兼職 / 顧問)** | 中 | 第 2 版加 part-time / contractor / consultant 模式 |
| **建議過於 generic** | 中 | LLM 強制引用具體數字 + 提供「混合」第 3 ending |
| **沒考慮稅務 / 補助 / 政府就服津貼** | 中 | Pro 版加企業就服中心津貼、青年就業獎勵金等試算 |
| **個資 / 公司財務隱私** | 高 | stateless API call;profile 不上雲;企業版 self-host LLM |

---

*第二十九輪在 2026-05-10 產出於 incubator(台灣優先,**第十九個 AI 架構模式 — A/B Decision Modeling with Uncertainty Bands**)。跟前 28 輪所有 pattern 都不同架構。*
