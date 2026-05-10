# snaporder(揪單 AI)

**台灣 LINE 團媽自動整單工具 — 群組對話 / 截圖 → 30 秒整出彙整表 + LINE 對帳訊息。**

把每月團媽花 2-4 小時手動把 LINE 訊息一筆筆複製到 Excel 的痛點,壓到 30 秒。

---

## 痛點

台灣 LINE 群組團購是日常,**團媽** 是這個生態的核心節點:每個月主辦 8-15 次私人揪團、靠人工把群組訊息一筆筆抄到 Excel。

> **「每次收完訂單要花 2-4 小時一筆筆複製貼到 Excel,錯誤率高,數量搞混就要自己賠。」** — Dcard 媽媽版常見抱怨

> **「同一個人在群組講了三次,有時候是改數量、有時候是追加,我整個人都要瘋了。」** — FB 主婦團購社團

> **「最後對帳時發現少算一個人 1 盒草莓,我自己掏錢補,虧 NT$250。」** — PTT WomenTalk

具體業務上的痛:

- 1 位團媽每月平均 8-15 次團 × 每次 30-80 個訂購訊息 = **每月 240-1,200 條訊息要逐條判讀**
- 訂購格式雜亂:「+1」「我要 5 包」「@王大明 草莓 3 盒」「對不起改成 2 盒」「取消」混雜閒聊
- 每月 20-40 小時純手工時間,團媽多半免費「服務鄰居」沒收手續費 = 純成本
- 算錯一個人 = 自己賠;少算一筆 = 賣不夠;超賣 = 失信用
- 估計台灣活躍團媽 **40-100 萬人**

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼填不了這個洞 |
|----------|-------------------|
| **揪好買 / 多多團** | 走「開獨立商城電商」方向 — 要團媽放棄熟悉的 LINE 群組,換到他們的平台。團媽不會搬家。 |
| **iCHEF / foodpanda** | 餐廳 POS / 外送平台,不是個人賣家 |
| **Excel + 手工複製** | 團媽現況。每月 2-4 小時 × 8-15 次 = 痛苦 |
| **ChatGPT 直接問** | 沒有結構化聚合(set/cancel/add 邏輯)、沒有 LINE 對帳訊息產出、每次要重貼產品清單 |

**Gap 結構性**:揪好買 / 多多團追求「電商 GMV」,不會回頭做「LINE 整單」這個 last-mile 工具(自打嘴巴會把用戶留在 LINE)。沒有人有動力做這個。

## snaporder 在做什麼

```
LINE 群組 30+ 條訊息(各種訂購格式 + 閒聊干擾)
  - "我要 5 包辛辣麵 + 1 盒草莓"
  - "+2 辛辣麵"
  - "對不起 草莓改成 2 盒"
  - "取消我之前的辛辣麵"
  - "老公那包不要了"
        │
        ▼
  Claude 解析(產品清單 grounding)
  → 結構化 OrderEvent 清單 [buyer, item, qty, action: add/set/cancel]
        │
        ▼
  ┌──────────────────────────────────┐
  │ aggregator.py 純函式聚合           │
  │  - add: 該買家該品項累加           │
  │  - set: 覆寫(處理「改成 N 個」)   │
  │  - cancel: 設為 0                 │
  │  - 過濾全部取消的買家              │
  │  - 計算每買家小計、品項總數、總金額 │
  └────────────────┬─────────────────┘
                   │
                   ▼
        ① markdown 彙整表(賣家對帳)
        ② LINE 對帳訊息(@每位買家,複製貼回群組)
```

3 個關鍵架構決策:

1. **`aggregator.py` 純函式聚合**:訂單合併與金額計算 100% 純函式。LLM 永不算錢,避免幻覺漏單。
2. **三種 action 區分**:`add` / `set` / `cancel`,精確處理「改數量」「取消」這類團購群組常見模糊語言。
3. **Skipped 事件透明標記**:LLM 可能把「我要 1 杯珍奶」這種不在產品清單的訂單仍輸出,純函式聚合會跳過並列在「⚠️ 未匹配到產品的訊息」section 給賣家手動審核。不會「靜默漏單」。

## 動作

### 結構化 JSON 輸入(免 API key)

```bash
python3 snaporder.py samples/sample_structured.json
```

`samples/sample_structured.json` 已預先解析好 17 筆 OrderEvent(來自 30 行 LINE 群組對話)。輸出完整彙整表 + 5 位買家的 LINE 對帳訊息。

### 自由文字 LINE 對話輸入(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 snaporder.py \
    --chat samples/sample_chat.txt \
    --products samples/products.json \
    --out output.md \
    --out-line line_replies.md
