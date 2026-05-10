"""trailmatch — 台灣登山路線 AI Personalization

Usage:
    python trailmatch.py samples/sample_input.json --no-ai
    python trailmatch.py samples/sample_input.json --out report.md

設計重點:
- 純函式硬條件過濾 (難度 / 天數 / 季節 / 高山症 / 地形)
- AI 從通過 hard filter 的山中挑 Top 3 + 寫個人化推薦理由 + 裝備建議
- LLM 永不繞過硬條件(經驗不夠不能推進階百岳,即使 AI 覺得「應該可以」)

ANTHROPIC_API_KEY 在 AI 模式必要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from mountains_db import (
    EXPERIENCE_TO_MAX_DIFFICULTY,
    FITNESS_TO_MAX_GAIN,
    MOUNTAINS,
    Mountain,
)


@dataclass
class UserProfile:
    experience_level: str       # first_time / beginner / intermediate / advanced / expert
    fitness_level: str          # low / medium / high / elite
    available_days: int
    departure_city: str
    season: str                 # spring / summer / autumn / winter
    avoid_terrains: tuple[str, ...] = ()
    altitude_sickness_history: bool = False
    max_party_size: int | None = None
    has_winter_gear: bool = False     # 是否有雪攀裝備
    gear_owned: tuple[str, ...] = ()   # tent / poles / headlamp / etc
    goals: tuple[str, ...] = ()        # 風景 / 縱走 / 第一座百岳 / 訓練體能 等


@dataclass
class FilterResult:
    mountain: Mountain
    passes: bool
    fail_reasons: list[str] = field(default_factory=list)


def filter_mountain(m: Mountain, profile: UserProfile) -> FilterResult:
    fails: list[str] = []

    # 難度上限
    max_diff = EXPERIENCE_TO_MAX_DIFFICULTY.get(profile.experience_level, 0)
    if m.difficulty_level > max_diff:
        fails.append(
            f"難度 {m.difficulty_level} 超過 '{profile.experience_level}' 上限 {max_diff}"
        )

    # 天數
    if m.days_min > profile.available_days:
        fails.append(
            f"最少需 {m.days_min} 天,使用者只有 {profile.available_days} 天"
        )

    # 體能 / elevation_gain
    max_gain = FITNESS_TO_MAX_GAIN.get(profile.fitness_level, 0)
    if m.elevation_gain_m > max_gain:
        fails.append(
            f"爬升 {m.elevation_gain_m}m 超過 '{profile.fitness_level}' 體能上限 {max_gain}m"
        )

    # 季節
    if m.typical_seasons and profile.season not in m.typical_seasons:
        seasons_zh = ", ".join(m.typical_seasons)
        fails.append(f"當前 {profile.season} 不在建議季節 ({seasons_zh})")

    # 高山症
    if profile.altitude_sickness_history and m.altitude_sickness_risk == "high":
        fails.append("高山症史 + 此山高山症風險 high,風險過高")

    # 地形避免
    avoid_overlap = set(m.terrain_features) & set(profile.avoid_terrains)
    if avoid_overlap:
        fails.append(f"含使用者想避免的地形:{', '.join(avoid_overlap)}")

    # 冬季雪攀裝備
    if profile.season == "winter" and not profile.has_winter_gear and m.height_m >= 3000:
        fails.append(f"冬季 3000m+ 雪況,使用者無雪攀裝備")

    return FilterResult(mountain=m, passes=(len(fails) == 0), fail_reasons=fails)


def filter_all(profile: UserProfile,
               pool: list[Mountain] | None = None) -> tuple[list[FilterResult], list[FilterResult]]:
    pool = pool if pool is not None else MOUNTAINS
    results = [filter_mountain(m, profile) for m in pool]
    passed = [r for r in results if r.passes]
    failed = [r for r in results if not r.passes]
    return passed, failed


# ---- LLM 任務:從通過 hard filter 的選 Top 3 + 寫推薦理由 ----

RECOMMEND_SYSTEM = """你是台灣登山顧問。我會給你一位準登山者的 profile + 已通過硬條件過濾的山岳清單,
你的任務是挑出 **Top 3 最適合** 的山,並為每座寫個人化推薦。

## 輸出格式 (只回 JSON,不要其他文字)

```json
{
  "recommendations": [
    {
      "rank": 1,
      "code": "<mountain code 從提供清單選>",
      "why_match": "1-2 句話為什麼適合這位使用者",
      "gear_tips": ["...個人化裝備建議 (依季節 + 經驗 + 已有裝備)"],
      "safety_warnings": ["...安全注意 (高山症 / 天氣 / 路況等)"],
      "party_advice": "建議獨攀 / 結伴 / 找協作"
    },
    ...
  ],
  "overall_advice": "綜合建議 1-2 句"
}
```

