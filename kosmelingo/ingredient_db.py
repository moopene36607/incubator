"""Cosmetic ingredient name dictionary — INCI / Korean / JCIA Japanese.

This is a *seed* database for the prototype demo. The JCIA (日本化粧品工業連合会)
publishes a complete standardized Japanese ingredient name dictionary covering
~10,000 entries — a real product would license / partner for the full dataset.

Names listed here are the most commonly seen ingredients in K-beauty
formulations and are sufficient to demonstrate end-to-end conversion of a
typical serum / cream / toner ingredient list.

Lookup is by normalized key (lowercase, stripped). The normalizer also
matches Korean Hangul names and a small list of common synonyms.

References:
- INCI names: PCPC International Cosmetic Ingredient Dictionary
- JCIA standard JP names: 日本化粧品工業連合会 化粧品の成分表示名称リスト
- Korean names: 식품의약품안전처 화장품 전성분 표기 가이드라인
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Ingredient:
    inci_en: str
    jcia_ja: str
    korean: tuple[str, ...]
    category: str  # solvent | humectant | active | preservative | emulsifier | thickener | ph_adjuster | fragrance | extract | lipid | vitamin | other
    notes: str = ""
    aliases_en: tuple[str, ...] = field(default_factory=tuple)


_RAW: list[Ingredient] = [
    Ingredient("Water", "水", ("정제수", "물"), "solvent"),
    Ingredient("Glycerin", "グリセリン", ("글리세린",), "humectant"),
    Ingredient("Butylene Glycol", "BG", ("부틸렌글라이콜",), "humectant",
               notes="JCIA 慣用表記は『BG』。フル表記『ブチレングリコール』も可。"),
    Ingredient("Propylene Glycol", "PG", ("프로필렌글라이콜",), "humectant"),
    Ingredient("1,2-Hexanediol", "1,2-ヘキサンジオール", ("1,2-헥산다이올",), "preservative"),
    Ingredient("Pentylene Glycol", "ペンチレングリコール", ("펜틸렌글라이콜",), "humectant"),
    Ingredient("Niacinamide", "ナイアシンアミド", ("나이아신아마이드",), "active",
               notes="美白有効成分。医薬部外品申請の場合は別途承認が必要。"),
    Ingredient("Hyaluronic Acid", "ヒアルロン酸", ("히알루론산",), "humectant",
               aliases_en=("Hyaluronic acid",)),
    Ingredient("Sodium Hyaluronate", "ヒアルロン酸Na", ("소듐하이알루로네이트",), "humectant"),
    Ingredient("Adenosine", "アデノシン", ("아데노신",), "active",
               notes="しわ改善・抗老化の医薬部外品有効成分。"),
    Ingredient("Allantoin", "アラントイン", ("알란토인",), "active"),
    Ingredient("Panthenol", "パンテノール", ("판테놀",), "humectant"),
    Ingredient("Tocopherol", "トコフェロール", ("토코페롤",), "vitamin",
               notes="ビタミンE。酸化防止剤。"),
    Ingredient("Tocopheryl Acetate", "酢酸トコフェロール", ("토코페릴아세테이트",), "vitamin"),
    Ingredient("Ascorbic Acid", "アスコルビン酸", ("아스코르빅애씨드",), "vitamin",
               notes="ビタミンC。水溶液中での安定性に注意。"),
    Ingredient("Sodium Ascorbyl Phosphate", "アスコルビルリン酸Na", ("소듐아스코빌포스페이트",), "vitamin"),
    Ingredient("Retinol", "レチノール", ("레티놀",), "active",
               notes="しわ改善有効成分。配合濃度に応じて医薬部外品申請の検討要。"),
    Ingredient("Retinyl Palmitate", "パルミチン酸レチノール", ("레티닐팔미테이트",), "active"),
    Ingredient("Centella Asiatica Extract", "ツボクサエキス", ("센텔라아시아티카추출물", "병풀추출물"), "extract"),
    Ingredient("Camellia Sinensis Leaf Extract", "チャ葉エキス", ("카멜리아시넨시스잎추출물", "녹차추출물"), "extract"),
    Ingredient("Aloe Barbadensis Leaf Juice", "アロエベラ葉エキス", ("알로에베라잎즙",), "extract"),
    Ingredient("Hydrolyzed Collagen", "加水分解コラーゲン", ("가수분해콜라겐",), "active"),
    Ingredient("Ceramide NP", "セラミドNP", ("세라마이드엔피",), "lipid"),
    Ingredient("Cholesterol", "コレステロール", ("콜레스테롤",), "lipid"),
    Ingredient("Squalane", "スクワラン", ("스쿠알란",), "lipid"),
    Ingredient("Caprylic/Capric Triglyceride", "トリ(カプリル酸/カプリン酸)グリセリル",
               ("카프릴릭/카프릭트라이글리세라이드",), "lipid"),
    Ingredient("Cetearyl Alcohol", "セテアリルアルコール", ("세테아릴알코올",), "emulsifier"),
    Ingredient("Cetyl Alcohol", "セチルアルコール", ("세틸알코올",), "emulsifier"),
    Ingredient("Stearic Acid", "ステアリン酸", ("스테아릭애씨드",), "emulsifier"),
    Ingredient("Glyceryl Stearate", "ステアリン酸グリセリル", ("글리세릴스테아레이트",), "emulsifier"),
    Ingredient("Polysorbate 60", "ポリソルベート60", ("폴리소르베이트60",), "emulsifier"),
    Ingredient("Carbomer", "カルボマー", ("카보머",), "thickener"),
    Ingredient("Xanthan Gum", "キサンタンガム", ("잔탄검",), "thickener"),
    Ingredient("Disodium EDTA", "EDTA-2Na", ("다이소듐이디티에이",), "other"),
    Ingredient("Citric Acid", "クエン酸", ("시트릭애씨드",), "ph_adjuster"),
    Ingredient("Sodium Citrate", "クエン酸Na", ("소듐시트레이트",), "ph_adjuster"),
    Ingredient("Sodium Hydroxide", "水酸化Na", ("소듐하이드록사이드",), "ph_adjuster"),
    Ingredient("Phenoxyethanol", "フェノキシエタノール", ("페녹시에탄올",), "preservative",
               notes="日本では化粧品配合上限 1.0%。1%超なら処方見直しが必要。"),
    Ingredient("Ethylhexylglycerin", "エチルヘキシルグリセリン", ("에칠헥실글리세린",), "preservative"),
    Ingredient("Fragrance", "香料", ("향료",), "fragrance",
               notes="香料の26 アレルゲン物質は EU では個別表示義務、日本では任意だが推奨。"),
    Ingredient("Limonene", "リモネン", ("리모넨",), "fragrance"),
    Ingredient("Linalool", "リナロール", ("리나룰",), "fragrance"),
]


def _normalize(s: str) -> str:
    return "".join(s.lower().split()).replace("-", "").replace(",", "").replace("(", "").replace(")", "").replace("/", "")


_INDEX: dict[str, Ingredient] = {}
for ing in _RAW:
    _INDEX[_normalize(ing.inci_en)] = ing
    for alias in ing.aliases_en:
        _INDEX[_normalize(alias)] = ing
    for kr in ing.korean:
        _INDEX[_normalize(kr)] = ing


def lookup(name: str) -> Ingredient | None:
    """Look up an ingredient by INCI English name, alias, or Korean name."""
    return _INDEX.get(_normalize(name))


def all_ingredients() -> Iterable[Ingredient]:
    return tuple(_RAW)
