"""kosmelingo — K-beauty 化粧品成分表 韓 → 日本 (JCIA) 自動変換 + ラベル草稿生成

Usage:
    python kosmelingo.py samples/sample_input.json
    python kosmelingo.py samples/sample_input.json --out label.md

入力 JSON ファイルには製品情報と韓国式の成分リスト (INCI 英語名 or Hangul) が
含まれます。本ツールはローカル辞書で完全一致を試みた後、未マッチの成分のみを
Claude に送って JCIA 標準日本語名を推定し、信頼度フラグを付けて出力します。

ANTHROPIC_API_KEY is required only when there are unknown ingredients.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingredient_db import Ingredient, lookup


@dataclass
class ResolvedIngredient:
    raw_input: str
    jcia_ja: str
    inci_en: str | None
    confidence: str  # "exact" | "ai_high" | "ai_low" | "unknown"
    notes: str
    category: str


AI_LOOKUP_SYSTEM = """あなたは化粧品成分の専門家です。与えられた成分名 (INCI 英語名 or 韓国語) について、
日本化粧品工業連合会 (JCIA) が定める標準的な日本語表示名を推定してください。

回答は以下の JSON 形式で、他の文字を含めないでください:
{
  "jcia_ja": "日本語表示名",
  "inci_en": "INCI English name (canonical)",
  "category": "solvent | humectant | active | preservative | emulsifier | thickener | ph_adjuster | fragrance | extract | lipid | vitamin | other",
  "confidence": "high | low",
  "notes": "規制上の注意点があれば日本語で 1〜2 文。なければ空文字。"
}

