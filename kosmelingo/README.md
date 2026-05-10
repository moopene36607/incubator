# kosmelingo

**K-beauty 화장품 → 일본 수출 전성분 라벨 자동 생성기.**
**K-beauty 化粧品 → 日本輸出 全成分ラベル AI 自動生成。**

韓国 indie cosmetic brand が 日本市場に出すたびに 50–200 万 KRW + 2–4 週間払って代行業者にやらせている「INCI 英語名 → JCIA 標準日本語名」変換 + 法規チェック + ラベル草稿生成を、9,900 KRW + 30 秒に圧縮するツール。

---

## 痛點(韓→日 cosmetic export における事実)

K-beauty indie brand が日本に出す時、超えなければならない法的ハードル:

> **「日本では化粧品の全成分を必ず日本語で表記しなければならず、英文 INCI 名のみは違法である。日本化粧品工業連合会 (JCIA) が定めた標準日本語成分名を使わなければならない。」** — 大韓化粧品協会 (KCIA) 公告

つまり韓国の전성분 표기 (例: `Sodium Hyaluronate`) を日本語の標準名 (`ヒアルロン酸Na`) に 1 対 1 で正確に変換しなければならない。間違えると製品自体出荷できない。Google 翻訳・DeepL は使えない (一般翻訳であり、JCIA 命名規則を知らない)。

現状の選択肢:

| 既存方法 | 何がダメか |
|----------|-----------|
| 代行業者 (KTR / CIRS / REACH24H) | **50–200 万 KRW/件**、2〜4 週間、人手依存 |
| KCIA 成分사전 (公開 DB) | 1 件 1 件手作業で検索する設計、バッチ処理不可 |
| work-son.com の Google Sheet (2024 公開) | 手動メンテの一覧表、新成分は自分で追加 |
| DeepL / ChatGPT generic | INCI→JCIA mapping を知らない、ハルシネーション率高 |

**結論: SaaS 化された自動変換ツールは現時点で存在しない**(REACH24H・KTR のような代行は人手ビジネスで SaaS 化のインセンティブがない)。

## 市場規模 (REACH24H 報告)

- 2024 Q3: K-beauty 日本輸出が過去最高、**+21.5% YoY**
- 日本は K-beauty の **第 3 大市場**
- 韓国 indie cosmetic brand は 2,000 社以上、ODM 工場経由含めると 5,000+
- うち年商 1〜30 億 KRW 規模で「日本進出したいが法務専任なし」の層が中核ターゲット

## kosmelingo の中核機能

```
韓国 ingredient list (INCI 英語 / Hangul)
         │
         ▼
   ローカル辞書 lookup (JCIA seed DB, ~40 entries in prototype, 全 DB 化で ~10,000)
         │
         ▼
   未マッチ成分 → Claude AI fallback (信頼度フラグ付き)
         │
         ▼
   JCIA 標準日本語成分表 + 規制注意点ハイライト + ラベル草稿
```

### 三段階の信頼度設計

| 信頼度 | 意味 | アクション |
|--------|------|-----------|
| ✅ 完全一致 (DB) | seed DB / 全 JCIA DB に存在 | そのまま使用可 |
| 🟢 AI 推定 (高信頼) | 学術慣用名から確実に推定可能 | レビュー推奨 |
| 🟡 AI 推定 (要レビュー) | 似ているがハルシネーション可能性 | 必ず人手確認 |
| ⚠️ 不明 | 一切判定不可 | JCIA 会員専用リスト or 厚生局窓口で最終確認 |

法規違反のリスクが大きいので「AI が全部自動で確定」とは絶対に言わない設計。代わりに **80% は確定、20% は人手レビュー** のワークフローを提供。

## デモを動かす

### 辞書のみモード(API key 不要)

```bash
python3 kosmelingo.py samples/sample_input.json --no-ai
```

`samples/sample_input.json` には GLOWHAUS 風の架空 K-beauty 美容液の成分 20 件が入っている。20 件中 18 件はローカル DB で完全一致、2 件 (Polyglutamic Acid / Beta-Glucan) は seed DB に未収録なので「要確認」フラグが立つ。

