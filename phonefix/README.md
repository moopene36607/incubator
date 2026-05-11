# phonefix — 台灣 3-8 歲兒童國語注音構音矯正居家輔助

**「我家小孩 5 歲了還是把『獅子』念成『絲子』,語言治療師排隊要 2 個月,在家該怎麼練?」** 用 Levenshtein (1965) 加權編輯距離 + 注音音素 substitution cost taxonomy,從一週的居家發音紀錄抓出**系統性構音模式**(翹舌→平舌 / ㄈ→ㄏ / ㄖ→ㄌ 等 12 種典型錯誤),給家長**具體舌位 / 嘴形 練習腳本 + 何時必看語言治療師**。

## 痛點

台灣 3-8 歲兒童 ~150 萬人,**構音異常盛行率約 10-15%** (來源:台灣語言治療師公會 / 衛福部國民健康署):
- ~15-22 萬兒童在某個發展階段有構音問題
- 6 歲後仍系統性錯誤者約 5-8 萬 (典型矯正對象)

**家長焦慮鏈** (親子王國 / 媽寶 / Dcard 親子 / FB「兒童語言發展互助」社群每天 50+ 貼文):
- 「我家 5 歲還在『絲子』『絲頭』,正常嗎?」(每天問)
- 「掛了語言治療師, 排到 2 個月後, 在這 2 個月怎麼辦?」(典型痛點)
- 「健保只有 5 次, 自費一次 NT$3,000, 練 6 個月吃不消」
- 「LINE 問群裡的媽媽, 她們都說『他大了就好』」

**現有資源**:
- 語言治療師: 健保 5 次 / 自費 NT$1,500-3,000 一次,排隊 1-3 月
- 學前特教中心: 各縣市有少數名額,審核嚴
- 早療中心 (0-6 歲) NT$200-500/次,排隊 1-2 月
- 兒科診所: 不一定有 ST,通常轉介

## 為什麼現有工具不解。Gap 結構性

| 工具 | 它做什麼 | 它沒做什麼(phonefix 補的) |
|---|---|---|
| 語言治療師 | 評估 + 治療 | 太貴 + 排隊長, 排隊期間無工具 |
| 兒童注音教材 / APP (4399 / 小康軒) | 教注音認讀 | 不分析孩子發音是否正確 |
| 自家錄音 + 自己聽 | 主觀判斷 | 家長不是專家, 抓不到 systematic 模式 |
| ChatterBaby / Speech Blubs (英) | 英語兒童 | 不認識中文注音 + phoneme |
| ChatGPT 直接問 | 一次性建議 | 不能持續分析 + 沒 levenshtein 量化 + 沒系統錯誤模式偵測 |

**Gap 結構性**: Levenshtein (1965) 學術成熟 60 年,**沒人做成台灣繁中兒童構音矯正 SaaS**。Google「兒童注音構音 AI」零本土 SaaS 結果。

## 架構 — Weighted Edit Distance with Phoneme-Aware Substitution Costs (39th 條 AI pattern)

```
Target bopomofo (家長念) → Tokenize syllables → list of phonemes
Actual bopomofo (孩子念) → Tokenize syllables → list of phonemes
                  │
                  ▼
┌────────────────────────────────────────────────┐
│ For each syllable pair (target_i, actual_i):   │
│   Weighted Levenshtein DP:                     │
│     C[i][j] = min(                              │
│       C[i-1][j] + del_cost,                    │
│       C[i][j-1] + ins_cost,                    │
│       C[i-1][j-1] + sub_cost(a, b))            │
└────────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────┐
│ Substitution cost taxonomy:                    │
│   ㄓ ↔ ㄗ (翹舌→平舌): 0.3 (典型 disorder)      │
│   ㄈ ↔ ㄏ (唇齒→舌根): 0.5 (閩南語影響)        │
│   ㄖ ↔ ㄌ (兒化→邊音): 0.4                      │
│   同類別不同音 (e.g., ㄇ↔ㄅ 唇音): 0.5         │
│   跨類別 (e.g., ㄓ↔ㄅ): 0.8                    │
│   完全不同 (vowel↔consonant): 1.0              │
└────────────────────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────┐
│ Aggregate across 多句:                         │
│   error_patterns counter                       │
│   most_common substitution pairs               │
│   accuracy_pct = 1 - cost/max_cost             │
└────────────────────────────────────────────────┘
                  │
                  ▼
            systematic? if count ≥ 3
```

**100% 純函式 stdlib** (collections + dataclass):
- `PHONEME_CLASSES`: 7 articulation classes (唇音 / 唇齒音 / 舌尖前 / 舌尖後 / 舌尖 / 舌面 / 舌根)
- `COMMON_SUBSTITUTION_PAIRS`: 12 hand-crafted 典型構音錯誤對 with cost & reason
- `substitution_cost(a, b)`: returns (cost, reason) — 4-tier taxonomy
- `tokenize_syllable`: 注音 → phoneme list + tone token
- `weighted_edit_distance`: standard Levenshtein DP + backtrace alignment
- `analyze_pronunciation`: aggregate over phrase + error_patterns counter
- `detect_systematic_pattern`: ≥3x = systematic, ≥2x = potential, <2 = sporadic

