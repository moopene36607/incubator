# hoadon (hóa đơn)

**AI trợ lý xuất hóa đơn điện tử ngày cho hộ kinh doanh F&B Việt Nam.**
**越南 hộ kinh doanh F&B 業者每日批量電子發票 AI 自動產生器(符合 Nghị định 70/2025)。**

Chỉ cần ghi nhớ giọng nói hoặc chụp ảnh sổ tay — AI tự động phân loại
giao dịch, tính VAT, sinh hóa đơn ngày đúng chuẩn Nghị định 70.

---

## 痛點

2025 年 6 月 1 日 越南 **Nghị định 70/2025/NĐ-CP** 強制上路:年營收超過 1 tỷ VND
(約 USD 39,000)的 hộ kinh doanh(家庭式生意)必須使用電子發票。違反 = 罰款。

實際痛點(來自越南媒體):

> **"42.7% of vendors do not fully understand tax types and calculation methods.
> Many vendors reported difficulties when adding steps related to issuing
> electronic invoices and declaring taxes."**
> — Vietnamnet, 2025

> **"For F&B/retail, consolidation of invoices for small-value retail
> transactions occurring frequently throughout the day should be allowed
> without requiring immediate invoice issuance — transactions under 50,000 VND
> can be aggregated."**
> — Vietnam.vn, 2025

但 Nghị định 70 設計的「每日彙總發票」邏輯太複雜:
- 單筆 ≥ 50,000 VND → 必須開立個別發票
- 單筆 < 50,000 VND → 可以彙總到當日一張發票
- 賣 50 杯 5,000 VND 的 trà đá 的攤商不可能每杯都開發票,但要懂規則才能合法彙總
- 加上 8% / 10% VAT 區分(F&B 暫減稅 8% 直到 2025 底,標準商品 10%)

對 80 歲的 Phở 阿姨來說?「我只想賣麵」。

## 為什麼現在沒有對的工具

| 既有方案 | 為什麼不適合 hộ kinh doanh F&B 攤商 |
|----------|----------------------------------|
| **MISA AMIS** | 中小企業會計軟體,月費幾百萬 VND,需要會計操作。攤商用不起。 |
| **VNPT 免費 e-invoice software** | 只是空白表單工具,沒有 AI 自動分類也不懂 Nghị định 70 批次邏輯。 |
| **手動在 MyInvois Portal 一筆一筆輸入** | 一天賣幾百筆,不可能。 |
| **找鄰居會計兼差** | NT$50–100/月人工費對攤商已經太貴。 |
| **不開發票** | 違法,罰款。 |

**Gap 明確**:沒有針對「每日銷售流水 → AI 解析 → Nghị định 70 自動分類 + 彙總」的 SaaS 工具。
搜尋 `hộ kinh doanh e-invoice AI startup` 沒有任何已知競品。

## hoadon 在做的事

```
                語音備忘錄 / 手寫銷售紀錄 / 結構化 JSON
                          │
                          ▼
              ┌─────────────────────────┐
              │   Claude API 解析       │ (--freetext 模式)
              │   非結構化 → 結構化     │
              └─────────────┬───────────┘
                            ▼
              ┌─────────────────────────┐
              │   vat_rules.py (純函式)  │
              │   分 Nghị định 70 兩類   │
              │   < 50,000 VND → 彙總    │
              │   ≥ 50,000 VND → 個別    │
              │   計算 8% / 10% VAT     │
              └─────────────┬───────────┘
                            ▼
              當日彙總電子發票 markdown(可直接送 VNPT API)
```

3 個關鍵組件:

1. **`vat_rules.py`** — 純 Python 計算邏輯,所有 VAT 率與門檻常數寫在頂部,Bộ Tài chính 公告改了只改一個檔案。Decree 70 批次規則和 8%/10% VAT 率都在這裡。
2. **`hoadon.py`** — CLI 主程式,雙模式輸入(JSON 或 freetext via Claude)。
3. **AI 解析 freetext**(`--freetext`)— 越南文 prompt + few-shot example,Claude 把 「Hôm nay bán 35 phở bò 65k...」變成結構化 lines list。

## 動作

### 純結構化 JSON 輸入(不需 API key)

```bash
python3 hoadon.py samples/sample_input.json
```

`samples/sample_input.json` 是典型 Phở 店一天銷售(11 個項目,5 個 ≥ 50,000 VND
需個別開發票,6 個 < 50,000 VND 可彙總)。輸出完整的 Decree 70 合規日彙總
發票草稿。

