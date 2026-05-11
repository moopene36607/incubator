# barktype -- 台灣 狗叫聲 voice signal 分類

**訓練樣本**: 40 個 bark (10 個 × 4 類)
**Feature pipeline**: Cooley-Tukey FFT + 自相關 pitch 偵測 + RMS 能量 + 頻譜質心 + 過零率 + 頻譜 rolloff
**Classifier**: kNN (k=3) with per-feature stdev normalisation

## 🎤 查詢 bark features (從 WAV / 預抽取)

_陳太太家貴賓犬 3 歲, 早上 9 點出門上班, 過 30 分鐘鄰居反映狗持續低中強度吠叫, 想知道是警戒還是分離焦慮_

| Feature | 值 | 物理意義 |
|---|---|---|
| pitch_mean_hz | 420.0 | 主頻 (越高 = 越尖) |
| pitch_std_hz | 35.0 | pitch 變化 (越大 = 越多變) |
| duration_ms | 1100 | 整段長度 |
| energy_mean | 0.420 | RMS 平均能量 |
| spectral_centroid_hz | 950 | 頻譜「重心」 |
| zero_crossing_rate | 0.085 | 過零率 (越大 = 越雜) |
| bark_rate_per_sec | 0.80 | 每秒爆發數 |
| spectral_rolloff_hz | 1650 | 85% 能量截止 |

## 😟 kNN 預測 (k=3)

### **焦慮孤獨** (信心 100%)

- **常見情境**: 分離焦慮 / 主人剛離開 / 長時間獨處
- **飼主可做**: 出門前 5 分鐘冷處理 + 留嗅聞玩具 / Kong 填食 + 慢慢延長獨處時間
- **不要做**: 不要回家立刻熱情打招呼 (強化『主人回來=超興奮』循環)

## 🗳️ Vote 分布

| 類別 | 票數 | 視覺 |
|---|---|---|
| ⭐ 焦慮孤獨 | 3 | `███████████████` |

## 🔍 Top 5 訓練樣本 (按 normalised Euclidean distance)

| Rank | 類別 | 距離 |
|---|---|---|
| #1 | 焦慮孤獨 | 0.181 |
| #2 | 焦慮孤獨 | 0.184 |
| #3 | 焦慮孤獨 | 0.254 |
| #4 | 焦慮孤獨 | 0.299 |
| #5 | 焦慮孤獨 | 0.355 |

## ⚠️ Voice signal + kNN 模型假設與限制

- **FFT 假設 stationarity**: 單一 FFT 假設信號頻譜在 window 內穩定; 真實叫聲頻譜會變動, Pro 版用 STFT (Short-Time FFT)
- **自相關 pitch 對噪音敏感**: 環境噪音大 (車流 / 風) 時 pitch 估計失準; Pro 版加 cepstral pitch detection
- **kNN 對 feature scale 敏感**: 已用 per-feature stdev 正規化, 但若新資料分布變動需重訓
- **訓練樣本不大**: prototype 40 件, real launch 需 ≥ 500 件 各品種 (柴犬 / 黃金 / 米克斯 / 貴賓 / 馬爾濟斯 / 比熊 / 邊牧)
- **品種差異大**: 中大型犬基頻 200-400 Hz / 小型犬 600-1200 Hz, prototype 沒分品種, Pro 版加品種 feature
- **不取代獸醫 / 訓練師**: 工具給「分流參考」, 痛苦不適 / 嚴重焦慮 仍需專業評估; 連續吠叫 > 30 分 → 24h 內看獸醫
- **個別狗差異**: 有些狗一輩子只用 1-2 種叫聲, 模型對「沉默型」「碎念型」極端狗準確度差
- **隱私敏感**: 音訊資料涉個人空間, 本地版完全在設備不上傳; 雲端版需加密 + 用戶同意

---
*barktype = Cooley-Tukey FFT + 自相關 pitch 偵測 + kNN × 台灣 狗叫聲 voice signal 分類 niche = 純函式 FFT 抽取 8 個 voice features (pitch / energy / centroid / ZCR / rolloff / bark_rate / duration / std), kNN 從 40+ 個訓練 bark 學「警戒 / 焦慮 / 玩耍 / 痛苦」4 類分類, 飼主拿到「我家狗為什麼叫」客觀建議 + 飼主動作 SOP + 紅旗 24h 就醫。*
