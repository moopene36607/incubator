"""vetnote — 獸醫 SOAP 結構模板與常見主訴分類 (純資料,no I/O, no LLM).

收錄犬貓門診最常見的 10 種主訴分類,每類附 SOAP 各區的「典型應記載要點」,
作為 LLM prompt 的 grounding 提示,避免 AI 漏寫關鍵欄位。

實際產品需擴充至馬科、外科、影像專科等。本 prototype 涵蓋小動物 (犬貓)
一般門診足以示範核心價值。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChiefComplaintCategory:
    code: str          # 內部代碼,給 LLM 用
    chinese: str       # 中文主訴大類名
    english: str       # 英文 (SOAP 慣用)
    common_etiologies: tuple[str, ...]    # 鑑別診斷常見項
    must_record_in_o: tuple[str, ...]     # 客觀檢查必記錄欄位
    typical_workup: tuple[str, ...]       # 通常下單檢查
    treatment_categories: tuple[str, ...] # 處置分類 (僅給類別,不開劑量)


COMMON_CATEGORIES: list[ChiefComplaintCategory] = [
    ChiefComplaintCategory(
        code="GI_ACUTE",
        chinese="急性胃腸炎 / 嘔吐 / 腹瀉",
        english="Acute gastroenteritis / vomiting / diarrhea",
        common_etiologies=(
            "飲食不慎 (dietary indiscretion)", "急性胰臟炎", "腸異物 / 腸阻塞",
            "病毒性腸炎 (parvovirus / coronavirus)", "細菌性腸炎", "胰島素瘤", "中毒",
        ),
        must_record_in_o=(
            "TPR (體溫/脈搏/呼吸)", "體重 + 上次體重對比", "脫水程度 (皮膚張力 / 黏膜濕潤度)",
            "腹部觸診 (痛感 / 腹脹 / mass)", "嘔吐物或排便性狀觀察",
        ),
        typical_workup=(
            "CBC + biochem", "血氣 + 電解質", "腹部 X 光",
            "腹部超音波 (持續 24h+ 嘔吐時)", "Parvo SNAP test (年輕犬)", "Pancreas SNAP cPL/fPL",
        ),
        treatment_categories=(
            "靜脈輸液 (IV fluid 矯正脫水)", "止吐劑 (antiemetic)", "胃腸黏膜保護 / 抗酸劑",
            "禁食 12-24h 觀察", "再餵食採低脂易消化飲食",
        ),
    ),
    ChiefComplaintCategory(
        code="DERM_PRURITUS",
        chinese="皮膚搔癢 / 皮膚病",
        english="Pruritus / dermatologic disease",
        common_etiologies=(
            "外寄生蟲 (蚤 / 疥癬 / 蠕形蟎)", "細菌性皮膚炎", "馬拉色菌皮膚炎",
            "異位性皮膚炎", "食物過敏", "接觸性皮膚炎",
        ),
        must_record_in_o=(
            "皮膚病灶分布 (耳/臉/腋下/腹部/趾間)", "病灶型態 (紅斑/丘疹/脫毛/結痂)",
            "搔癢頻率與程度 (1-10)", "毛色 / 皮屑 / 異味",
        ),
        typical_workup=(
            "皮膚刮搔檢查", "膠帶採集細胞學", "Wood's lamp", "黴菌培養",
            "食物排除試驗 (≥8 週)", "過敏原 IgE / IDST",
        ),
        treatment_categories=(
            "外寄生蟲驅除", "抗生素 (細菌感染)", "抗黴菌藥",
            "止癢 (抗組織胺 / oclacitinib / lokivetmab)", "藥浴 / 藥用洗劑", "飲食調整",
        ),
    ),
    ChiefComplaintCategory(
        code="RESP",
        chinese="呼吸道症狀 (咳嗽 / 喘 / 流鼻水)",
        english="Respiratory signs (cough, dyspnea, nasal discharge)",
        common_etiologies=(
            "犬咳 (kennel cough complex)", "貓上呼吸道感染 (FHV/FCV/Chlamydia)",
            "氣管塌陷 (小型犬)", "心因性肺水腫", "肺炎", "支氣管炎",
            "肺臟腫瘤 (老年)", "鼻咽息肉 (貓)",
        ),
        must_record_in_o=(
            "TPR 含呼吸頻率與型態", "胸聽診 (心音 / 肺音 / 雜音)",
            "黏膜顏色 + capillary refill time", "上呼吸道理學檢查 (鼻分泌物 / 喉嚨)",
        ),
        typical_workup=(
            "胸部 X 光 (LR/VD/DV 三方位)", "心臟超音波 (老年犬可疑心衰)",
            "氣管沖洗或 BAL (反覆病例)", "FHV/FCV PCR (貓)",
        ),
        treatment_categories=(
            "止咳藥 (對症)", "支氣管擴張劑", "抗生素 (有細菌感染證據時)",
            "氧氣支持 / 住院觀察 (重症)", "心臟用藥 (心因性肺水腫)",
        ),
    ),
    ChiefComplaintCategory(
        code="UTI_LUTS",
        chinese="泌尿症狀 (頻尿 / 血尿 / 排尿困難)",
        english="Lower urinary tract signs",
        common_etiologies=(
            "細菌性膀胱炎", "貓特發性膀胱炎 (FIC)", "尿路結石",
            "尿道阻塞 (公貓急症)", "前列腺疾病 (公犬未絕育)", "膀胱腫瘤 (老年)",
        ),
        must_record_in_o=(
            "膀胱觸診 (大小 / 痛感)", "尿道口外觀", "前列腺觸診 (公犬,直腸觸診)",
        ),
        typical_workup=(
            "尿液檢查 (urinalysis + sediment)", "尿液細菌培養 + 藥敏",
            "腹部 X 光 (放射不透 stone)", "腹部超音波",
        ),
        treatment_categories=(
            "抗生素 (依培養結果)", "止痛 / NSAID", "尿道導管解阻塞 (急症)",
            "處方飼料 (溶結石 / 預防再發)", "增加飲水措施",
        ),
    ),
    ChiefComplaintCategory(
        code="ORTHO_LAME",
        chinese="跛行 / 骨骼肌肉症狀",
        english="Lameness / musculoskeletal signs",
        common_etiologies=(
            "膝蓋骨脫位 (Luxating patella, 小型犬)", "前十字韌帶斷裂 (CCL rupture)",
            "髖關節發育不良 (HD)", "椎間盤疾病 (IVDD)", "骨折", "關節炎 (老年)",
        ),
        must_record_in_o=(
            "跛行分級 (1-5)", "影響肢別 (LF/RF/LH/RH)", "關節觸診 (腫脹 / 痛 / drawer test)",
            "脊椎觸診 (痛感 / 神經學檢查)",
        ),
        typical_workup=(
            "受影響部位 X 光 (患側 + 對側對比)", "神經學檢查",
            "MRI (疑似 IVDD 或軟組織)", "關節液抽吸 (反覆腫脹)",
        ),
        treatment_categories=(
            "止痛 / NSAID", "限制活動 / 籠內休息", "關節保健劑",
            "物理治療 / 復健", "外科介入 (TPLO / 椎間盤手術 / 整復)",
        ),
    ),
]


_BY_CODE: dict[str, ChiefComplaintCategory] = {c.code: c for c in COMMON_CATEGORIES}


def lookup(code: str) -> ChiefComplaintCategory | None:
    return _BY_CODE.get(code.strip().upper())


def all_categories() -> list[ChiefComplaintCategory]:
    return list(COMMON_CATEGORIES)
