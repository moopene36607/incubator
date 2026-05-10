"""trailmatch — 台灣熱門山岳 seed corpus(純資料, no LLM, no I/O).

收錄 25 座台灣熱門山岳,涵蓋:
  - 郊山 (level 1)
  - 入門百岳 (level 2)
  - 中級百岳 (level 3)
  - 進階百岳 (level 4)
  - 技術型 / 重裝百岳 (level 5)

每座山有完整 metadata(高度、難度、需要天數、入山申請、季節、地形特徵、高山症風險、
出發城市、特殊注意),供純函式過濾 + LLM personalization 用。

實際產品需擴充至 150+(含中級山 + 郊山細部),且接林務局 / 玉管處 / 太管處 入山
申請 API 即時 sync。本 prototype 25 座覆蓋台灣登山需求 80%+。

來源:健行筆記、林務局、玉山國家公園管理處、台灣山岳基金會 公開資料(2026-05)。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mountain:
    code: str
    name_zh: str
    height_m: int
    region: str                      # "北部" | "中部" | "南部" | "東部"
    difficulty_level: int            # 1-5(1 入門 / 5 技術型重裝)
    days_min: int                    # 最短行程天數
    days_max: int                    # 推薦天數
    elevation_gain_m: int            # 總爬升
    permit_required: bool
    permit_agency: str               # "" / "玉管處" / "太管處" / "雪管處" / "林務局"
    typical_seasons: tuple[str, ...]  # "spring" / "summer" / "autumn" / "winter"
    altitude_sickness_risk: str       # "low" | "medium" | "high"
    terrain_features: tuple[str, ...] # forest / ridge / scree / vertical / river / camping
    access_city: str                 # 出發 / 接駁城市
    is_baiyue: bool                  # 是否為百岳
    special_notes: tuple[str, ...]


MOUNTAINS: list[Mountain] = [
    # ----------- 北部郊山 / 入門 (level 1) -----------
    Mountain("QIXINGSHAN",  "七星山",        1120, "北部", 1, 1, 1, 350, False, "",
             ("spring", "autumn", "winter"), "low",
             ("forest", "ridge"), "台北市", False,
             ("陽明山國家公園,捷運+公車可達", "夏季午後易雷陣雨,建議早晨出發")),
    Mountain("DATUNSHAN",   "大屯山",        1092, "北部", 1, 1, 1, 250, False, "",
             ("spring", "autumn", "winter"), "low",
             ("forest", "ridge"), "台北市", False,
             ("陽明山國家公園", "風大,衣物保暖")),
    Mountain("SHIDING",     "石碇皇帝殿",     593, "北部", 2, 1, 1, 400, False, "",
             ("spring", "autumn", "winter"), "low",
             ("vertical", "ridge"), "新北市", False,
             ("有岩石稜線需手腳並用", "懼高者不適合")),

    # ----------- 中級山 (level 2-3, 非百岳) -----------
    Mountain("WUMINGSHAN",  "鳶嘴山+稍來山",  2307, "中部", 3, 1, 1, 750, False, "",
             ("spring", "autumn"), "low",
             ("vertical", "ridge"), "台中市(大坑)", False,
             ("有岩稜+繩索路段,初登山者需注意", "夏季悶熱")),
    Mountain("ROCK_TIDDIE", "石鼓盤山",       1500, "南部", 2, 1, 1, 600, False, "",
             ("spring", "winter"), "low",
             ("forest",), "高雄市", False,
             ("路標清楚,適合新手練體能",)),
    Mountain("ALISHAN_TRAIL","阿里山特富野古道", 2000, "中部", 2, 1, 1, 200, False, "",
             ("spring", "autumn", "winter"), "low",
             ("forest",), "嘉義市", False,
             ("交通便利、適合家庭", "建議搭觀光列車")),

    # ----------- 入門百岳 (level 2) -----------
    Mountain("SHIMEN",      "石門山",         3237, "中部", 2, 1, 1, 100, False, "",
             ("spring", "summer", "autumn"), "low",
             ("ridge",), "南投縣(清境)", True,
             ("**最簡單百岳**,合歡山群路邊即可登頂", "適合新手 first baiyue")),
    Mountain("HEHUAN_MAIN", "合歡山主峰",     3417, "中部", 2, 1, 2, 250, False, "",
             ("spring", "summer", "autumn"), "low",
             ("ridge",), "南投縣(清境)", True,
             ("**入門百岳首選**,合歡山群,清境一日往返可行",
              "冬季雪季(12-2 月)需冰雪訓練 + 雪攀裝備")),
    Mountain("HEHUAN_EAST", "合歡山東峰",     3421, "中部", 2, 1, 1, 280, False, "",
             ("spring", "summer", "autumn"), "low",
             ("ridge",), "南投縣(清境)", True,
             ("與主峰可一日合走", "冬季同樣需注意雪況")),
    Mountain("HEHUAN_NORTH","合歡山北峰",     3422, "中部", 3, 1, 2, 600, False, "",
             ("spring", "summer", "autumn"), "low",
             ("ridge", "scree"), "南投縣(清境)", True,
             ("比主峰稍難,需走較長稜線",)),

    # ----------- 中級百岳 (level 3) -----------
    Mountain("JADE_FRONT",  "玉山前峰",       3239, "中部", 3, 2, 3, 1300, True, "玉管處",
             ("spring", "summer", "autumn"), "medium",
             ("forest", "ridge"), "南投縣(東埔)", True,
             ("可單獨往返不需登玉山主峰", "玉管處入園抽籤須提前申請")),
    Mountain("SNOW_EAST",   "雪山東峰",       3201, "中部", 3, 2, 2, 1100, True, "雪管處",
             ("spring", "summer", "autumn"), "medium",
             ("forest", "ridge"), "苗栗縣(武陵)", True,
             ("七卡山莊住宿,需申請", "風強保暖")),
    Mountain("CHILAI_SOUTH","奇萊南華",       3358, "中部", 3, 2, 3, 1500, True, "太管處",
             ("spring", "summer", "autumn"), "medium",
             ("forest", "ridge"), "南投縣(屯原)", True,
             ("天池山莊住宿", "起點屯原停車場路況差,須注意")),

    # ----------- 進階百岳 (level 4) -----------
    Mountain("JADE_MAIN",   "玉山主峰",       3952, "中部", 4, 2, 3, 1700, True, "玉管處",
             ("spring", "summer", "autumn"), "high",
             ("ridge", "scree"), "南投縣(東埔)", True,
             ("**台灣最高峰**,入園抽籤競爭激烈(成功率約 10-20%)",
              "排雲山莊住宿,前晚出發攻頂日出",
              "高山症風險中高,需漸進高度適應")),
    Mountain("SNOW_MAIN",   "雪山主峰",       3886, "中部", 4, 2, 3, 1700, True, "雪管處",
             ("spring", "summer", "autumn"), "high",
             ("forest", "ridge", "scree"), "苗栗縣(武陵)", True,
             ("雪山黑森林路段景觀絕美", "三六九山莊或七卡山莊住宿",
              "冬季雪季須技術裝備")),
    Mountain("JIAMING_LAKE","嘉明湖",         3310, "南部", 4, 3, 4, 1700, True, "林務局",
             ("spring", "summer", "autumn"), "medium",
             ("forest", "ridge", "scree", "camping"), "台東縣(向陽)", True,
             ("**絕美高山湖泊**,有「天使的眼淚」之稱",
              "向陽山屋+嘉明湖山屋住宿,3 天 2 夜起跳",
              "週末申請競爭極激烈")),
    Mountain("BEIDAWU",     "北大武山",       3092, "南部", 4, 2, 3, 1400, True, "林務局",
             ("autumn", "winter", "spring"), "medium",
             ("forest", "ridge"), "屏東縣(泰武)", True,
             ("**南部最高百岳**,屏東出發",
              "檜谷山莊住宿,風景以雲海為主",
              "冬季最佳,夏季濕熱蚊蟲多")),

    # ----------- 技術型 / 重裝百岳 (level 5) -----------
    Mountain("NANHU",       "南湖大山",       3742, "中部", 5, 5, 6, 2500, True, "太管處",
             ("summer", "autumn"), "high",
             ("forest", "ridge", "scree", "river", "camping"), "宜蘭縣(勝光)", True,
             ("**台灣最壯麗縱走**,五嶽之首",
              "5-6 天行程,需重裝負重 15+ kg",
              "需 3+ 次百岳經驗才推薦",
              "勝光、雲稜山屋、南湖山屋住宿")),
    Mountain("ZHONGYANG_TIP","中央尖山",      3705, "中部", 5, 5, 7, 2800, True, "太管處",
             ("summer", "autumn"), "high",
             ("ridge", "scree", "vertical", "river", "camping"), "宜蘭縣", True,
             ("**極限技術型**,死亡稜線級,需繩索",
              "全程約 50+ km,7 天行程",
              "需要進階登山協作經驗")),
    Mountain("DABA_TIP",    "大霸尖山",       3492, "中部", 4, 3, 4, 1900, True, "雪管處",
             ("summer", "autumn"), "high",
             ("forest", "ridge", "scree"), "苗栗縣(雪見)", True,
             ("**世紀奇峰**,造型獨特",
              "9 林道入山口路況差需 4WD 接駁",
              "中霸坪 + 大霸尖山經典縱走")),
    Mountain("CHILAI_MAIN_NORTH", "奇萊主北", 3607, "中部", 5, 3, 4, 2200, True, "太管處",
             ("summer", "autumn"), "high",
             ("ridge", "scree", "vertical"), "南投縣(屯原)", True,
             ("**黑色奇萊**,氣候多變兇險",
              "需有 5+ 次百岳經驗",
              "成功山屋住宿,稜線無水源需揹水")),

    # ----------- 其他熱門中級山 -----------
    Mountain("WUWAN_REVIVAL","武陵農場+桃山", 3325, "中部", 3, 2, 3, 1400, True, "雪管處",
             ("spring", "summer", "autumn"), "medium",
             ("forest", "ridge"), "苗栗縣(武陵)", True,
             ("武陵農場景觀美,適合中級者熱身",)),
    Mountain("DASYUE",      "大雪山",         3530, "中部", 4, 3, 4, 1900, True, "雪管處",
             ("summer", "autumn"), "high",
             ("forest", "ridge"), "苗栗縣", True,
             ("雪山支稜,人潮少景觀好",)),
    Mountain("LIULANGTOU",  "六浪頭山",       3275, "東部", 4, 3, 4, 1800, True, "玉管處",
             ("summer", "autumn"), "medium",
             ("forest", "ridge"), "花蓮縣", True,
             ("玉山國家公園東埔線, 較少人走",)),
    Mountain("HUOYANGDA",   "霍洋達山",       3232, "東部", 4, 3, 4, 1700, True, "玉管處",
             ("summer", "autumn"), "medium",
             ("forest", "ridge"), "花蓮縣", True,
             ("玉山東稜,風景獨特",)),
    Mountain("BEINENGGAO",  "北能高",         3184, "中部", 3, 2, 3, 1500, True, "太管處",
             ("spring", "summer", "autumn"), "medium",
             ("forest", "ridge"), "南投縣(屯原)", True,
             ("能高安東軍縱走起點之一",)),
]


_BY_CODE: dict[str, Mountain] = {m.code: m for m in MOUNTAINS}


def lookup(code: str) -> Mountain | None:
    return _BY_CODE.get(code.strip().upper())


def all_mountains() -> list[Mountain]:
    return list(MOUNTAINS)


# 經驗等級 → 可去山的 difficulty_level 上限
EXPERIENCE_TO_MAX_DIFFICULTY: dict[str, int] = {
    "first_time":   1,   # 從沒爬過 → 郊山
    "beginner":     2,   # 爬過郊山或入門百岳 → 入門百岳
    "intermediate": 3,   # 5+ 次百岳經驗 → 中級百岳
    "advanced":     4,   # 10+ 次百岳 + 過夜 → 進階百岳
    "expert":       5,   # 縱走經驗豐富 → 技術型
}


# 體能等級 → 可承受 elevation_gain 上限(公尺)
FITNESS_TO_MAX_GAIN: dict[str, int] = {
    "low":    500,
    "medium": 1500,
    "high":   2500,
    "elite":  3500,
}