**LLM 只負責**: 寫 250-350 字「家長居家練習腳本 (鏡子練習 / 吹紙條 / 對比卡) + 何時必看 ST + 情緒安撫」
**LLM 絕不負責**: 計算 edit distance / accuracy / 系統性模式 (數字 100% 來自純函式)

## 使用示例

```bash
# 純函式模式 (無 API key)
python phonefix.py --session samples/practice_session.json --no-ai

# AI 模式
export ANTHROPIC_API_KEY=sk-ant-...
python phonefix.py --session samples/practice_session.json
```

預期輸出 (詳見 `examples/sample_output.md`):

樣本 (陳小美 5 歲 8 個月, 7 句練習):

| 系統性模式 | 出現次數 | 嚴重度 |
|---|---|---|
| 🔴 翹舌→平舌 | **8x** | 系統性 = 治療目標 |
| 🔴 唇齒→舌根 (ㄈ→ㄏ) | **3x** | 系統性 = 治療目標 |
| 🟢 ㄖ→ㄌ | 1x | 零星 |

**整體準確度 96.3%** | **總編輯成本 4.30** | **7 句 117 音素**

→ 診斷:**雙重系統性構音錯誤** (翹舌 + ㄈ),5 歲 8 個月可開始矯正。

## 目標市場

- **TAM**:
  - 3-8 歲兒童 ~150 萬,構音異常 10-15% = **15-22 萬潛在用戶**
  - 6 歲後仍系統性錯誤 = 5-8 萬核心 (高 urgency)
- **WTP 錨點**:
  - 語言治療師自費 NT$2-3K/次 × 10 次 = NT$20-30K vs phonefix Solo NT$199/月 = **100-150x 便宜**
  - 排隊 1-3 月 期間「沒有任何工具」的痛點清晰,**單一行為 trigger 高**

## 定價

| 方案 | 月費 | 包含 | 適合 |
|---|---|---|---|
| **Free** | 0 | 3 句/週 + 基本分析 | 試用 |
| **Solo** | NT$199/月 | 無限句 + LINE 進度追蹤 + 7 類 articulation | 個人家庭 |
| **Family** | NT$399/月 | 多孩 + 配偶共享 + 月度進度報告 | 多孩家庭 |
| **Pro (ST 輔助)** | NT$1,999/月 | 語言治療師 client dashboard + 自動評估報告 | 語言治療師 |
| **School** | NT$8,000+/月 | 幼兒園 / 國小特教整合 + 班級匯總 | 學校 / 早療中心 |

## Distribution

- **親子王國 / 媽寶 / Dcard 親子 / FB「兒童語言發展互助」** 5-15 萬人社群長尾 SEO
- **語言治療師公會** B2B BD (約 2,500 名 ST in TW)
- **早療中心 / 兒童發展中心** 教育部委辦 partner
- **小兒科 / 兒童心智科診所** (馬偕 / 國泰 / 長庚 等) B2B referral
- **幼兒園 / 國小特教班** 機構訂閱 (台北 / 新北 / 桃園優先)
- **YouTube 親子 / 早療 KOL** (Roxy 媽媽 / 阿包醫生 / 黃瑽寧醫師) 案例
- **健保署 / 衛福部國民健康署** 早療早期介入計畫 partner

## TAM

- 1% × 22 萬 = 2,200 × NT$199 = **月 NT$44 萬**
- + Family 800 × NT$399 = NT$32 萬/月
- + Pro ST 200 × NT$1,999 = NT$40 萬/月 (台灣 2,500 ST 中 8% 採用)
- + School 50 × NT$8K = NT$40 萬/月
- 總計 **月 MRR NT$156 萬 / 年 ARR NT$1,870 萬**
- 加滲透 + 橫移港新馬 / 日本廣東話兒童 → 翻倍至 **NT$3,000-5,000 萬 ARR**

## 風險與限制

- **依賴家長輸入** — prototype 用注音對照, 真實 launch 需錄音 → Whisper 中文 / Pin1Yin1 自動 phoneme 識別
- **substitution cost 是 hand-crafted** — 12 對 prior cost, Pro 版用 1000+ 件臨床資料學 cost matrix
- **聲調未深度比對** — 簡化版 _toneN, 真實 launch 需 prosodic analysis (F0 contour)
- **不取代語言治療師** — 工具用於 home practice + 監控進度, 確診 / 治療需專業評估;UI 必須強調紅旗 + 何時必看 ST
- **4-5 歲發展期錯誤是正常的** — ㄓㄔㄕ 4 歲還在 emerging, 6 歲後仍系統錯誤才算 disorder;模型回應需 age-aware
- **方言影響** — 閩南語家庭 ㄈ↔ㄏ 替換是 culturally common, 不一定是 disorder
- **隱私敏感** — 兒童發音資料涉個資 + 醫療性質, 雲端版需加密 + 家長同意 + 資料留存政策

---
*phonefix = Levenshtein 1965 weighted edit distance × 台灣 3-8 歲兒童構音矯正 niche = 補語言治療師排隊 2-3 個月空窗期, 給家長系統性錯誤偵測 + 居家練習腳本。*
