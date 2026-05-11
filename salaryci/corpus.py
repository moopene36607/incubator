"""salaryci — 台灣薪資 corpus.

For prototype: 50+ realistic synthetic records reflecting 2024-2026 Taiwan
salary market across 4 industries × 5 role families × 3 levels. Real
production: replace with scraped PTT Salary / 104 / Yourator data with
informed consent.

Records intentionally include moderate intra-cluster variance so conformal
prediction interval is non-trivial.

Currency: monthly base salary in NT$ thousands (excludes bonus / stock).
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SalaryRecord:
    industry: str          # SOFTWARE / FINANCE / MFG / RETAIL / BIO
    role_family: str       # BACKEND / FRONTEND / DATA / PM / DESIGN / RD / SALES / OPS
    level: str             # JUNIOR / MID / SENIOR / STAFF
    exp_years: int         # 0-15
    location: str          # TAIPEI / HSINCHU / TAICHUNG / KAOHSIUNG / REMOTE
    monthly_salary_ntd_k: int   # in thousands NTD (e.g., 65 = NT$65,000)
    source_year: int = 2025


CORPUS: list[SalaryRecord] = [
    # SOFTWARE / BACKEND
    SalaryRecord("SOFTWARE", "BACKEND", "JUNIOR", 1, "TAIPEI", 48),
    SalaryRecord("SOFTWARE", "BACKEND", "JUNIOR", 1, "TAIPEI", 50),
    SalaryRecord("SOFTWARE", "BACKEND", "JUNIOR", 2, "TAIPEI", 55),
    SalaryRecord("SOFTWARE", "BACKEND", "JUNIOR", 2, "TAIPEI", 52),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 3, "TAIPEI", 65),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 3, "TAIPEI", 60),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 4, "TAIPEI", 72),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 4, "TAIPEI", 70),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 4, "TAIPEI", 78),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 5, "TAIPEI", 82),
    SalaryRecord("SOFTWARE", "BACKEND", "MID", 5, "TAIPEI", 75),
    SalaryRecord("SOFTWARE", "BACKEND", "SENIOR", 6, "TAIPEI", 95),
    SalaryRecord("SOFTWARE", "BACKEND", "SENIOR", 7, "TAIPEI", 105),
    SalaryRecord("SOFTWARE", "BACKEND", "SENIOR", 8, "TAIPEI", 115),
    SalaryRecord("SOFTWARE", "BACKEND", "STAFF", 10, "TAIPEI", 145),

    # SOFTWARE / FRONTEND
    SalaryRecord("SOFTWARE", "FRONTEND", "JUNIOR", 1, "TAIPEI", 45),
    SalaryRecord("SOFTWARE", "FRONTEND", "MID", 3, "TAIPEI", 58),
    SalaryRecord("SOFTWARE", "FRONTEND", "MID", 4, "TAIPEI", 68),
    SalaryRecord("SOFTWARE", "FRONTEND", "MID", 4, "TAIPEI", 65),
    SalaryRecord("SOFTWARE", "FRONTEND", "MID", 5, "TAIPEI", 75),
    SalaryRecord("SOFTWARE", "FRONTEND", "SENIOR", 6, "TAIPEI", 88),
    SalaryRecord("SOFTWARE", "FRONTEND", "SENIOR", 8, "TAIPEI", 102),

    # SOFTWARE / DATA
    SalaryRecord("SOFTWARE", "DATA", "JUNIOR", 1, "TAIPEI", 50),
    SalaryRecord("SOFTWARE", "DATA", "MID", 3, "TAIPEI", 68),
    SalaryRecord("SOFTWARE", "DATA", "MID", 4, "TAIPEI", 78),
    SalaryRecord("SOFTWARE", "DATA", "MID", 5, "TAIPEI", 85),
    SalaryRecord("SOFTWARE", "DATA", "SENIOR", 6, "TAIPEI", 100),
    SalaryRecord("SOFTWARE", "DATA", "SENIOR", 8, "TAIPEI", 120),

    # SOFTWARE / PM
    SalaryRecord("SOFTWARE", "PM", "JUNIOR", 1, "TAIPEI", 48),
    SalaryRecord("SOFTWARE", "PM", "MID", 3, "TAIPEI", 65),
    SalaryRecord("SOFTWARE", "PM", "MID", 4, "TAIPEI", 75),
    SalaryRecord("SOFTWARE", "PM", "MID", 5, "TAIPEI", 82),
    SalaryRecord("SOFTWARE", "PM", "SENIOR", 7, "TAIPEI", 105),

    # SOFTWARE / DESIGN
    SalaryRecord("SOFTWARE", "DESIGN", "JUNIOR", 1, "TAIPEI", 42),
    SalaryRecord("SOFTWARE", "DESIGN", "MID", 3, "TAIPEI", 55),
    SalaryRecord("SOFTWARE", "DESIGN", "MID", 4, "TAIPEI", 65),
    SalaryRecord("SOFTWARE", "DESIGN", "SENIOR", 6, "TAIPEI", 80),

    # FINANCE / RD
    SalaryRecord("FINANCE", "RD", "JUNIOR", 1, "TAIPEI", 52),
    SalaryRecord("FINANCE", "RD", "MID", 3, "TAIPEI", 72),
    SalaryRecord("FINANCE", "RD", "MID", 5, "TAIPEI", 88),
    SalaryRecord("FINANCE", "RD", "SENIOR", 7, "TAIPEI", 110),

    # FINANCE / DATA
    SalaryRecord("FINANCE", "DATA", "MID", 4, "TAIPEI", 82),
    SalaryRecord("FINANCE", "DATA", "SENIOR", 6, "TAIPEI", 105),

    # MFG / RD (科技業硬體 / 製造業 R&D)
    SalaryRecord("MFG", "RD", "JUNIOR", 1, "HSINCHU", 55),
    SalaryRecord("MFG", "RD", "JUNIOR", 1, "HSINCHU", 60),
    SalaryRecord("MFG", "RD", "MID", 3, "HSINCHU", 75),
    SalaryRecord("MFG", "RD", "MID", 4, "HSINCHU", 88),
    SalaryRecord("MFG", "RD", "MID", 5, "HSINCHU", 95),
    SalaryRecord("MFG", "RD", "SENIOR", 6, "HSINCHU", 115),
    SalaryRecord("MFG", "RD", "SENIOR", 8, "HSINCHU", 135),
    SalaryRecord("MFG", "RD", "STAFF", 10, "HSINCHU", 165),

    # MFG / DATA
    SalaryRecord("MFG", "DATA", "MID", 4, "HSINCHU", 80),
    SalaryRecord("MFG", "DATA", "SENIOR", 7, "HSINCHU", 110),

    # RETAIL / SALES
    SalaryRecord("RETAIL", "SALES", "JUNIOR", 1, "TAIPEI", 38),
    SalaryRecord("RETAIL", "SALES", "MID", 3, "TAIPEI", 50),
    SalaryRecord("RETAIL", "SALES", "MID", 5, "TAIPEI", 65),
    SalaryRecord("RETAIL", "SALES", "SENIOR", 8, "TAIPEI", 85),

    # RETAIL / OPS
    SalaryRecord("RETAIL", "OPS", "JUNIOR", 1, "TAIPEI", 36),
    SalaryRecord("RETAIL", "OPS", "MID", 3, "TAIPEI", 45),
    SalaryRecord("RETAIL", "OPS", "MID", 5, "TAIPEI", 55),

    # BIO / RD
    SalaryRecord("BIO", "RD", "JUNIOR", 1, "TAIPEI", 50),
    SalaryRecord("BIO", "RD", "MID", 3, "TAIPEI", 65),
    SalaryRecord("BIO", "RD", "MID", 5, "TAIPEI", 82),
    SalaryRecord("BIO", "RD", "SENIOR", 7, "TAIPEI", 100),
]


def filter_corpus(industry: str | None = None, role_family: str | None = None,
                   level: str | None = None, location: str | None = None,
                   exp_band: tuple[int, int] | None = None) -> list[SalaryRecord]:
    """Pure-function filter for similarity-based calibration set selection."""
    out = []
    for r in CORPUS:
        if industry and r.industry != industry:
            continue
        if role_family and r.role_family != role_family:
            continue
        if level and r.level != level:
            continue
        if location and r.location != location:
            continue
        if exp_band:
            lo, hi = exp_band
            if not (lo <= r.exp_years <= hi):
                continue
        out.append(r)
    return out
