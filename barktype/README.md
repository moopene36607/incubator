# barktype -- 台灣狗叫聲 voice signal 分類 (FFT + 自相關 pitch + kNN)

**「家裡 3 歲貴賓自從我出門就一直叫, 是警戒還是分離焦慮?」** 用 Cooley-Tukey FFT + 自相關 pitch 偵測純函式從狗叫聲抽 8 個 voice features (pitch / energy / spectral centroid / ZCR / rolloff / bark_rate / duration / pitch_std), kNN (k=3) 從 40 個訓練 bark 學「警戒 / 焦慮孤獨 / 玩耍興奮 / 痛苦不適」4 類分類, 飼主拿到「我家狗在叫什麼意思」客觀建議 + 飼主動作 SOP + 紅旗 24h 就醫。

## 痛點

台灣犬主市場:
- **登記犬主**: 233 萬戶 (農業部 2024)
- **多狗家庭**: ~25% (60+ 萬戶)
- **公寓飼養比例**: 70%+ (鄰居投訴是頭號生活痛點)
- **每月吠叫困擾**: 估計 30-50% 犬主每月遇 1+ 次「狗為什麼一直叫」困擾

**飼主痛點** (FB「米克斯共和國 / 我愛貴賓狗 / 柴犬」5-30 萬人社群 / Dcard pet / PTT dog_cat / Mobile01 寵物板):
- 「我家狗為什麼一直叫」(每週都有人問)
- 「鄰居又投訴, 但我不知道怎麼讓他停」
- 「ChatGPT 跟我說可能是分離焦慮, 但又說也可能是警戒, 不確定」
- 「找訓練師一堂 NT$1,500-3,000, 心疼但又不敢拖」
- **隔壁鄰居反覆投訴** → 房東警告 / 大樓管委會 / 警察開單 = 房客 / 飼主壓力極大

**現有資源**:
- 犬行為訓練師 NT$1,500-3,000/堂, 全台 ~500 位, 預約 1-2 週
- 獸醫只看醫療面 (脫水 / 受傷 / 內臟), 不擅長行為分析
- YouTube / FB / 書 (戴更基 / 熊爸 / Cesar Millan) 內容導向不對應個別狗
- 海外 app (Petbark / BarkBuddy) 訓練在歐美犬種, **不認識台灣常見品種 (柴犬 / 貴賓 / 馬爾濟斯 / 米克斯)**

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(barktype 補的) |
|---|---|---|
| 犬行為訓練師 | 一對一行為矯正 | NT$1,500-3,000 + 排隊 1-2 週 |
| 獸醫 | 醫療診斷 + 處方 | 不擅長行為分析, 多半建議去找訓練師 |
| YouTube / FB / 書 | 內容導向 | 不對應個別狗 + 飼主收到訊息時忘了 |
| Petbark / BarkBuddy (海外) | 海外狗叫分類 | 訓練在歐美犬種, 不認識台灣常見品種音域 |
| ChatGPT 一次問 | 一次性建議 | 不能處理音訊, 沒持續學習 |
| Excel / 紙筆記錄 | 純人工 | 沒系統化 voice signal feature 分析 |
| **petfeed r57** (本 incubator) | 飼料推薦 HB shrinkage | 完全不同問題 |
| **petskin r59** | 皮膚 LDA triage | 完全不同問題 |
| **vetnote r9** | 獸醫 SOAP 病歷 | 服務獸醫師, 飼主用不到 |
| **crybabel r48** | 嬰兒哭聲 RF 分類 (text features) | 同精神不同對象, 嬰兒 vs 寵物 |

**Gap 結構性**: Voice signal analysis (FFT 1965 Cooley-Tukey + 自相關 pitch 1960s) 學術成熟 60 年, **沒人做成台灣繁中犬主端 voice signal SaaS**。Google「台灣 狗叫聲 voice signal 中文」零本土 SaaS。**跟 crybabel r48 同精神不同對象** — r48 嬰兒哭聲 RF on text-extracted features, r65 狗叫聲 voice signal on real audio FFT 純函式 pipeline。

## 架構 -- Voice Signal Analysis with FFT + Autocorrelation + kNN (55th 條 AI pattern)

