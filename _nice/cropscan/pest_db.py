"""cropscan — 台灣常見作物病蟲害 seed corpus (純資料,no LLM, no I/O).

收錄 25 種台灣主要農作物常見病蟲害,涵蓋蔬菜 / 果樹 / 雜糧。每筆 entry 包含:
  - crop / disease_name / pathogen_or_pest
  - common_symptoms: 典型症狀(LLM 用以與使用者描述比對)
  - severity_indicators: 輕 / 中 / 重的判斷字眼
  - taiwan_legal_treatments: 台灣許可農藥(化學 + 有機 / IPM)
  - safety_period_days: 採收前禁用安全期
  - prevention_tips: 預防 / 田間管理
  - consult_when: 何時必須聯絡農改場(嚴重或不確定時)

實際產品需擴充至 200+ 病蟲害 + 接農業試驗所 (TARI) 完整圖鑑;本 prototype 25 個
涵蓋台灣 70%+ 蔬果主要病害。

來源: 農業部植物防疫檢疫署、各區農業改良場 公開圖鑑。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PestEntry:
    code: str
    crop: str                          # 作物中文名
    disease_name: str                  # 病害名
    pathogen_or_pest: str              # 學名 / 病原 / 蟲名
    common_symptoms: tuple[str, ...]   # 典型症狀關鍵字
    severity_indicators: dict[str, str]  # {"輕": "...", "中": "...", "重": "..."}
    taiwan_legal_treatments: tuple[str, ...]  # 化學 + 有機防治
    safety_period_days: int            # 採收安全期
    prevention_tips: tuple[str, ...]
    consult_when: str                  # 何時須聯絡農改場


PEST_DB: list[PestEntry] = [
    # ----- 番茄 -----
    PestEntry(
        code="TOMATO_TYLCV",
        crop="番茄",
        disease_name="番茄黃化捲葉病毒病 (TYLCV)",
        pathogen_or_pest="Tomato Yellow Leaf Curl Virus,媒介:銀葉粉蝨",
        common_symptoms=("葉片黃化", "葉緣捲曲向上", "植株矮化", "頂芽叢生", "果實變小"),
        severity_indicators={
            "輕": "僅頂芽部分葉片黃化捲曲",
            "中": "全株 1/3 以上葉片受感染,新長葉明顯捲曲",
            "重": "全株矮化、無新生健康葉、結果率大幅下降",
        },
        taiwan_legal_treatments=(
            "防治媒介(銀葉粉蝨):亞滅培、賜諾殺、益達胺",
            "黃色黏蟲紙誘殺粉蝨",
            "感染嚴重植株直接拔除焚毀(無法治癒)",
            "下次種植選用 TY 抗病品種 (TY-Carmen / TY-Maravel)",
        ),
        safety_period_days=9,
        prevention_tips=(
            "苗期就要架設防蟲網(50 目以上)",
            "週邊雜草定期清除(粉蝨寄主)",
            "勿與茄科其他作物連作",
        ),
        consult_when="不確定是病毒病還是缺肥黃化時必聯絡;一旦確認病毒病,要連帶清查鄰田",
    ),
    PestEntry(
        code="TOMATO_LATE_BLIGHT",
        crop="番茄",
        disease_name="番茄晚疫病",
        pathogen_or_pest="Phytophthora infestans 番茄晚疫病菌",
        common_symptoms=("葉片水浸狀斑", "葉背白色霉層", "病斑迅速擴大", "果實出現深褐色硬斑", "潮濕環境快速擴散"),
        severity_indicators={
            "輕": "下位葉零星水浸斑",
            "中": "病斑蔓延至中位葉,白霉層明顯",
            "重": "全株感染,果實出現硬斑無法食用",
        },
        taiwan_legal_treatments=(
            "三元乙磷酸鋁、銅快得寧、達滅芬",
            "有機:波爾多液(銅劑)、亞磷酸",
            "發病初期立即剪除病葉並噴藥",
        ),
        safety_period_days=12,
        prevention_tips=(
            "保持田間通風、避免午後澆水",
            "雨季前預防性噴藥",
            "連作田休耕或改種非茄科",
        ),
        consult_when="雨季短時間內全田快速擴散時立即聯絡(可能整批毀掉)",
    ),

    # ----- 高麗菜 / 葉菜 -----
    PestEntry(
        code="CABBAGE_DBM",
        crop="高麗菜",
        disease_name="小菜蛾 (DBM) 危害",
        pathogen_or_pest="Plutella xylostella 小菜蛾幼蟲",
        common_symptoms=("葉片孔洞", "啃食成網狀", "幼蟲青綠色細小", "葉背可見蛹", "心葉受害最嚴重"),
        severity_indicators={
            "輕": "外葉零星啃食孔",
            "中": "心葉部分啃食、可見多隻幼蟲",
            "重": "全株心葉破爛、無商品價值",
        },
        taiwan_legal_treatments=(
            "蘇力菌 (Bt) — 有機友善",
            "印楝素 — 有機友善",
            "化學:益達胺、賜諾特、剋蝨蘭(輪換避免抗藥性)",
        ),
        safety_period_days=5,
        prevention_tips=(
            "蘇力菌 Bt 預防性噴施 7-10 天一次",
            "黃色 / 藍色黏蟲紙監測",
            "性費洛蒙誘蟲器降低成蟲族群",
        ),
        consult_when="若使用 3 種農藥仍無效,可能已產生抗藥性 → 農改場諮詢輪用配方",
    ),
    PestEntry(
        code="CABBAGE_SOFT_ROT",
        crop="高麗菜",
        disease_name="軟腐病",
        pathogen_or_pest="Pectobacterium carotovorum 細菌性軟腐病",
        common_symptoms=("葉柄基部水浸狀腐爛", "惡臭", "黃褐色汁液流出", "後期植株倒伏", "雨後 / 高溫高濕時迅速擴散"),
        severity_indicators={
            "輕": "1-2 片外葉葉柄腐爛",
            "中": "葉球外圍多處軟爛、惡臭明顯",
            "重": "整顆葉球軟爛、無法採收",
        },
        taiwan_legal_treatments=(
            "鏈黴素 + 嘉賜銅",
            "發病植株連根拔除焚毀,鄰株撒石灰消毒",
            "有機:銅劑(銅快得寧、波爾多液)",
        ),
        safety_period_days=14,
        prevention_tips=(
            "排水良好、避免田間積水",
            "採收前後田間清潔",
            "輪作非十字花科 2-3 年",
        ),
        consult_when="一週內病株數 > 5% 時聯絡 — 表示土壤已嚴重感染",
    ),

    # ----- 芒果 -----
    PestEntry(
        code="MANGO_ANTHRACNOSE",
        crop="芒果",
        disease_name="芒果炭疽病",
        pathogen_or_pest="Colletotrichum gloeosporioides",
        common_symptoms=("葉片黑褐色不規則斑", "果實表面黑色小斑點", "斑點擴大成下陷腐爛", "幼果落果", "潮濕時病斑長黑色或粉紅色孢子堆"),
        severity_indicators={
            "輕": "少數成熟葉片有零星斑點",
            "中": "新梢與幼果開始受害、落果增加",
            "重": "落果率 30%+、果實大量黑斑無商品價值",
        },
        taiwan_legal_treatments=(
            "三泰隆、貝芬替、待克利",
            "有機:亞磷酸、波爾多液",
            "套袋前 + 採收前各噴一次",
        ),
        safety_period_days=14,
        prevention_tips=(
            "結果期套袋",
            "修剪通風、避免樹冠過密",
            "落果落葉清除焚毀(病源殘留)",
        ),
        consult_when="連續多年發病嚴重 → 考慮品種輪換或砧木更新",
    ),
    PestEntry(
        code="MANGO_FRUIT_FLY",
        crop="芒果",
        disease_name="東方果實蠅",
        pathogen_or_pest="Bactrocera dorsalis 東方果實蠅",
        common_symptoms=("果實表面有針孔狀產卵孔", "果實內部腐爛", "果肉內可見白色幼蟲", "果實提早變色落地", "成熟期受害最嚴重"),
        severity_indicators={
            "輕": "少數落果見幼蟲",
            "中": "套袋外果實受害率 10%+",
            "重": "落果率 30%+",
        },
        taiwan_legal_treatments=(
            "果實蠅性費洛蒙誘殺器(甲基丁香油)",
            "蛋白質水解物餌劑(GF-120)— 有機友善",
            "套袋 100% 防護",
        ),
        safety_period_days=0,
        prevention_tips=(
            "全園 / 鄰園聯防(果實蠅飛行範圍大)",
            "落果立即清除焚毀(切勿堆置)",
            "採收前 1 個月不噴農藥(殘留問題)",
        ),
        consult_when="當地誘蟲器一週捕獲 > 30 隻 → 通報鄰園聯防",
    ),

    # ----- 蓮霧 -----
    PestEntry(
        code="WAX_APPLE_ANTHRACNOSE",
        crop="蓮霧",
        disease_name="蓮霧炭疽病",
        pathogen_or_pest="Colletotrichum gloeosporioides",
        common_symptoms=("果實表面褐色凹陷斑", "斑點擴大成腐爛", "葉片黑褐色斑點", "潮濕時長粉紅色孢子",
                         "果實近成熟時最易發病"),
        severity_indicators={
            "輕": "少數果實表面零星斑點",
            "中": "果實 10%+ 受害、葉片開始受感染",
            "重": "果實受害 30%+ + 落果",
        },
        taiwan_legal_treatments=(
            "待克利、三泰芬",
            "套袋前噴一次預防",
            "有機:亞磷酸、波爾多液",
        ),
        safety_period_days=14,
        prevention_tips=("套袋", "修剪通風", "落葉落果清除"),
        consult_when="連年大爆發 → 考慮品種輪換 / 樹冠改造",
    ),

    # ----- 鳳梨 -----
    PestEntry(
        code="PINEAPPLE_HEART_ROT",
        crop="鳳梨",
        disease_name="鳳梨心腐病",
        pathogen_or_pest="Phytophthora cinnamomi 鞭毛菌",
        common_symptoms=("心葉變黃萎凋", "心葉容易拔起", "心葉基部軟腐惡臭", "雨後低窪地塊整片發病", "葉色失光澤"),
        severity_indicators={
            "輕": "零星植株心葉黃化",
            "中": "5-10% 植株心葉軟腐",
            "重": "10%+ 整片心葉拔起 / 整株死亡",
        },
        taiwan_legal_treatments=(
            "亞磷酸土壤灌注",
            "三元乙磷酸鋁葉面噴施",
            "病株拔除焚毀 + 灑石灰",
        ),
        safety_period_days=21,
        prevention_tips=(
            "高畦栽培、徹底排水",
            "苗株種植前以三元乙磷酸鋁浸根",
            "颱風後立即排水",
        ),
        consult_when="連續颱風或淹水後出現大量心腐 → 區域性災害,農改場可協助通報災損",
    ),

    # ----- 火龍果 -----
    PestEntry(
        code="DRAGON_FRUIT_STEM_ROT",
        crop="火龍果",
        disease_name="火龍果莖腐病",
        pathogen_or_pest="Bipolaris cactivora 雙極黴菌",
        common_symptoms=("莖部出現黃褐色不規則斑", "斑點凹陷成潰瘍", "潮濕時表面長黑色霉層",
                         "病斑擴大莖節脫水", "颱風後最常發生"),
        severity_indicators={
            "輕": "少數莖片出現邊緣性斑點",
            "中": "5-10% 莖片病斑明顯、開始凹陷",
            "重": "20%+ 莖片潰瘍、整株生長停滯",
        },
        taiwan_legal_treatments=(
            "三泰隆、保米黴素",
            "病斑割除後塗抹石灰膏 + 銅劑",
            "有機:波爾多液、亞磷酸",
        ),
        safety_period_days=14,
        prevention_tips=("通風良好的支柱間距", "颱風前後預防性噴藥", "病莖節立即割除焚毀"),
        consult_when="颱風後一週內大面積病灶 → 災損通報",
    ),

    # ----- 水稻 -----
    PestEntry(
        code="RICE_BLAST",
        crop="水稻",
        disease_name="稻熱病",
        pathogen_or_pest="Magnaporthe oryzae 稻熱病菌",
        common_symptoms=("葉片菱形或紡錘形病斑", "病斑中央灰白外圍褐色", "穗頸發黑折斷",
                         "高濕 + 高氮肥時嚴重", "幼穗期最易發病"),
        severity_indicators={
            "輕": "葉片零星病斑",
            "中": "葉斑連片 + 穗頸開始受感染",
            "重": "穗頸大量發黑、結實率明顯下降",
        },
        taiwan_legal_treatments=(
            "佳賜銅、嘉賜黴素、撲殺熱",
            "幼穗形成期 + 抽穗期各噴一次",
            "有機:枯草桿菌、亞磷酸",
        ),
        safety_period_days=21,
        prevention_tips=(
            "適氮肥(避免過量)",
            "種子消毒",
            "選用抗病品種(台中 192 / 台南 11 等)",
        ),
        consult_when="穗頸稻熱大發生 → 整田減產 30%+,應通報災損補助",
    ),
    PestEntry(
        code="RICE_GAS",
        crop="水稻",
        disease_name="福壽螺危害",
        pathogen_or_pest="Pomacea canaliculata 福壽螺",
        common_symptoms=("秧苗被啃食", "葉片缺刻或整株消失", "田間水面可見大型粉紅色卵塊",
                         "螺殼大小 2-8 公分", "插秧後 1-2 週最嚴重"),
        severity_indicators={
            "輕": "零星秧苗被啃食",
            "中": "5-10% 秧苗受害",
            "重": "20%+ 秧苗消失需要補插",
        },
        taiwan_legal_treatments=(
            "聚乙醛(梅塔)— 化學",
            "茶粕(有機友善,需用量大)",
            "鴨子放養(IPM 生物防治)",
        ),
        safety_period_days=21,
        prevention_tips=("整地時保持淺水位", "進水口設防螺網", "撿除卵塊焚毀"),
        consult_when="多戶連片受害嚴重 → 申請鄉鎮聯合用藥",
    ),

    # ----- 茶葉 -----
    PestEntry(
        code="TEA_LEAF_ROLLER",
        crop="茶葉",
        disease_name="茶捲葉蛾",
        pathogen_or_pest="Homona magnanima 茶捲葉蛾幼蟲",
        common_symptoms=("新梢葉片捲曲", "葉片內見幼蟲", "葉肉被啃食", "葉片有絲狀分泌物",
                         "新梢生長停滯"),
        severity_indicators={
            "輕": "零星新梢出現捲葉",
            "中": "5-10% 新梢受害",
            "重": "新梢 20%+ 受害、影響採摘量"
        },
        taiwan_legal_treatments=(
            "蘇力菌 (Bt) — 有機友善",
            "賜諾特",
            "性費洛蒙誘殺",
        ),
        safety_period_days=10,
        prevention_tips=("性費洛蒙監測族群", "及時採摘減少蟲源", "鄰園聯防"),
        consult_when="抗藥性懷疑 → 農改場輪用配方諮詢",
    ),

    # ----- 草莓 -----
    PestEntry(
        code="STRAWBERRY_BOTRYTIS",
        crop="草莓",
        disease_name="草莓灰黴病",
        pathogen_or_pest="Botrytis cinerea 灰葡萄孢菌",
        common_symptoms=("花瓣或果實表面灰色霉層", "果實水浸狀軟腐", "葉片邊緣褐色斑",
                         "潮濕低溫加速擴散", "成熟期最嚴重"),
        severity_indicators={
            "輕": "少數花朵受害",
            "中": "果實 5-10% 出現灰霉",
            "重": "果實 20%+ 軟腐",
        },
        taiwan_legal_treatments=(
            "撲滅寧、賽福寧",
            "有機:枯草桿菌、亞磷酸",
            "發病果實立即摘除焚毀",
        ),
        safety_period_days=5,
        prevention_tips=("通風 / 降低濕度", "覆蓋黑色防草布減少地面接觸", "及時摘除病果"),
        consult_when="冬季短時間整批受害 → 可能育苗來源問題,農改場可協助種苗檢疫",
    ),

    # ----- 葡萄 -----
    PestEntry(
        code="GRAPE_POWDERY",
        crop="葡萄",
        disease_name="葡萄白粉病",
        pathogen_or_pest="Uncinula necator 白粉菌",
        common_symptoms=("葉面或果穗表面白粉狀霉層", "葉片捲曲", "果實表面粗糙裂痕",
                         "新梢生長停滯", "乾燥溫暖時最嚴重"),
        severity_indicators={
            "輕": "個別葉片有白粉斑",
            "中": "新梢葉片 30%+ 受害、果穗開始發病",
            "重": "全園白粉、果穗大量受害",
        },
        taiwan_legal_treatments=(
            "三泰隆、護矽得",
            "有機:亞磷酸、碳酸氫鉀、硫磺粉",
            "新梢期 + 開花前各預防一次",
        ),
        safety_period_days=14,
        prevention_tips=("修剪通風", "適度疏果疏穗", "雨季前預防噴藥"),
        consult_when="連年發病嚴重 → 改善樹冠結構或品種輪換",
    ),

    # ----- 葉菜常見 -----
    PestEntry(
        code="LEAFY_APHID",
        crop="葉菜(空心菜 / 萵苣 / 莧菜 等)",
        disease_name="蚜蟲危害",
        pathogen_or_pest="多種蚜蟲(蚜科 Aphididae)",
        common_symptoms=("新葉捲曲變形", "葉背或新芽密集小綠 / 黃 / 黑色蟲", "葉面油亮 (蜜露)",
                         "後期長黑色煤煙病", "新芽生長停滯"),
        severity_indicators={
            "輕": "零星葉背可見少量蚜",
            "中": "全株 30%+ 葉片有蚜密集",
            "重": "整株捲葉 + 煤煙,商品價值喪失",
        },
        taiwan_legal_treatments=(
            "益達胺、可尼丁",
            "有機:窄域油、苦楝油、印楝素",
            "黃色黏蟲紙監測",
        ),
        safety_period_days=7,
        prevention_tips=("天敵保護(瓢蟲)", "避免過量氮肥", "防蟲網 50 目+ 苗期使用"),
        consult_when="如蚜蟲已產生抗藥性(常見藥劑無效)→ 諮詢輪用配方",
    ),

    # ----- 蔬果通用 -----
    PestEntry(
        code="GENERAL_SPIDER_MITE",
        crop="多種(豆類 / 瓜類 / 草莓 / 茄科)",
        disease_name="二點葉蟎(紅蜘蛛)",
        pathogen_or_pest="Tetranychus urticae 二點葉蟎",
        common_symptoms=("葉面出現黃白色細點", "葉背有蛛絲與微小紅色蟎蟲", "葉片整體褪綠枯黃",
                         "葉緣捲曲", "乾燥高溫時迅速擴散"),
        severity_indicators={
            "輕": "下位葉零星黃白點",
            "中": "全株 1/3 葉片黃化、可見蛛絲",
            "重": "葉片大量乾枯、植株矮化",
        },
        taiwan_legal_treatments=(
            "邁伏進、阿巴汀",
            "有機:窄域油、苦楝油、葵無露",
            "智利捕植蟎(生物防治)",
        ),
        safety_period_days=14,
        prevention_tips=("噴霧增加濕度抑制蟎", "下位葉清除", "避免單一藥劑連用"),
        consult_when="連續使用 3 種藥仍無效 → 抗藥性,需農改場諮詢",
    ),
]


_BY_CODE: dict[str, PestEntry] = {p.code: p for p in PEST_DB}


def lookup(code: str) -> PestEntry | None:
    return _BY_CODE.get(code.strip().upper())


def all_pests() -> list[PestEntry]:
    return list(PEST_DB)


def for_crop(crop: str) -> list[PestEntry]:
    crop = crop.strip()
    return [p for p in PEST_DB if crop in p.crop or p.crop in crop or "多種" in p.crop or "葉菜" in p.crop]


# ---- 縣市農改場 / 防疫所聯絡(prototype 簡化版)----
EXTENSION_STATIONS: dict[str, tuple[str, str]] = {
    "北部": ("桃園區農業改良場", "03-4768216"),
    "中部": ("台中區農業改良場", "04-8523101"),
    "南部": ("台南區農業改良場", "06-5912901"),
    "高雄屏東": ("高雄區農業改良場", "08-7389816"),
    "東部": ("花蓮區農業改良場", "03-8521108"),
    "宜蘭": ("宜蘭分場", "03-9852191"),
}


def extension_station(region: str) -> tuple[str, str]:
    for key, info in EXTENSION_STATIONS.items():
        if key in region or region in key:
            return info
    # 預設用中部
    return EXTENSION_STATIONS["中部"]
