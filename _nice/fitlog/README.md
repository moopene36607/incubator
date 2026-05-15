# fitlog

**台灣健身教練(PT)/ 瑜珈教練 課後訓練報告 AI 助手。**

教練每堂課結束後 30 秒輸入學員的組數/重量/RPE + 觀察 + 學員主述,fitlog 立刻產出一份學員會看完的繁中課後報告(markdown + LINE 截圖友好版),把每天 6-8 節課的「課後文書」從 30-40 分鐘壓縮到 5 分鐘。

---

## 痛點

台灣自由接案的 1 對 1 健身教練(PT、瑜珈教練)最大的「隱性工時」**不是訓練、是課後文書**。

> **「每次上完課要在記事本寫訓練記錄,寫完再 copy 給學員,一天 6 節課要寫 6 份,累死。」**
> — Dcard 健身板,2024-05

> **「課後紀錄、進度報告、下週課表用 Word 模板,還是很花時間。」**
> — PTT FITNESS 板,2024-03

> **「有沒有什麼 App 可以快速產生客製化訓練菜單傳給學員?」**
> — FB「健身教練交流」社團,反覆出現的提問

具體業務上的痛:

- 1 位 PT 通常每天上 6-8 節 1 對 1 課,每節結束後想留學員一份課後紀錄維持留存與信任
- 寫得太簡略 → 學員覺得「教練沒在用心」,流失率上升
- 寫得太用心 → 5-10 分鐘/份 × 8 節 = **每天 40-80 分鐘純文書**,等於白做 1 節課
- 教練時薪 NT$1,000-2,000(高階 PT 更高),這個 admin 時間沒有人付錢
- 文書品質直接影響「續報率」,但教練多半沒時間做細

## PMF 已被英文世界驗證

| 海外競品 | 證明什麼 |
|----------|----------|
| **TrueCoach** (USA, USD$26.34/月起) | 全球 PT 最大 SaaS 工具,證明教練願意付這個費用 |
| **My PT Hub** (UK, USD$25/月起) | 同上,英國市場第二大(Starter $25 / Premium $59 / Ultimate $215) |
| **Mindbody** (USA, 月費 $200+) | 大型健身房系統 |

**繁中市場**:零 AI 課後報告產生器。
- 台灣本土:MixFit / SportSoft 等是課程預約 + 點名,**完全沒有 AI 課後報告**
- 海外英文工具:不懂繁中、不懂台灣健身圈詞彙(RPE、組數、deload、TUT)
- ChatGPT 直接問:每次要重打學員資料,沒有結構化動作 grounding,容易寫成空泛廢話

**Gap 結構性**:TrueCoach 沒有動力做繁中(英文市場太大不缺單),台灣本土健身房 SaaS 沒有 AI DNA。1-3 人小工作室與自由接案 PT 是 VC 嫌小、健身房 SaaS 嫌雜的縫隙。

## fitlog 在做什麼

```
教練每堂課後 30 秒輸入:
  - 學員 + 課程基本(姓名 / 第 N 堂 / 主題)
  - 動作清單(動作代碼 + 組數 + 重量 + RPE + 備註)
  - 教練觀察 / 學員主述 / 下次計畫 / 恢復目標
        │
        ▼
  ┌──────────────────────────────────┐
  │ 純函式組裝報告標頭                  │
  │  - 量化訓練紀錄表(動作中英文 + RPE)│
  │  - LINE 純文字版(去 markdown 符號) │
  └────────────────┬─────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────┐
  │ Claude(系統 prompt + 30 動作 DB) │
  │ 撰寫 5 段:                        │
  │  ① 今日訓練摘要                    │
  │  ② 本次主要進步 / 突破             │
  │  ③ 身體反應與觀察                  │
  │  ④ 下次課程重點                    │
  │  ⑤ 本週恢復 / 飲食提醒(只用教練輸入)│
  └────────────────┬─────────────────┘
                   │
                   ▼
        markdown 課後報告 + LINE 友好純文字版
        (教練確認 → LINE 截圖直接傳學員)
```

3 個關鍵架構決策:

1. **`exercise_db.py` — 30 動作 grounding**:含中文(槓鈴背蹲舉)、英文(Back Squat)、目標肌群、典型 RPE 範圍。LLM 寫到動作時自動套台灣健身圈通用詞,不會把 Squat 翻成「蹲坐」這種生硬機翻。
2. **AI 嚴禁編造**:System prompt 明確禁止編造學員體重 / 體脂 / 卡路里 / 心率;恢復飲食只能用教練輸入的數字,不能憑空創造「每日喝 3L 水」「攝取 2,000 大卡」這種空話。
3. **AI 不下醫療診斷**:學員主述不適時(例:下背稍緊),AI 用「下次留意 / 視情況調整」措辭,**絕不寫**「你可能有椎間盤突出」這種診斷性語言 — 規避 PT 與物理治療師職業界線。

## 動作

### 不開 AI(骨架版,免 API key)

```bash
python3 fitlog.py samples/sample_input.json --no-ai
```

