"""teachsay — 老師回覆風格特徵抽取 + active learning update(純函式,no I/O, no LLM).

責任:
  - 從老師過去 5-10 則回覆中抽 12 個風格特徵(平均長度 / 開頭暖度 / 結尾正式度 /
    emoji 密度 / 敬語強度 / 引用具體事件頻率 / 段落結構 / 語氣詞 / ...)
  - 平均成「老師個人風格 profile」
  - 接收「老師編輯後的版本」作為 active learning signal,更新 profile + 顯示 diff
  - 計算「草稿 vs profile」風格匹配度(0-100)

100% stdlib(只用 statistics + re),不依賴 numpy。

Active learning loop:
  baseline_profile = compute_profile(initial_corpus)
  for each new message:
      draft = LLM(intent, baseline_profile)
      teacher_edits draft → final_text
      delta = extract_style_features(final_text) - extract_style_features(draft)
      baseline_profile = update_profile(baseline_profile, final_text)  # 平滑加入 corpus
  → profile 逐步收斂到該老師的真實風格
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field, asdict


# 中文敬語 / 暖意 / 表情符號 字典
WARMTH_OPENERS = ("家長您好", "辛苦了", "謝謝您", "您好", "親愛的")
FORMAL_CLOSERS = ("謹此", "此致", "敬祝", "敬上", "順頌", "謝謝")
WARM_CLOSERS = ("一起加油", "希望", "祝福", "辛苦了", "幫忙")
HONORIFICS = ("您", "麻煩", "請", "煩請", "貴")
MODAL_PARTICLES = ("呢", "啦", "啊", "喔", "唷", "哦", "吧")
EVENT_MARKERS = ("今天", "昨天", "上次", "前天", "這週", "上週", "明天", "下週")
SPECIFIC_ACTION_MARKERS = ("我會", "我們會", "建議", "可以", "請您", "希望您")

EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001FAFF]|[☀-➿]|[\U0001F600-\U0001F64F]"
)


# 12 個風格特徵 — 數值 0-100 normalized
FEATURE_NAMES = (
    "avg_length",                    # 平均字數
    "sentence_count_normalized",     # 每 100 字句數
    "opener_warmth_score",           # 0-10 開頭暖度
    "closer_formality_score",        # 0-10 結尾正式度
    "emoji_density_per100",          # emoji 每 100 字
    "honorific_density_per100",      # 敬語密度
    "modal_particle_density_per100", # 語氣詞密度
    "event_reference_count",         # 引用具體事件次數
    "specific_action_count",         # 具體行動建議次數
    "paragraph_count",               # 段落數
    "question_density_per100",       # 問句密度
    "exclamation_density_per100",    # 驚嘆密度
)


@dataclass
class StyleFeatures:
    """從一則回覆抽出的 12 個特徵。"""
    avg_length: float
    sentence_count_normalized: float
    opener_warmth_score: float
    closer_formality_score: float
    emoji_density_per100: float
    honorific_density_per100: float
    modal_particle_density_per100: float
    event_reference_count: float
    specific_action_count: float
    paragraph_count: float
    question_density_per100: float
    exclamation_density_per100: float


def _per100(count: int, text_len: int) -> float:
    if text_len <= 0:
        return 0.0
    return round(count * 100 / text_len, 2)


def _count_any(text: str, words: tuple[str, ...]) -> int:
    return sum(text.count(w) for w in words)


def _opener_warmth(text: str) -> float:
    """檢查開頭 30 字內是否有暖意關鍵字。"""
    head = text[:30]
    hits = sum(1 for w in WARMTH_OPENERS if w in head)
    return min(10.0, hits * 5.0)


def _closer_formality(text: str) -> float:
    """檢查結尾 30 字內是否正式 / 暖意收尾。"""
    tail = text[-30:]
    formal = sum(1 for w in FORMAL_CLOSERS if w in tail)
    warm = sum(1 for w in WARM_CLOSERS if w in tail)
    # 正式度 = formal × 3 + warm × 1.5(formal 比 warm 偏正式)
    return min(10.0, formal * 3.0 + warm * 1.5)


def extract_style_features(text: str) -> StyleFeatures:
    text = text.strip()
    L = len(text)
    if L == 0:
        return StyleFeatures(*([0.0] * 12))
    sentences = [s.strip() for s in re.split(r"[。!?!\?\n]", text) if s.strip()]
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    n_sentences = max(1, len(sentences))

    return StyleFeatures(
        avg_length=float(L),
        sentence_count_normalized=_per100(n_sentences, L),
        opener_warmth_score=_opener_warmth(text),
        closer_formality_score=_closer_formality(text),
        emoji_density_per100=_per100(len(EMOJI_PATTERN.findall(text)), L),
        honorific_density_per100=_per100(_count_any(text, HONORIFICS), L),
        modal_particle_density_per100=_per100(_count_any(text, MODAL_PARTICLES), L),
        event_reference_count=float(_count_any(text, EVENT_MARKERS)),
        specific_action_count=float(_count_any(text, SPECIFIC_ACTION_MARKERS)),
        paragraph_count=float(len(paragraphs)),
        question_density_per100=_per100(text.count("?") + text.count("?"), L),
        exclamation_density_per100=_per100(text.count("!") + text.count("!"), L),
    )


@dataclass
class TeacherStyleProfile:
    """老師個人風格 profile — 從多則回覆平均出。"""
    n_samples: int                   # 累積學了幾則
    features: StyleFeatures
    feature_names: tuple[str, ...] = FEATURE_NAMES

    def to_dict(self) -> dict:
        return {
            "n_samples": self.n_samples,
            "features": asdict(self.features),
        }


def compute_profile(texts: list[str]) -> TeacherStyleProfile:
    """從多則文字算 baseline profile(等權平均)。"""
    if not texts:
        return TeacherStyleProfile(n_samples=0, features=StyleFeatures(*([0.0] * 12)))
    all_features = [extract_style_features(t) for t in texts]
    averaged = {}
    for name in FEATURE_NAMES:
        vals = [getattr(f, name) for f in all_features]
        averaged[name] = round(statistics.mean(vals), 2)
    return TeacherStyleProfile(
        n_samples=len(texts),
        features=StyleFeatures(**averaged),
    )


def update_profile_with_new_sample(profile: TeacherStyleProfile, new_text: str) -> TeacherStyleProfile:
    """Active learning update:用 weighted average 把新 sample 加入 profile。

    用 weight = 1 / (n_samples + 1) 讓早期 sample 影響大(快速適應),
    後期 sample 影響小(穩定收斂)。
    """
    new_features = extract_style_features(new_text)
    n_old = profile.n_samples
    n_new = n_old + 1

    merged = {}
    for name in FEATURE_NAMES:
        old_val = getattr(profile.features, name)
        new_val = getattr(new_features, name)
        merged[name] = round((old_val * n_old + new_val) / n_new, 2)

    return TeacherStyleProfile(
        n_samples=n_new,
        features=StyleFeatures(**merged),
    )


@dataclass
class FeatureDelta:
    """單一特徵的變化。"""
    feature: str
    old_value: float
    new_value: float
    delta: float
    interpretation: str          # 人話解釋(例「emoji 比之前多用」)


# 對每個特徵的「人話解釋」模板
DELTA_INTERPRETATION = {
    "avg_length": ("回覆變更長", "回覆變更短"),
    "opener_warmth_score": ("開頭更暖", "開頭更直接"),
    "closer_formality_score": ("結尾更正式", "結尾更輕鬆"),
    "emoji_density_per100": ("emoji 比之前多用", "emoji 比之前少用"),
    "honorific_density_per100": ("敬語密度提高", "敬語密度降低"),
    "modal_particle_density_per100": ("語氣詞變多 (啦 / 呢 / 喔)", "語氣詞變少"),
    "event_reference_count": ("引用具體事件次數增加(更個人化)", "引用具體事件減少"),
    "specific_action_count": ("具體行動建議增加", "具體行動建議減少"),
    "paragraph_count": ("分段更多", "分段更少"),
    "question_density_per100": ("用更多問句", "用更少問句"),
    "exclamation_density_per100": ("驚嘆號變多", "驚嘆號變少"),
    "sentence_count_normalized": ("句子更短", "句子更長"),
}


def compute_diff(old: TeacherStyleProfile, new: TeacherStyleProfile, top_n: int = 5) -> list[FeatureDelta]:
    """找出 profile 之間最大的變化 — 用於展示 active learning 學到什麼。"""
    out: list[FeatureDelta] = []
    for name in FEATURE_NAMES:
        old_v = getattr(old.features, name)
        new_v = getattr(new.features, name)
        delta = new_v - old_v
        if abs(delta) < 0.05:
            continue
        increase_text, decrease_text = DELTA_INTERPRETATION.get(name, (f"{name} 增", f"{name} 減"))
        interp = increase_text if delta > 0 else decrease_text
        out.append(FeatureDelta(
            feature=name,
            old_value=old_v,
            new_value=new_v,
            delta=round(delta, 2),
            interpretation=interp,
        ))
    # 排序 by |delta| 的相對大小(以特徵典型量級 normalize)
    feature_scales = {
        "avg_length": 50.0,
        "sentence_count_normalized": 5.0,
        "opener_warmth_score": 5.0,
        "closer_formality_score": 5.0,
        "emoji_density_per100": 3.0,
        "honorific_density_per100": 3.0,
        "modal_particle_density_per100": 3.0,
        "event_reference_count": 1.5,
        "specific_action_count": 1.5,
        "paragraph_count": 2.0,
        "question_density_per100": 2.0,
        "exclamation_density_per100": 2.0,
    }
    out.sort(key=lambda d: abs(d.delta) / feature_scales.get(d.feature, 1.0), reverse=True)
    return out[:top_n]


def style_match_score(draft_text: str, profile: TeacherStyleProfile) -> float:
    """評分:草稿風格與老師 profile 的相似度(0-100,越高越相似)。

    用 1 / (1 + normalized_distance) 的形式。
    """
    draft_features = extract_style_features(draft_text)
    feature_scales = {
        "avg_length": 50.0,
        "sentence_count_normalized": 5.0,
        "opener_warmth_score": 5.0,
        "closer_formality_score": 5.0,
        "emoji_density_per100": 3.0,
        "honorific_density_per100": 3.0,
        "modal_particle_density_per100": 3.0,
        "event_reference_count": 1.5,
        "specific_action_count": 1.5,
        "paragraph_count": 2.0,
        "question_density_per100": 2.0,
        "exclamation_density_per100": 2.0,
    }
    diff = 0.0
    for name in FEATURE_NAMES:
        d = getattr(draft_features, name)
        p = getattr(profile.features, name)
        diff += abs(d - p) / feature_scales.get(name, 1.0)
    avg_normalized_diff = diff / len(FEATURE_NAMES)
    score = 100 / (1 + avg_normalized_diff)
    return round(score, 1)
