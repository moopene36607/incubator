"""examready CLI — 升學考前多科溫習 MDP 排程助手。

Usage:
    python examready.py --student samples/student.json
    python examready.py --student samples/student.json --no-ai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from mdp import (
    Subject, StudentState, StudyPlan, Action,
    find_optimal_tonight, project_seven_day_plan, baseline_score_if_no_study,
    fair_share_baseline, weighted_familiarity, predicted_exam_score,
)


def load_student(path: Path) -> tuple[StudyPlan, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    valid_fields = set(Subject.__dataclass_fields__.keys())
    subjects = [
        Subject(**{k: v for k, v in s.items() if k in valid_fields})
        for s in data["subjects"]
    ]
    state = StudentState(
        familiarity={s["code"]: s["familiarity"] for s in data["subjects"]},
        days_since_studied={s["code"]: s.get("days_since_studied", 0) for s in data["subjects"]},
        days_to_exam=data["days_to_exam"],
    )
    plan = StudyPlan(
        name=data["student_name"],
        student_state=state,
        subjects=subjects,
        nightly_available_minutes=data["nightly_available_minutes"],
        max_subjects_per_night=data.get("max_subjects_per_night", 3),
    )
    return plan, data


def fmt_action(action: Action, subjects: list[Subject]) -> str:
    if not action.allocation:
        return "(無)"
    name_by_code = {s.code: s.name for s in subjects}
    parts = []
    for code, minutes in sorted(action.allocation.items(), key=lambda x: -x[1]):
        parts.append(f"{name_by_code.get(code, code)} {minutes}分")
    return " + ".join(parts)


def render_no_ai(plan: StudyPlan, data: dict) -> str:
    best_action, all_results = find_optimal_tonight(plan)
    best_score = all_results[0].expected_exam_score if all_results else 0
    fair = fair_share_baseline(plan)
    no_study = baseline_score_if_no_study(plan)
    seven_day = project_seven_day_plan(plan)

    lines = [
        f"# examready 升學考前 MDP 溫習計劃",
        "",
        f"**學生**: {plan.name}",
        f"**考試**: {data.get('exam_name', '學測')}  ·  **倒數**: {plan.student_state.days_to_exam} 天",
        f"**今晚可讀**: {plan.nightly_available_minutes} 分鐘  ·  **每晚最多科目數**: {plan.max_subjects_per_night}",
        f"**評估候選動作數**: {len(all_results)}  ·  **rollout 方法**: forward-simulation 至考試日",
        "",
        "## 目前各科熟悉度與權重",
        "",
        "| 科目 | 熟悉度 | 權重 | 遺忘速率/天 | 上次練習 | 加權差距 |",
        "|---|---|---|---|---|---|",
    ]
    gaps = weighted_familiarity(plan.student_state, plan.subjects)
    for s in sorted(plan.subjects, key=lambda x: -gaps[x.code]):
        f = plan.student_state.familiarity[s.code]
        d = plan.student_state.days_since_studied.get(s.code, 0)
        lines.append(
            f"| {s.name} ({s.code}) | {f:.0f} | ×{s.weight} | {s.forgetting_rate:.3f} | "
            f"{d} 天前 | {gaps[s.code]:.1f} |"
        )

    lines.extend([
        "",
        "## 🎯 今晚 MDP 最佳建議",
        "",
        f"### ⭐ {fmt_action(best_action, plan.subjects)}",
        "",
        f"- **預期考試總分**: {best_score:.1f} / 500",
        f"- vs 一週固定排表(fair-share): {fair.expected_exam_score:.1f}  (差距 **+{best_score - fair.expected_exam_score:.1f}**)",
        f"- vs 完全不讀: {no_study:.1f}  (差距 **+{best_score - no_study:.1f}**)",
        "",
        "## 為什麼是這個分配 — 純函式分析",
        "",
    ])
    # Reasoning: which subjects default policy will cover & which need tonight
    from mdp import default_future_action
    default_act = default_future_action(plan.student_state, plan.subjects, plan)
    name_by_code = {s.code: s.name for s in plan.subjects}
    default_subjects = [name_by_code[c] for c in default_act.studied_subjects()]
    tonight_subjects = [name_by_code[c] for c in best_action.studied_subjects()]
    coverage_gap = [s for s in tonight_subjects if s not in default_subjects]
    lines.append(f"- **預設未來政策**會每晚優先讀: {', '.join(default_subjects) if default_subjects else '(無)'}")
    lines.append(f"- 所以今晚 MDP 建議「補預設政策不會碰的科目」: {', '.join(coverage_gap) if coverage_gap else '與預設相同'}")
    lines.append(f"- 在 {plan.student_state.days_to_exam} 天滾動 rollout 下,此分配考試日預期 +{best_score - fair.expected_exam_score:.1f} 分")
    lines.append("")

    lines.append("## 📅 未來 7 天計劃投影")
    lines.append("")
    lines.append("| 第 N 晚 | 建議讀 | 屆時預期考試總分 |")
    lines.append("|---|---|---|")
    for day, action, projected in seven_day:
        lines.append(f"| 第 {day} 晚 | {fmt_action(action, plan.subjects)} | {projected:.1f} |")

    lines.extend([
        "",
        "## 候選動作排序(前 5)",
        "",
        "| 排名 | 分配 | 預期分 |",
        "|---|---|---|",
    ])
    for i, r in enumerate(all_results[:5]):
        lines.append(f"| {i + 1} | {fmt_action(r.action, plan.subjects)} | {r.expected_exam_score:.1f} |")

    lines.append("")
    lines.append("## ⚠️ 模型假設與限制")
    lines.append("")
    lines.append("- 熟悉度 0-100 是學生自評,**模型只能在自評上面做相對最佳化**")
    lines.append("- 預期分數採線性 f/100 × 100 假設,真實考試非線性(尾段難拉)")
    lines.append("- 不考慮**睡眠 / 心情 / 學校進度**,單純看遺忘曲線 + 加權考期")
    lines.append("- 模型每晚最多 3 科,不適合衝刺週的單科集中模式")
    lines.append("")
    lines.append("---")
    lines.append("*examready = 升學考前 MDP 助手。今晚讀什麼,讓 rollout 替你想。*")
    return "\n".join(lines)


def render_with_ai(plan: StudyPlan, data: dict) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(plan, data)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(plan, data)

    base = render_no_ai(plan, data)
    best_action, all_results = find_optimal_tonight(plan)
    fair = fair_share_baseline(plan)
    name_by_code = {s.code: s.name for s in plan.subjects}
    tonight_breakdown = ", ".join(
        f"{name_by_code[c]} {m}分" for c, m in best_action.allocation.items() if m > 0
    )

    prompt = f"""你是一位升學顧問。下面是 {plan.name}(考試 {data.get('exam_name','學測')} 倒數 {plan.student_state.days_to_exam} 天)的 MDP rollout 計算結果。

