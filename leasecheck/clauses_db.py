"""leasecheck — 台灣住宅租賃合約常見條款 corpus + 風險等級.

每條 metadata 含:
  - code            : 條款代碼(如 DEPOSIT_OVER_2MTH)
  - category        : 條款類別(押金 / 解約 / 修繕 / 入住 / 退租 / 個資...)
  - risk_level      : red(違法 / 嚴重不利)/ yellow(可談 / 模糊不利)/ green(合理 / 合法)
  - keywords        : 關鍵字 list,no-AI 模式 keyword extraction 使用
  - legal_basis     : 法源(住宅租賃定型化契約應記載 / 不得記載事項 / 民法 / 租賃住宅市場發展條例)
  - common_phrasing : 該條款常見的中文句法樣本(供 AI 比對)
  - negotiation_tip : 房客可以怎麼跟房東談(口語化建議)
  - severity_score  : 0-30,風險加總時的權重

Source: 內政部「住宅租賃定型化契約應記載及不得記載事項」(2017 公告,
        2023 修正);民法 421-463 條;租賃住宅市場發展及管理條例。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClauseSpec:
    code: str
    category: str
    risk_level: str  # red / yellow / green
    description_zh: str
    keywords: tuple[str, ...]
    legal_basis: str
    common_phrasing: str
    negotiation_tip: str
    severity_score: int


CLAUSES: list[ClauseSpec] = [

    # === 押金 ===
    ClauseSpec(
        code="DEPOSIT_OVER_2MTH",
        category="押金",
        risk_level="red",
        description_zh="押金超過 2 個月租金 — 法定上限是 2 個月,超過即違法。房東如收 3 個月以上,你可以直接拒繳,房東無法強制扣留你的東西或斷水斷電。",
        keywords=("押金為新台幣肆萬", "押金為新台幣陸萬", "相當於三個月租金", "相當於3個月租金",
                  "相當於六個月租金", "相當於6個月租金", "押金三個月", "押金3個月", "押金六個月", "押金6個月"),
        legal_basis="租賃住宅市場發展條例第 7 條:押金不得超過 2 個月租金總額",
        common_phrasing="押金為新台幣三萬元(相當於三個月租金)",
        negotiation_tip="直接告知房東依《租賃住宅市場發展條例第 7 條》押金上限為 2 個月租金,要求調整。多收的部分租客可拒繳。",
        severity_score=25,
    ),
    ClauseSpec(
        code="DEPOSIT_NO_INTEREST",
        category="押金",
        risk_level="green",
        description_zh="押金本身合法(2 個月以內),不論是否付息均符合慣例。",
        keywords=("相當於兩個月租金", "相當於2個月租金", "押金兩個月", "押金2個月", "押金不計息"),
        legal_basis="租賃住宅市場發展條例第 7 條",
        common_phrasing="押金為新台幣兩萬元(相當於兩個月租金),押金不計息",
        negotiation_tip="押金 ≤ 2 個月租金完全合法,不需爭議。",
        severity_score=0,
    ),
    ClauseSpec(
        code="DEPOSIT_FORFEIT_NO_REASON",
        category="押金",
        risk_level="red",
        description_zh="房東保留「無條件沒收押金」權利 — 應記載事項規定:押金應於合約終止後 15 日內,扣除欠租 / 修繕 / 違約金後返還。任何「房東有權沒收」「不予退還」的條款都不合法。",
        keywords=("沒收", "不予退還", "全數扣留", "押金不退"),
        legal_basis="住宅租賃定型化契約應記載事項第 11 點 — 押金返還義務",
        common_phrasing="若有違約情事,房東得沒收全部押金不予退還",
        negotiation_tip="要求修改為「依實際損害扣除後返還」+「合約終止後 15 日內返還」。",
        severity_score=20,
    ),

    # === 解約 / 違約金 ===
    ClauseSpec(
        code="EARLY_TERMINATION_PENALTY_OVER_1MTH",
        category="解約",
        risk_level="red",
        description_zh="提前解約違約金超過 1 個月租金 — 應記載事項規定違約金不得超過 1 個月租金,且需提前 30 天告知。常見坑:寫「2 個月」「全部押金沒收」皆違法。",
        keywords=("二個月租金之違約金", "兩個月租金之違約金", "三個月租金之違約金", "2個月租金之違約金",
                  "二個月違約金", "三個月違約金", "全部押金沒收", "違約金全額"),
        legal_basis="住宅租賃定型化契約應記載事項第 14 點",
        common_phrasing="租客若提前終止租約,需賠償房東二個月租金之違約金",
        negotiation_tip="主張依應記載事項第 14 點,違約金上限為 1 個月。請房東修改後再簽。",
        severity_score=20,
    ),
    ClauseSpec(
        code="EARLY_TERMINATION_NOTICE_30D",
        category="解約",
        risk_level="green",
        description_zh="提前 30 天告知 + 1 個月違約金 — 完全合法且合理。",
        keywords=("提前30日", "提前30天", "提前一個月", "一個月違約金"),
        legal_basis="住宅租賃定型化契約應記載事項第 14 點",
        common_phrasing="租客需於終止前 30 日通知房東,並支付一個月租金作為違約金",
        negotiation_tip="這條合理,可接受。",
        severity_score=0,
    ),
    ClauseSpec(
        code="MANDATORY_RENEWAL",
        category="解約",
        risk_level="red",
        description_zh="強制續約條款 — 應記載事項禁止「房東得單方面要求續約」「自動續約且租客不得拒絕」。租客有權選擇是否續約。",
        keywords=("自動續約", "強制續約", "不得拒絕", "視為續約"),
        legal_basis="住宅租賃定型化契約不得記載事項第 7 點",
        common_phrasing="租期屆滿時,自動續約一年,租客不得拒絕",
        negotiation_tip="刪除或改為「雙方合意得續約」。",
        severity_score=15,
    ),

    # === 修繕 ===
    ClauseSpec(
        code="REPAIR_ALL_ON_TENANT",
        category="修繕",
        risk_level="red",
        description_zh="所有修繕由房客負擔 — 民法 429 條規定「修繕義務除契約另有訂定外由出租人負擔」。但「除契約另有訂定外」不是空白支票:應記載事項第 9 點規定房屋本體 + 既有設備修繕應由房東負擔,房客只負責一般使用磨耗 + 自身過失。",
        keywords=("所有修繕", "全部修繕", "概由租客自行負擔", "概由房客自行負擔",
                  "概由租客負擔", "概由房客負擔", "房東不負任何修繕", "修繕費用,概由"),
        legal_basis="民法第 429 條 + 住宅租賃定型化契約應記載事項第 9 點",
        common_phrasing="租賃物之修繕費用,概由租客自行負擔",
        negotiation_tip="主張既有設備(冷氣 / 熱水器 / 馬桶 / 漏水)修繕應由房東負擔,僅一般磨耗 + 過失損壞由房客承擔。",
        severity_score=18,
    ),
    ClauseSpec(
        code="REPAIR_REASONABLE_SPLIT",
        category="修繕",
        risk_level="green",
        description_zh="合理修繕分擔(房東負擔本體 + 既有設備,房客負擔一般使用磨耗) — 完全合法。",
        keywords=("既有設備", "房東負擔修繕", "本體修繕", "正常使用磨耗"),
        legal_basis="住宅租賃定型化契約應記載事項第 9 點",
        common_phrasing="房屋本體及既有設備之修繕由房東負擔,正常使用磨耗或房客過失導致之損害由房客負擔",
        negotiation_tip="這條合理,可接受。",
        severity_score=0,
    ),

    # === 報稅 ===
    ClauseSpec(
        code="NO_TAX_DECLARATION",
        category="報稅",
        risk_level="red",
        description_zh="禁止房客申報租金支出 — 嚴重侵害房客權益:房客可列舉扣除額或申請租金補貼,但合約寫「不得申報」是違法的。應記載事項明定房東不得限制房客申報。",
        keywords=("不得申報", "不得報稅", "禁止申報", "拒絕報稅", "申報所得稅扣除額", "申報扣除額", "不得以本租約申報"),
        legal_basis="住宅租賃定型化契約不得記載事項第 4 點",
        common_phrasing="租客不得以本租約申報所得稅扣除額或申請任何政府補貼",
        negotiation_tip="此條無效,房客本來就有權申報。建議直接刪除,並告知房東是違法條款。如房東不同意,考慮放棄此租約。",
        severity_score=22,
    ),

    # === 入住 / 房東進入 ===
    ClauseSpec(
        code="LANDLORD_ENTER_NO_NOTICE",
        category="入住",
        risk_level="red",
        description_zh="房東得隨時進入 — 民法 423 條規定房東進入需經房客同意 / 預告。應記載事項要求「應於合理時間 24 小時前預告」。",
        keywords=("隨時進入", "不需通知", "得進入", "房東有鑰匙隨時"),
        legal_basis="民法第 423 條 + 住宅租賃定型化契約應記載事項第 6 點",
        common_phrasing="房東保留隨時進入租賃物進行檢查之權利",
        negotiation_tip="要求改為「房東進入需提前 24 小時通知,且僅於合理時間」。",
        severity_score=15,
    ),
    ClauseSpec(
        code="LANDLORD_ENTER_24H",
        category="入住",
        risk_level="green",
        description_zh="房東進入需提前 24 小時通知 — 完全合法。",
        keywords=("24小時通知", "24小時前", "預告進入"),
        legal_basis="住宅租賃定型化契約應記載事項第 6 點",
        common_phrasing="房東欲進入租賃物應於 24 小時前通知房客",
        negotiation_tip="這條合理,可接受。",
        severity_score=0,
    ),

    # === 退租清掃費 ===
    ClauseSpec(
        code="MOVEOUT_CLEANING_FEE",
        category="退租",
        risk_level="yellow",
        description_zh="預設退租清掃費 — 應記載事項規定房東不得預先扣除「未實際發生」費用。如清掃費需有實際清潔報價單佐證,不得用「固定 NT$3,000」這種預設條款。",
        keywords=("清潔費", "清掃費", "退租清潔", "固定費用"),
        legal_basis="住宅租賃定型化契約應記載事項第 11 點 — 押金返還與扣除原則",
        common_phrasing="退租時,房東得從押金扣除新台幣參仟元作為清潔費",
        negotiation_tip="要求改為「依實際清潔需求 + 報價單扣除」,且房客有權自行清潔免費用。",
        severity_score=8,
    ),

    # === 寵物 / 家具 ===
    ClauseSpec(
        code="NO_PETS_STRICT",
        category="入住",
        risk_level="yellow",
        description_zh="禁止寵物條款 — 完全合法,但若已養寵物應提前告知房東協商。違反此條房東可解約。",
        keywords=("禁止寵物", "不得養寵物", "禁止飼養"),
        legal_basis="契約自由原則(民法 153 條)",
        common_phrasing="租賃物內禁止飼養任何寵物,違者房東得立即終止合約",
        negotiation_tip="若你有寵物,簽約前一定要跟房東協商寵物押金 / 家具保護方案,否則違反等同違約。",
        severity_score=5,
    ),

    # === 個資 / 連帶保證 ===
    ClauseSpec(
        code="EXCESSIVE_PERSONAL_INFO",
        category="個資",
        risk_level="yellow",
        description_zh="過度個資授權 — 房東僅需身分證 + 緊急聯絡人,不得要求公司營收 / 父母收入 / 銀行帳戶餘額。",
        keywords=("授權查詢", "查詢公司", "薪資證明", "銀行存款", "向其公司", "向其銀行", "查詢任何相關財務", "查詢相關財務", "查詢財務資料"),
        legal_basis="個人資料保護法第 5 條 — 蒐集應符合特定目的",
        common_phrasing="租客同意房東得向其公司、銀行查詢任何相關財務資料",
        negotiation_tip="要求僅提供薪轉證明 + 緊急聯絡人,拒絕授權房東主動查詢。",
        severity_score=10,
    ),

    # === 違約事件 ===
    ClauseSpec(
        code="LANDLORD_TERMINATE_NO_REASON",
        category="解約",
        risk_level="red",
        description_zh="房東得無條件終止合約 — 應記載事項禁止此類條款。房東終止合約需有法定事由(欠租 2 個月以上 / 用途違反 / 重大破壞),且需通知催告。",
        keywords=("無條件終止", "得隨時終止", "得單方終止"),
        legal_basis="住宅租賃定型化契約不得記載事項第 5 點",
        common_phrasing="房東得隨時無條件終止本租約,租客需於 7 日內遷離",
        negotiation_tip="此條無效。應改為「房東依民法 / 租賃條例規定事由終止」。",
        severity_score=22,
    ),
    ClauseSpec(
        code="MOVEOUT_DAYS_TOO_SHORT",
        category="退租",
        risk_level="red",
        description_zh="退租 / 搬家期限過短(< 30 天) — 應記載事項規定房東終止合約後,房客有合理期限(通常 30 天)搬遷。寫「7 日」「3 日」等屬不合理短期。",
        keywords=("7日內遷離", "3日內遷離", "5日內搬離", "七日內遷離", "三日內遷離"),
        legal_basis="民法第 451 條 + 住宅租賃定型化契約應記載事項",
        common_phrasing="合約終止後,租客需於 7 日內遷離租賃物",
        negotiation_tip="要求改為「30 日內遷離」最低門檻。",
        severity_score=12,
    ),

    # === 租金調整 ===
    ClauseSpec(
        code="RENT_INCREASE_DURING_TERM",
        category="租金",
        risk_level="red",
        description_zh="合約期內單方漲房租 — 應記載事項禁止房東於原約定期間內單方面調漲。可漲時機為續約。",
        keywords=("單方調整租金", "得調漲", "每年調漲", "視物價"),
        legal_basis="住宅租賃定型化契約不得記載事項第 6 點",
        common_phrasing="房東得依物價指數每年調漲租金 5%,租客不得異議",
        negotiation_tip="要求僅於續約時可協議調整,合約期內不得漲。",
        severity_score=15,
    ),
    ClauseSpec(
        code="RENT_FIXED_TERM",
        category="租金",
        risk_level="green",
        description_zh="合約期內租金固定 — 完全合法且符合應記載事項。",
        keywords=("租金固定", "本約期內不調整", "租金為新台幣"),
        legal_basis="住宅租賃定型化契約應記載事項第 3 點",
        common_phrasing="租金為每月新台幣壹萬伍仟元整,本約期內不予調整",
        negotiation_tip="這條合理,可接受。",
        severity_score=0,
    ),

    # === 水電費 / 管理費 ===
    ClauseSpec(
        code="UTILITY_FEES_INFLATED",
        category="水電",
        risk_level="yellow",
        description_zh="電費浮動上限 — 房東不得收取超過台電實際電價 + 合理代收(如管理 NT$1-2 / 度)。寫「每度 6 元」已遠高於台電商業用電平均(< 5 元),屬於營利。",
        keywords=("每度6元", "每度7元", "每度8元", "每度陸元", "每度柒元", "每度捌元", "電費每度6元", "電費每度7元"),
        legal_basis="租賃住宅市場發展條例 + 公平交易法",
        common_phrasing="電費每度新台幣陸元整,租客需依實際使用付清",
        negotiation_tip="要求依台電帳單實際分攤。或要求看到台電帳單再分攤。",
        severity_score=8,
    ),

    # === 違禁項 ===
    ClauseSpec(
        code="NO_GUEST_OVERNIGHT",
        category="入住",
        risk_level="yellow",
        description_zh="禁止留宿訪客 — 通常不會被認為違法,但若太嚴(如連伴侶都不能留宿)有侵害居住權之虞。可協商。",
        keywords=("禁止留宿", "不得留宿", "訪客不得過夜"),
        legal_basis="契約自由原則(但需符合公序良俗)",
        common_phrasing="非租客本人不得於租賃物內留宿",
        negotiation_tip="可協商改為「同居伴侶 / 親屬除外」,或「訪客留宿 ≤ 5 晚 / 月不違約」。",
        severity_score=5,
    ),
]


def get_clause_by_code(code: str) -> ClauseSpec | None:
    return next((c for c in CLAUSES if c.code == code), None)


def all_codes() -> list[str]:
    return [c.code for c in CLAUSES]