### AI fallback モード

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python3 kosmelingo.py samples/sample_input.json
```

未マッチ成分のみ Claude に送り、JCIA 推定名 + 信頼度 + 注記を取得する。20 件中 2 件のみ API 呼び出し → コストは 1 件約 ¢1。

### Hangul 入力もそのまま使える

```python
from ingredient_db import lookup
lookup("정제수").jcia_ja        # → '水'
lookup("나이아신아마이드").jcia_ja  # → 'ナイアシンアミド'
lookup("알로에베라잎즙").jcia_ja   # → 'アロエベラ葉エキス'
```

## 出力例

`examples/sample_output.md` に予生成済みのラベル草稿があり、無 API key でも全体像が見える。含まれる項目:

- 製品基本情報 (ブランド・商品名・容量・原産国)
- 成分変換テーブル (信頼度マーク付き)
- 要レビュー成分一覧
- ラベル貼付用全成分表示 (`水、グリセリン、ナイアシンアミド、BG、ヒアルロン酸Na…` 形式)
- 規制チェックポイント (例: フェノキシエタノール上限 1.0% / 医薬部外品申請判定)
- 輸入販売者情報枠 (日本上市の必須項目)

## プロジェクト構成

```
kosmelingo/
├── README.md
├── kosmelingo.py             # CLI 主程式
├── ingredient_db.py          # JCIA seed dictionary (40 件、全 DB へ拡張可能)
├── samples/
│   └── sample_input.json     # K-beauty 美容液 20 成分 sample
├── examples/
│   └── sample_output.md      # 予生成済みラベル草稿
└── requirements.txt
```

総計約 350 行 Python。依存は `anthropic` のみ(AI fallback を使う場合のみ必要)。

## 検証済み smoke test

- ✅ 完全 DB マッチ 18/20 (Water → 水、Sodium Hyaluronate → ヒアルロン酸Na、Phenoxyethanol → フェノキシエタノール、…)
- ✅ DB 外成分 (Polyglutamic Acid / Beta-Glucan) は ⚠️ フラグ立つ
- ✅ Hangul 入力で同じ結果 (정제수 → 水、나이아신아마이드 → ナイアシンアミド、…)
- ✅ 規制注記が出力に統合 (フェノキシエタノール 1.0% 上限、医薬部外品判定など)

## 真正版に必要だがプロトタイプには未実装

- **完全 JCIA DB** — 약 10,000 件の成分。化妝品工業連合会への正式アクセス契約 or KTR 経由データ取得
- **PDF / 画像出力** — ラベル印刷用 1:1 スケール PDF (現在 markdown のみ)
- **OCR 入力** — KCIA 발급 전성분 표 PDF を直接読み込み
- **韓・日両言語 UI** — Web 페이지化、로그인、SKU 履歴管理
- **自動更新** — JCIA / 厚労省告示 RSS 監視、規制改正時に既存 SKU を再評価
- **医薬部外品 (quasi-drug) ワークフロー** — 美白・しわ改善・育毛など効能訴求の場合の薬機法承認補助
- **ODM 向けバルク変換** — CSV 一括処理、複数 SKU の差分比較
- **化粧品製造販売業者ネットワーク** — 日本国内法人を持たない韓国 brand のための代理店マッチング

## 商業モデル

| プラン | 価格 | 対象 |
|--------|------|------|
| Pay-per-SKU | **9,900 KRW / SKU**(約 $7) | 単発で 1〜2 製品出すだけの indie brand |
| Indie Pro | **99,000 KRW / 月**、月 20 SKU まで | 年 5 製品以上の中規模 indie |
| ODM Plan | **300〜500 万 KRW / 年**、無制限 | 韓国 ODM 工場(顧客 brand 代理処理) |
| Enterprise | カスタム | 韓国大手化粧品グループ・代理店網 |

伝統的代行 50〜200 万 KRW/件 と比べて **10〜100 倍の価格優位性**。1 製品処理する間に既に元が取れる。

## 早期 distribution

1. **韓国 화장품 ODM 工場** — 顧客 brand への付加サービスとして導入提案 (B2B2B 漏れがない)
2. **K-beauty 出口協会・Korea Cosmetic Industry Forum** — 日本進出を支援する政府系プログラムの partner ツール
3. **Naver / Tistory blog 운영하는 indie cosmetic founder** — 「내 브랜드 일본 진출 후기」를 쓰는 KOL과 contra
4. **Tokyo cosmetic trade fair (BITE Tokyo / Cosme Tokyo)** — 韓国 booth に直接アタック
5. **Cosme Hunt / Q-trend / Cosme Kitchen バイヤー** — 日本側バイヤーが「これを韓国 brand に薦めて」と勧めるルート

最初の 100 paying SKU = 約 $700 MRR。月 30 brand × 5 SKU 出ればすぐスケール可能。

## リスク評価

| リスク | 評価 | 緩和策 |
|--------|------|--------|
| JCIA が公式 SaaS をリリース | 中 | 政府系団体は SaaS 開発が遅い。先行者利益を community / brand network で固める |
| 大手代行 (KTR) が SaaS 内製化 | 中 | KTR は人月で稼ぐ構造、SaaS 化は社内コンフリクト |
| ハルシネーション 1 件 → 法的事故 | 高 | 信頼度フラグ + 「人手レビュー必須」UX で責任移転を明示 |
| K-beauty 日本市場が冷えこむ | 低 | 2024 Q3 で過去最高、トレンドは長期 |
| 中国・アメリカ市場展開で焦点ボケ | 中 | 韓→日に集中、他言語ペアは Phase 2 以降 |

---

*第三輪在 2026-05-10 產出於 incubator(亞洲市場優先,韓國 → 日本 cross-border vertical)。第一個有「規制必須」性質的 prototype。*
