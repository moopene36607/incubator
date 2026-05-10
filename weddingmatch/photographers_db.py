"""weddingmatch — 台灣婚攝師 seed 資料庫(prototype 用 12 位代表性婚攝).

實際產品需爬取 WeddingDay / IG / FB 婚禮社團 ~5,000-8,000 位專業婚攝公開作品集 +
取得授權同意條款。本 prototype 用結構化 mock 資料展示「自然語言風格描述 → 純函式
cosine similarity → Top-N 配對」的核心邏輯。

風格 12 維:用 0/1 binary tags 表達。每位婚攝通常 3-6 個 tag = 1,代表他擅長 / 偏好的風格。
匹配時用 cosine similarity 比對使用者的需求向量 vs 婚攝師向量。
"""

from __future__ import annotations

from dataclasses import dataclass


# 12 維風格 tag(順序固定,所有 vector 都用此順序)
STYLE_DIMENSIONS: tuple[str, ...] = (
    "film_emulation",   # 底片感 / 真實底片相機
    "digital_clean",    # 數位乾淨銳利
    "contrast_high",    # 高對比 / 暗調 / 戲劇性
    "pastel_soft",      # 粉嫩柔和 / 清新淡雅
    "cinematic",        # 電影感 / 電影色彩
    "posed",            # 擺拍 / 經典 portrait
    "candid",           # 隨拍 / 抓拍自然瞬間
    "journalistic",     # 新聞紀錄式 / 故事感
    "outdoor",          # 戶外 / 自然光
    "indoor_ceremony",  # 室內儀式 / 教堂 / 飯店
    "studio_glamour",   # 棚拍 / glamour
    "detail_focus",     # 細節控 / 飾品 / 場佈特寫
)


# 風格 tag 的中文說明(供 LLM grounding 與最終輸出使用)
STYLE_LABELS_ZH: dict[str, str] = {
    "film_emulation": "底片感",
    "digital_clean":  "數位乾淨",
    "contrast_high":  "高對比 / 暗調",
    "pastel_soft":    "粉嫩柔和 / 清新",
    "cinematic":      "電影感",
    "posed":          "擺拍",
    "candid":         "隨拍 / 自然瞬間",
    "journalistic":   "新聞紀錄式 / 故事感",
    "outdoor":        "戶外",
    "indoor_ceremony":"室內儀式 / 飯店",
    "studio_glamour": "棚拍 glam",
    "detail_focus":   "細節控",
}


@dataclass(frozen=True)
class Photographer:
    code: str
    name: str
    ig_handle: str
    region: str                # 主要服務區域 — "北部" / "中部" / "南部" / "全台"
    price_range_min_twd: int   # 婚禮全程最低價
    price_range_max_twd: int
    style_tags: tuple[int, ...]  # 12 維 0/1 vector,順序對應 STYLE_DIMENSIONS
    short_bio: str             # 一句話自我介紹(供 AI 寫推薦理由用)
    typical_session_hours: int = 10  # 典型一場時數


def _vec(*tag_keys: str) -> tuple[int, ...]:
    """從 tag 名稱清單建構 12 維向量。"""
    return tuple(1 if dim in tag_keys else 0 for dim in STYLE_DIMENSIONS)


