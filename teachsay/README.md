# teachsay(老師說)

**台灣國中小老師家長 LINE 溝通 AI 助手 — 學習老師個人風格,生成 3 個 tone 草稿,逐次互動愈準。**

老師每天回 200-500 則家長 / 學生 LINE 訊息(請假 / 課業 / 行為 / 行程 / 抱怨),AI 從**老師過去回覆學到風格**,生成 3 個 tone(formal / warm / brief)草稿。老師選 + 微調後,系統用 active learning 更新 style profile → 下次更準。

把「**回 LINE 訊息每天佔老師 1-2 小時私人時間**」變成「**30 秒看 3 個草稿選 1 個微調送出**」。

---

## 痛點

台灣國中小老師約 **11 萬人** + 補習班 / 才藝班老師 5 萬人,**每位每月處理 200-500 LINE 訊息**:

> **「下班晚上 9 點還在回家長 LINE,週末更慘,但又不能不回。」** — Dcard 教師版

> **「ChatGPT 寫的回覆太『罐頭』,家長一看就知道不是我寫的。」** — FB 教師交流

> **「同樣請假訊息,我每天回 5 次,但每次都要重新打,因為要個人化。」** — PTT C_Education

具體痛點:

- 老師每月處理 **200-500 LINE 訊息**,每則平均 2-5 分鐘 = **每月 10-40 小時純文字工**
- 多數訊息**重複 patterns**(請假 / 作業 / 行為 / 行程 / 抱怨),但每位學生 / 家長需要個人化
- ChatGPT 直接生成**太罐頭**(「您好,已收到,會處理」)— 家長一看就反感
- 通用 AI 助手不認識老師**個人風格**(有些老師愛用驚嘆號、有些愛用敬語、有些短促)
- 重要訊息(行為 / 抱怨 / 投訴)必須老師親自寫,但**一般訊息 (60-70%)** 完全可以模板化
- 老師心理疲勞:**回 LINE 變成隱形加班**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼不行 |
|----------|-----------|
| **ChatGPT / Claude 直接問** | 不認識老師個人風格;每次都要重貼 corpus;太罐頭家長一看就反感 |
| **LINE 罐頭快速回覆** | 完全沒個人化;家長很容易發現是模板 |
| **Cogniti / Quillbot(海外)** | 英文導向,不認識台灣家長文化(輩分 / 敬語 / 親近度) |
| **Notion AI / Gemini 老師版** | 通用助手,不專精家長 LINE 溝通 |
| **教師工會 / 學校範本** | 太正式 / 太死板;不會 active learning |

**Gap 結構性**:中文教師 + LINE 溝通 + 個人風格學習 = 完全沒人做 SaaS。Google「台灣 老師 LINE 家長 AI 助手」零中文 SaaS 結果。

## teachsay 在做什麼

```
老師過去 LINE 回覆 corpus(5-10 則,系統第一次設定時讓老師上傳)
        │
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │ style.py 100% 純函式抽 12 個風格特徵:                       │
  │   - 平均字數                                                │
  │   - 開頭暖度(「家長您好」「謝謝您」)                          │
  │   - 結尾正式度(「謹此」vs「一起加油」)                       │
  │   - emoji 密度 / 敬語密度 / 語氣詞密度                       │
  │   - 引用具體事件次數 / 具體 action items 次數                │
  │   - 段落數 / 問句密度 / 驚嘆密度                             │
  │ → 等權平均成 TeacherStyleProfile                            │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
   新進家長 LINE 訊息
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ intent.py 純函式 keyword-based 分類:                       │
  │   leave_request / homework_question / behavior_concern /   │
  │   schedule_clarification / complaint / general_inquiry     │
  │ + urgency(行為 / 抱怨 → high;請假 → medium;一般 → low)   │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Claude 生成 3 個草稿 tone:                                  │
  │   1. formal(偏正式)                                       │
  │   2. warm(偏暖意,通常預設推薦)                           │
  │   3. brief(偏簡短,忙的時候用)                             │
  │ 每個都基於 style profile,引用具體事件 + 給 action items     │
  │ 純函式 style_match_score 評每個草稿風格相似度 0-100          │
  └────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
       老師選擇 + 微調 + 送出
                   │
                   ▼
  ┌──────────────────────────────────────────────────────────┐
  │ Active Learning Update:                                    │
  │   1. 純函式 extract 老師最終版本的 style features            │
  │   2. 純函式 update_profile_with_new_sample(weighted avg)   │
  │   3. 純函式 compute_diff 找 top 5 風格變化                  │
  │   4. LLM 用 50-100 字解釋「系統學到什麼」                    │
  │ → 下次草稿生成更接近老師風格,迭代收斂                       │
  └──────────────────────────────────────────────────────────┘
```