```

Claude 解析 30 行 LINE 群組對話(含閒聊「老闆我可以晚一點付款嗎」「LINE Pay 收到」「下次團購」等干擾文字),只抽出實際訂購事件。每團 API 成本約 NT$1。

### 預先產出的 demo

`examples/sample_output.md` 是完整彙整(全團統計 + 5 位買家明細 + skipped events 區),`examples/sample_line_replies.md` 是 5 條可直接複製貼到 LINE 的對帳訊息。

從預先產出可看到:
- **辛辣麵 18 包 × NT$100 + 草莓 14 盒 × NT$250 + 八寶粥 9 罐 × NT$35 = NT$5,615 全團**
- **5 位買家(阿美 / 小薇 / 阿欣 / 嘉媽 / 新人小姐)各自小計準確**
- **嘉媽老公的辛辣麵**:add 1 → cancel 0 結果正確過濾
- **阿美、嘉媽、阿欣 的草莓「改成 N 盒」**:set action 正確覆寫前面 add 累計

## 已驗證 smoke test

- ✅ Sample 30 條訊息 → 18 辛辣麵 / 14 草莓 / 9 八寶粥 = NT$5,615 全團
- ✅ Ghost cancel:沒下過單的人說「取消」→ 不影響其他人(現實常見:小華從沒下過單卻說「取消我之前的」)
- ✅ Set 覆寫前面 add:阿美草莓 1→2、嘉媽 3→4、阿欣 3→5 (set action) 全部正確
- ✅ 全部取消的買家自動從買家清單過濾
- ✅ 不在產品清單的品項自動列入「skipped events」section 不靜默漏單
- ✅ 負數量自動 clamp 到 0

## 專案結構

```
snaporder/
├── README.md
├── snaporder.py            # CLI 主程式(--out 彙整 + --out-line 對帳)
├── aggregator.py           # 純函式聚合 + markdown 渲染
├── samples/
│   ├── sample_chat.txt          # 30 行 LINE 群組對話(含閒聊)
│   ├── products.json            # 產品清單 + 單價
│   └── sample_structured.json   # 預先解析的 17 筆 OrderEvent
├── examples/
│   ├── sample_output.md         # 預先產出的彙整表
│   └── sample_line_replies.md   # 預先產出的 LINE 對帳訊息
└── requirements.txt
```

總計約 350 行 Python。依賴僅 `anthropic`(--chat 模式才需要)。

## 真正產品要有但 prototype 沒做

- **真正的 LINE Bot**:團媽轉發 LINE 截圖到 Bot → 自動整單 → 推回彙整 PDF
- **GPT-4o vision 真截圖 OCR**:不只純文字,接受截圖直接抽訂單
- **多次團追蹤**:同一團媽 6 個月歷史 → 識別熟客 / 流失客 / 忘記付款客
- **付款追蹤**:對帳訊息發出後,LINE Pay / 街口 / 轉帳收款 → 自動 mark 已付款
- **Google Sheets 整合**:輸出直接寫入賣家的 Google Sheet 而不是 markdown
- **斷貨提醒**:某品項數量超過供應上限 → 自動告知後續訂購者「已賣完」
- **賣家端品項管理**:不必每次重打產品清單,從歷史團模板帶
- **多語言**:外籍配偶 / 港僑社群也用 LINE 團購
- **印刷出貨單**:配合本地超商寄送 / 親送,自動產出每位買家的取貨清單

## 商業模式

| 方案 | 月費 | 對象 |
|------|------|------|
| **Free** | 月 10 次整單 | 試用團媽 |
| **Pro** | **NT$299 / 月**(無限次) | 1 人團媽,8-15 次/月 |
| **Business** | **NT$699 / 月** | 多人協作 / 多 LINE 群組 |
| **年付** | 上方 × 10 個月 | 省 2 個月 |

### WTP 計算

- 團媽每月平均 12 次團 × 整單 3 小時 = **每月 36 小時手工**
- 即使按 NT$200/小時算 = 月省 NT$7,200 機會成本
- vs Pro NT$299/月 = **24x ROI**(實際 ROI 對團媽更高,因為這是放棄睡眠時間)

### TAM 估算

- 估計台灣活躍團媽 40-100 萬人,取保守 50 萬
- 1% 滲透 = 5,000 人 × NT$299 = **月 NT$150 萬 MRR / 年 NT$1,800 萬 ARR**
- 加上 Business 多人版 + 海外港澳 + 簡單橫移到日韓繁中 LINE 團購 → 翻倍以上

## 早期 distribution

1. **FB 大型團購社團**(「TAIWAN 媽媽團購交流」「台灣團媽聯盟」等 5-10 萬人社團)— 痛點來源即 distribution 來源
2. **Dcard 媽媽版 / WomenTalk 板** — 月底發 demo,觸達剛被「整單到崩潰」的團媽
3. **YouTube / Threads 主婦 KOL 合作 demo** — 一位媽媽 KOL 推薦可帶上萬曝光
4. **LINE 官方 Bot Store / LINE 開發者社群** — 上架後可被 LINE 用戶發現
5. **Google Ads 鎖定關鍵字「團購整單」「團媽工具」「團購記帳」**
6. **與大型團購電商 partner**(揪好買 / 多多團 退場使用者收容)— 它們導流走電商,失敗或嫌煩的賣家可轉給 snaporder

最初 100 位 paying Pro = 月 NT$30,000 MRR,1-2 個月內可達成代表 PMF 訊號到位(LINE 社群口碑傳播極快)。

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **LINE 改 API 政策禁止 Bot 接群訊息** | 中~高 | 截圖手動上傳模式可完全規避 LINE Bot API,最壞情況仍可運作 |
| **AI 解析錯誤導致漏單 / 多單** | 高 | skipped_events 透明列出 + 純函式聚合可重現 + 賣家審閱 final gate |
| **揪好買 / 多多團 推競品** | 中 | 他們電商商業模式衝突;不會自己做「鼓勵留在 LINE」的工具 |
| **AI 個資外洩(LINE 截圖含買家姓名 / 地址)** | 高 | 可走 stateless 不存資料;企業版可走 self-host LLM |
| **團媽不願付費(覺得這是免費鄰居義務)** | 中~高 | 先免費 10 次 hook,等團媽用過後感受時間節省再轉訂閱;Pro NT$299 落在衝動消費區 |
| **市場教育成本(中老年團媽對 AI 怕)** | 中 | LINE-native 操作介面降低學習門檻;影片 demo 比文字說明有效 |

---

*第十三輪在 2026-05-10 產出於 incubator(台灣優先,**第二個非 doc-gen 模式**:OCR / NLP 從多源訊息聚合)。跟前 12 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B / 長照 / 法律 / 獸醫 / 月報 / 健身 / 機車估價 都不同 vertical。*
