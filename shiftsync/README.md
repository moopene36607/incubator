# shiftsync(排班同步)

**台灣餐廳外場排班 LINE Bot 助手 — 員工用 LINE 講話,AI + 純函式規則檢查 → 立刻回覆批准/建議/拒絕。**

把店長每週 2-3 小時手排班 + 每天處理「換班 / 請假 / 加班」訊息的混亂,壓到員工發 LINE 就自動處理。

---

## 痛點

台灣 5-30 人中小餐廳店長最大時間漏斗:**處理員工 LINE 群組的排班變更**。

實際業務情境(Dcard 餐飲業 / PTT restaurant 板高頻討論模式):

> **「臨時換班用 LINE 群組通知,訊息一片混亂,常常有人沒看到 / 誤會。」**
> **「店長整理班表已經夠累,還要回覆每個換班訊息,週末還要查工時防止超過。」**
> **「員工說『跟小明換週五晚班』,我要翻群組找小明的訊息,還要自己算工時不能超過,有時候排重了沒發現。」**

具體痛點:

- 1 位店長排 6-30 員工 × 每週 1-3 個換班 / 請假請求 = 每週 6-90 條請求要處理
- 每次需查:當事人現有班表 / 對方班表 / 工時 / 法定上限 / 角色相容性 — 平均每則 5-10 分鐘
- 每月店長花 **20-40 小時 admin** 在 LINE 訊息來回,**機會成本 NT$6K-12K/月**(時薪 NT$300)
- 換班漏算造成過勞 / 缺人 / 員工抱怨,小餐廳一個排班失誤可能損失整晚生意
- **海外工具(Schedulefly / 7shifts)月費 USD$25+/店 + 全英文 + 員工要另下 app**,台灣 LINE-native 文化下幾乎沒人用

## 既有工具為什麼填不了這個洞

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **Schedulefly / 7shifts (美)** | 全英文 + 月費 USD$25+ + 員工要下 app(小店員工不會配合) |
| **Excel + LINE 群組** | 店長現況。手動算工時 / 找衝突,容易漏 |
| **ChatGPT 直接問** | 不知道你店裡的班表結構 + 每次要重貼員工資料 + 不會做 LINE 推播 |
| **本土排班 SaaS(欣河 / 商之器)** | 主打中大連鎖店,小餐廳介面複雜 + 月費高 + 仍不解決 LINE 自然語言訊息問題 |

**Gap 結構性**:台灣餐廳員工 100% 用 LINE 溝通,LINE-native 整合 + 自然語言解析是必需條件。海外工具不會做台灣 LINE,本土排班 SaaS 不做 LLM 對話介面。沒有人有動力做這個橋接層。

## shiftsync 在做什麼

```
員工 LINE 訊息(自由文字)
  - 「店長,我這週五午班想跟阿偉的週六晚班換」
  - 「我下週四晚班要請假去考試」
  - 「我這週才 12 小時,週五午班可以幫忙嗎?」
       │
       ▼
 Claude 解析 → 結構化請求 (type: swap | leave | extra)
       │
       ▼
 ┌───────────────────────────────────┐
 │ schedule_rules.py 純函式驗證       │
 │  - 班次存在性、員工角色相容        │
 │  - 同日時段重疊檢查                │
 │  - 工時上限(40h 一般 / 48h hard)│
 │  - 找代班候選(請假時)            │
 │  - 加班費警示(>40h/週)            │
 └───────────────┬───────────────────┘
                 │
                 ▼
        LINE 友善回覆訊息
        (✅ 核准 / ⚠️ 警示 / 📋 待選 / ❌ 拒絕 + 原因)
```

3 個關鍵架構決策:

