"""phonefix — Weighted Levenshtein edit distance for Mandarin bopomofo (注音).

Levenshtein (1965) edit distance with **phoneme-aware substitution costs**:
   - Same phoneme: 0
   - Common confusion pair (e.g., ㄓ↔ㄗ): 0.3
   - Same articulation class: 0.4
   - Same general place different manner: 0.6
   - Unrelated: 1.0

Pure stdlib (math + dataclass + collections). LLM never touches the
distance / alignment computation.

Bopomofo phonology (Mandarin):
   - 唇音 (bilabial): ㄅ ㄆ ㄇ
   - 唇齒音 (labiodental): ㄈ
   - 舌尖前音 (alveolar): ㄉ ㄊ ㄋ ㄌ
   - 舌尖後音/翹舌 (retroflex): ㄓ ㄔ ㄕ ㄖ
   - 舌尖音/平舌 (dental sibilant): ㄗ ㄘ ㄙ
   - 舌面音 (palatal): ㄐ ㄑ ㄒ
   - 舌根音 (velar): ㄍ ㄎ ㄏ
   - Vowels / glides: ㄚ ㄛ ㄜ ㄝ ㄞ ㄟ ㄠ ㄡ ㄢ ㄣ ㄤ ㄥ ㄦ ㄧ ㄨ ㄩ
   - Tones: 1 2 3 4 5 (5 = neutral 輕聲, '·')
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


# ============== Phoneme classification ==============
PHONEME_CLASSES = {
    "唇音": ["ㄅ", "ㄆ", "ㄇ"],
    "唇齒音": ["ㄈ"],
    "舌尖前音": ["ㄉ", "ㄊ", "ㄋ", "ㄌ"],
    "舌尖後音": ["ㄓ", "ㄔ", "ㄕ", "ㄖ"],
    "舌尖音": ["ㄗ", "ㄘ", "ㄙ"],
    "舌面音": ["ㄐ", "ㄑ", "ㄒ"],
    "舌根音": ["ㄍ", "ㄎ", "ㄏ"],
}

# Reverse lookup: phoneme → class
PHONEME_TO_CLASS = {}
for cls, phs in PHONEME_CLASSES.items():
    for p in phs:
        PHONEME_TO_CLASS[p] = cls


# Common 構音異常 substitution patterns (低 cost = 系統性錯誤,典型 articulation disorder)
COMMON_SUBSTITUTION_PAIRS: dict[frozenset[str], tuple[float, str]] = {
    frozenset({"ㄓ", "ㄗ"}): (0.3, "翹舌→平舌 (最常見構音錯誤)"),
    frozenset({"ㄔ", "ㄘ"}): (0.3, "翹舌→平舌 (最常見構音錯誤)"),
    frozenset({"ㄕ", "ㄙ"}): (0.3, "翹舌→平舌 (最常見構音錯誤)"),
    frozenset({"ㄖ", "ㄌ"}): (0.4, "ㄖ 弱化為 ㄌ (兒化音替代)"),
    frozenset({"ㄈ", "ㄏ"}): (0.5, "唇齒→舌根 (常見於閩南語影響)"),
    frozenset({"ㄐ", "ㄉ"}): (0.5, "舌面→舌尖前 (palatal→alveolar)"),
    frozenset({"ㄑ", "ㄊ"}): (0.5, "舌面→舌尖前 (palatal→alveolar)"),
    frozenset({"ㄒ", "ㄙ"}): (0.5, "舌面→平舌 (palatal→dental)"),
    frozenset({"ㄋ", "ㄌ"}): (0.4, "鼻音→邊音 (常見)"),
    frozenset({"ㄍ", "ㄎ"}): (0.4, "送氣 vs 不送氣 (常見幼兒)"),
    frozenset({"ㄅ", "ㄆ"}): (0.4, "送氣 vs 不送氣 (常見幼兒)"),
    frozenset({"ㄉ", "ㄊ"}): (0.4, "送氣 vs 不送氣 (常見幼兒)"),
}


def substitution_cost(a: str, b: str) -> tuple[float, str]:
    """Returns (cost, reason) for substituting phoneme a with b."""
    if a == b:
        return (0.0, "")
    key = frozenset({a, b})
    if key in COMMON_SUBSTITUTION_PAIRS:
        return COMMON_SUBSTITUTION_PAIRS[key]
    # Same articulation class
    cls_a = PHONEME_TO_CLASS.get(a)
    cls_b = PHONEME_TO_CLASS.get(b)
    if cls_a and cls_b and cls_a == cls_b:
        return (0.5, f"同類 ({cls_a}) 但不同音")
    # Both are consonants but different classes
    if cls_a and cls_b:
        return (0.8, f"跨類 ({cls_a} → {cls_b})")
    # One or both are vowel-like or unknown
    return (1.0, "完全不同類")


# ============== Tokenization ==============
def tokenize_syllable(syllable: str) -> list[str]:
    """Break a bopomofo syllable into a list of phoneme symbols + tone marker.

    Tones in bopomofo: ˊ(2) ˇ(3) ˋ(4) ·(5/輕聲). Tone 1 has no mark.
    """
    tokens = []
    tone_marks = {"ˊ": "2", "ˇ": "3", "ˋ": "4", "·": "5"}
    has_tone = False
    for ch in syllable:
        if ch in tone_marks:
            tokens.append(f"_tone{tone_marks[ch]}")
            has_tone = True
        elif ch.strip():
            tokens.append(ch)
    if not has_tone:
        tokens.append("_tone1")
    return tokens


def tokenize_phrase(phrase: str) -> list[list[str]]:
    """Parse a phrase like 'ㄓㄤ ㄒㄧㄢ' into list of syllables, each a list of phonemes."""
    syllables = phrase.strip().split()
    return [tokenize_syllable(s) for s in syllables]


# ============== Weighted Levenshtein ==============
@dataclass
class Alignment:
    operations: list[tuple[str, str, str]]    # (op, target, actual) where op in {"=","sub","del","ins"}
    total_cost: float
    n_substitutions: int = 0
    n_deletions: int = 0
    n_insertions: int = 0


def weighted_edit_distance(target: list[str], actual: list[str],
                              ins_cost: float = 1.0,
                              del_cost: float = 1.0) -> Alignment:
    """Levenshtein with custom substitution cost. Returns alignment + total cost."""
    n, m = len(target), len(actual)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + del_cost
        back[i][0] = ("del", target[i - 1], None)
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + ins_cost
        back[0][j] = ("ins", None, actual[j - 1])

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub_c, _reason = substitution_cost(target[i - 1], actual[j - 1])
            sub = dp[i - 1][j - 1] + sub_c
            ins = dp[i][j - 1] + ins_cost
            del_ = dp[i - 1][j] + del_cost
            best = min(sub, ins, del_)
            dp[i][j] = best
            if best == sub:
                op = "=" if target[i - 1] == actual[j - 1] else "sub"
                back[i][j] = (op, target[i - 1], actual[j - 1])
            elif best == ins:
                back[i][j] = ("ins", None, actual[j - 1])
            else:
                back[i][j] = ("del", target[i - 1], None)

    # Backtrace
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        op_info = back[i][j]
        if op_info is None:
            break
        op, t, a = op_info
        ops.append((op, t, a))
        if op == "=":
            i -= 1; j -= 1
        elif op == "sub":
            i -= 1; j -= 1
        elif op == "ins":
            j -= 1
        elif op == "del":
            i -= 1
    ops.reverse()

    n_sub = sum(1 for op, _, _ in ops if op == "sub")
    n_del = sum(1 for op, _, _ in ops if op == "del")
    n_ins = sum(1 for op, _, _ in ops if op == "ins")

    return Alignment(
        operations=ops,
        total_cost=round(dp[n][m], 3),
        n_substitutions=n_sub,
        n_deletions=n_del,
        n_insertions=n_ins,
    )


# ============== Aggregate analysis ==============
@dataclass
class PronunciationReport:
    n_syllables: int
    n_phonemes_target: int
    n_phonemes_actual: int
    total_edit_cost: float
    accuracy_pct: float                              # 1 - cost / max_possible
    error_patterns: dict[str, int]                    # 構音模式 → 次數
    error_details: list[dict]                         # per substitution detail
    syllable_alignments: list[Alignment] = field(default_factory=list)


def analyze_pronunciation(target_phrase: str, actual_phrase: str) -> PronunciationReport:
    """Compare target vs actual bopomofo phrase, produce error analysis."""
    target_syls = tokenize_phrase(target_phrase)
    actual_syls = tokenize_phrase(actual_phrase)

    # Align syllable-by-syllable (assume same number; if not, pad)
    n_syls = min(len(target_syls), len(actual_syls))

    syllable_aligns = []
    total_cost = 0.0
    error_pattern_counter: Counter = Counter()
    error_details = []
    total_phonemes_target = 0
    total_phonemes_actual = 0

    for idx in range(n_syls):
        t = target_syls[idx]
        a = actual_syls[idx]
        align = weighted_edit_distance(t, a)
        syllable_aligns.append(align)
        total_cost += align.total_cost
        total_phonemes_target += len(t)
        total_phonemes_actual += len(a)

        # Identify systematic patterns
        for op, t_p, a_p in align.operations:
            if op == "sub":
                _cost, reason = substitution_cost(t_p, a_p)
                if reason:
                    error_pattern_counter[reason] += 1
                    error_details.append({
                        "syllable_idx": idx,
                        "target_phoneme": t_p,
                        "actual_phoneme": a_p,
                        "pattern": reason,
                        "cost": _cost,
                    })

    max_possible_cost = max(total_phonemes_target, total_phonemes_actual) * 1.0
    accuracy_pct = 1.0 - (total_cost / max_possible_cost) if max_possible_cost > 0 else 1.0

    return PronunciationReport(
        n_syllables=n_syls,
        n_phonemes_target=total_phonemes_target,
        n_phonemes_actual=total_phonemes_actual,
        total_edit_cost=round(total_cost, 3),
        accuracy_pct=round(accuracy_pct * 100, 1),
        error_patterns=dict(error_pattern_counter),
        error_details=error_details,
        syllable_alignments=syllable_aligns,
    )


def detect_systematic_pattern(report: PronunciationReport) -> str | None:
    """Identify if the child has a systematic articulation disorder pattern."""
    if not report.error_patterns:
        return None
    sorted_patterns = sorted(report.error_patterns.items(), key=lambda x: -x[1])
    top_pattern, top_count = sorted_patterns[0]
    if top_count >= 2:
        return f"系統性錯誤 ({top_count}x): {top_pattern}"
    return f"零星錯誤: {top_pattern}"