### freetext 輸入(Claude 解析,需 API key)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 hoadon.py --freetext samples/sample_input_freetext.txt --shop samples/shop_config.json
```

`samples/sample_input_freetext.txt` 是模擬語音備忘錄轉文字。Claude 會把它解析成
結構化 lines,然後流程同上。1 day 的 demo 成本約 $0.01。

### 預先產出的 demo

`examples/sample_output.md` 已經跑好,無 API key 也看得到完整 Decree 70 兩段式
日彙總發票。

## 驗證 smoke test

- ✅ 結構化 sample(11 line items,11 種商品):總金額 8,557,000 VND ÷ 1.08 = net 7,923,148 VND + VAT 633,852 VND ✓
- ✅ < 50,000 VND 全彙總(全部分到 batch_aggregated)
- ✅ ≥ 50,000 VND 全個別(全部分到 individual_invoices)
- ✅ 邊界值剛好 50,000 VND → 必須個別(per Decree 70 「>=」邏輯)
- ✅ 10% 標準 VAT 計算正確(108,000 → net 98,182 + VAT 9,818)
- ✅ 空輸入 raises ValueError

## 專案結構

```
hoadon/
├── README.md
├── hoadon.py              # CLI 主程式
├── vat_rules.py           # 純函式 VAT + Decree 70 邏輯
├── samples/
│   ├── sample_input.json          # 結構化 Phở 店日銷售
│   ├── sample_input_freetext.txt  # 越南文語音備忘錄樣本
│   └── shop_config.json           # 店鋪資料(配合 freetext 用)
├── examples/
│   └── sample_output.md   # 預先產出的 Decree 70 日彙總發票
└── requirements.txt
```

總計約 350 行 Python。依賴僅 `anthropic`(只在 `--freetext` 模式才需要)。

## 真正產品要有但 prototype 沒做的

- **VNPT / MISA e-invoice API 接口** — 目前產 markdown,真正產品要直接 push XML 上 VNPT 的 cổng e-invoice
- **多媒體輸入**:
  - 拍照手寫账本 → OCR(Vision API)
  - 直接錄語音 → Whisper 轉文字 → 解析
  - WhatsApp / Zalo bot:店主轉發訂單訊息給 bot,自動處理
- **每月稅務申報自動化**:30 天累積 → 月報表 → tự động đẩy lên 國稅總局 cổng eTax
- **多店連鎖支援**:同一老闆 3 家攤位,每家獨立 Mã số thuế
- **越南文 / 英文 雙語介面**(目前 CLI 中越混雜,真正產品要 Vietnamese-first)
- **離線模式**:攤商網路不穩,要能離線記錄、有訊號再同步
- **庫存反向推算**:從每日銷售反推剩餘 ingredients,提醒採購
- **匯出 Excel / CSV** 給會計師年度結算
- **App 版**(攤商沒電腦只有手機)

## 商業模式

| 方案 | 價格 | 對象 |
|------|------|------|
| Free | 月 30 筆 | 試用 hoặc rất nhỏ |
| Solo | **49,000 VND/月**(~USD 2)| 標準 hộ kinh doanh F&B |
| Solo Năm | **399,000 VND/年**(2 個月免費)| 確定使用的攤商 |
| Multi-shop | **129,000 VND/月**(3 cửa hàng)| 連鎖小食/咖啡店 |
| Pro | **499,000 VND/月**(無限張 + WhatsApp bot + 月報自動申報)| 中型店 |

**WTP 錨點**:不請會計人員一年省 1–2 百萬 VND;違反 Decree 70 罰款 4–10 百萬 VND
(per regulation)。Solo 年費 399k VND = 比一杯星巴克。

**TAM 估算**:全越南 ~2.2 百萬 hộ kinh doanh,F&B 切片估 30–40% (~700K)。即使
1% 滲透 = 7,000 paying users × 49,000 VND = 月 343 百萬 VND ≈ USD 14K MRR。

## 早期 distribution

1. **與供應商合作**:啤酒批發、菜販、米店每日固定送貨給攤商,在送貨單上 cobrand
   推廣("用 hoadon 跟我們對帳更快")
2. **Zalo 群組行銷**:越南 SMB 老闆群組密度高,在區域性 hộ kinh doanh 老闆群組做
   demo 影片 + 試用碼
3. **VNPT / MISA 二級 distributor**:他們的 sales force 散布全國,合作把 hoadon
   當作他們企業 API 的「個人版前端」
4. **TikTok Việt Nam 教學影片**:「Tên đăng ký Decree 70 trong 5 phút」
5. **Quận uỷ ban / Sở Tài chính 地方政府**:政府本身想 onboard hộ kinh doanh,
   合作做免費 workshop,workshop 裡發試用碼

## 風險評估

| 風險 | 評估 | 緩解 |
|------|------|------|
| **Decree 70 條款細節變動** | 中 | 純函式設計,常數改一行;訂閱客戶 lock-in 在「規則改了我馬上更新」這個價值 |
| **VNPT / MISA 自己出免費 AI 版** | 中 | 政府系統開發慢、UX 差;先佔住 SMB 心占率 |
| **越南金融管制 / 外資限制** | 中 | 純 SaaS 不接金流,規避 fintech 監管;若需金流走 ZaloPay/VNPay 在地 partner |
| **越南店主 not paying** | 中 | 49,000 VND/月低門檻 + 罰款威脅(賣點) + 試用 30 天 |
| **AI 解析錯誤導致漏稅** | 高 | 一律提供「人工 review 階段」, AI 只做「草稿」, 最終一鍵確認權在用戶 |
| **VNPT API 商業授權限制** | 中 | 先做純 markdown / XML 輸出, 用戶手動 upload;Phase 2 再申請 API 商業權 |

---

*第六輪在 2026-05-10 產出於 incubator(亞洲市場優先,SEA 越南本土 vertical,5 輪都沒碰過)。*
