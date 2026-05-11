# crybabel — 陳小寶 哭聲 Random Forest 分類

**年齡**: 3 個月
**模型訓練**: 105 samples × 7 類 × 80 棵樹
**Training accuracy**: 100.0% (in-sample)
**Max depth**: 8, **Max features/split**: 2

## 哭聲與情境特徵

| 特徵 | 值 | 直覺意義 |
|---|---|---|
| 主頻率 (Hz) | 820 | 高頻 (痛 / colic 嫌疑) |
| 持續時間 (秒) | 210 | 長 (>90 秒) |
| 規律性 0-1 | 0.15 | 極不規律 (爆發型) |
| 強度趨勢 -1~+1 | +0.70 | 快速升強 (急迫) |
| 距上次餵奶 (分) | 60 | 中段 |
| 距上次尿布 (分) | 30 | 中段 |
| 距上次小睡 (分) | 45 | 中段 |

## 🎯 Random Forest 分類結果

### 💢 腸絞痛 (colic)

- **預測類別**: `colic`
- **信心度 (vote share)**: **90.0%** (72/80 棵樹投這類)

## 各類別投票分布

| 類別 | 投票機率 | 標籤 |
|---|---|---|
| ⭐ 💢 腸絞痛 (colic) | 90.0% | `███████████████████████████` |
|   😖 疼痛 | 10.0% | `███` |
|   😣 不舒服 (衣物 / 溫度) | 0.0% | `` |
|   🍼 餓了 | 0.0% | `` |
|   😵 過度刺激 | 0.0% | `` |
|   😴 累了 / 想睡 | 0.0% | `` |
|   💧 尿布濕 / 髒 | 0.0% | `` |

## 純函式判讀: 推薦動作

**對 `colic` 的標準建議**:

- **典型黃昏腸絞痛** (3-3-3 規則:每天 3 hr+, 每週 3 天+, 持續 3 週+)。試 5S (Swaddle / Side-stomach 位 / Shush / Swing / Suck).

⚠️ **就醫紅旗**: 若 + 血便 / 嘔吐墨綠色 / 體重停滯 → 看小兒科

## Feature importance (整 forest)

| 特徵 | 重要度 (normalized) | 視覺 |
|---|---|---|
| `duration_s` | 0.180 | `█████████` |
| `rhythm_regularity` | 0.171 | `████████` |
| `pitch_mean_hz` | 0.161 | `████████` |
| `intensity_slope` | 0.158 | `███████` |
| `time_since_diaper_min` | 0.130 | `██████` |
| `time_since_feed_min` | 0.105 | `█████` |
| `time_since_nap_min` | 0.094 | `████` |

## ⚠️ Random Forest 模型假設與限制

- **訓練資料 simulated**: prototype 用合成 features 訓練, 真實 launch 需要兒科 / 月子中心 標註資料 ≥ 1000 件
- **哭聲特徵需要 audio extract**: prototype 用數值輸入, 真實 app 需要錄音 → MFCC 特徵抽取 (用 librosa 或 Claude audio API)
- **多類別不平衡**: colic 比 hungry 少見;Pro 版用 SMOTE / weighted classes
- **個別寶寶差異**: 「我家寶寶哭聲」可能 baseline 偏離訓練集;Pro 版加 per-baby calibration
- **不取代醫師判斷**: AI 給的是 likely 類別,**痛 / 異常哭聲**永遠優先看小兒科
- **新手父母 anxiety**: 用工具可能 anchor 在某類別反而忽略其他可能;UI 上要強調「3 個動作試試 + 不見效就重新評估」

---
*crybabel = Breiman 2001 Random Forest × 台灣繁中嬰幼兒哭聲 niche = 把 ChatterBaby 帶進中文母嬰市場。*