```
WAV 音訊樣本 (mono 16-bit PCM)
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ wave.open() 純 stdlib 讀取 + struct.unpack    │
│ Normalise to [-1, 1] 浮點數                   │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Frame-by-frame analysis (frame=1024 hop=512): │
│   Cooley-Tukey radix-2 FFT (純 stdlib)        │
│   X[k] = sum_n x[n] e^{-2πikn/N}              │
│   even / odd split + twiddle factor recursion │
│                                                │
│   自相關 pitch 偵測:                           │
│   r[k] = sum_i x[i] * x[i+k]                  │
│   pitch = sr / argmax_{lag} r[lag]            │
│   sanity-check r[lag] / r[0] > 0.15           │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ 8 維 feature 抽取:                            │
│   pitch_mean_hz       (frame 平均)            │
│   pitch_std_hz        (frame 變異性)          │
│   duration_ms         (整段長度)              │
│   energy_mean         (RMS 平均)              │
│   spectral_centroid_hz (頻譜重心)             │
│   zero_crossing_rate  (高頻能量 proxy)        │
│   bark_rate_per_sec   (能量超 threshold 計數) │
│   spectral_rolloff_hz (85% 能量截止頻率)      │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ kNN (k=3) classifier:                         │
│   per-feature stdev 正規化避免 scale 失衡     │
│   d(x, y) = sqrt(sum_j ((xj-yj)/sj)²)        │
│   majority vote of k nearest training barks   │
│   confidence = winner_votes / k               │
└──────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────┐
│ Output 4 類 triage 建議:                      │
│   警戒 / 焦慮孤獨 / 玩耍興奮 / 痛苦不適       │
│   飼主可做 + 不要做 + 紅旗就醫 + 訓練師清單   │
└──────────────────────────────────────────────┘
```

**100% 純函式 stdlib** (math + cmath + statistics + dataclasses + collections + wave + struct):
- `fft / magnitude_spectrum`: Cooley-Tukey radix-2 recursive FFT
- `autocorrelation / estimate_pitch_hz`: 自相關 + lag-search pitch detection with sanity check
- `rms_energy / zero_crossing_rate / spectral_centroid / spectral_rolloff`: 標準 voice features
- `extract_features_from_signal`: 完整 pipeline (frame + FFT + features) on raw audio
- `synthesise_bark`: 合成 bark waveform 用 (sine + 諧波 + 噪音) 給 tests + demo
- `read_wav_file`: stdlib wave + struct 讀取 16-bit PCM WAV
- `knn_predict`: per-feature stdev 正規化 kNN

**LLM 只負責**: 寫 250-330 字「飼主深夜讀的 SOP + 訓練師紅旗 + 容易做錯的事」
**LLM 絕不負責**: 計算 pitch / FFT / classification (數字 100% 來自 voice signal pipeline)

### 為什麼 FFT + 自相關 適合這個 use case

- **狗叫的 fundamental frequency 在 150-1000 Hz**: pitch 是分類最強信號 (痛苦低頻 vs 警戒高頻), 自相關純函式可直接抽
- **Cooley-Tukey FFT pure stdlib 可實作**: 不需 numpy / scipy, 30 行 Python 解決
- **品種差異反映在 pitch 範圍**: 中大型犬 200-400 Hz / 小型犬 600-1200 Hz, FFT 結果直接區分
- **不需要 deep learning model**: 簡單 8 features + kNN 對 4 類分類 prototype 期已能用; 真實 launch 可升級 ResNet / CNN

## 使用示例

```bash
# 純函式模式 (用預抽取的 features)
python3 barktype.py --data samples/bark_dataset.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python3 barktype.py --data samples/bark_dataset.json

# 從 WAV 檔案抽 features (展示 real audio pipeline)
python3 barktype.py --wav /path/to/dog_bark.wav
```

預期輸出 (詳見 `examples/sample_output.md`):

陳太太家貴賓犬 3 歲, 出門 30 分鐘後鄰居投訴持續吠叫:

| Feature | 值 |
|---|---|
| pitch_mean_hz | 420.0 |
| duration_ms | 1100 |
| bark_rate_per_sec | 0.80 |

→ **kNN 預測: 😟 焦慮孤獨 (信心 100%)** Top 5 nearest training barks 全是焦慮孤獨類 (距離 0.181-0.355). 推薦 SOP: 儀式化離家 + Kong 填食 + 回家不興奮; 若持續 2 週以上找熊爸 / 戴更基 / 王介菁 訓練師。

訓練診斷: 28 voice tests passed 包含 FFT 在純 sine 波 220/440 Hz 正確峰值偵測 + 自相關 pitch 精準到 ±5Hz。

## 目標市場

- **TAM**:
  - 233 萬登記犬主 (B2C)
  - 500 犬行為訓練師 (B2B 工具)
  - 2,600 寵物醫院 (B2B 行為諮詢前端)
  - 寵物保險 (Petplan / 國泰 / 富邦) — 行為矯正理賠減損