1. **`schedule_rules.py` 100% 純函式驗證**:衝突檢查、工時計算、勞基法上限、代班搜尋全部不靠 LLM。LLM 永不負責「能不能換」這個判斷,避免對工時 / 法規 hallucination。
2. **AI 只負責語意解析 + 訊息措辭**:從台灣口語「我跟小明換週五晚班」抽結構化資料(swap_target, swap_my_shift_id, swap_their_shift_id),以及把 ApprovalResult 翻成人性化 LINE 回覆。
3. **三類請求統一介面**(swap / leave / extra):每類有自己的 ApprovalResult 結構,規則檢查可單元測試 + 可單獨擴充新規則(例:夜班強制間隔 11 小時休息)。

## 動作

### 結構化 JSON 輸入(免 API key)

```bash
python3 shiftsync.py \
    --schedule samples/initial_schedule.json \
    --request samples/structured_requests.json
```

`samples/initial_schedule.json` 是 8 員工 × 35 班次的微光咖啡食堂本週班表。`samples/structured_requests.json` 包含 5 個請求 case(換班 / 請假 / 加班 / 角色衝突 / 已被佔用班次)。

### 自由文字 LINE 訊息輸入(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 shiftsync.py \
    --schedule samples/initial_schedule.json \
    --line-text samples/sample_requests.txt \
    --out output.md
