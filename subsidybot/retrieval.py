"""subsidybot — 用戶條件 → 補助方案匹配 (純函式).

依用戶 profile 將 corpus 中每個方案分類為:
  - "fully_eligible"  完全符合硬條件(年齡 / 設立年限 / 員工數 / 性別 / 行業)
  - "soft_match"      部分符合 / 條件相近(差一點不放棄)
  - "ineligible"      明確不符合(列出原因供 AI 解釋)

LLM 之後接收:用戶問題 + 三組分類結果 → 撰寫對話式回答 + 引用方案。
本檔案不碰 LLM,確保條件邏輯可單元測試。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from subsidies_db import PROGRAMS, SubsidyProgram


@dataclass
class UserProfile:
    age: int | None = None
    gender: str | None = None                  # "女" | "男"
    is_new_immigrant: bool = False              # 新住民
    has_business_registered: bool = False       # 已登記公司 / 商業
    business_age_years: float | None = None     # 公司行號設立年限
    employee_count: int | None = None
    industry: str | None = None                 # 自由文字 — 例「咖啡廳」「網路服務業」「有機農業」
    capital_twd: int | None = None              # 實收資本額
    free_text: str = ""                          # 用戶其他自述


@dataclass
class MatchResult:
    program: SubsidyProgram
    status: str                                  # "fully_eligible" | "soft_match" | "ineligible"
    matched_reasons: list[str] = field(default_factory=list)
    failed_reasons: list[str] = field(default_factory=list)


def _check_age(p: SubsidyProgram, profile: UserProfile) -> tuple[bool, str | None]:
    """Returns (passes, reason if fails or notes)."""
    if profile.age is None:
        return True, None
    if p.eligibility_age_min is not None and profile.age < p.eligibility_age_min:
        return False, f"年齡需 ≥ {p.eligibility_age_min} 歲(用戶 {profile.age} 歲)"
    if p.eligibility_age_max is not None and profile.age > p.eligibility_age_max:
        return False, f"年齡需 ≤ {p.eligibility_age_max} 歲(用戶 {profile.age} 歲)"
    return True, None


def _check_business_age(p: SubsidyProgram, profile: UserProfile) -> tuple[bool, str | None]:
    if p.eligibility_business_age_max_years is None:
        return True, None
    if profile.business_age_years is None:
        return True, None  # 未提供 → 不阻擋
    if profile.business_age_years > p.eligibility_business_age_max_years:
        return False, (f"事業設立 {profile.business_age_years} 年,"
                       f"超過上限 {p.eligibility_business_age_max_years} 年")
    return True, None


def _check_employee(p: SubsidyProgram, profile: UserProfile) -> tuple[bool, str | None]:
    if p.eligibility_employee_max is None:
        return True, None
    if profile.employee_count is None:
        return True, None
    if profile.employee_count > p.eligibility_employee_max:
        return False, (f"員工 {profile.employee_count} 人,超過上限 "
                       f"{p.eligibility_employee_max} 人")
    return True, None


def _check_business_registered(p: SubsidyProgram, profile: UserProfile) -> tuple[bool, str | None]:
    if not p.eligibility_business_required:
        return True, None
    if not profile.has_business_registered:
        return False, "需已設立公司 / 商業登記"
    return True, None


def _check_gender(p: SubsidyProgram, profile: UserProfile) -> tuple[bool, str | None]:
    if not p.eligibility_genders:
        return True, None
    if profile.gender is None:
        return True, None  # 未填 → 不阻擋

    # 嚴格 exact-match;特殊情況「男(45歲以上)」獨立處理
    for required in p.eligibility_genders:
        if required == profile.gender:
            return True, None
        if required == "男(45歲以上)":
            if profile.gender == "男" and profile.age is not None and profile.age >= 45:
                return True, None
    return False, f"性別 / 身分限制:{', '.join(p.eligibility_genders)}"


def _check_industry(p: SubsidyProgram, profile: UserProfile) -> tuple[bool, str | None, bool]:
    """回傳 (passes, reason, is_soft)。is_soft=True 表示用戶沒填行業,可進入 soft match。"""
    if not p.eligibility_industries:
        return True, None, False
    if profile.industry is None:
        return True, None, True  # 沒填 → soft match
    industry_lower = profile.industry.strip()
    for required in p.eligibility_industries:
        if required in industry_lower or industry_lower in required:
            return True, None, False
    return False, f"行業限制:{', '.join(p.eligibility_industries)}", False


def match_programs(profile: UserProfile,
                   programs: list[SubsidyProgram] | None = None) -> list[MatchResult]:
    progs = programs if programs is not None else PROGRAMS
    results: list[MatchResult] = []
    for p in progs:
        matched: list[str] = []
        failed: list[str] = []
        soft = False

        for fn in (_check_age, _check_business_age, _check_employee,
                   _check_business_registered, _check_gender):
            ok, reason = fn(p, profile)
            if not ok and reason:
                failed.append(reason)
            elif reason is None and ok:
                pass  # silent pass

        ind_ok, ind_reason, ind_soft = _check_industry(p, profile)
        if not ind_ok and ind_reason:
            failed.append(ind_reason)
        elif ind_soft:
            soft = True
            matched.append("行業欄位未填,假設可能符合")

        # determine status
        if not failed:
            if soft:
                status = "soft_match"
            else:
                status = "fully_eligible"
        elif len(failed) <= 1:
            status = "soft_match"
        else:
            status = "ineligible"

        # add positive matches
        if profile.age is not None and p.eligibility_age_min and p.eligibility_age_max:
            if p.eligibility_age_min <= profile.age <= p.eligibility_age_max:
                matched.append(
                    f"年齡 {profile.age} 在 {p.eligibility_age_min}-{p.eligibility_age_max} 範圍"
                )
        if profile.gender is not None and p.eligibility_genders:
            for required in p.eligibility_genders:
                if required == profile.gender:
                    matched.append(f"性別 / 身分符合({profile.gender})")
                    break
                if required == "男(45歲以上)" and profile.gender == "男" \
                   and profile.age is not None and profile.age >= 45:
                    matched.append(f"性別 / 身分符合({profile.gender}, 45+)")
                    break

        results.append(MatchResult(
            program=p, status=status, matched_reasons=matched, failed_reasons=failed,
        ))
    return results
