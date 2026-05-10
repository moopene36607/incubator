"""retiremate — 台灣退休規劃 AI 顧問 CLI(conversational agent with tools).

純函式工具 (tools.py) 計算所有金額;LLM 用 Anthropic tool-use API
**自主決定**何時調用哪個 tool、傳什麼參數,然後組合成自然語言報告。

模式:
  --no-ai  : 確定性模擬(依序呼叫全部 tools + 組成基礎報告,免 API key)
  full     : Claude tool-use agent 自主決定調用順序

LLM 規範:
  - LLM 不算金額(用 tool 結果)
  - LLM 不擅自編造 tool 沒回的數字
  - 給的建議都是「中立第三方」立場(不推銷保險 / 投資商品)
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from tools import (
    LIVING_COST_BY_REGION,
    NHI_RETIREMENT_TIER6_MONTHLY,
    TOOL_DEFINITIONS,
    call_tool,
    compute_retirement_gap,
    estimate_labor_insurance_pension,
    estimate_labor_pension_new,
    estimate_monthly_living_cost,
    estimate_national_pension,
    estimate_post_retirement_nhi,
    project_personal_savings,
    required_savings_for_gap,
)


SYSTEM_PROMPT = textwrap.dedent("""
    你是台灣中立、不收佣金的退休規劃顧問。你協助 50-60 歲族群評估退休前 5-10 年的財務準備。

    你有 8 個 tools 可以用(見 tool list)。請按以下順序自主使用 tools:
      1. estimate_labor_pension_new — 算勞退新制累積 + 月領
      2. estimate_labor_insurance_pension — 算勞保老年年金月領
      3. estimate_national_pension — 若使用者有國保年資則算,否則 skip
      4. project_personal_savings — 算自有儲蓄到退休時複利成長
      5. estimate_monthly_living_cost — 查退休月支出基準
      6. estimate_post_retirement_nhi — 查退休健保月費
      7. compute_retirement_gap — 用前面結果算月缺口 + 等級
      8. required_savings_for_gap — 算缺口需要多少儲蓄補足
    然後對照 (4) 的儲蓄成長預測 vs (8) 的需要儲蓄,判斷是否足夠。

    最後寫一份完整退休規劃報告(中文),包括:
      - **執行摘要**(2-3 句):你的退休準備狀態 + 關鍵數字
      - **各項所得來源**(逐項 NT$/月,引用 tool 結果)
      - **月支出與缺口**(逐項 NT$/月)
      - **儲蓄成長預測 vs 需要儲蓄缺口**
      - **3-5 條具體建議**(避免推銷投資 / 保險產品;聚焦「自願提繳節稅」/「延後退休 1-2 年影響」/「延後請領加碼」這類具體 lever)
      - **重要提醒**(本工具僅初步試算,實際請洽勞動部試算系統 / 銀行退休理財規劃師)

    硬規則:
      - 你**絕不**算 NT$ 數字 — 全部從 tool 結果引用
      - 你**絕不**推銷特定保險 / 投資商品(如「建議買 XX 終身險」)
      - 報告用台灣繁體中文 + 在地用語(勞退 / 勞保 / 國保 / 健保 / 月領)
      - 引用具體公式名稱(新式 / 舊式 / A 式 / B 式)讓使用者可去勞動部官網對照
