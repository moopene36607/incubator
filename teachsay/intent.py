"""teachsay — 家長 LINE 訊息 intent 分類(純函式,no LLM, no I/O).

6 類常見 intent:
  - leave_request:請假
  - homework_question:作業 / 課業詢問
  - behavior_concern:行為 / 情緒 / 同學相處
  - schedule_clarification:行程 / 通知 / 時間確認
  - complaint:抱怨 / 不滿(常涉及老師 / 學校 / 其他學生)
  - general_inquiry:一般問候 / 其他

同時抽出 urgency:high / medium / low(用於排序老師待回 list)。
"""

from __future__ import annotations

from dataclasses import dataclass


INTENT_KEYWORDS = {
    "leave_request": ("請假", "不能來", "看醫生", "醫生", "醫師", "牙醫", "牙齒", "感冒", "發燒",
                       "生病", "事假", "病假", "回診", "看診", "晚到", "晚一點到", "預約"),
    "homework_question": ("作業", "功課", "怎麼寫", "考試", "考券", "複習", "範圍", "重點"),
    "behavior_concern": ("吵架", "打架", "欺負", "被欺負", "霸凌", "哭", "不想上學", "情緒", "難過", "生氣"),
    "schedule_clarification": ("幾點", "什麼時候", "時間", "戶外教學", "校外", "活動", "通知", "回條", "繳費"),
    "complaint": ("不滿", "抱怨", "不公平", "為什麼", "投訴", "意見", "建議", "希望改善", "覺得不對"),
}

URGENT_KEYWORDS = ("急", "馬上", "今天", "現在", "立刻", "緊急", "事情", "等等")
HIGH_URGENCY_INTENTS = ("complaint", "behavior_concern")


@dataclass
class Intent:
    category: str           # leave_request / homework_question / ...
    confidence: float       # 0-1
    urgency: str            # high / medium / low
    keyword_hits: dict[str, int]  # 每類 intent 命中的關鍵字數量


def classify_parent_message(text: str) -> Intent:
    """純函式 keyword-based 分類。每類用關鍵字命中數計分,取最高。"""
    text = text.strip()
    hits = {cat: sum(1 for kw in kws if kw in text) for cat, kws in INTENT_KEYWORDS.items()}

    # 找最高分類
    max_cat = max(hits, key=lambda c: hits[c]) if hits else "general_inquiry"
    max_score = hits[max_cat]

    if max_score == 0:
        category = "general_inquiry"
        confidence = 0.5
    else:
        category = max_cat
        # confidence = 命中數 / total 該類關鍵字數
        n_keywords = len(INTENT_KEYWORDS[max_cat])
        confidence = round(min(1.0, max_score / max(n_keywords / 2, 1)), 2)

    # Urgency
    has_urgent = any(uk in text for uk in URGENT_KEYWORDS)
    if category in HIGH_URGENCY_INTENTS:
        urgency = "high"
    elif has_urgent:
        urgency = "high"
    elif category in ("leave_request", "schedule_clarification"):
        urgency = "medium"
    else:
        urgency = "low"

    return Intent(
        category=category,
        confidence=confidence,
        urgency=urgency,
        keyword_hits=hits,
    )


INTENT_LABEL_ZH = {
    "leave_request": "請假",
    "homework_question": "課業 / 作業",
    "behavior_concern": "行為 / 情緒",
    "schedule_clarification": "行程 / 通知",
    "complaint": "抱怨 / 建議",
    "general_inquiry": "一般問候",
}
