"""Weak Supervision (Snorkel-style) with Dawid-Skene EM for noisy-label aggregation.

We model a set of weak labelling functions (LFs), each of which inspects a
message and emits a label in {0, 1, ..., K-1} or abstains (-1). Each LF has
its own (unknown) accuracy / confusion matrix per true class. We fit a
Dawid & Skene (1979) latent-class model via Expectation-Maximisation:

    Latent:    y_i  (true class of message i)
    Observed:  L_{i,j}  (label emitted by LF j on message i; -1 = abstain)
    Params:
        pi[c]            = P(y = c)
        theta_j[c][l]    = P(LF j emits l | true class c)

E-step:
    P(y_i = c | observations)
        propto  pi[c] * prod_{j : L_ij != -1}  theta_j[c][L_ij]

M-step:
    pi[c]          = (sum_i P(y_i = c)) / N
    theta_j[c][l]  = (sum_i [L_ij = l] * P(y_i = c)) /
                     (sum_i [L_ij != -1] * P(y_i = c))

We also expose `majority_vote` as a much simpler aggregator for sanity-check.

Pure stdlib: math + statistics + dataclasses + collections.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field


ABSTAIN = -1


# =========================== labelling functions ======================== #


def lf_invest_keywords(text: str) -> int:
    """LF: bombs out '假投資' if text mentions strong investment-scam keywords."""
    keys = ["保證獲利", "穩賺", "高報酬", "年化", "翻倍", "內線消息",
            "老師帶你", "穩賺方法", "投資群", "回收快", "保本"]
    return 1 if any(k in text for k in keys) else ABSTAIN


def lf_impersonation_authority(text: str) -> int:
    """LF: bombs out '假冒身份' if text mentions authority + action request."""
    auth = ["警察", "檢察官", "檢調", "法院", "監管會", "凍結帳戶", "銀行通知", "帳戶異常"]
    action = ["驗證碼", "個資", "帳號", "密碼", "立即處理", "立即配合"]
    if any(a in text for a in auth) and any(b in text for b in action):
        return 2
    if "您的帳戶異常" in text or "您的卡片被盜刷" in text:
        return 2
    return ABSTAIN


def lf_phishing_short_link(text: str) -> int:
    """LF: bombs out '釣魚連結' if text contains a shortened URL pattern."""
    patterns = ["bit.ly/", "tinyurl.com/", "lihi.cc/", "shorturl.at/",
                "ppt.cc/", "tinyurl.cc/", "is.gd/", "reurl.cc/"]
    if any(p in text.lower() for p in patterns):
        return 3
    if "點此領取" in text or "立即領取" in text:
        return 3
    return ABSTAIN


def lf_phishing_prize(text: str) -> int:
    """LF: 中獎 / 抽到 / 限時類話術 → 釣魚."""
    keys = ["恭喜中獎", "您已中獎", "限時搶購", "驚喜禮包", "免費領取"]
    return 3 if any(k in text for k in keys) else ABSTAIN


def lf_borrow_urgency(text: str) -> int:
    """LF: 急借錢 / 親友裝熟 → 假借錢."""
    keys = ["急用", "幫忙轉帳", "我現在不方便", "媽我手機壞了", "弟我", "兄弟",
            "明天還", "週轉一下", "借個幾萬"]
    return 4 if any(k in text for k in keys) else ABSTAIN


def lf_msg_length_link(text: str) -> int:
    """LF: 訊息極短 + 帶連結, 通常 = 釣魚."""
    has_link = ("http" in text or "www." in text)
    if has_link and len(text) < 30:
        return 3
    return ABSTAIN


def lf_legitimate_long_no_link(text: str) -> int:
    """LF: 長訊息 + 無連結 + 無敏感字 → 多半合法 (極弱信號)."""
    if len(text) > 30 and "http" not in text and "投資" not in text and "急" not in text:
        return 0
    return ABSTAIN


def lf_invest_percent_number(text: str) -> int:
    """LF: 訊息含 數字% + 時間區間 (一天 / 一週) → 投資詐騙."""
    keys = ["每天", "每週", "每月", "天賺", "週賺", "月賺"]
    has_time = any(k in text for k in keys)
    has_pct = "%" in text
    if has_time and (has_pct or "萬" in text):
        return 1
    return ABSTAIN


def lf_mlm_dating(text: str) -> int:
    """LF: 假交友 + 拉投資 / MLM 話術."""
    keys = ["我們是命中註定", "可以聊聊嗎", "你看起來很特別", "加我 LINE",
             "認識你", "感情", "緣分"]
    if any(k in text for k in keys):
        # 暫時歸為 invest (因為這類最終目的多半是拉投資 / 假交友詐騙)
        return 1
    return ABSTAIN


def lf_impersonation_family(text: str) -> int:
    """LF: 假冒家人「媽我手機壞了」這類話術 → 假借錢 (不是 impersonation 因為對方說自己是親人)."""
    keys = ["媽我", "爸我", "我手機壞了", "請媽幫我", "請爸幫我",
            "我這隻是新號碼"]
    return 4 if any(k in text for k in keys) else ABSTAIN


DEFAULT_LFS = [
    ("lf_invest_keywords",       lf_invest_keywords),
    ("lf_impersonation_authority", lf_impersonation_authority),
    ("lf_phishing_short_link",    lf_phishing_short_link),
    ("lf_phishing_prize",         lf_phishing_prize),
    ("lf_borrow_urgency",         lf_borrow_urgency),
    ("lf_msg_length_link",        lf_msg_length_link),
    ("lf_legitimate_long_no_link", lf_legitimate_long_no_link),
    ("lf_invest_percent_number",  lf_invest_percent_number),
    ("lf_mlm_dating",             lf_mlm_dating),
    ("lf_impersonation_family",   lf_impersonation_family),
]


CLASS_NAMES = [
    "合法訊息",      # 0
    "假投資詐騙",    # 1
    "假冒身份詐騙",  # 2
    "釣魚連結 / 中獎詐騙",   # 3
    "假借錢詐騙",    # 4
]
N_CLASSES = len(CLASS_NAMES)


# ============================ apply LFs ============================== #


def apply_lfs(text: str, lfs=DEFAULT_LFS) -> list[int]:
    return [fn(text) for _, fn in lfs]


def apply_lfs_batch(texts: list[str], lfs=DEFAULT_LFS) -> list[list[int]]:
    return [apply_lfs(t, lfs) for t in texts]


# ============================ majority vote ========================== #


def majority_vote(lf_outputs: list[int], n_classes: int = N_CLASSES) -> tuple[int, dict[int, int]]:
    """Plain majority vote across non-abstaining LFs.

    Returns (predicted_class, votes_per_class).
    Ties break toward smallest class index (deterministic).
    """
    votes: Counter[int] = Counter()
    for L in lf_outputs:
        if L != ABSTAIN:
            votes[L] += 1
    if not votes:
        return 0, {c: 0 for c in range(n_classes)}  # everyone abstained -> default legitimate
    top = max(votes.values())
    winners = sorted([c for c, v in votes.items() if v == top])
    return winners[0], dict(votes)


# ============================ Dawid-Skene EM ========================= #


@dataclass
class DawidSkeneModel:
    n_classes: int
    n_lfs: int
    lf_names: list[str]
    pi: list[float]                        # P(y = c)
    theta: list[list[list[float]]]         # theta[j][c][l] (l from 0..n_classes-1; abstain handled separately)
    abstain_rate: list[list[float]]        # abstain_rate[j][c] = P(LF j abstains | true class c)
    n_iter_used: int
    final_log_lik: float


def _init_theta(n_lfs: int, n_classes: int, diagonal: float = 0.7) -> list[list[list[float]]]:
    """Initialise confusion matrices: high diagonal, uniform off-diagonal."""
    off = (1.0 - diagonal) / max(n_classes - 1, 1)
    theta = []
    for _ in range(n_lfs):
        mat = []
        for c in range(n_classes):
            row = [off] * n_classes
            row[c] = diagonal
            mat.append(row)
        theta.append(mat)
    return theta


def _init_abstain(n_lfs: int, n_classes: int, rate: float = 0.5) -> list[list[float]]:
    return [[rate] * n_classes for _ in range(n_lfs)]


def fit_dawid_skene(
    L: list[list[int]],      # L[i][j] = output of LF j on message i, or ABSTAIN (-1)
    n_classes: int = N_CLASSES,
    lf_names: list[str] | None = None,
    n_iter: int = 50,
    tol: float = 1e-6,
    smoothing: float = 0.1,
    init_diagonal: float = 0.7,
) -> DawidSkeneModel:
    """Dawid-Skene EM. No true labels needed.

    Initialise responsibilities q[i][c] from majority vote (standard DS practice)
    rather than uniform; otherwise symmetric init collapses to a single class.
    """
    n = len(L)
    if n == 0:
        raise ValueError("fit_dawid_skene 需要至少 1 個 message")
    n_lfs = len(L[0])
    if lf_names is None:
        lf_names = [f"LF_{j}" for j in range(n_lfs)]

    # Initialise responsibilities from majority vote with smoothing.
    # q[i][c] = (votes_for_c + smoothing) / (total_votes + n_classes * smoothing)
    init_q = []
    for i in range(n):
        votes = [smoothing] * n_classes
        total = n_classes * smoothing
        for j in range(n_lfs):
            l = L[i][j]
            if l != ABSTAIN and 0 <= l < n_classes:
                votes[l] += 1.0
                total += 1.0
        init_q.append([v / total for v in votes])

    # Run an initial M-step from these responsibilities to get pi/theta/abstain.
    pi = [sum(init_q[i][c] for i in range(n)) / n for c in range(n_classes)]
    theta = _init_theta(n_lfs, n_classes, diagonal=init_diagonal)
    abstain = _init_abstain(n_lfs, n_classes, rate=0.5)
    for j in range(n_lfs):
        soft_count_class = [0.0] * n_classes
        soft_count_active = [0.0] * n_classes
        soft_count_emit = [[0.0] * n_classes for _ in range(n_classes)]
        for i in range(n):
            for c in range(n_classes):
                soft_count_class[c] += init_q[i][c]
            if L[i][j] != ABSTAIN and 0 <= L[i][j] < n_classes:
                for c in range(n_classes):
                    soft_count_active[c] += init_q[i][c]
                    soft_count_emit[c][L[i][j]] += init_q[i][c]
        for c in range(n_classes):
            active_p = (soft_count_active[c] + smoothing) / (soft_count_class[c] + 2.0 * smoothing)
            abstain[j][c] = 1.0 - active_p
            denom = soft_count_active[c] + n_classes * smoothing
            for l in range(n_classes):
                theta[j][c][l] = (soft_count_emit[c][l] + smoothing) / denom

    prev_ll = float("-inf")
    last_iter = 0

    for it in range(n_iter):
        last_iter = it + 1

        # ------- E-step: compute responsibilities q[i][c] ∝ pi[c] * prod_j P(L_ij | c) -------
        q = []
        log_lik = 0.0
        for i in range(n):
            log_unn = [math.log(max(pi[c], 1e-300)) for c in range(n_classes)]
            for j in range(n_lfs):
                if L[i][j] == ABSTAIN:
                    # Contribution: probability of abstain | y=c
                    for c in range(n_classes):
                        log_unn[c] += math.log(max(abstain[j][c], 1e-12))
                else:
                    l_obs = L[i][j]
                    if l_obs < 0 or l_obs >= n_classes:
                        # Malformed LF output -- treat as abstain.
                        for c in range(n_classes):
                            log_unn[c] += math.log(max(abstain[j][c], 1e-12))
                    else:
                        for c in range(n_classes):
                            # Probability of emitting this specific non-abstain label given y=c
                            p_active = max(1.0 - abstain[j][c], 1e-12)
                            log_unn[c] += math.log(p_active) + math.log(max(theta[j][c][l_obs], 1e-12))
            mx = max(log_unn)
            exps = [math.exp(v - mx) for v in log_unn]
            Z = sum(exps)
            log_lik += mx + math.log(Z)
            q.append([e / Z for e in exps])

        # ------- M-step: update pi, theta, abstain -------
        pi = [sum(q[i][c] for i in range(n)) / n for c in range(n_classes)]

        for j in range(n_lfs):
            # Sums needed
            soft_count_class = [0.0] * n_classes  # sum_i q[i][c]
            soft_count_active = [0.0] * n_classes  # sum_i [L_ij != -1] q[i][c]
            soft_count_emit = [[0.0] * n_classes for _ in range(n_classes)]
            # soft_count_emit[c][l] = sum_i [L_ij == l] * q[i][c]

            for i in range(n):
                for c in range(n_classes):
                    soft_count_class[c] += q[i][c]
                if L[i][j] != ABSTAIN and 0 <= L[i][j] < n_classes:
                    for c in range(n_classes):
                        soft_count_active[c] += q[i][c]
                        soft_count_emit[c][L[i][j]] += q[i][c]

            for c in range(n_classes):
                # Active vs abstain rate (with Laplace smoothing)
                active_p = (soft_count_active[c] + smoothing) / (soft_count_class[c] + 2.0 * smoothing)
                abstain[j][c] = 1.0 - active_p
                # theta_j[c][l] = soft_count_emit[c][l] / soft_count_active[c]
                denom = soft_count_active[c] + n_classes * smoothing
                for l in range(n_classes):
                    theta[j][c][l] = (soft_count_emit[c][l] + smoothing) / denom

        if abs(log_lik - prev_ll) < tol:
            break
        prev_ll = log_lik

    return DawidSkeneModel(
        n_classes=n_classes,
        n_lfs=n_lfs,
        lf_names=list(lf_names),
        pi=pi,
        theta=theta,
        abstain_rate=abstain,
        n_iter_used=last_iter,
        final_log_lik=prev_ll if math.isfinite(prev_ll) else log_lik,
    )


def predict_one(model: DawidSkeneModel, lf_outputs: list[int]) -> dict:
    """Return posterior over classes for a single message + predicted class."""
    log_unn = [math.log(max(model.pi[c], 1e-300)) for c in range(model.n_classes)]
    for j in range(model.n_lfs):
        if lf_outputs[j] == ABSTAIN:
            for c in range(model.n_classes):
                log_unn[c] += math.log(max(model.abstain_rate[j][c], 1e-12))
        else:
            l = lf_outputs[j]
            if l < 0 or l >= model.n_classes:
                for c in range(model.n_classes):
                    log_unn[c] += math.log(max(model.abstain_rate[j][c], 1e-12))
            else:
                for c in range(model.n_classes):
                    p_active = max(1.0 - model.abstain_rate[j][c], 1e-12)
                    log_unn[c] += math.log(p_active) + math.log(max(model.theta[j][c][l], 1e-12))
    mx = max(log_unn)
    exps = [math.exp(v - mx) for v in log_unn]
    Z = sum(exps)
    probs = [e / Z for e in exps]
    pred = max(range(model.n_classes), key=lambda c: probs[c])
    return {
        "predicted_class": pred,
        "probs": probs,
        "lf_outputs": lf_outputs,
    }


# ============================ diagnostics ============================ #


def lf_coverage(L: list[list[int]]) -> list[float]:
    """Fraction of messages where each LF did NOT abstain."""
    if not L:
        return []
    n = len(L)
    n_lfs = len(L[0])
    cover = [0] * n_lfs
    for i in range(n):
        for j in range(n_lfs):
            if L[i][j] != ABSTAIN:
                cover[j] += 1
    return [c / n for c in cover]


def lf_estimated_accuracy(model: DawidSkeneModel) -> list[float]:
    """For each LF, average diagonal of confusion matrix weighted by class prior.

    accuracy_j = sum_c pi[c] * theta_j[c][c]
    (Approximation: assumes LF emits its "claimed" label when active.)
    """
    accs = []
    for j in range(model.n_lfs):
        a = sum(model.pi[c] * model.theta[j][c][c] for c in range(model.n_classes))
        accs.append(a)
    return accs