## 嚴格規則

- **只能從提供清單中挑** code,**絕對不能編造其他山**
- 推薦理由要引用使用者具體 profile 欄位(season, fitness, goals 等)
- gear_tips 不要重複常識(「帶水」「帶頭燈」),只列**該座山 + 該季節 + 該體能等級**特殊需要
- safety_warnings 必須具體(不要寫「注意安全」這種空話)
- 不要過度樂觀(沒登過百岳的人即使體能 high 也不要推 level 4)
"""


def llm_recommend(profile: UserProfile, passed: list[FilterResult]) -> dict[str, Any]:
    import anthropic

    pool_summary = []
    for r in passed:
        m = r.mountain
        pool_summary.append({
            "code": m.code, "name": m.name_zh, "height_m": m.height_m,
            "region": m.region, "difficulty": m.difficulty_level,
            "days": f"{m.days_min}-{m.days_max}", "gain_m": m.elevation_gain_m,
            "permit": m.permit_required and m.permit_agency,
            "altitude_risk": m.altitude_sickness_risk,
            "terrain": list(m.terrain_features),
            "access_city": m.access_city,
            "is_baiyue": m.is_baiyue,
            "notes": list(m.special_notes),
        })
    profile_dict = {
        "experience_level": profile.experience_level,
        "fitness_level": profile.fitness_level,
        "available_days": profile.available_days,
        "departure_city": profile.departure_city,
        "season": profile.season,
        "avoid_terrains": list(profile.avoid_terrains),
        "altitude_sickness_history": profile.altitude_sickness_history,
        "has_winter_gear": profile.has_winter_gear,
        "gear_owned": list(profile.gear_owned),
        "goals": list(profile.goals),
    }
    user_msg = (
        f"## 使用者 profile\n```json\n{json.dumps(profile_dict, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 通過硬條件的山岳清單(從中挑 Top 3)\n"
        f"```json\n{json.dumps(pool_summary, ensure_ascii=False, indent=2)}\n```\n\n"
        f"請給 Top 3 推薦 JSON。"
    )
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[{"type": "text", "text": RECOMMEND_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"AI 沒回 JSON: {raw}")
    return json.loads(raw[start : end + 1])


def render_skeleton_recommendation(passed: list[FilterResult]) -> dict[str, Any]:
    """無 AI 時的純函式 Top 3 baseline:按 difficulty 降序選 3 個(挑戰性高的優先)。"""
    sorted_by_diff = sorted(passed, key=lambda r: -r.mountain.difficulty_level)
    top3 = sorted_by_diff[:3]
    return {
        "recommendations": [
            {
                "rank": i + 1,
                "code": r.mountain.code,
                "why_match": f"通過硬條件 + 難度 {r.mountain.difficulty_level} 是清單中較有挑戰性的選項",
                "gear_tips": ["(無 AI;請參考山岳基本資料 + 季節)"],
                "safety_warnings": list(r.mountain.special_notes[:2]),
                "party_advice": "建議結伴 + 老手帶隊",
            }
            for i, r in enumerate(top3)
        ],
        "overall_advice": "(無 AI 模式,請審視通過硬條件清單後親自評估)",
    }


def render_report(profile: UserProfile, today: date,
                  passed: list[FilterResult], failed: list[FilterResult],
                  rec_result: dict[str, Any]) -> str:
    out: list[str] = []
    out.append(f"# 登山路線 AI 個人化推薦")
    out.append("")
    out.append(f"**諮詢日期**: {today.isoformat()}    "
               f"**出發城市**: {profile.departure_city}    **季節**: {profile.season}")
    out.append("")

    out.append("## 你的登山者 profile")
    out.append("")
    out.append(f"- **經驗等級**: {profile.experience_level}")
    out.append(f"- **體能等級**: {profile.fitness_level}")
    out.append(f"- **可用天數**: {profile.available_days} 天")
    out.append(f"- **高山症史**: {'有' if profile.altitude_sickness_history else '無'}")
    out.append(f"- **冬季雪攀裝備**: {'有' if profile.has_winter_gear else '無'}")
    if profile.avoid_terrains:
        out.append(f"- **想避免的地形**: {', '.join(profile.avoid_terrains)}")
    if profile.goals:
        out.append(f"- **目標**: {', '.join(profile.goals)}")
    out.append("")

    out.append(f"## 過濾結果")
    out.append("")
    out.append(f"全 corpus 共 {len(passed) + len(failed)} 座 → 通過硬條件 **{len(passed)}** 座 / 不適合 **{len(failed)}** 座")
    out.append("")

    out.append("## 🎯 Top 推薦山岳")
    out.append("")
    code_to_mountain = {m.code: m for m in MOUNTAINS}
    for rec in rec_result.get("recommendations", []):
        code = rec.get("code", "")
        m = code_to_mountain.get(code)
        if m is None:
            continue
        out.append(f"### {rec.get('rank', '?')}. {m.name_zh} ({m.height_m}m)")
        out.append("")
        out.append(f"- **地區**: {m.region} / 出發 {m.access_city}")
        out.append(f"- **難度**: {m.difficulty_level}/5    **天數**: {m.days_min}-{m.days_max} 天    "
                   f"**爬升**: {m.elevation_gain_m}m    **高山症風險**: {m.altitude_sickness_risk}")
        if m.permit_required:
            out.append(f"- **入山申請**: {m.permit_agency}")
        out.append(f"- **百岳**: {'✓' if m.is_baiyue else '✗(中級山 / 郊山)'}")
        out.append("")
        out.append(f"**為什麼適合你**: {rec.get('why_match', '')}")
        out.append("")
        if rec.get("gear_tips"):
            out.append(f"**個人化裝備建議**:")
            for tip in rec["gear_tips"]:
                out.append(f"  - {tip}")
            out.append("")
        if rec.get("safety_warnings"):
            out.append(f"**⚠️ 安全注意**:")
            for w in rec["safety_warnings"]:
                out.append(f"  - {w}")
            out.append("")
        party = rec.get("party_advice", "")
        if party:
            out.append(f"**同行建議**: {party}")
            out.append("")
        if m.special_notes:
            out.append(f"**山岳特色 / 注意**:")
            for n in m.special_notes:
                out.append(f"  - {n}")
            out.append("")

    overall = rec_result.get("overall_advice", "")
    if overall:
        out.append("## 綜合建議")
        out.append("")
        out.append(overall)
        out.append("")

    # 通過清單(讓使用者自己看)
    if len(passed) > 3:
        out.append("## 其他通過硬條件但未列 Top 3 的山岳")
        out.append("")
        rec_codes = {r["code"] for r in rec_result.get("recommendations", []) if "code" in r}
        for r in passed:
            if r.mountain.code in rec_codes:
                continue
            m = r.mountain
            out.append(f"- **{m.name_zh}** ({m.height_m}m, 難度 {m.difficulty_level}, "
                       f"{m.days_min}-{m.days_max} 天, {m.region})")
        out.append("")

    # 失敗清單
    if failed:
        out.append("## ❌ 不適合的山岳(供參考)")
        out.append("")
        for r in failed[:8]:
            out.append(f"- **{r.mountain.name_zh}** ({r.mountain.height_m}m): "
                       f"{'; '.join(r.fail_reasons)}")
        if len(failed) > 8:
            out.append(f"- (還有 {len(failed) - 8} 座因條件不符未列出)")
        out.append("")

    out.append("---")
    out.append("")
    out.append(f"*由 trailmatch 自動產生於 {today.isoformat()}。"
               f"推薦僅供參考,實際登山請依當週天氣、入山申請結果、體能狀況再確認。安全第一。*")
    return "\n".join(out) + "\n"


def parse_profile(payload: dict[str, Any]) -> UserProfile:
    p = payload["profile"]
    return UserProfile(
        experience_level=p["experience_level"],
        fitness_level=p["fitness_level"],
        available_days=int(p["available_days"]),
        departure_city=p["departure_city"],
        season=p["season"],
        avoid_terrains=tuple(p.get("avoid_terrains", [])),
        altitude_sickness_history=bool(p.get("altitude_sickness_history", False)),
        max_party_size=p.get("max_party_size"),
        has_winter_gear=bool(p.get("has_winter_gear", False)),
        gear_owned=tuple(p.get("gear_owned", [])),
        goals=tuple(p.get("goals", [])),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="使用者 profile JSON")
    parser.add_argument("--today", help="模擬日期 YYYY-MM-DD")
    parser.add_argument("--out", type=Path, help="輸出 markdown 路徑")
    parser.add_argument("--no-ai", action="store_true",
                        help="不呼叫 AI,純函式硬條件 baseline")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: 找不到 {args.input}", file=sys.stderr)
        return 2

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    profile = parse_profile(payload)
    today = date.fromisoformat(args.today) if args.today else date.today()

    passed, failed = filter_all(profile)
    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_ai and not args.no_ai:
        print("info: ANTHROPIC_API_KEY 未設,用純函式 baseline", file=sys.stderr)

    if use_ai and passed:
        rec_result = llm_recommend(profile, passed)
    else:
        rec_result = render_skeleton_recommendation(passed)

    report = render_report(profile, today, passed, failed, rec_result)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"已寫入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
