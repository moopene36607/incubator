# clinicqueue — 台灣自費診所預約 No-Show 預測 (Gradient Boosting)

**「我這家自費牙科 / 醫美 / 中醫 每月 no-show rate 30%+, 醫師空班 2 小時就少賺 NT$10K — 哪些病患該優先打電話確認?」** 用 Friedman (2001) Gradient Boosting Decision Trees 從歷史 200 件 appointment 學 no-show pattern, 對未來 appt 預測 P(no-show) → 高風險雙重預約 + 個人化 LINE 提醒 + 候補名單 SOP。

## 痛點

台灣自費 / 部分自費醫療市場:
- **醫美診所**: ~2,500 家 (台北 / 高雄 / 台中集中)
- **自費牙科 / 牙醫**: ~3,500 家
- **中醫診所**: ~3,500 家
- **物理治療 / 復健**: ~2,000 家
- **心理諮商 / 健身教練**: ~3,000+ 家
- **共 ~15,000 家** 高 no-show 風險預約服務業

**Core pain** (PTT pharmacy / Salary / Soft_Job / FB 診所經營者 / Dcard 牙醫護理師版):
- **No-show rate 15-35%**, 醫美 / 牙科自費療程尤其高 (病患預約後反悔 / 比價 / 找其他醫師)
- **損失估算**: 1 個 60 分 no-show = 醫師空班 + 助理空班 + 房租水電 = NT$3-8K (高端醫美可達 NT$10-30K)
- **店家沒系統化分析 + 高風險病患沒個人化提醒**:
  - 30% 診所只用「自動簡訊提醒」一視同仁,效果差
  - 50% 完全沒提醒
  - 20% 用 LINE@ 但沒區分 high/low risk
- **醫師時間有限**: 自費名醫 1 小時 NT$5-15K opportunity cost, no-show 直接損失

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(clinicqueue 補的) |
|---|---|---|
| 診所管理系統 (PTC / SimplyClinic / 久興) | 預約 / 收費 / 病歷 | 不做 no-show 預測, 不分風險 |
| LINE@ 商家提醒 | 自動 broadcast | 一視同仁 → 高風險 ignore, 低風險騷擾 |
| 預收訂金系統 | 收款 | 不個人化 + 不知道對誰收 |
| Excel 自己追 | 純手動 | 沒 GBDT, 200 件主觀記錯 |
| ChatGPT 一次問 | 一次性建議 | 不能跑 GBDT, 沒持續學模式 |

**Gap 結構性**: GBDT (Friedman 2001) 學術 + 工業界成熟 24 年,XGBoost / LightGBM 隨處可用,**但沒人做成台灣自費診所運營 SaaS**。Google「自費診所 no-show 預測 中文」零本土 SaaS。

## 架構 — Gradient Boosting Decision Trees (43rd 條 AI pattern)

```
Historical 200 appointments (features + no_show label)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Initialize:                                   │
│   F_0(x) = log(p / (1-p)) where p = mean(y)  │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ For m in 1..M (50 trees):                     │
│   r_i = y_i - sigmoid(F_{m-1}(x_i))           │
│   h_m = fit_regression_tree(X, r, max_depth=3)│
│   F_m = F_{m-1} + lr × h_m                    │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Predict: sigmoid(F_M(x))                      │
└──────────────────────────────────────────────┘
                  │
                  ▼
   Per-feature importance via gain summation
   + 4-tier severity (高/中高/中/低)
   + 4-tier action recommendation
```

**100% 純函式 stdlib** (math + random + dataclass):
- `RegressionTree`: CART regression tree with variance-reduction splits
- `find_best_split_reg`: random feature subset × midpoint thresholds → max gain
- `build_regression_tree`: recursive, max_depth + min_samples_split bound
- `fit_gbdt`: logistic-loss boosting with negative-gradient residuals
- `predict_proba`: F = F_0 + Σ lr × tree(x), sigmoid
- `feature_importance_gain`: sum gain per feature across all trees
- `log_loss / accuracy / auc_roc_approx`: in-sample metrics

**LLM 只負責**: 寫 250-330 字「運營建議 + 流程改造 + 行動分配 + 風險」
**LLM 絕不負責**: 計算 P(no-show) / log_loss / AUC / feature_importance (數字 100% 來自 GBDT)

## 使用示例

