"""monthrep — 月報結構模板 (純資料,no I/O, no LLM).

收錄常見才藝 / 學科類別的「月報應記載要點」, 給 LLM 做 grounding 使用。
不同年齡層 (幼兒 / 國小 / 國中 / 高中) 措辭調性不同, 也在這裡定義。

目標:讓 AI 寫出來的月報結構一致、不漏項、貼近台灣才藝班 / 補習班老師
口吻, 而不是泛泛通用 AI 文案。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectTemplate:
    code: str               # 內部代碼
    chinese: str            # 中文科目名
    typical_focus: tuple[str, ...]    # 月報通常會評論的學習面向
    parent_concerns: tuple[str, ...]  # 家長最在意的點


SUBJECT_TEMPLATES: list[SubjectTemplate] = [
    SubjectTemplate(
        code="PIANO",
        chinese="鋼琴",
        typical_focus=("基本指法", "節奏穩定度", "視奏速度", "雙手協調",
                       "曲目進度", "情感表達", "指考曲目準備", "比賽曲目"),
        parent_concerns=("是否有進步", "練琴時間夠不夠", "比賽 / 檢定準備度",
                         "上課專注度", "對音樂的熱情"),
    ),
    SubjectTemplate(
        code="ART",
        chinese="繪畫 / 美術",
        typical_focus=("基礎構圖", "色彩運用", "線條練習", "媒材掌握",
                       "創意發想", "作品完成度", "個人風格"),
        parent_concerns=("作品是否拿得出手", "創意有無發揮", "是否覺得好玩",
                         "技巧進步", "比賽 / 投稿成績"),
    ),
    SubjectTemplate(
        code="ENGLISH",
        chinese="兒童 / 國中英文",
        typical_focus=("單字量", "聽力", "口說自信", "文法理解", "閱讀速度",
                       "寫作架構", "課堂參與度", "考試成績"),
        parent_concerns=("學校段考成績", "兒美 / 全民英檢級數", "口說敢不敢開口",
                         "回家是否願意複習", "對英文的接受度"),
    ),
    SubjectTemplate(
        code="MATH",
        chinese="國中 / 國小數學",
        typical_focus=("計算正確率", "解題速度", "應用題理解", "幾何概念",
                       "新單元適應", "作業完成度", "段考表現", "錯題訂正"),
        parent_concerns=("段考分數", "排名變化", "弱點單元",
                         "上課跟得上嗎", "升學準備"),
    ),
    SubjectTemplate(
        code="DANCE",
        chinese="舞蹈 (芭蕾 / 街舞 / 民族)",
        typical_focus=("基本動作", "節拍感", "身體柔軟度", "肌力",
                       "編舞記憶", "舞台呈現", "團體配合"),
        parent_concerns=("體態進步", "對團體生活適應",
                         "公演 / 比賽準備", "受傷風險", "孩子興趣維持"),
    ),
    SubjectTemplate(
        code="VIOLIN",
        chinese="小提琴",
        typical_focus=("姿勢", "握弓", "音準", "節奏", "換弦流暢度",
                       "曲目進度", "視奏", "情感表達"),
        parent_concerns=("音準是否進步", "練琴頻率", "檢定 / 比賽成績",
                         "上課專注度", "持續學習意願"),
    ),
    SubjectTemplate(
        code="GO",
        chinese="圍棋",
        typical_focus=("定式記憶", "死活題", "佈局思路", "對局風格",
                       "段位進階", "復盤能力", "棋力穩定度"),
        parent_concerns=("段位進度", "比賽成績", "邏輯思考能力",
                         "上課專注", "孩子是否有興趣"),
    ),
    SubjectTemplate(
        code="CHINESE",
        chinese="作文 / 國語",
        typical_focus=("字彙量", "句型運用", "段落組織", "主題發想",
                       "閱讀理解", "錯別字", "標點", "語感"),
        parent_concerns=("作文分數", "閱讀興趣", "段考表現",
                         "錯別字頻率", "升學準備"),
    ),
]


@dataclass(frozen=True)
class AgeBandTone:
    code: str
    label: str
    voice_note: str   # 給 LLM 的口吻指引


AGE_BANDS: list[AgeBandTone] = [
    AgeBandTone(
        code="PRESCHOOL",
        label="學齡前 (3-6 歲)",
        voice_note="家長最在意快樂學習與基本社交,重點放在『今天有沒有笑、有沒有交到朋友、有沒有完成小目標』,不要寫太多技巧細節",
    ),
    AgeBandTone(
        code="ELEMENTARY",
        label="國小 (7-12 歲)",
        voice_note="家長同時關心興趣與成績,可以提技巧進步也提情感觀察,語氣溫暖正向,具體舉例(本月哪一首曲子 / 哪一個段考)",
    ),
    AgeBandTone(
        code="JUNIOR_HIGH",
        label="國中 (13-15 歲)",
        voice_note="家長以成績與升學為主,語氣專業客觀,要有量化指標(段考 X 分、進步 Y 分、排名變化、檢定級數),指出明確弱點與改善計畫",
    ),
    AgeBandTone(
        code="SENIOR_HIGH",
        label="高中 (16-18 歲)",
        voice_note="同國中但更聚焦學測 / 指考準備,可以提模擬考成績、各科權重、學群志向關聯",
    ),
]


_SUBJECT_BY_CODE: dict[str, SubjectTemplate] = {s.code: s for s in SUBJECT_TEMPLATES}
_AGE_BY_CODE: dict[str, AgeBandTone] = {a.code: a for a in AGE_BANDS}


def lookup_subject(code: str) -> SubjectTemplate | None:
    return _SUBJECT_BY_CODE.get(code.strip().upper())


def lookup_age_band(code: str) -> AgeBandTone | None:
    return _AGE_BY_CODE.get(code.strip().upper())


def all_subjects() -> list[SubjectTemplate]:
    return list(SUBJECT_TEMPLATES)


def all_age_bands() -> list[AgeBandTone]:
    return list(AGE_BANDS)