PHOTOGRAPHERS: list[Photographer] = [
    Photographer(
        code="P001", name="阿杰 Jay", ig_handle="@jayphoto.tw",
        region="北部", price_range_min_twd=80_000, price_range_max_twd=120_000,
        style_tags=_vec("film_emulation", "candid", "outdoor", "journalistic"),
        short_bio="日系底片感婚攝,擅長戶外自然光下的隨拍故事感。新北 / 台北為主。",
    ),
    Photographer(
        code="P002", name="小綠 Lin", ig_handle="@green.wedding",
        region="北部", price_range_min_twd=65_000, price_range_max_twd=95_000,
        style_tags=_vec("pastel_soft", "candid", "outdoor", "detail_focus"),
        short_bio="清新粉嫩戶外風,擅捕捉新人互動細節。婚紗外拍經驗豐富。",
    ),
    Photographer(
        code="P003", name="阿凱 Kai", ig_handle="@kai.cinema.wed",
        region="全台", price_range_min_twd=120_000, price_range_max_twd=180_000,
        style_tags=_vec("cinematic", "contrast_high", "posed", "studio_glamour"),
        short_bio="電影感戲劇性婚攝,高對比色調 + 棚拍經驗。價格中高,適合追求大片感的新人。",
    ),
    Photographer(
        code="P004", name="美玲 Mei", ig_handle="@meilin.weddings",
        region="中部", price_range_min_twd=45_000, price_range_max_twd=70_000,
        style_tags=_vec("digital_clean", "posed", "indoor_ceremony"),
        short_bio="台中飯店宴客專業,數位乾淨銳利風格。價格親民適合預算有限的新人。",
    ),
    Photographer(
        code="P005", name="阿哲 Z-Studio", ig_handle="@zstudio.wed",
        region="北部", price_range_min_twd=90_000, price_range_max_twd=140_000,
        style_tags=_vec("film_emulation", "cinematic", "candid", "journalistic"),
        short_bio="底片感 + 電影色調混搭,新聞紀錄式抓拍。北部知名工作室,口碑穩定。",
    ),
    Photographer(
        code="P006", name="光點 LightDot", ig_handle="@lightdot.wed",
        region="南部", price_range_min_twd=55_000, price_range_max_twd=85_000,
        style_tags=_vec("pastel_soft", "outdoor", "candid", "detail_focus"),
        short_bio="高雄 / 台南粉嫩戶外婚攝,擅長海邊 / 草地場景。CP 值高的清新派。",
    ),
    Photographer(
        code="P007", name="Vivien W.", ig_handle="@vivien.weddings",
        region="北部", price_range_min_twd=150_000, price_range_max_twd=220_000,
        style_tags=_vec("cinematic", "contrast_high", "studio_glamour", "detail_focus"),
        short_bio="高端棚拍 + 電影感大片,合作過多家精品飯店。價格頂級,風格時尚 editorial。",
    ),
    Photographer(
        code="P008", name="老吳 Wu", ig_handle="@wu.classic.wed",
        region="全台", price_range_min_twd=50_000, price_range_max_twd=80_000,
        style_tags=_vec("digital_clean", "posed", "indoor_ceremony", "outdoor"),
        short_bio="20 年經驗老牌,經典擺拍 + 飯店宴客專業。長輩接受度高,流程順。",
    ),
    Photographer(
        code="P009", name="Lulu Studio", ig_handle="@lulu.wedding",
        region="北部", price_range_min_twd=70_000, price_range_max_twd=110_000,
        style_tags=_vec("film_emulation", "pastel_soft", "candid", "outdoor"),
        short_bio="底片感 + 清新粉嫩戶外風,小資新人最愛。Lulu 本人攝影。",
    ),
    Photographer(
        code="P010", name="阿丹 Dan", ig_handle="@dan.docu.wed",
        region="北部", price_range_min_twd=85_000, price_range_max_twd=130_000,
        style_tags=_vec("journalistic", "candid", "contrast_high", "indoor_ceremony"),
        short_bio="紀錄片風格婚攝,高對比黑白 + 故事感為招牌。教堂 / 戲劇性宴客場景。",
    ),
    Photographer(
        code="P011", name="陽光攝影 Sunny", ig_handle="@sunny.wedding.tw",
        region="中部", price_range_min_twd=40_000, price_range_max_twd=65_000,
        style_tags=_vec("digital_clean", "outdoor", "posed", "pastel_soft"),
        short_bio="台中經濟實惠新人首選,戶外婚紗 + 飯店宴客 all-in-one。",
    ),
    Photographer(
        code="P012", name="鏡頭裡的故事 Story", ig_handle="@story.wedding",
        region="南部", price_range_min_twd=75_000, price_range_max_twd=115_000,
        style_tags=_vec("cinematic", "journalistic", "candid", "outdoor"),
        short_bio="台南電影感故事派,擅長融合戶外景與人文情感。",
    ),
]


_BY_CODE: dict[str, Photographer] = {p.code: p for p in PHOTOGRAPHERS}


def lookup(code: str) -> Photographer | None:
    return _BY_CODE.get(code.strip().upper())


def all_photographers() -> list[Photographer]:
    return list(PHOTOGRAPHERS)
