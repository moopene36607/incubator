"""subsidybot — 台灣中小企業 / 創業 / 個人補助方案 seed corpus.

Prototype 用 8 個代表性補助方案。實際產品需擴充至 50+,並接政府開放資料 API
(資料.gov.tw、SBIR 官網、創業台灣 startup.taiwan.gov.tw)做每日 sync。

每個方案的 eligibility 採結構化欄位 + 自然語言補充,讓:
  - 純函式 retrieval 可做硬條件過濾(年齡 / 設立年限 / 員工數)
  - LLM 可根據 free-text 條件做語意判斷(行業 / 創新性 / 性別 / 地區優先)

來源: 各主管機關官網 (2026-05 公告版本)。實際申請前必查最新公告!
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SubsidyProgram:
    code: str                    # 內部代碼
    name_zh: str                 # 中文名
    name_en: str                 # 英文名(若有)
    agency: str                  # 主管機關
    category: str                # "loan" | "grant" | "training" | "tax_break"
    max_amount_twd: int          # 上限金額(贷款額度 or 補助額度);0 表示非金錢類
    interest_terms: str          # 利率/還款條件;贷款型才有
    eligibility_summary: str     # 一句話資格摘要
    eligibility_age_min: int | None = None
    eligibility_age_max: int | None = None
    eligibility_business_age_max_years: float | None = None  # 設立年限上限
    eligibility_employee_max: int | None = None              # 員工上限
    eligibility_business_required: bool = False              # 是否須已設立公司行號
    eligibility_industries: tuple[str, ...] = field(default_factory=tuple)
    eligibility_genders: tuple[str, ...] = field(default_factory=tuple)
    application_deadline: str = "全年受理"
    required_documents: tuple[str, ...] = field(default_factory=tuple)
    official_url: str = ""
    last_updated: str = ""


PROGRAMS: list[SubsidyProgram] = [
    SubsidyProgram(
        code="MICRO_PHOENIX",
        name_zh="微型創業鳳凰貸款",
        name_en="Micro Phoenix Startup Loan",
        agency="勞動部勞動力發展署",
        category="loan",
        max_amount_twd=2_000_000,
        interest_terms="優惠利率(目前約 1%-2%);7 年期、前 2 年免息",
        eligibility_summary="20-65 歲女性、45 歲以上男性、新住民、中高齡 / 高齡 / 失業者 申請創業貸款。需通過 18 小時創業相關課程。",
        eligibility_age_min=20,
        eligibility_age_max=65,
        eligibility_business_age_max_years=5,
        eligibility_genders=("女", "男(45歲以上)"),
        application_deadline="全年受理",
        required_documents=("身分證", "創業計畫書", "18 小時創業課程結業證明",
                            "信用查詢同意書", "事業設立資料(若已設立)"),
        official_url="https://wda.gov.tw/cp.aspx?n=BB7DCDFCF99E47B5",
        last_updated="2026-04",
    ),
    SubsidyProgram(
        code="YOUTH_LOAN",
        name_zh="青年創業及啟動金貸款",
        name_en="Youth Entrepreneurship Startup Loan",
        agency="經濟部中小企業處",
        category="loan",
        max_amount_twd=12_000_000,
        interest_terms="郵局 2 年期定儲機動利率 +0.575%;7 年期、前 2 年免息;啟動金部分 NT$200 萬內免擔保",
        eligibility_summary="20-45 歲青年,事業設立 5 年內或籌備中,公司行號或商業登記。",
        eligibility_age_min=20,
        eligibility_age_max=45,
        eligibility_business_age_max_years=5,
        eligibility_business_required=True,
        application_deadline="全年受理",
        required_documents=("身分證", "公司 / 商業登記證明", "創業計畫書",
                            "信用查詢同意書", "資金運用計畫"),
        official_url="https://www.moeasmea.gov.tw/article-tw-2607-3960",
        last_updated="2026-04",
    ),
    SubsidyProgram(
        code="SBIR_PHASE1",
        name_zh="SBIR 小型企業創新研發計畫(第一階段:可行性研究)",
        name_en="SBIR Phase 1 - Feasibility Study",
        agency="經濟部產業發展署",
        category="grant",
        max_amount_twd=1_000_000,
        interest_terms="N/A(補助型,無需返還)",
        eligibility_summary="依法登記之中小企業(實收資本額 1 億以下 *或* 員工 200 人以下),具創新研發案。補助上限為總計畫經費 50%。",
        eligibility_employee_max=200,
        eligibility_business_required=True,
        application_deadline="每年 2-3 季開放收件;確切日期請查官網",
        required_documents=("公司登記文件", "近三年財務報表", "創新研發計畫書",
                            "技術資料 / 專利", "經費預算表", "團隊履歷"),
        official_url="https://www.sbir.org.tw/",
        last_updated="2026-03",
    ),
    SubsidyProgram(
        code="SIIR",
        name_zh="服務業創新研發計畫(SIIR)",
        name_en="SIIR - Service Industry Innovation Research",
        agency="經濟部商業發展署",
        category="grant",
        max_amount_twd=5_000_000,
        interest_terms="N/A",
        eligibility_summary="服務業中小企業(批發零售、餐飲、運輸、出版、資訊、住宿、文創等),從事服務模式創新或數位化轉型計畫。",
        eligibility_business_required=True,
        eligibility_industries=("服務業", "零售業", "餐飲業", "資訊服務業",
                                "出版業", "住宿業", "運輸業", "文創產業"),
        application_deadline="每年通常 1-2 次徵件,各 1-2 個月",
        required_documents=("公司登記證明", "計畫書", "經費預算表",
                            "近三年財務報表", "服務創新概念說明"),
        official_url="https://gcis.nat.gov.tw/mainNew/aboutCenterAction.do?method=siir",
        last_updated="2026-03",
    ),
    SubsidyProgram(
        code="DIGITAL_CLOUD",
        name_zh="中小企業數位雲端服務補助方案",
        name_en="SME Digital Cloud Service Subsidy",
        agency="數位發展部數位產業署",
        category="grant",
        max_amount_twd=250_000,
        interest_terms="N/A;補助比率最高 50%",
        eligibility_summary="本國中小企業(實收資本額 1 億以下或員工 100 人以下),購置雲端服務、行銷推廣、資訊安全等數位工具。",
        eligibility_employee_max=100,
        eligibility_business_required=True,
        application_deadline="每年通常 Q1-Q2 開放;額滿即截止",
        required_documents=("公司登記證明", "近三年財務報表",
                            "雲端服務報價單", "申請表", "銀行存摺影本"),
        official_url="https://www.smes.org.tw/digital/",
        last_updated="2026-04",
    ),
    SubsidyProgram(
        code="WOMEN_FLY",
        name_zh="女性創業飛雁計畫",
        name_en="Women Entrepreneurship Flying Geese Program",
        agency="經濟部中小企業處",
        category="training",
        max_amount_twd=0,
        interest_terms="N/A(免費培訓 + 一對一顧問輔導,無金錢補助)",
        eligibility_summary="女性企業主或女性想創業者,事業設立 5 年內為主。提供 1.5 年期培訓 + 業師媒合 + 行銷展售機會。",
        eligibility_business_age_max_years=5,
        eligibility_genders=("女",),
        application_deadline="每年通常 4-5 月招募",
        required_documents=("身分證", "事業現況或計畫書", "推薦信(選擇性)"),
        official_url="https://woman.sme.gov.tw/",
        last_updated="2026-03",
    ),
    SubsidyProgram(
        code="CITD",
        name_zh="協助傳統產業技術開發計畫(CITD)",
        name_en="Conventional Industries Technology Development",
        agency="經濟部產業發展署",
        category="grant",
        max_amount_twd=3_000_000,
        interest_terms="N/A;補助比率上限 50%",
        eligibility_summary="傳統製造業中小企業(食品、紡織、金屬、塑膠、機械等),從事產品 / 製程創新或淨零轉型計畫。",
        eligibility_business_required=True,
        eligibility_industries=("食品製造業", "紡織業", "金屬製品業", "塑膠製品業",
                                "機械設備業", "電子零組件業", "傳統製造業"),
        application_deadline="每年通常 Q1 + Q3 兩次徵件",
        required_documents=("公司登記證明", "近三年財務報表",
                            "技術 / 製程創新計畫書", "經費預算表", "ISO / 專利證明"),
        official_url="https://www.citd.tw/",
        last_updated="2026-03",
    ),
    SubsidyProgram(
        code="RURAL_YOUTH",
        name_zh="農村青年農民創業貸款 + 補助",
        name_en="Rural Youth Farmer Startup Loan & Grant",
        agency="農業部農業金融署",
        category="loan",
        max_amount_twd=5_000_000,
        interest_terms="優惠利率 1.025%;最長 20 年期;前 5 年寬限免還本",
        eligibility_summary="20-45 歲(可放寬到 65 歲)從事農業生產者,具農民身分或農會會員。",
        eligibility_age_min=20,
        eligibility_age_max=45,
        eligibility_industries=("農業", "漁業", "畜牧業", "農產加工"),
        application_deadline="全年受理",
        required_documents=("身分證", "農民身分證明", "農地 / 漁塭 / 牧場使用權證明",
                            "創業 / 經營計畫書", "信用查詢同意書"),
        official_url="https://www.naf.gov.tw/",
        last_updated="2026-03",
    ),
]


_BY_CODE: dict[str, SubsidyProgram] = {p.code: p for p in PROGRAMS}


def lookup(code: str) -> SubsidyProgram | None:
    return _BY_CODE.get(code.strip().upper())


def all_programs() -> list[SubsidyProgram]:
    return list(PROGRAMS)