```bash
# 純函式模式 (無 API key)
python clinicqueue.py --data samples/clinic_appointments.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python clinicqueue.py --data samples/clinic_appointments.json

# 自訂 hyperparams
python clinicqueue.py --trees 100 --max-depth 4 --lr 0.05
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (好牙好醫 中山自費牙科, 200 件歷史 no-show rate 34.5%, 20 件 upcoming):

| 指標 | 值 | 解讀 |
|---|---|---|
| Accuracy (in-sample) | 80.5% | Good |
| AUC | **0.959** | Excellent |
| Top feature | 歷史失約次數 (37%) | 強信號 |

**Top 3 high-risk upcoming**:
1. A1006 (3x 失約史, 28d 預約, 60% 雨) **P=59.6%** 🟠
2. A1003 (3x 失約史, 1d 預約, 52% 雨) **P=55.0%** 🟠
3. A1010 (新病患, 8AM 早班, 23% 雨) **P=40.0%** 🟡

→ 20 件中 2 件高/中高 + 13 件中 + 5 件低,**雙重預約 + 個人化 LINE + 訂金政策** 可降 no-show 50%。

## 目標市場

- **TAM**:
  - 醫美 ~2,500 + 自費牙科 ~3,500 + 中醫 ~3,500 + PT ~2,000 + 諮商/健身 ~3,000 = **~15,000 家**
  - + 美髮 / 美甲 / 美容沙龍 高 no-show 服務業 +10,000 家可橫移
- **WTP 錨點**:
  - 1 個 no-show 損失 NT$3-30K, 月 10-20 件 no-show = 月損 NT$30K-600K
  - Solo NT$499/月 vs 月省 NT$10-50K = **20-100x ROI**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 50 件歷史 + 5 個預測 | 試用 |
| **Solo** | NT$499/月 | 無限件 + LINE 提醒模板 + dashboard | 個人診所 |
| **Pro** | NT$1,499/月 | + 預收訂金系統整合 + 雙重預約自動化 + 候補名單 | 多醫師診所 |
| **Chain** | NT$4,999/月 | 連鎖診所 (5-30 分院) + 跨院 benchmark | 連鎖醫美 / 牙科集團 |
| **Enterprise** | NT$15,000+/月 | EHR 整合 + 健保 API + 客製模型 | 醫院門診部 |

## Distribution

- **PTT pharmacy / 診所經營 / FB「自費診所老闆交流」** 5-10K 社群案例分享
- **YouTube 醫美 / 牙科 / 中醫 KOL** (KGI 王炯珵 / 黃君豪 / 牙醫顧問) 案例
- **診所管理系統 partner** (PTC / SimplyClinic / 久興) integration
- **LINE@ 認證合作伙伴** (若可申)
- **醫師公會 / 牙醫師公會 / 中醫師公會 / 美容醫學會** B2B BD
- **醫療顧問公司** B2B 白標
- **台北醫療展 / 國際牙科展** 每年 11 月 booth

## TAM

- 1% × 15,000 = 150 × NT$499 = **月 NT$7.5 萬**
- + Pro 100 × NT$1,499 = NT$15 萬/月
- + Chain 50 × NT$4,999 = NT$25 萬/月
- + Enterprise 20 × NT$15K = NT$30 萬/月
- 總計 **月 MRR NT$78 萬 / 年 ARR NT$936 萬**
- 加滲透 + 橫移港新馬 / 日韓自費醫療 → 翻倍至 **NT$2,000-3,000 萬 ARR**

## 風險與限制

- **In-sample 高 AUC = overfit 風險** — 真實 launch 必須 train/test split + CV;Pro 版加 holdout 驗證
- **歷史 200 件不足** — 鼓勵診所累積 ≥ 500 件才正式上線, Pro 版加 transfer learning between similar clinics
- **季節 / 節日 / 颱風天 / 流感季 systematic 因素**: 模型沒納入, Pro 版加外部 features
- **GBDT 易 overfit on noise** — max_depth=3 + lr=0.1 是 conservative;產品需 ablation study
- **GBDT 不解釋為何個別案高** — feature_importance 給總體, 個別 SHAP / TreeSHAP 需 Pro 版
- **訂金政策法律風險** — 不可超過合理範圍, 需書面 ToS + LINE@ 自動回覆條款連結
- **隱私敏感** — 病患就診紀錄涉個資 + 醫療性質, 雲端版需加密 + 院方同意 + 資料去識別化 + 衛福部健保署規範

---
*clinicqueue = Friedman 2001 Gradient Boosting Decision Trees × 台灣自費診所 no-show 預測 niche = 從 200 件歷史學 no-show 模式, 對未來 20 個 appt 標出高風險, 個人化提醒 + 訂金 + 候補名單 SOP 降 no-show 50%。*
