"""tenderwatch — 政府標案硬條件過濾(純函式).

責任:
  - 載入用戶 capability profile
  - 對每個標案做硬條件檢查(資本額 / 經驗 / 預算 / 截止日 / 排除類別)
  - 輸出 (passes, fail_reasons) — 不通過的不送 LLM 浪費 token

LLM 在另一個檔案(tenderwatch.py)做 semantic match,只負責「描述符合度」
這個語意判斷;硬條件留純函式以可單元測試。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class UserProfile:
    company_name: str
    capital_twd: int                  # 實收資本額
    employee_count: int
    capability_description: str       # 自由文字:擅長的服務、技術、產業領域
    min_tender_budget_twd: int = 0    # 不接低於此預算的標案
    max_tender_budget_twd: int | None = None
    excluded_categories: tuple[str, ...] = ()  # 不接的類別 (如「工程施作」「採購」)
    iso_certifications: tuple[str, ...] = ()   # ISO 9001 / 27001 / etc
    minimum_days_to_deadline: int = 7  # 截止日須至少 N 天後


@dataclass
class Tender:
    case_no: str                       # 政採網案號
    title: str                         # 標案名稱
    agency: str                        # 主管機關
    category: str                      # 標案類別
    budget_twd: int                    # 預算上限
    posted_date: str                   # YYYY-MM-DD
    deadline_date: str                 # YYYY-MM-DD
    description: str                   # 標案描述(供 LLM 語意比對)
    required_capital_twd: int = 0      # 投標廠商最低資本額
    required_certs: tuple[str, ...] = ()  # 必備認證
    location: str = "全國"


@dataclass
class FilterResult:
    tender: Tender
    passes_hard_filter: bool
    fail_reasons: list[str] = field(default_factory=list)


def _days_until(deadline_iso: str, today: date) -> int:
    y, m, d = deadline_iso.split("-")
    return (date(int(y), int(m), int(d)) - today).days


def filter_tender(tender: Tender, profile: UserProfile, today: date) -> FilterResult:
    fails: list[str] = []

    if tender.required_capital_twd > profile.capital_twd:
        fails.append(
            f"投標廠商資本額需 NT${tender.required_capital_twd:,},"
            f"用戶 NT${profile.capital_twd:,}"
        )

    if tender.budget_twd < profile.min_tender_budget_twd:
        fails.append(
            f"預算 NT${tender.budget_twd:,} 低於用戶最低門檻 NT${profile.min_tender_budget_twd:,}"
        )

    if profile.max_tender_budget_twd and tender.budget_twd > profile.max_tender_budget_twd:
        fails.append(
            f"預算 NT${tender.budget_twd:,} 高於用戶上限 NT${profile.max_tender_budget_twd:,} "
            "(可能規模過大難以承接)"
        )

    days = _days_until(tender.deadline_date, today)
    if days < profile.minimum_days_to_deadline:
        fails.append(
            f"截止日 {tender.deadline_date} 距今僅 {days} 天,少於 {profile.minimum_days_to_deadline} 天準備期"
        )

    if tender.category in profile.excluded_categories:
        fails.append(f"標案類別「{tender.category}」在用戶排除清單")

    missing_certs = [c for c in tender.required_certs if c not in profile.iso_certifications]
    if missing_certs:
        fails.append(f"缺必備認證:{', '.join(missing_certs)}")

    return FilterResult(
        tender=tender,
        passes_hard_filter=len(fails) == 0,
        fail_reasons=fails,
    )


def filter_all(tenders: list[Tender], profile: UserProfile,
               today: date | None = None) -> tuple[list[FilterResult], list[FilterResult]]:
    """Returns (passed, failed) — 兩個清單。"""
    today = today or date.today()
    results = [filter_tender(t, profile, today) for t in tenders]
    passed = [r for r in results if r.passes_hard_filter]
    failed = [r for r in results if not r.passes_hard_filter]
    return passed, failed