各科現況:
{chr(10).join(f"- {s.name} ({s.code}): 熟悉度 {plan.student_state.familiarity[s.code]:.0f} / 權重 ×{s.weight} / 遺忘 {s.forgetting_rate:.3f}/天 / 上次練 {plan.student_state.days_since_studied.get(s.code, 0)} 天前" for s in plan.subjects)}

今晚 MDP 建議:**{tonight_breakdown}**
- 預期考試總分(此分配): {all_results[0].expected_exam_score:.1f} / 500
- 預期考試總分(平均分配): {fair.expected_exam_score:.1f}
- 差距: +{all_results[0].expected_exam_score - fair.expected_exam_score:.1f} 分

請寫一段 150-200 字「給學生 + 家長讀的解釋」:
1. 為什麼今晚是這個分配(用「預設未來政策會幫你顧弱科,所以今晚補弱科以外」邏輯解釋,但用學生聽得懂的話)
2. 1-2 個學習建議(專注度 / 順序 / 休息)
3. 1 個明確風險提醒(例如:模型不會幫你顧學校段考 / 模型自評熟悉度需誠實)

**規則**:
- 不要重新計算分數,引用上面數字
- 不要套話(「祝順利」「相信自己」等)
- 不要寫超過 200 字
- 不要做 markdown 標題或表格

直接寫內容。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    ai_text = resp.content[0].text
    return base + "\n\n## 🤖 AI 升學顧問解讀\n\n" + ai_text + "\n"


def main():
    p = argparse.ArgumentParser(description="examready — 升學考前 MDP 多科溫習排程")
    p.add_argument("--student", default="samples/student.json", help="學生 JSON")
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    plan, data = load_student(Path(args.student))
    if args.no_ai:
        print(render_no_ai(plan, data))
    else:
        print(render_with_ai(plan, data))


if __name__ == "__main__":
    main()