""").strip()


# --- 確定性模擬模式(no-AI fallback)---

def deterministic_simulate(profile: dict) -> dict:
    """免 API key 模式:依序呼叫所有 tools 並組合成 report-ready dict。

    這個模式無 LLM,只用純函式 + 簡單模板。AI 模式會更精緻。
    """
    age = profile["age"]
    target_retire_age = profile["target_retire_age"]
    years_to_retirement = max(0, target_retire_age - age)
    years_in_retirement = max(1, 84 - target_retire_age)

    monthly_salary = profile["monthly_salary"]

    # 1. 勞退新制
    labor_new = estimate_labor_pension_new(
        avg_monthly_salary=monthly_salary,
        years_contributed=profile["labor_pension_years"],
        self_contribute_rate=profile.get("self_contribute_rate", 0.0),
    )

    # 2. 勞保
    labor_ins = estimate_labor_insurance_pension(
        avg_monthly_insurance_salary=profile.get("avg_insurance_salary", min(monthly_salary, 45800)),
        years_paid=profile["labor_insurance_years"],
    )

    # 3. 國民年金
    national_years = profile.get("national_pension_years", 0)
    national = estimate_national_pension(years_paid=national_years) if national_years > 0 else None

    # 4. 個人儲蓄
    savings = project_personal_savings(
        current_balance=profile["current_savings"],
        monthly_save=profile["monthly_save"],
        years_to_retirement=years_to_retirement,
    )

    # 5. 月支出
    living = estimate_monthly_living_cost(
        region=profile["region"],
        household_type=profile["household_type"],
    )

    # 6. 健保
    nhi = estimate_post_retirement_nhi()

    # 7. 缺口分析
    income_sources = {
        labor_new["scheme"]: labor_new["estimated_monthly_pension"],
        labor_ins["scheme"]: labor_ins["selected_monthly_pension"],
    }
    if national:
        income_sources[national["scheme"]] = national["selected_monthly_pension"]
    gap = compute_retirement_gap(
        monthly_income_sources=income_sources,
        monthly_expenses=living["monthly_living_cost_baseline"],
        nhi_monthly=nhi["monthly_nhi_premium"],
    )

    # 8. 缺口所需儲蓄
    required = required_savings_for_gap(
        monthly_gap=max(0, -gap["monthly_gap"]),
        years_in_retirement=years_in_retirement,
    )

    return {
        "labor_new": labor_new,
        "labor_ins": labor_ins,
        "national": national,
        "savings": savings,
        "living": living,
        "nhi": nhi,
        "gap": gap,
        "required": required,
        "years_to_retirement": years_to_retirement,
        "years_in_retirement": years_in_retirement,
    }


def render_no_ai_report(profile: dict, sim: dict) -> str:
    parts: list[str] = []
    parts.append(f"# retiremate 退休規劃初步試算 — {profile.get('name', '(匿名)')}\n")
    parts.append("**模式**: 純函式試算(免 API key)\n")
    parts.append("## 您的基本資料\n")
    parts.append(f"- 目前年齡: {profile['age']} / 目標退休年齡: {profile['target_retire_age']} / 距退休 {sim['years_to_retirement']} 年")
    parts.append(f"- 居住地: {profile['region']} / 家庭結構: {'雙人' if profile['household_type'] == 'couple' else '單人'}")
    parts.append(f"- 平均月薪: NT$ {profile['monthly_salary']:,}")
    parts.append(f"- 勞退新制提繳年數: {profile['labor_pension_years']}")
    parts.append(f"- 勞保加保年數: {profile['labor_insurance_years']}")
    if profile.get("national_pension_years", 0) > 0:
        parts.append(f"- 國民年金加保年數: {profile['national_pension_years']}")
    parts.append(f"- 目前儲蓄: NT$ {profile['current_savings']:,} / 每月再存: NT$ {profile['monthly_save']:,}")
    parts.append("")

    parts.append("## 各項所得來源(月領)\n")
    parts.append(f"### 1. {sim['labor_new']['scheme']}")
    parts.append(f"- {sim['labor_new']['notes']}")
    parts.append(f"- **60 歲累積**: NT$ {sim['labor_new']['total_account_balance_at_60']:,}")
    parts.append(f"- **月領預估**: NT$ {sim['labor_new']['estimated_monthly_pension']:,}")
    parts.append("")
    parts.append(f"### 2. {sim['labor_ins']['scheme']}")
    parts.append(f"- {sim['labor_ins']['notes']}")
    parts.append(f"- **月領預估**: NT$ {sim['labor_ins']['selected_monthly_pension']:,}")
    parts.append("")
    if sim["national"]:
        parts.append(f"### 3. {sim['national']['scheme']}")
        parts.append(f"- {sim['national']['notes']}")
        parts.append(f"- **月領預估**: NT$ {sim['national']['selected_monthly_pension']:,}")
        parts.append("")

    parts.append("## 個人儲蓄成長預測\n")
    parts.append(f"- {sim['savings']['notes']}")
    for label, v in sim["savings"]["scenarios_balance_at_retirement"].items():
        parts.append(f"  - {label}: 退休時累積 NT$ {v:,}")
    parts.append("")

    parts.append("## 退休月支出 + 健保\n")
    parts.append(f"- {sim['living']['notes']}")
    parts.append(f"- {sim['nhi']['notes']}")
    parts.append(f"- 合計每月支出: NT$ {sim['gap']['monthly_total_expense']:,}")
    parts.append("")

    parts.append("## 月所得 vs 月支出 缺口分析\n")
    parts.append(f"- 月所得加總: NT$ {sim['gap']['monthly_income_total']:,}")
    parts.append(f"- 月支出加總: NT$ {sim['gap']['monthly_total_expense']:,}")
    parts.append(f"- **每月{ '結餘' if sim['gap']['monthly_gap'] >= 0 else '缺口' }**: NT$ {abs(sim['gap']['monthly_gap']):,}")
    parts.append(f"- **缺口等級**: `{sim['gap']['gap_level']}`")
    parts.append(f"- 結論: {sim['gap']['verdict']}")
    parts.append("")

    if sim["required"]["required_savings"] > 0:
        parts.append("## 補足缺口需要的儲蓄\n")
        parts.append(f"- {sim['required']['notes']}")
        parts.append(f"- **退休時需備儲蓄**: NT$ {sim['required']['required_savings']:,}")
        parts.append(f"- **平均情境下你預計累積**: NT$ {sim['savings']['scenarios_balance_at_retirement']['平均 (5%)']:,}")
        diff = sim["savings"]["scenarios_balance_at_retirement"]["平均 (5%)"] - sim["required"]["required_savings"]
        if diff >= 0:
            parts.append(f"- **判定**: 預計累積 ≥ 需要儲蓄,**可覆蓋退休缺口**(餘 NT$ {diff:,})")
        else:
            parts.append(f"- **判定**: ⚠️ 預計累積 < 需要儲蓄,差 NT$ {-diff:,};請考慮提高每月儲蓄 / 延後退休")
        parts.append("")
    parts.append("---")
    parts.append("*純函式模式無個人化建議。AI 模式會根據你的具體情境給 3-5 條具體建議。*")
    parts.append("*重要提醒:本試算僅供參考,實際請對照勞動部「勞工保險局個人專戶資料查詢」與「勞退新制試算」官網。*")
    return "\n".join(parts)


# --- AI agent 模式(Claude tool-use)---

def run_agent(profile: dict, max_iterations: int = 12) -> tuple[str, list[dict]]:
    """以 Claude tool-use API 執行 agent loop。

    Returns:
        (final_assistant_text, tool_call_log)
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("AI 模式需要安裝 anthropic SDK,請執行:pip install anthropic")
    client = Anthropic()

    user_prompt = textwrap.dedent(f"""
        以下是用戶的退休規劃 profile,請你按照系統提示的順序使用 tools 並產出完整退休規劃報告:

        ```json
        {json.dumps(profile, ensure_ascii=False, indent=2)}
        ```
    """).strip()

    messages = [{"role": "user", "content": user_prompt}]
    tool_log: list[dict] = []

    for _ in range(max_iterations):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # 將 assistant 回應加入訊息歷史
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            # LLM 結束 — 取最後 text 輸出
            final_text = "\n".join(
                b.text for b in resp.content if b.type == "text"
            )
            return final_text, tool_log

        # 處理 tool calls
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            name = block.name
            args = block.input
            result = call_tool(name, args)
            tool_log.append({"tool": name, "args": args, "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": tool_results})

    return "(達到 max_iterations 上限,未產生最終報告)", tool_log