```

每行一則 LINE 訊息。Claude 自動分類成 swap / leave / extra,然後丟給純函式驗證。

### 預先產出的 demo

`examples/sample_output.md` 是 5 個請求的完整處理流程,展示:
- ✅ Request 4(大雄 ↔ 阿成 週三 swap):同角色 / 工時不變 → 直接核准
- ❌ Request 1(小華 ↔ 阿偉 週五午 ↔ 週六晚):**抓出小華原本就在週六晚已有班(SAT_DINNER_2),換班會造成同日 17:00-21:00 重疊**
- 📋 Request 2(小君 週四晚請假):找出 4 位可代班候選人(小華 / 小芳 / 阿偉 / 阿美),自動排除衝突或角色不符的人
- ❌ Request 3(阿美 加班 FRI_LUNCH):該班已有人,自動建議走換班流程
- ❌ Request 5(店長加班 TUE_LUNCH):同上

## 已驗證 smoke test

- ✅ Sample 5 case 處理結果合理(approved / rejected / needs_replacement 分類正確)
- ✅ 同日時段重疊偵測正確識別 SAT_DINNER + SAT_DINNER_2 衝突(11:00-15:00 vs 17:00-21:00 不算,但 17:00-21:00 vs 17:00-21:00 算)
- ✅ Bug fix: 重疊訊息原本會重複輸出 — 改用 `set(days)` 去重 + 帶 shift_id 細節
- ✅ 5 個 edge case 全過:乾淨換班、重疊偵測、無人代班、加班超 hard limit、班次已被佔用

## 專案結構

```
shiftsync/
├── README.md
├── shiftsync.py            # CLI 主程式(LLM 解析 + 純函式驗證 + 訊息產出)
├── schedule_rules.py       # 純函式排班規則(換班 / 請假 / 加班 三類驗證)
├── samples/
│   ├── initial_schedule.json    # 8 員工 × 35 班次的微光咖啡食堂本週班表
│   └── structured_requests.json # 5 個 case(swap / leave / extra / 衝突)
├── examples/
│   └── sample_output.md         # 預先產出的處理結果
└── requirements.txt
```

總計約 450 行 Python。依賴僅 `anthropic`(自由文字模式才需要)。

## 真正產品要有但 prototype 沒做

- **真正的 LINE Bot**:接 LINE Messaging API,員工發 LINE → Bot 直接回覆;店長 dashboard 看歷史請求 / 修改決議
- **OCR / Vision 班表**:店長拍 Excel 班表 → vision 解析成結構;不必手 key
- **初始排班最佳化**:目前只處理「變更」,不做「從零自動排班」 — 真實產品要 OR-tools / constraint solver(技能配對 / 公平分配 / 員工偏好)
- **法定加班費自動計算**:勞基法第 24 條(週工時 40+):前 2 小時 +1/3、後續 +2/3;假日工時另計
- **多分店總部視圖**:連鎖餐廳老闆看所有分店班表 + 跨店支援
- **員工偏好持久化**:阿美「只能週末早班」是長期條件,自動套用而非每次提
- **預警式提醒**:某員工本週 38h,自動警示「再加 1 班會進入加班費計算」
- **歷史分析**:換班最多的員工 / 最常請假的時段 → 老闆看趨勢
- **角色擴充 / 技能矩陣**:咖啡師等級 / 收銀許可 / 過敏訓練 等多維技能標籤

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 6 員工以下 + 月 30 個請求 | 試用 / 微型店 |
| **Solo** | **NT$499 / 月** | 6-15 員工的小餐廳 |
| **Pro** | NT$1,499 / 月 | 15-50 員工 + 多分店 + 加班費自動計算 |
| **Enterprise** | 客製 | 連鎖餐廳 / 中大型集團 |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 店長每週排班 + 處理變更 2-3 小時 × NT$300/hr × 4 週 = **月省 NT$2,400-3,600 機會成本**
- 1 次排班漏算造成晚班缺人 = 損失 NT$5K-15K 營收
- vs Solo NT$499/月 = **5-7x ROI**

### TAM

- 全台餐飲業約 17 萬家,5-30 員工規模佔 50% = ~85,000 家
- 取 2% 滲透率 = 1,700 家 × NT$499 = **月 NT$85 萬 MRR / 年 NT$1,020 萬 ARR**(solo dev 維生綽綽有餘)
- 加 Pro 中型餐廳 + Enterprise 連鎖 + 橫移到日本 / 韓國繁中 LINE 餐廳市場 → 翻倍

## 早期 distribution

1. **FB 餐飲老闆社群**(「台灣餐飲業老闆」「餐廳經營者交流」5-10 萬人社團)— 痛點來源 + 直接觸達決策者
2. **PTT restaurant / Dcard 餐飲業 / job 板** — 排班痛點討論底下發 demo 影片
3. **LINE 官方帳號 Bot Marketplace** — 上架後可被 LINE 用戶發現
4. **連鎖餐飲集團 BD**(瓦城 / 王品 / 鼎泰豐分店店長)— 大客戶單一 BD 拿下 = 多分店一次入帳
5. **餐飲設備商 + POS 廠商 partner**(iCHEF / 沛點)— 他們服務店家 onboarding 時順便推 shiftsync
6. **YouTube / Threads 餐飲 KOL 合作**(餐飲老媽 / 開店達人)— 一個影片可帶上萬曝光

最初 100 家 paying Solo = 月 NT$50,000 MRR,3-6 個月內可達成代表 PMF 訊號到位。

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **LINE 改 API 政策** | 中 | 先做網頁版 Web App,LINE 整合是 add-on;最壞情況仍可運作 |
| **AI 解析錯誤導致誤批/拒** | 高 | 規則檢查 100% 純函式 → AI 只解析自然語言,最後決議由規則決定;店長有最終覆核權 |
| **連鎖餐廳已有 in-house POS 排班** | 中 | 大連鎖會自建,我們攻 1-15 員工小餐廳市場 |
| **iCHEF / 沛點 加 AI 排班** | 中 | 他們是 POS 廠,排班是邊緣功能;搶占小餐廳心占率 |
| **店長覺得「LINE 群組不就好了」** | 中~高 | 提供 free tier 6 員工以下,讓店長體會 30 員工後 LINE 群組失控的痛點 |
| **AI 對台灣口語 / 台語不熟** | 中 | system prompt 用大量台灣餐飲術語 few-shot;測 100+ 案例修 prompt |
| **個資 / 員工資料外洩** | 中 | stateless API call(不存員工資料);企業版可走 self-host LLM |

---

*第十五輪在 2026-05-10 產出於 incubator(台灣優先,**第四個非 doc-gen 模式 — Scheduling 最佳化 + LINE bot 對話流程**)。跟前 14 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B 稅 / 長照 / 法律 / 獸醫 / 月報 / 健身 / 機車估價 / LINE 整單 / 補助 RAG 都不同 vertical 也不同架構。*
