"""stylescan — 繁中作文書寫指紋特徵抽取(純函式,no I/O, no LLM).

責任:
  - 從一段中文作文抽取 ~20 個 stylometric features
  - 計算兩個 feature 向量之間的 cosine similarity
  - 提供合成「學生歷史平均」函式

設計守則:
  - 數字 100% 純函式;LLM 永不算 cosine 或 feature
  - Features per-1000-char (per1k) 是 normalized,可跨不同長度作文比較
  - 用 dict 而非 numpy → 不依賴 numpy,純 stdlib

特徵分組:
  ① 句長分布 4 個(均/std/短句比/長句比)
  ② 標點密度 7 個(逗 / 頓 / 分 / 問 / 嘆 / 引 / 刪)
  ③ 詞彙風格 5 個(連接詞 / 語氣詞 / 抒情比擬詞 / 抽象思辨詞 / 古文書面詞)
  ④ 結構特徵 3 個(段落數 / 段落長 std / 起承轉合 keyword 命中)
  ⑤ 雜訊 1 個(emoji / 顏文字密度)
  共 20 個 features,構成「書寫指紋」向量。
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass


# --- 詞典 (台灣國高中常見) ---

TRANSITION_WORDS = (
    "因此", "然而", "所以", "因為", "雖然", "但是", "不過", "可是",
    "此外", "另外", "於是", "故", "而", "卻", "倘若", "既然",
)

MODAL_PARTICLES = ("啊", "呀", "啦", "吧", "嗎", "呢", "哦", "哎", "哩", "唄")

LYRICAL_WORDS = (
    "彷彿", "如同", "宛如", "似乎", "彷若", "猶如", "宛若",
    "感慨", "感動", "震撼", "難忘", "心頭一暖", "暖意", "湧上",
)

ABSTRACT_WORDS = (
    "思考", "思緒", "感悟", "體悟", "感受", "心境", "境界",
    "人生", "成長", "意義", "價值", "啟發", "領悟", "省思",
)

LITERARY_WORDS = (
    # AI 寫文常用的「過度書面語」
    "彼時", "然則", "不禁", "無不", "誠然", "乃", "竟",
    "不僅", "不僅僅", "尤其", "更甚者", "由此可見", "綜上所述",
    "令人", "使得", "進而", "繼而", "從中", "最終",
)

STRUCTURE_KEYWORDS = (
    # 起承轉合 + 起頭結尾標記
    "首先", "其次", "再者", "最後", "總而言之", "綜觀", "回想",
    "記得", "那一次", "那一天", "那是", "話說",
)

EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001FAFF]|[☀-➿]|[\U0001F600-\U0001F64F]"
)
KAOMOJI_PATTERN = re.compile(r"[><Owowo\^\-]+[_o\.]+[><Owowo\^\-]+|XD|xd")


# --- 句子切分(中文標點) ---

SENTENCE_SEPARATORS = "。!?!?;;\n"


def _split_sentences(text: str) -> list[str]:
    """以 中文 / 英文 句末標點 + 換行切分。空白與標點本身去除。"""
    out: list[str] = []
    buf: list[str] = []
    for ch in text:
        if ch in SENTENCE_SEPARATORS:
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def _count_any(text: str, words: tuple[str, ...]) -> int:
    return sum(text.count(w) for w in words)


# --- Feature extraction ---

FEATURE_NAMES = (
    # 句長
    "avg_sentence_len", "sentence_len_std",
    "short_sentence_ratio", "long_sentence_ratio",
    # 標點 per1k
    "comma_per1k", "dunhao_per1k", "fenhao_per1k",
    "wenhao_per1k", "shenhao_per1k", "quote_per1k", "ellipsis_per1k",
    # 詞彙
    "transition_per1k", "modal_per1k",
    "lyrical_per1k", "abstract_per1k", "literary_per1k",
    # 結構
    "paragraph_count_norm", "paragraph_len_std", "structure_kw_per1k",
    # 雜訊
    "emoji_kao_per1k",
)


def extract_features(text: str) -> dict[str, float]:
    """從文字抽 20 個 stylometric features。文字長度 < 50 字會回傳全 0(避免噪音主導)。"""
    text = text.strip()
    chars_total = len(text)
    if chars_total < 50:
        return {k: 0.0 for k in FEATURE_NAMES}

    sentences = _split_sentences(text)
    paragraphs = _split_paragraphs(text)
    if not sentences:
        sentences = [text]

    sent_lens = [len(s) for s in sentences]
    para_lens = [len(p) for p in paragraphs] if paragraphs else [chars_total]

    def per1k(count: int) -> float:
        return round(count * 1000 / chars_total, 3)

    feats: dict[str, float] = {}

    # 句長
    feats["avg_sentence_len"] = round(statistics.mean(sent_lens), 2)
    feats["sentence_len_std"] = round(statistics.stdev(sent_lens), 2) if len(sent_lens) > 1 else 0.0
    feats["short_sentence_ratio"] = round(sum(1 for L in sent_lens if L < 12) / len(sent_lens), 3)
    feats["long_sentence_ratio"] = round(sum(1 for L in sent_lens if L > 30) / len(sent_lens), 3)

    # 標點
    feats["comma_per1k"] = per1k(text.count(",") + text.count(","))
    feats["dunhao_per1k"] = per1k(text.count("、"))
    feats["fenhao_per1k"] = per1k(text.count(";") + text.count(";"))
    feats["wenhao_per1k"] = per1k(text.count("?") + text.count("?"))
    feats["shenhao_per1k"] = per1k(text.count("!") + text.count("!"))
    feats["quote_per1k"] = per1k(text.count("「") + text.count("」") + text.count("『") + text.count("』"))
    feats["ellipsis_per1k"] = per1k(text.count("…") + text.count("..."))

    # 詞彙
    feats["transition_per1k"] = per1k(_count_any(text, TRANSITION_WORDS))
    feats["modal_per1k"] = per1k(_count_any(text, MODAL_PARTICLES))
    feats["lyrical_per1k"] = per1k(_count_any(text, LYRICAL_WORDS))
    feats["abstract_per1k"] = per1k(_count_any(text, ABSTRACT_WORDS))
    feats["literary_per1k"] = per1k(_count_any(text, LITERARY_WORDS))

    # 結構
    # paragraph_count_norm = 段落數 / 100 字 (避免 dominate 向量)
    feats["paragraph_count_norm"] = round(len(paragraphs) * 100 / chars_total, 3)
    feats["paragraph_len_std"] = round(statistics.stdev(para_lens), 2) if len(para_lens) > 1 else 0.0
    feats["structure_kw_per1k"] = per1k(_count_any(text, STRUCTURE_KEYWORDS))

    # 雜訊
    feats["emoji_kao_per1k"] = per1k(
        len(EMOJI_PATTERN.findall(text)) + len(KAOMOJI_PATTERN.findall(text))
    )

    return feats


# --- Cosine similarity ---

def _normalize_for_cosine(feats: dict[str, float]) -> dict[str, float]:
    """有些特徵 scale 差很多(avg_sentence_len 數十 / per1k 數)。用 z-score-like 的固定 scale 再算 cosine。"""
    # 經驗 scale (中文國高中作文觀測)
    scale = {
        "avg_sentence_len": 30.0,
        "sentence_len_std": 12.0,
        "short_sentence_ratio": 0.4,
        "long_sentence_ratio": 0.3,
        "comma_per1k": 80.0,
        "dunhao_per1k": 8.0,
        "fenhao_per1k": 5.0,
        "wenhao_per1k": 8.0,
        "shenhao_per1k": 8.0,
        "quote_per1k": 15.0,
        "ellipsis_per1k": 6.0,
        "transition_per1k": 30.0,
        "modal_per1k": 10.0,
        "lyrical_per1k": 12.0,
        "abstract_per1k": 15.0,
        "literary_per1k": 18.0,
        "paragraph_count_norm": 1.0,
        "paragraph_len_std": 80.0,
        "structure_kw_per1k": 10.0,
        "emoji_kao_per1k": 8.0,
    }
    return {k: feats.get(k, 0.0) / scale[k] for k in FEATURE_NAMES}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """0..1 cosine,值愈大愈相似。空向量回 0。"""
    na = _normalize_for_cosine(a)
    nb = _normalize_for_cosine(b)
    dot = sum(na[k] * nb[k] for k in FEATURE_NAMES)
    norm_a = math.sqrt(sum(na[k] ** 2 for k in FEATURE_NAMES))
    norm_b = math.sqrt(sum(nb[k] ** 2 for k in FEATURE_NAMES))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return round(dot / (norm_a * norm_b), 4)


def average_features(feats_list: list[dict[str, float]]) -> dict[str, float]:
    """合成多篇作文的「平均書寫指紋」(學生歷史)。"""
    assert feats_list, "需要至少 1 篇"
    out: dict[str, float] = {}
    for k in FEATURE_NAMES:
        vals = [f.get(k, 0.0) for f in feats_list]
        out[k] = round(statistics.mean(vals), 3)
    return out


# --- Top differing features helper ---

@dataclass
class FeatureDiff:
    feature: str
    student_value: float
    new_value: float
    ai_value: float
    abs_drift_from_student: float
    closer_to_ai: bool


def top_differing_features(
    student_avg: dict[str, float],
    new_essay: dict[str, float],
    ai_reference: dict[str, float],
    top_n: int = 6,
) -> list[FeatureDiff]:
    """找出新作文跟學生平均偏差最大的 N 個特徵,標註是否更靠近 AI 風格。

    用 _normalize_for_cosine 的 feature scale 把不同單位的差異拉平,
    避免 'student=0, ai=0, new=3' 這種小絕對差被當成巨大偏離。
    """
    student_n = _normalize_for_cosine(student_avg)
    new_n = _normalize_for_cosine(new_essay)
    ai_n = _normalize_for_cosine(ai_reference)
    diffs: list[FeatureDiff] = []
    for k in FEATURE_NAMES:
        sv = student_avg.get(k, 0.0)
        nv = new_essay.get(k, 0.0)
        av = ai_reference.get(k, 0.0)
        # scale-normalized drift (0..few)
        scaled_drift = abs(new_n[k] - student_n[k])
        # 是否更靠近 AI:用 normalized 距離比較,且 AI/學生本身要有顯著差異
        if abs(ai_n[k] - student_n[k]) > 0.05:
            closer_to_ai = abs(new_n[k] - ai_n[k]) < abs(new_n[k] - student_n[k])
        else:
            closer_to_ai = False
        diffs.append(FeatureDiff(
            feature=k,
            student_value=round(sv, 3),
            new_value=round(nv, 3),
            ai_value=round(av, 3),
            abs_drift_from_student=round(scaled_drift, 3),
            closer_to_ai=closer_to_ai,
        ))
    diffs.sort(key=lambda d: d.abs_drift_from_student, reverse=True)
    return diffs[:top_n]