def render_full_report(profile: dict, ai_text: str, tool_log: list[dict]) -> str:
    parts: list[str] = []
    parts.append(f"# retiremate 退休規劃 — {profile.get('name', '(匿名)')}\n")
    parts.append("**模式**: AI agent + tool-use(Claude 自主規劃 + 純函式精算)\n")
    parts.append("## AI 顧問報告\n")
    parts.append(ai_text)
    parts.append("")
    parts.append("---")
    parts.append("## Agent tool 調用紀錄(透明化)\n")
    for i, log in enumerate(tool_log, 1):
        parts.append(f"### Step {i}: `{log['tool']}`")
        parts.append(f"- args: `{json.dumps(log['args'], ensure_ascii=False)}`")
        result_preview = json.dumps(log["result"], ensure_ascii=False)
        if len(result_preview) > 250:
            result_preview = result_preview[:250] + "..."
        parts.append(f"- result: `{result_preview}`")
        parts.append("")
    parts.append("---")
    parts.append("*重要提醒:本試算僅供參考,實際請對照勞動部「勞工保險局個人專戶資料查詢」與「勞退新制試算」官網。*")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description="retiremate — 台灣退休規劃 AI agent")
    p.add_argument("profile", help="使用者 profile JSON")
    p.add_argument("--out", help="輸出 markdown")
    p.add_argument("--no-ai", action="store_true", help="只跑純函式 (免 API key)")
    args = p.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))

    if args.no_ai:
        sim = deterministic_simulate(profile)
        report = render_no_ai_report(profile, sim)
    else:
        ai_text, tool_log = run_agent(profile)
        report = render_full_report(profile, ai_text, tool_log)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"報告已寫入 {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