- **WTP 錨點**:
  - 1 堂訓練師 NT$1,500-3,000 vs Solo NT$99/月 = **15-30x 便宜**
  - 鄰居投訴 → 房東警告 → 換房成本 NT$30-100K vs Solo NT$99 = **300-1000x 防損**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 3 次/月 voice 分類 | 飼主試用 |
| **Solo** | NT$99/月 | 無限 voice + 個人化追蹤 + LINE Bot | 個別飼主 |
| **Family** | NT$299/月 | + 多狗家庭 + 配偶共享 + 進階訓練教材 | 多狗 / 多代家庭 |
| **Trainer** | NT$1,999/月 | 訓練師 white-label + 客戶記錄 + 進度報告 | 犬行為訓練師 |
| **Clinic** | NT$4,999/月 | 寵物醫院 行為諮詢前端 + EHR API | 寵物醫院 |
| **Insurance** | NT$15,000+/月 | 寵物保險公司 行為矯正理賠減損 | 寵物保險 |

## Distribution

- **FB「米克斯共和國 / 我愛貴賓狗 / 柴犬 / 黃金獵犬 / 馬爾濟斯 / 邊牧」** 5-30 萬人社群案例分享
- **Dcard pet / 寵物 / 動物溝通 / 領養** 板長尾 SEO
- **PTT dog_cat / dog / cat / pet** 板
- **Mobile01 寵物板** (中年飼主)
- **YouTube 犬訓練 / 寵物 KOL** (熊爸 / 戴更基 / 王介菁 / 黃金毛 / 大胃王皮卡丘)
- **犬行為訓練師 B2B BD** (台灣寵物訓練協會 / 各縣市犬訓練師工會)
- **寵物醫院 B2B BD** (太僕 / 茂楷 / 中興 / 仁愛 / 哈寶)
- **寵物保險 partner** (Petplan / 國泰 / 富邦 寵物險 — 行為矯正理賠減損)
- **寵物 APP 整合** (毛孩兒 / 寵物隨身 / 毛起來)
- **大樓管委會 / 房東協會** 反投訴宣導
- **台北寵物用品大展** (每年 8 月南港) booth

## TAM

- 0.5% × 233 萬 = 11,650 × Solo NT$99 = **月 NT$115 萬**
- + Family 2,000 × NT$299 = NT$60 萬/月
- + Trainer 50 × NT$1,999 = NT$10 萬/月 (500 訓練師 10%)
- + Clinic 100 × NT$4,999 = NT$50 萬/月
- + Insurance 5 × NT$15K = NT$7.5 萬/月
- 總計 **月 MRR NT$242 萬 / 年 ARR NT$2,900 萬**
- 加滲透 + 橫移日本 (700 萬犬) / 韓國 (500 萬犬) / 港新馬 → **NT$1-1.5 億 ARR**

## 風險與限制

- **40 件 prototype 太小** — real launch 需 ≥ 1,000 件多品種多情境 cases, 鼓勵飼主 contribute 換取免費 Family 月
- **FFT 假設 stationarity**: 單一 FFT 假設信號頻譜在 window 內穩定, 真實叫聲頻譜會變動, Pro 版用 STFT (Short-Time FFT)
- **自相關 pitch 對噪音敏感**: 環境噪音大 (車流 / 風 / 電視) 時 pitch 估計失準, Pro 版加 cepstral pitch detection + noise reduction
- **品種差異大**: 中大型犬基頻 200-400 Hz / 小型犬 600-1200 Hz, prototype 沒分品種, Pro 版加品種 feature + 品種專用模型
- **kNN 對 feature scale 敏感**: 已用 per-feature stdev 正規化, 但若新資料分布變動需重訓
- **不取代獸醫 / 訓練師**: 工具給「分流參考」, 痛苦不適 / 嚴重焦慮 仍需專業評估; 連續吠叫 > 30 分 → 24h 內看獸醫
- **個別狗差異**: 有些狗一輩子只用 1-2 種叫聲, 模型對「沉默型」「碎念型」極端狗準確度差
- **隱私敏感**: 音訊資料涉個人空間, 本地版完全在設備不上傳; 雲端版需加密 + 用戶同意
- **避免過度 label 狗**: 不要因 1 次分類就斷定「我家狗就是焦慮狗」, 行為會隨環境 / 訓練改變

---
*barktype = Cooley-Tukey FFT (1965) + 自相關 pitch + kNN × 台灣 狗叫聲 voice signal 分類 niche = "純函式 FFT 抽 8 voice features → kNN 4 類分類 → 飼主 SOP + 訓練師清單", 補犬行為訓練師 1-2 週排隊 + NT$1,500-3,000 一堂 + 海外 app 不認識台灣犬種的縫隙。*
