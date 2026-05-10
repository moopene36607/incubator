"""fitlog — 健身訓練動作分類 seed dictionary (純資料,no I/O, no LLM).

收錄台灣健身教練最常處方的 ~30 個動作,分為:
  push (推系) / pull (拉系) / legs (腿系) /
  core (核心) / cardio (有氧) / mobility (活動度)

每個動作附:中文名、英文名、目標肌群(中文)、計量單位、典型 RPE 範圍。
給 LLM grounding 用,確保 AI 寫報告時用台灣健身圈通用詞,不會把 squat 寫成「蹲坐」。

實際產品需擴展至 200+ 動作,涵蓋 powerlifting / 街健 / 機械式 / 瑜珈 / 舞蹈
等不同模組。本 prototype 30 個涵蓋 80%+ 一般 1 對 1 PT 課程。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Exercise:
    code: str
    chinese: str
    english: str
    category: str       # "push" | "pull" | "legs" | "core" | "cardio" | "mobility"
    target_muscles: str # 主要肌群中文
    measure_unit: str   # "rep" | "sec" | "min" | "m"
    typical_rpe_range: tuple[int, int]


EXERCISES: list[Exercise] = [
    # ---------- legs ----------
    Exercise("BB_BACK_SQUAT", "槓鈴背蹲舉", "Barbell Back Squat", "legs", "股四頭/臀大肌/下背", "rep", (6, 9)),
    Exercise("DUMBBELL_LUNGE", "啞鈴弓步蹲", "Dumbbell Lunge", "legs", "股四頭/臀大肌/股二頭", "rep", (5, 8)),
    Exercise("ROMANIAN_DL", "羅馬尼亞硬舉", "Romanian Deadlift", "legs", "股二頭/臀大肌/下背", "rep", (6, 9)),
    Exercise("LEG_PRESS", "腿推機", "Leg Press", "legs", "股四頭/臀大肌", "rep", (6, 8)),
    Exercise("BULGARIAN_SPLIT", "保加利亞分腿蹲", "Bulgarian Split Squat", "legs", "股四頭/臀中肌", "rep", (6, 9)),

    # ---------- pull ----------
    Exercise("DEADLIFT", "傳統硬舉", "Conventional Deadlift", "pull", "下背/臀大肌/股二頭", "rep", (7, 9)),
    Exercise("PULL_UP", "引體向上", "Pull-up", "pull", "背闊肌/二頭", "rep", (7, 10)),
    Exercise("LAT_PULLDOWN", "滑輪下拉", "Lat Pulldown", "pull", "背闊肌/中斜方肌", "rep", (5, 8)),
    Exercise("BB_ROW", "槓鈴划船", "Barbell Row", "pull", "中背/後三角", "rep", (6, 8)),
    Exercise("DUMBBELL_ROW", "單臂啞鈴划船", "Single-arm Dumbbell Row", "pull", "背闊肌/中背", "rep", (5, 8)),
    Exercise("FACE_PULL", "面拉", "Face Pull", "pull", "後三角/旋轉肌群", "rep", (3, 6)),

    # ---------- push ----------
    Exercise("BENCH_PRESS", "槓鈴臥推", "Barbell Bench Press", "push", "胸大肌/前三角/三頭", "rep", (6, 9)),
    Exercise("DB_BENCH", "啞鈴臥推", "Dumbbell Bench Press", "push", "胸大肌/前三角/三頭", "rep", (5, 8)),
    Exercise("INCLINE_PRESS", "上斜推", "Incline Press", "push", "上胸/前三角", "rep", (5, 8)),
    Exercise("OHP", "肩推", "Overhead Press", "push", "三角肌/上胸/三頭", "rep", (6, 8)),
    Exercise("DB_SHOULDER_PRESS", "啞鈴肩推", "Dumbbell Shoulder Press", "push", "三角肌/三頭", "rep", (5, 8)),
    Exercise("DIPS", "雙槓臂屈伸", "Dips", "push", "胸大肌/三頭/前三角", "rep", (6, 9)),
    Exercise("PUSHUP", "伏地挺身", "Push-up", "push", "胸大肌/三頭", "rep", (4, 8)),

    # ---------- core ----------
    Exercise("PLANK", "棒式", "Plank", "core", "核心/腹橫肌", "sec", (4, 7)),
    Exercise("DEAD_BUG", "死蟲式", "Dead Bug", "core", "核心控制", "rep", (3, 6)),
    Exercise("PALLOF_PRESS", "Pallof Press", "Pallof Press", "core", "核心抗旋轉", "rep", (4, 7)),
    Exercise("HANGING_LEG_RAISE", "懸吊舉腿", "Hanging Leg Raise", "core", "腹直肌下段", "rep", (6, 9)),
    Exercise("SIDE_PLANK", "側棒式", "Side Plank", "core", "腹斜肌", "sec", (4, 7)),

    # ---------- cardio ----------
    Exercise("RUN_TREADMILL", "跑步機", "Treadmill Run", "cardio", "心肺", "min", (5, 8)),
    Exercise("ROW_ERG", "划船機", "Rowing Erg", "cardio", "全身/心肺", "m", (6, 9)),
    Exercise("ASSAULT_BIKE", "Assault Bike", "Assault Bike", "cardio", "全身/心肺", "min", (7, 10)),
    Exercise("JUMP_ROPE", "跳繩", "Jump Rope", "cardio", "心肺/小腿", "min", (5, 8)),

    # ---------- mobility / warmup ----------
    Exercise("HIP_OPENER", "髖部活動", "90/90 Hip Opener", "mobility", "髖關節活動度", "rep", (1, 3)),
    Exercise("THORACIC_ROT", "胸椎旋轉", "Thoracic Rotation", "mobility", "胸椎活動度", "rep", (1, 3)),
    Exercise("WORLDS_GREATEST", "世界最強拉伸", "World's Greatest Stretch", "mobility", "全身動態", "rep", (1, 3)),
]


_BY_CODE: dict[str, Exercise] = {e.code: e for e in EXERCISES}


def lookup(code: str) -> Exercise | None:
    return _BY_CODE.get(code.strip().upper())


def all_exercises() -> list[Exercise]:
    return list(EXERCISES)


def by_category(category: str) -> list[Exercise]:
    return [e for e in EXERCISES if e.category == category]