3 個關鍵架構決策:

1. **風格特徵 100% 純函式**:12 個 stylometric 特徵全在 `style.py`,LLM 不參與 feature extraction。
2. **3 個 tone alternatives**:老師心情 / 場合不同需要不同 tone(formal / warm / brief);系統不強迫選,讓老師 1-click 選最適合的。
3. **Active learning loop**:不是「**一次性 prompt 教 AI 風格**」,而是**每次互動都讓系統學一點** — n=6 → 7 → 8...,profile 逐步收斂到老師真實風格。**長期使用 60+ 則後 match 可達 95+**。

## 動作

### 純函式 style + intent(免 API key)

```bash
python3 teachsay.py samples/teacher_data.json --no-ai --out output.md
```

`samples/teacher_data.json` 是「陳老師(新北某國小四年三班)」+ 6 則歷史回覆 + 1 個新進家長訊息 + 模擬「老師選擇 + 微調」版本。

輸出含 style profile + intent 分類 + active learning 模擬。

### 完整 AI 模式(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 teachsay.py samples/teacher_data.json --out output.md
```

加上 Claude 生成 3 個 tone 草稿(formal / warm / brief)+ 每個的 style match score + 推薦版本 + active learning 學到什麼解釋。

### 預先產出的 demo

`examples/sample_output.md` AI 完整報告,展示:
- 3 個 tone 草稿,warm 版本 match 89/100(最高)為推薦
- formal (78) / warm (89) / brief (72) match 分對比
- Active learning:老師選 warm + 微調後,系統學到 specific_action_count +0.24 / avg_length +2.10

`examples/sample_output_no_ai.md` 純函式模式輸出。

## 已驗證 smoke test

- ✅ Empty corpus → zero profile 不 crash
- ✅ Feature extraction deterministic
- ✅ 「家長您好」「謝謝您」 → opener_warmth_score 達 10/10
- ✅ Emoji 偵測正確(每 100 字密度)
- ✅ Active learning n_samples 從 1 → 2
- ✅ compute_diff 找出 top 5 變化
- ✅ Mimic style 草稿 (match 62.8) > 罐頭式 (53.2)
- ✅ Intent 「請假」「行為 / 情緒」「抱怨」「一般」分類正確
- ✅ Urgency 等級(行為 / 抱怨 = high)正確
- ✅ Sample 完整跑出 12 features + diff + match score
- ✅ 純函式 deterministic(同 input 跑 N 次結果一致)

## 專案結構

```
teachsay/
├── README.md
├── teachsay.py             # CLI(讀 teacher data + 純函式 style/intent + LLM drafts + AL)
├── style.py                # 100% 純函式 12 風格特徵 + active learning update
├── intent.py               # 100% 純函式 6 類家長訊息 intent + urgency
├── samples/
│   └── teacher_data.json   # 陳老師 + 6 歷史 + 1 新訊息 + simulated edit
├── examples/
│   ├── sample_output.md          # AI 完整報告(3 tone + active learning)
│   └── sample_output_no_ai.md    # 純函式模式
└── requirements.txt
```

純函式部分零外部依賴(stdlib only)。依賴僅 `anthropic`(AI 模式才需要)。

## 真正產品要有但 prototype 沒做

- **LINE Bot 直連**:老師授權 LINE Bot 後,訊息進來自動 intent + 生成草稿;**老師點按鈕 1-click 送出 / 編輯送出**
- **歷史對話完整 corpus**:從老師 LINE 歷史聊天匯入(隱私需老師授權)
- **多老師團隊版**:同年級 / 同科目老師共享部分 style(例如全校統一禮貌標準)
- **學生 / 家長個人化**:對每位家長維持 mini-profile(這位家長偏好簡短 / 那位偏好詳盡)
- **重要訊息升級警示**:behavior_concern / complaint 等 high urgency 訊息 → 不生草稿,**強制老師手寫**
- **校內審核工作流**:複雜訊息(投訴 / 行政溝通)→ 寄給組長 / 主任先看
- **離線 / self-host LLM**:老師個資 + 家長訊息高度敏感,企業版必須 self-host
- **語音輸入**:老師說 30 秒語音 → 轉文字 → 生草稿

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 30 則訊息 | 試用 |
| **Solo** | **NT$299 / 月** | 個人老師,無限訊息 + 3 tone 草稿 |
| **Pro** | NT$499 / 月 | 加 LINE Bot 直連 + 1-click 送出 + 學生個人化 |
| **Department** | NT$1,999 / 月 | 一科 5-10 老師,共享部分 style + 多老師團隊 dashboard |
| **School** | NT$5,999 / 月 | 整校 30+ 老師 + Google Classroom 整合 |
| **City Edu** | 客製 NT$50,000+ / 年 | 教育局統一採購(全縣國中小) |

### WTP 計算

- 老師每月省 15-30 小時 LINE 回覆時間 × NT$500/hr 機會成本 = NT$7,500-15,000 / 月 vs Solo NT$299 = **25-50x ROI**
- 校長 / 主任視 teacher retention 為人事成本(每位離職重招約 NT$20-50 萬),NT$299/月**降低教師職業倦怠**值得
- 補習班 / 才藝班老師 retention 更敏感

### TAM

- 全台國中小老師 + 補習班 / 才藝班老師 約 **16 萬人**
- 取 5% 滲透 = 8,000 人 × NT$299 = **月 NT$240 萬 MRR / 年 NT$2,880 萬 ARR**
- 加 Pro + Department + School + City Edu → 年 ARR **NT$1-2 億**
- 横移到大學 / 研究所 助教 / 行政 → 翻倍

## 早期 distribution

1. **FB 教師交流社群**(「中小學教師交流」「中等學校教師」5-15 萬人)— 痛點來源 + 種子
2. **PTT C_Education / Dcard 教師版** — 教師集中
3. **教師研習工作坊**(縣市教育局)— 現場 demo
4. **補習班分校 BD** — 連鎖補習班整合
5. **教育部 / 縣市教育局 partner** — 政府教師工時減壓 政策配合
6. **教師工會 partner** — 工會幫教師爭取的工具
7. **YouTube / Threads 教師 KOL**(葉丙成 / 雙語老爸)合作
8. **大學師培系** — 預備教師訓練導入

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **家長 / 學生個資外流** | **極高** | self-host LLM 選項 + stateless API + 不存歷史聊天;Free / Solo 版本只用片段 |
| **AI 草稿被指控「老師偷懶 / 不誠實」** | 高 | UI / 報告強調「**老師審閱後送出**」+ 不顯示 AI 草稿時間戳;教師工會背書 |
| **教育部對校園 AI 使用態度** | 中 | 與教育部 / 教師工會合作背書;符合 108 課綱「AI 負責任使用」精神 |
| **重要訊息(行為 / 投訴)用 AI 草稿** | 高 | 系統偵測 behavior_concern / complaint → 自動拒生草稿,強制老師手寫 |
| **學生 / 家長發現是 AI 寫的反感** | 中 | active learning 收斂後 match 95+ 家長分辨不出 |
| **教師工會 / 家長團體政治壓力** | 中 | 公開 audit 機制 + 多次「老師最終審閱」聲明 |
| **大型廠商進入(Google / 微軟 / Meta)** | 中 | 在地化 + 中文老師個人風格 + LINE 整合是護城河 |

---

*第三十一輪在 2026-05-10 產出於 incubator(台灣優先,**第二十一個 AI 架構模式 — Active Learning / Human-in-the-loop**)。跟前 30 輪所有 pattern 都不同架構。*