骨架版會渲染完整訓練量化表(動作中英文 + RPE + 備註),5 段內容是 placeholder。
即使沒 AI,純函式渲染的訓練表本身已經比 Word 模板強。

### AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# 同時產 markdown 與 LINE 純文字版
python3 fitlog.py samples/sample_input.json \
    --out reports/lin_aming_s12.md \
    --out-line reports/lin_aming_s12_line.txt
```

每堂課 API 成本約 NT$0.5,毛利空間極大。

### 多學員批次模式 (`--batch`)

PT 一天 6-8 節 1 對 1 課,把當日所有 session JSON 放同一目錄,
一行 CLI 全部產出 markdown 報告:

```bash
python3 fitlog.py --batch students_today/ --no-ai
# → students_today/aming.json → students_today/aming.md (+ _batch_summary.md)
```

報告預設寫在原 JSON 旁同名 `.md`。也可用 `--out-dir` 把輸出
分到獨立目錄(輸入目錄保持只有 .json,易於 .gitignore reports/):

```bash
python3 fitlog.py --batch students_today/ --out-dir reports/today/ --no-ai
# → reports/today/aming.md, reports/today/wang.md, reports/today/_batch_summary.md
```

範例輸出見 `examples/batch_demo/` (3 學員 → 3 .md + summary)。

PT 跑週報只要彙總 + 學員 trend (個別 session 已在日常 LINE 給學員了)
時,加 `--summary-only` 跳過個別 .md:

```bash
python3 fitlog.py --batch students_today/ --out-dir reports/week/ \
    --no-ai --summary-only
# → reports/week/_batch_summary.md, reports/week/_student_*.md
```

### 跨堂進步追蹤 (PR 標記)

```bash
python3 fitlog.py samples/sample_input.json --no-ai \
    --prev samples/sample_prev_input.json \
    --out reports/lin_aming_s12.md
```

把上次課程 JSON 用 `--prev` 帶進來,fitlog 會自動算出每個動作的 PR
(personal record):重量上升標 PR、噸位上升標噸位 delta。範例輸出:
「槓鈴臥推 47.5→50 kg (+2.5 kg PR)」。

### CSV 匯出 (Excel / Google Sheets 友好)

```bash
python3 fitlog.py samples/sample_input.json --no-ai \
    --csv reports/lin_aming_s12.csv
