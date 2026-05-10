# motoval

**台灣二手機車 AI 估價助手 — 自然語言車況描述 → 30 秒估值 + 議價建議。**

把「我的 Force 155 2021 年型 7 萬公里,完整保養手冊,輕微漆面刮傷」變成「自售合理價 NT$ 37,500 ~ 50,500、車行收購 NT$ 28,500 ~ 35,500、急售底價 NT$ 37,400」這份完整估價報告。

---

## 痛點

台灣每年二手機車交易量約 **60 萬台**,但賣家最常見的問題是 **「我這台車到底值多少?」**

> **「我的 Force 155 2021 年型 7 萬公里,合理售價大概多少?」** — PTT biker 板每週數篇詢價貼文

> **「家裡的車要賣掉,完全不知道開價多少才合理,問車行又怕被坑。」** — Dcard 機車版常見

> **27 萬成員**的 FB「台灣二手機車買賣」社團,每天上百篇詢價貼文,沒有結構化答案。

具體痛點:

- **賣家**:不知開多少 → 開太高乏人問津 / 開太低被車行賺走利潤
- **車行**:每月接 10-50 台估價,要快速報收購價,目前靠老闆心算 + 經驗
- **買家**:看到一台想下手但怕被坑,沒有客觀第二意見可參考
- **海外工具不通用**:Kelley Blue Book 等英美汽車估價工具不做台灣機車;台灣車款(Force 155 / DRG / 新勁戰)海外查無資料

## 為什麼現在沒有對的工具

| 既有工具 | 為什麼填不了這個洞 |
|----------|-------------------|
| **8891 / U-CAR** | 主打汽車,機車交易頁是 listing 而已,**完全沒有估價功能** |
| **Yahoo 拍賣 / 露天** | 只有 listing,沒有「給定車況推估價」 |
| **車行老闆心算** | 一家一個價,賣家無法 cross-check |
| **PTT / FB 社團詢問** | 大家給意見差距 NT$10K+,沒有客觀依據 |
| **Kelley Blue Book / Edmunds** | 英美工具,不認得台灣機車車款 |

**Gap 結構性**:台灣機車市場 60 萬台年交易、車款高度在地化(光陽 / 三陽 / Yamaha 台規 / Gogoro)、市場規模對 Kelley Blue Book 級玩家太小不值得做、本土 SaaS 又沒有這個 vertical。是 niche 中的 niche。

## motoval 在做什麼

```
自然語言車況描述                結構化 JSON
("我的 Force 155 2021              {model_code, year,
 跑了 7 萬,完整保養手冊...")        mileage, condition,
                                   adjustments[]}
       │                              │
       ▼                              │
  Claude 解析為結構化 ──────────────┘
                                      │
                                      ▼
                  ┌──────────────────────────────────┐
                  │ pricing.py 純函式估價              │
                  │  1. MSRP × (1 - dep_rate)^age     │
                  │  2. × mileage_factor (預期 vs 實際)│
                  │  3. × condition_multiplier         │
                  │  4. × (1 + Σ 細項加減分)            │
                  │  5. cap @ MSRP × 0.95             │
                  │  6. 區間 ±15%                     │
                  └────────────────┬─────────────────┘
                                   │
                                   ▼
                估價報告 markdown:
                  - 自售合理價區間
                  - 車行收購價區間 (扣 20-25% 利潤)
                  - 急售底價
                  - 折舊明細表 (5 步驟可追溯)
                  - 細項加減分 (透明)
                  - 議價建議
```

3 個關鍵架構決策:

1. **`motorcycle_db.py` 純資料**:12 個常見車款 × MSRP × 年折舊率 × 預期年里程 × 車況等級係數 × 13 個加減分項目。產品化會擴充至 200+ 車款 + 接 8891/露天/監理所實際成交資料動態 update。
2. **數字計算 100% 純函式**:估價演算法在 `pricing.py`,從不交給 LLM。AI 不會憑空編造價格 — 它只解析自由文字,實際計算靠透明可追溯的公式。
3. **Sanity cap @ MSRP × 0.95**:即使近新、單一車主、保養完美的二手車,估值也不會超過 MSRP 的 95% — 因為買家寧可付差價買新車 + 原廠保固。這個 cap 防止極端 case 報出荒謬高價。