ルール:
- JCIA 命名規則: 学術名・慣用名のうち日本で標準化されたものを採用 (例: Sodium Hyaluronate → ヒアルロン酸Na)
- 不明な場合は jcia_ja に "(要確認)" を入れ、confidence を "low" にしてください
- 推測に基づく回答は必ず confidence を "low" にすること
"""


def ai_resolve(name: str) -> ResolvedIngredient:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=[{"type": "text", "text": AI_LOOKUP_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"成分名: {name}\n\n上記について JCIA 標準表記を回答してください。"}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return ResolvedIngredient(raw_input=name, jcia_ja="(要確認)", inci_en=None,
                                   confidence="unknown", notes="AI 응답 파싱 실패", category="other")
    parsed = json.loads(text[start : end + 1])
    confidence = "ai_high" if parsed.get("confidence") == "high" else "ai_low"
    return ResolvedIngredient(
        raw_input=name,
        jcia_ja=parsed.get("jcia_ja", "(要確認)"),
        inci_en=parsed.get("inci_en"),
        confidence=confidence,
        notes=parsed.get("notes", ""),
        category=parsed.get("category", "other"),
    )


def resolve_ingredients(raw_list: list[str], use_ai: bool) -> list[ResolvedIngredient]:
    resolved: list[ResolvedIngredient] = []
    for name in raw_list:
        ing = lookup(name)
        if ing is not None:
            resolved.append(ResolvedIngredient(
                raw_input=name,
                jcia_ja=ing.jcia_ja,
                inci_en=ing.inci_en,
                confidence="exact",
                notes=ing.notes,
                category=ing.category,
            ))
        elif use_ai:
            resolved.append(ai_resolve(name))
        else:
            resolved.append(ResolvedIngredient(
                raw_input=name,
                jcia_ja="(要確認)",
                inci_en=None,
                confidence="unknown",
                notes="ローカル辞書未収録。AI モードで再実行してください。",
                category="other",
            ))
    return resolved


def confidence_emoji(c: str) -> str:
    return {"exact": "✅", "ai_high": "🟢", "ai_low": "🟡", "unknown": "⚠️"}.get(c, "?")


def confidence_label(c: str) -> str:
    return {
        "exact": "完全一致 (DB)",
        "ai_high": "AI 推定 (高信頼)",
        "ai_low": "AI 推定 (要レビュー)",
        "unknown": "不明 (要手動確認)",
    }.get(c, c)


def format_label(payload: dict[str, Any], resolved: list[ResolvedIngredient]) -> str:
    product = payload.get("product", {})
    brand = product.get("brand_ja") or product.get("brand", "")
    name = product.get("name_ja") or product.get("name", "")
    category = product.get("category_ja") or product.get("category", "")
    importer = payload.get("importer", {})

    lines: list[str] = []
    lines.append(f"# 化粧品ラベル草稿 — {brand} {name}")
    lines.append("")
    lines.append("## 製品情報")
    lines.append("")
    lines.append(f"- **ブランド**: {brand}")
    lines.append(f"- **商品名**: {name}")
    lines.append(f"- **種類**: {category}")
    if product.get("net_weight"):
        lines.append(f"- **内容量**: {product['net_weight']}")
    if product.get("country_of_origin"):
        lines.append(f"- **原産国**: {product['country_of_origin']}")
    lines.append("")

    lines.append("## 成分変換結果")
    lines.append("")
    lines.append("| # | 入力 (韓/英) | JCIA 日本語表示 | 信頼度 | 注記 |")
    lines.append("|---|---|---|---|---|")
    for i, r in enumerate(resolved, 1):
        emoji = confidence_emoji(r.confidence)
        note = r.notes.replace("|", "│") if r.notes else ""
        lines.append(f"| {i} | {r.raw_input} | **{r.jcia_ja}** | {emoji} {confidence_label(r.confidence)} | {note} |")
    lines.append("")

    review_needed = [r for r in resolved if r.confidence in ("ai_low", "unknown")]
    if review_needed:
        lines.append("## ⚠️ 要レビュー成分")
        lines.append("")
        lines.append(f"以下 {len(review_needed)} 件は出荷前に必ず JCIA 名称リスト (有料: 化粧品工業連合会会員専用) または")
        lines.append("輸入販売届出時の地方厚生局窓口で最終確認してください:")
        lines.append("")
        for r in review_needed:
            lines.append(f"- `{r.raw_input}` → 暫定: **{r.jcia_ja}**  ({confidence_label(r.confidence)})")
        lines.append("")

    lines.append("## 全成分表示 (ラベル貼付用)")
    lines.append("")
    lines.append("```")
    lines.append("【全成分】")
    formatted = "、".join(r.jcia_ja for r in resolved)
    lines.append(formatted)
    lines.append("```")
    lines.append("")

    flagged_notes = [r for r in resolved if r.notes]
    if flagged_notes:
        lines.append("## 規制チェックポイント")
        lines.append("")
        for r in flagged_notes:
            lines.append(f"- **{r.jcia_ja}**: {r.notes}")
        lines.append("")

    lines.append("## 輸入販売者情報 (日本語ラベル必須項目)")
    lines.append("")
    lines.append(f"- **輸入販売業者**: {importer.get('name_ja', '(未入力 — 日本国内法人が必要)')}")
    lines.append(f"- **住所**: {importer.get('address_ja', '(未入力)')}")
    lines.append(f"- **化粧品製造販売業許可番号**: {importer.get('license_number', '(未入力)')}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*kosmelingo prototype 出力。本ファイルは草稿です。日本市場への上市前に化粧品製造販売業者・薬事責任者の最終確認を取得してください。*")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="製品 + 成分リストの JSON")
    parser.add_argument("--out", type=Path, help="出力先ファイル(省略時 stdout)")
    parser.add_argument("--no-ai", action="store_true", help="AI fallback を無効化(辞書のみ)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: ファイルが見つかりません: {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    raw_ingredients: list[str] = payload.get("ingredients", [])
    if not raw_ingredients:
        print("error: ingredients フィールドが空です", file=sys.stderr)
        return 2

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設定 — AI fallback はスキップされます。", file=sys.stderr)

    resolved = resolve_ingredients(raw_ingredients, use_ai=use_ai)
    label = format_label(payload, resolved)

    if args.out:
        args.out.write_text(label, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(label)

    return 0


if __name__ == "__main__":
    sys.exit(main())