```

每筆 set 一行,欄位:date / student_name / session_no / set_index /
exercise_code / exercise_zh / exercise_en / category / sets /
reps_or_duration / weight_kg / rpe / tonnage_kg / note。
多堂 CSV 可直接 `cat` 串起做進步 dashboard / pivot table。
範例輸出見 `examples/sample_session.csv`。

### 預先產出的 demo

`examples/sample_output.md` 是完整課後報告,展示典型 60 分鐘全身肌力課程(學員:32 yo 男性,目標減脂 + 增肌,第 12 堂):
- 6 個動作的量化紀錄(Squat 4×10@70kg / Bench 4×8@50kg / RDL 3×10@60kg / Pull-up + Plank)
- 摘要 + 4 個具體進步突破(Bench 突破 47.5kg 瓶頸、Squat 深度 90→110°、Pull-up band 換色)
- 4 個身體反應觀察(膝蓋追蹤、髖鉸鏈、學員下背緊、本週睡眠不足)
- 下次課程主題切到 pull + 核心 + 心肺,並解釋為什麼這樣安排
- 恢復飲食提醒 prioritize 睡眠 > 蛋白質 > 有氧

## 收錄動作分類(56 動作 v2 擴充版)

| 大類 | 動作數 | 範例代碼 |
|------|------|----------|
| **legs**(腿系) | 11 | BB_BACK_SQUAT, ROMANIAN_DL, LEG_PRESS, HACK_SQUAT, HIP_THRUST, GOBLET_SQUAT, LEG_EXTENSION, LEG_CURL, CALF_RAISE |
| **pull**(拉系) | 11 | DEADLIFT, PULL_UP, CHIN_UP, LAT_PULLDOWN, BB_ROW, T_BAR_ROW, CABLE_ROW, INVERTED_ROW, KETTLEBELL_SWING |
| **push**(推系) | 12 | BENCH_PRESS, OHP, INCLINE_DB_PRESS, DECLINE_PRESS, LATERAL_RAISE, CABLE_FLY, MACHINE_CHEST_PRESS, DIPS |
| **core**(核心) | 9 | PLANK, AB_WHEEL, V_UP, HANGING_KNEE_RAISE, CABLE_WOODCHOP, PALLOF_PRESS |
| **cardio**(心肺) | 7 | RUN_TREADMILL, ROW_ERG, ASSAULT_BIKE, BURPEE, KETTLEBELL_SWING, BATTLE_ROPE, STAIR_CLIMBER |
| **mobility**(活動度) | 6 | HIP_OPENER, THORACIC_ROT, WORLDS_GREATEST, CAT_COW, COSSACK_SQUAT, CHILD_POSE |

(實際產品需擴充至 200+ 動作,涵蓋 powerlifting / 進階街健 / 普拉提全模組。)

## 專案結構

```
fitlog/
├── README.md
├── fitlog.py              # CLI 主程式(--out + --out-line)
├── exercise_db.py         # 30 動作 grounding seed dictionary
├── samples/
│   └── sample_input.json  # 60 分鐘全身肌力課程 (第 12 堂)
├── examples/
│   └── sample_output.md   # 預先產出的完整課後報告
└── requirements.txt
```

總計約 350 行 Python。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **Whisper 語音輸入**:教練上完課直接錄 30 秒「今天小明做了 Squat 4 組...」,Whisper 轉文字 → 結構化動作清單
- **學員資料庫 + 進度追蹤圖**:6 堂後自動產出趨勢圖(Squat 1RM 進步曲線、Bench Press 突破史)
- **行動版(LIFF / PWA)**:教練手機現場輸入,不需要回家開電腦
- **自動辨識前次 PR**:教練輸入今日 50 kg Bench,自動標「對比第 8 堂的 47.5 kg = +5%」
- **學員端查看 / 留言** App
- **自定義模板 / 教練 brand**:工作室 logo / 簽名圖,個性化品牌
- **多教練協作**:工作室共用學員資料庫,跨教練接手不掉資訊
- **餐食 / 補充劑追蹤**(可選):若教練有 sports nutrition 證照,可加飲食模組
- **報告自動排程發送**:課後 6 小時自動發給學員,不需教練手動

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 10 份免費 | 試用教練 |
| **Solo** | **NT$299 / 月** | 個人 PT,無限份 |
| **Solo+ Whisper** | NT$599 / 月 | + 語音輸入 + 進度趨勢圖 |
| **Studio** | NT$1,499 / 月 | 5 人以下小工作室,共享學員資料庫 |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 個人 PT 時薪 NT$1,500(中位)
- 課後 6-8 節 × 5 分鐘/份 = **每天 30-40 分鐘 admin × NT$1,500 = 月省 NT$11,000+**(22 工作日)
- fitlog Solo NT$299/月 vs 月省 NT$11,000 = **37x ROI**
- 對標 TrueCoach Starter NT$790/月(USD$26.34)、My PT Hub Starter NT$750/月(USD$25),fitlog NT$299 便宜 60%+

### TAM

- 全台持照 PT 約 2-3 萬人(體適能協會 + 各認證單位估算)
- 取 5% 滲透率 = 1,000 個 paying user × NT$299 = **月 NT$30 萬 MRR / 年 NT$360 萬 ARR**(solo dev 維生足夠)
- 加上瑜珈教練 / 物治復健師 / 街健教練橫移 → TAM x2-3
- 海外橫移日本(緊鄰健身大爆發中,專業 PT 急速增加)、香港 / 新馬繁中市場 → x4

## 早期 distribution

1. **FB「健身教練交流」+「肌力與體能訓練協會」社團** — 痛點來源 + 教練 KOL 密度高
2. **PTT FITNESS / Dcard 健身板** — 月底發 demo 影片,觸達自由接案 PT
3. **體適能協會 (CTSCA / CSCS) 持照訓練營** — 新進 PT 最缺工具,願意嘗試
4. **YouTube 健身 KOL 合作 demo**(肌肉爸爸、健人蓋伊、館長)— 一個影片可帶上萬曝光
5. **Threads / IG 健身教練個人帳號** — 提供「免費課表生成」當引流 magnet → 轉訂閱
6. **健身房駐店 PT 系統 BD**:World Gym / Anytime Fitness 駐店教練是大量 prosumer 用戶 — 健身房不會做但教練自己會付

最初 100 位 paying Solo = 月 NT$30,000 MRR,3 個月內達成代表 PMF 訊號到位。

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **TrueCoach 推繁中版** | 中 | 英文市場仍未飽和,繁中 ROI 不夠;先佔在地 + LINE 整合(英文工具不會做)護城河 |
| **MixFit / SportSoft 等台灣健身房 SaaS 加 AI** | 中~高 | 他們是健身房導向、銷售周期長;搶占自由接案 PT 心占率 |
| **AI 編造學員未提到的數據** | 高 | system prompt 嚴禁;測試 multi-case 確認;教練審閱 final gate |
| **PT 跨界寫醫療診斷被告** | 中 | system prompt 強制「不下診斷」措辭;報告尾段標明「如有疑慮請尋求物理治療師」 |
| **教練覺得「LINE 傳 voice memo 比較快」** | 低 | LINE 純文字版讓教練可以一鍵截圖傳 = 比 voice memo 還快 + 學員留存 |
| **個資與學員生理數據** | 中 | 不長期儲存(stateless API call);企業版可走 self-host LLM |

---

*第十一輪在 2026-05-10 產出於 incubator(台灣優先,健身教練 vertical — 跟前 10 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B / 長照 / 法律 / 獸醫 / 月報 都不同)。*