## 動作

### 結構化 JSON 輸入(免 API key)

```bash
python3 motoval.py samples/sample_input.json
```

`samples/sample_input.json` 是 KYMCO Force 155 2021 / 7 萬 km / 良好車況 + 6 個加減分項目。輸出完整估價報告。

### 自由文字描述輸入(需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 motoval.py --freetext samples/sample_input_freetext.txt
```

Claude 從自然語言「我的 Force 155 2021 跑了 7 萬,完整保養手冊...」抽取結構化 JSON,然後走同一套 pricing。每次 API 成本約 NT$0.5。

### 預先產出的 demo

`examples/sample_output.md` 是完整估價報告 — 可直接看出:
- 自售區間 NT$37,500–50,500、中位 NT$44,000
- 車行收購 NT$28,500–35,500
- 5 步驟折舊明細(MSRP NT$93,500 → 5 年折舊 NT$55,000 → 里程 ×0.775 → NT$43,000 → 車況 ×1.0 → 細項 +3% → NT$44,000)
- 細項加減分透明列出(✓ 單一車主 / 完整保養 / 原廠保養 / 新胎 vs ✗ 漆面刮傷 / 高里程)

## 已驗證 smoke test

- ✅ 標準 case:Force 155 2021 / 7 萬 km / good → NT$44,000(中位)
- ✅ 近新車 sanity cap:Force 155 2025 / 2,000 km / excellent → NT$89,000(<= MSRP × 0.95 NT$88,825)
- ✅ 高里程差車況:Force 155 2018 / 12 萬 km / poor → NT$13,500(合理低估)
- ✅ 泡水車:BWS R 125 + flooded + accident → -30% 累積上限 cap 套用
- ✅ Edge case raises:未來年份 / 無效車況 → ValueError

## 收錄車款 (prototype seed,12 款)

| 代碼 | 車款 | 排氣量 | MSRP |
|------|------|------:|------:|
| KYMCO_FORCE_155 | 光陽 Force 155 | 155 cc | NT$93,500 |
| KYMCO_LIKE_125 | 光陽 Like 125 | 125 cc | NT$75,500 |
| KYMCO_RACING_S150 | 光陽 Racing S 150 | 150 cc | NT$89,800 |
| SYM_DRG_BT_158 | 三陽 DRG BT | 158 cc | NT$92,800 |
| SYM_JET_SR_125 | 三陽 Jet SR | 125 cc | NT$73,900 |
| SYM_MMBCU_158 | 三陽 MMBCU | 158 cc | NT$99,800 |
| YAMAHA_BWS_R_125 | Yamaha BWS R | 125 cc | NT$81,500 |
| YAMAHA_CYGNUS_125 | 新勁戰 Cygnus | 125 cc | NT$79,500 |
| YAMAHA_SMAX_155 | Yamaha SMAX | 155 cc | NT$96,900 |
| HONDA_PCX_160 | Honda PCX | 160 cc | NT$109,000 |
| HONDA_FORZA_350 | Honda Forza | 350 cc | NT$235,000 |
| GOGORO_VIVA_MIX | Gogoro VIVA MIX | 電動 | NT$65,980 |

(實際產品需擴充至 200+ 涵蓋舊機車如野狼 / 重機進口 / 二代戰 / Gogoro 1/2/3 全系列等。)

## 專案結構

```
motoval/
├── README.md
├── motoval.py            # CLI 主程式
├── motorcycle_db.py      # 12 車款 + 加減分係數 seed dictionary
├── pricing.py            # 純函式估價邏輯 (公式 + sanity cap)
├── samples/
│   ├── sample_input.json         # 結構化 Force 155 案例
│   └── sample_input_freetext.txt # 自然語言版同一台車
├── examples/
│   └── sample_output.md  # 預先產出的估價報告
└── requirements.txt
```

總計約 380 行 Python。依賴僅 `anthropic`(自由文字模式才需要)。

## 真正產品要有但 prototype 沒做

- **Vision 估價**:用戶拍正側兩張照,GPT-4o vision 自動辨識車款 / 年份 / 損傷面積 — 不需打字
- **接實際成交資料庫**:爬 8891 / 露天 / Yahoo / 監理所過戶資料,pricing model 從靜態係數變動態
- **季節性供需 / 地區係數**:北部、中南部、東部估值差異(東部車源少售價高)
- **完整 200+ 車款**:目前 12 款只覆蓋 70% 主流;水冷重機、舊野狼、Gogoro 全系列要補
- **車主端分享圖**:一鍵產出 IG / FB 社團可分享圖卡(車況 + 估值 + QR code)
- **車行端批次估價**:車行老闆每天估 10-50 台,單張 form 太慢;要 CSV 批次 + 搜尋功能
- **保險月剩餘額計算 + 過戶費試算**:報告含「實際成交可拿 / 要付」明細
- **改裝車 / 水貨車 / 競品車** 估值
- **歷史走勢追蹤**:同車款近 6 個月成交價趨勢圖

## 商業模式

| 方案 | 價格 | 對象 |
|------|------|------|
| **Free** | 月 1 次估價 | 一般網友 |
| **B2C 估價** | **NT$49 / 次** | 想賣機車 / 看車前評估的個人 |
| **B2C 月會員** | NT$199 / 月(無限次) | 重度買賣的個人 |
| **B2B 車行** | **NT$799 / 月** | 二手車行(無限次 + 批次估價) |
| **B2B 連鎖** | NT$2,499 / 月 | 5+ 分店 |
| **API access** | NT$0.5 / call | 第三方平台 (8891 / 拍賣網) |

### WTP

- **B2C**:NT$49 vs 開錯 NT$5,000 = 100x 保險,衝動消費價位
- **B2B 車行**:車行老闆每月 30 台估價,一台估錯收太貴 / 賣太便宜 NT$2,000+ = 月費一次回本

### TAM 估算

- 60 萬台年交易 × 5% 估價滲透 = **3 萬次/年 × NT$49 = NT$147 萬/年(B2C)**
- 全台二手機車行約 2,000 家 × 10% 訂閱 = 200 家 × NT$799 = **月 NT$16 萬 MRR / 年 NT$192 萬 ARR(B2B)**
- 加 API access 給 8891 / Yahoo / 露天:潛在 enterprise 月費 NT$10–30 萬

合計 ARR 天花板 ~NT$1,000 萬,solo dev 維生綽綽有餘。

## 早期 distribution

1. **PTT biker 板 + Dcard 機車版** — 詢價發文底下回覆「我做了個工具,30 秒估給你看」
2. **FB「台灣二手機車買賣」27 萬成員社團** — 痛點來源即 distribution 來源
3. **YouTube 機車 KOL 合作 demo**(老吳 / Apex / 老查 / 大鳥車)— 一個影片可帶上萬曝光
4. **8891 / 露天 listing 頁面 SEO**:長尾「Force 155 2021 二手價」「DRG 158 估價」抓自然流量
5. **二手車行直接 BD**:中正路、五分埔等車行密集區實地拜訪
6. **保險業務員合作**:很多保險業務員會幫客人估賣車後保險退費,把 motoval 當送禮工具

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **8891 推官方估價** | 中 | 8891 過去 5 年沒做,可能是商業考量(買家賣家利益衝突);搶在他們前面建用戶心占率 |
| **AI 解析自由文字錯誤導致估值錯** | 中 | system prompt 嚴格 white-list 車款代碼;LLM 解析後仍經結構化 schema 驗證;最後估值有 sanity cap |
| **MSRP / 折舊率不準** | 中~高 | 純資料設計易更新;產品化要接實際成交資料動態 update |
| **政府接案保險險種變動** | 低 | 報告有「估值不含保險月剩餘額」免責 |
| **車行不願付費(我自己會估)** | 中 | 訴求「批次估價 + 統一報價標準避免員工亂報」,不是取代老闆專業 |
| **Listing 平台禁止估值嵌入** | 低 | 估值報告本身產生於外部,使用者再貼回去 |

---

*第十二輪在 2026-05-10 產出於 incubator(台灣優先,**首次跳出 document-gen 模式**,改採 vertical pricing model + 自然語言解析)。跟前 11 輪保險 / 稅 / 化妝品 / 製造 / 創作者 / F&B / 長照 / 法律 / 獸醫 / 月報 / 健身 都不同 vertical 也不同架構。*
