"""長照支付制度 (LTCIS) 居家服務代碼對照表 — prototype seed.

實際 LTCIS 涵蓋約 100+ 服務代碼。本 prototype 僅收錄居家服務(BA / DA / GA
系列)中最常出現的 12 個,足以涵蓋 80%+ 的日常照服紀錄場景。

來源: 衛福部長照支付制度公告 113 年版本(本資料於 2026-05 仍適用,實際申報前
請以衛福部最新公告為準)。

代碼欄位:
  code: 服務項目代碼
  name: 服務名稱
  category: 大分類 (身體照顧 / 家事服務 / 陪伴服務 / 健康監測 / 異常通報)
  unit: 計價單位
  example_keywords: 自動推斷時用的關鍵字提示(LLM 用)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceCode:
    code: str
    name: str
    category: str
    unit: str
    example_keywords: tuple[str, ...]


SERVICE_CODES: list[ServiceCode] = [
    ServiceCode("BA01", "基本身體清潔", "身體照顧", "次", ("洗澡", "擦澡", "沐浴", "盥洗", "刷牙")),
    ServiceCode("BA02", "陪同就醫", "家事服務", "次", ("看醫生", "回診", "就醫", "陪同就診", "醫院")),
    ServiceCode("BA03", "代購用品", "家事服務", "次", ("買菜", "買藥", "代購", "採買", "拿藥")),
    ServiceCode("BA04", "協助沐浴(臥床)", "身體照顧", "次", ("臥床", "沐浴", "床上洗澡", "床浴")),
    ServiceCode("BA05", "備餐 / 協助進食", "身體照顧", "次", ("備餐", "煮飯", "做飯", "餵食", "進食", "用餐")),
    ServiceCode("BA09", "陪伴活動", "陪伴服務", "小時", ("陪伴", "聊天", "散步", "陪同", "活動")),
    ServiceCode("BA10", "翻身擺位 / 移位", "身體照顧", "次", ("翻身", "擺位", "移位", "起身", "下床", "上床")),
    ServiceCode("BA13", "如廁協助 / 換尿布", "身體照顧", "次", ("換尿布", "如廁", "上廁所", "便盆", "尿管")),
    ServiceCode("DA01", "簡易被動運動", "身體照顧", "次", ("被動運動", "關節活動", "復健動作", "拉筋")),
    ServiceCode("DA02", "拍背 / 拍痰", "身體照顧", "次", ("拍背", "拍痰", "排痰", "咳嗽")),
    ServiceCode("GA01", "生命徵象監測", "健康監測", "次", ("血壓", "心跳", "體溫", "血糖", "脈搏", "監測")),
    ServiceCode("GA09", "異常事件通報", "異常通報", "次", ("跌倒", "受傷", "出血", "呼吸困難", "意識", "通報", "急救")),
]


_BY_CODE: dict[str, ServiceCode] = {s.code: s for s in SERVICE_CODES}


def lookup_by_code(code: str) -> ServiceCode | None:
    return _BY_CODE.get(code.strip().upper())


def all_codes_table() -> list[ServiceCode]:
    return list(SERVICE_CODES)
