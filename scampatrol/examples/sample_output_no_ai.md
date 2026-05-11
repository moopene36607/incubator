# scampatrol -- LINE 詐騙訊息 weak-supervision 個人端偵測

**LFs (labelling functions)**: 10
**Classes**: 5 (合法訊息, 假投資詐騙, 假冒身份詐騙, 釣魚連結 / 中獎詐騙, 假借錢詐騙)
**訓練 messages (無標註)**: 40
**Dawid-Skene EM 收斂**: 39 iterations (log-lik -113.7)

## 📡 LF 診斷

| LF | 覆蓋率 | 估計準確度 (E[pi·diag]) |
|---|---|---|
| `lf_invest_keywords` | 20% | 17% |
| `lf_impersonation_authority` | 15% | 10% |
| `lf_phishing_short_link` | 48% | 52% |
| `lf_phishing_prize` | 12% | 51% |
| `lf_borrow_urgency` | 15% | 42% |
| `lf_msg_length_link` | 0% | 20% |
| `lf_legitimate_long_no_link` | 22% | 34% |
| `lf_invest_percent_number` | 8% | 25% |
| `lf_mlm_dating` | 2% | 24% |
| `lf_impersonation_family` | 10% | 37% |

> **覆蓋率**: 該 LF 不 abstain 的訊息比例; 太低 (< 5%) 代表 LF 太嚴; 太高 (> 80%) 代表 LF 太寬鬆
> **準確度**: Dawid-Skene EM 估計的「對齊真實類別」機率, 反映該 LF 的可信度

## 📊 訓練先驗 P(類別)

| 類別 | π (prior) |
|---|---|
| 合法訊息 | 20.3% |
| 假投資詐騙 | 7.6% |
| 假冒身份詐騙 | 0.0% |
| 釣魚連結 / 中獎詐騙 | 42.8% |
| 假借錢詐騙 | 29.3% |

## 🎯 待檢驗訊息

> _陳媽媽收到陌生 LINE 訊息, 看起來像投資邀請, 想知道該不該理_

```
陳大哥您好,我是專業投資老師,每天保證獲利 3-5%,加入我們的內線消息群組,一個月就能讓您資產翻倍。穩賺方法限時開放,點此立即加入：https://bit.ly/3xyzABC
```

## 🔍 LF 對此訊息的判決

| LF | 輸出 | 意義 |
|---|---|---|
| `lf_invest_keywords` | 1 | 假投資詐騙 |
| `lf_impersonation_authority` | -- | (abstain) |
| `lf_phishing_short_link` | 3 | 釣魚連結 / 中獎詐騙 |
| `lf_phishing_prize` | -- | (abstain) |
| `lf_borrow_urgency` | -- | (abstain) |
| `lf_msg_length_link` | -- | (abstain) |
| `lf_legitimate_long_no_link` | -- | (abstain) |
| `lf_invest_percent_number` | 1 | 假投資詐騙 |
| `lf_mlm_dating` | -- | (abstain) |
| `lf_impersonation_family` | -- | (abstain) |

## 🗳️ Majority Vote (簡單基準)

**簡單票數**: {'假投資詐騙': 2, '釣魚連結 / 中獎詐騙': 1}
**贏家**: 假投資詐騙

## 🧠 Dawid-Skene EM 後驗

| 類別 | 後驗 P(y \| LF 輸出) |
|---|---|
| ⭐ 假投資詐騙 | 99.1% `█████████████████████████████` |
|    釣魚連結 / 中獎詐騙 | 0.9% `` |
|    假借錢詐騙 | 0.0% `` |
|    合法訊息 | 0.0% `` |
|    假冒身份詐騙 | 0.0% `` |

## 🚨 對應建議 (假投資詐騙)

- **緊急度**: 🔴 高度懷疑
- **個人應對**: **立刻封鎖** + 不點任何連結 + 不轉帳;告知家人朋友這個 LINE 帳號;不要單獨進入「投資群組」
- **通報管道**: 165 反詐騙專線 + 警政署「打詐儀表板」https://165dashboard.tw 通報

## ⚠️ Weak Supervision 模型假設與限制

- **LF 獨立性假設**: Dawid-Skene 假設「給定真實類別, LF 輸出彼此條件獨立」; 真實有相依 (LF1 LF8 都看 '%'), Pro 版用 Snorkel-style generative model with LF correlations
- **LF 是手工規則**: 規則太嚴 → 覆蓋率低; 太寬 → 雜訊高;Pro 版加 ML LFs (BERT-classifier 當 LF 之一)
- **訓練無標註**: Dawid-Skene 是 unsupervised, 完全依賴 LF 輸出投票 + EM 推估;若所有 LF 系統性錯誤, 整體就錯
- **不含視覺資訊**: 真實詐騙圖片 / 假網址截圖, prototype 只看文字; Pro 版加 vision
- **不含時序 / 帳號信譽**: 同一帳號連發 100 則, 純文字模型看不出; Pro 版加 sender history
- **法律邊界**: 工具只給「值得警覺」分流, **最終判定 / 報警仍需 165 反詐騙專線 / 警政署**; 不取代專業
- **隱私敏感**: 私訊內容可能涉個資, 本地版完全在用戶設備不上傳;雲端版需加密 + 用戶同意 + 訊息匿名化

---
*scampatrol = Ratner et al. 2016 Snorkel weak supervision + Dawid & Skene 1979 EM × LINE 詐騙偵測 niche = 10 個手工 weak rules 投票 + EM 學每個 rule 的可信度 → 5 類詐騙分流 + 通報路徑, 個人端工具補 165 反詐騙專線只能事後通報的缺口。*
