"""fitlog — 健身訓練動作分類 seed dictionary (純資料,no I/O, no LLM).

收錄台灣健身教練最常處方的 160+ 個動作,分為:
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

    # ===== v2 擴充 (機械式 / 街健 / 瑜珈) =====

    # ---------- legs (+6) ----------
    Exercise("HACK_SQUAT", "Hack 蹲", "Hack Squat", "legs", "股四頭/臀大肌", "rep", (6, 8)),
    Exercise("LEG_EXTENSION", "腿伸機", "Leg Extension", "legs", "股四頭", "rep", (5, 8)),
    Exercise("LEG_CURL", "腿彎舉機", "Leg Curl", "legs", "股二頭", "rep", (5, 8)),
    Exercise("HIP_THRUST", "臀推", "Hip Thrust", "legs", "臀大肌/股二頭", "rep", (6, 9)),
    Exercise("CALF_RAISE", "小腿提踵", "Calf Raise", "legs", "腓腸肌/比目魚肌", "rep", (5, 8)),
    Exercise("GOBLET_SQUAT", "高腳杯深蹲", "Goblet Squat", "legs", "股四頭/臀大肌/核心", "rep", (5, 7)),

    # ---------- pull (+5) ----------
    Exercise("T_BAR_ROW", "T-bar 划船", "T-bar Row", "pull", "中背/背闊肌", "rep", (6, 9)),
    Exercise("CABLE_ROW", "坐姿划船機", "Seated Cable Row", "pull", "中背/背闊肌", "rep", (5, 8)),
    Exercise("CHIN_UP", "反握引體向上", "Chin-up", "pull", "背闊肌/二頭", "rep", (7, 10)),
    Exercise("INVERTED_ROW", "反式划船", "Inverted Row", "pull", "中背/後三角", "rep", (5, 8)),
    Exercise("KETTLEBELL_SWING", "壺鈴擺盪", "Kettlebell Swing", "pull", "臀大肌/下背/全身爆發", "rep", (6, 9)),

    # ---------- push (+5) ----------
    Exercise("INCLINE_DB_PRESS", "上斜啞鈴推", "Incline Dumbbell Press", "push", "上胸/前三角", "rep", (5, 8)),
    Exercise("DECLINE_PRESS", "下斜推", "Decline Press", "push", "下胸/三頭", "rep", (5, 8)),
    Exercise("LATERAL_RAISE", "啞鈴側平舉", "Lateral Raise", "push", "三角肌側束", "rep", (4, 7)),
    Exercise("CABLE_FLY", "滑輪夾胸", "Cable Fly", "push", "胸大肌", "rep", (5, 8)),
    Exercise("MACHINE_CHEST_PRESS", "蝴蝶機臥推", "Machine Chest Press", "push", "胸大肌/三頭", "rep", (5, 8)),

    # ---------- core (+4) ----------
    Exercise("AB_WHEEL", "健腹輪", "Ab Wheel Rollout", "core", "腹直肌/核心穩定", "rep", (6, 9)),
    Exercise("HANGING_KNEE_RAISE", "懸吊屈膝", "Hanging Knee Raise", "core", "腹直肌下段", "rep", (5, 8)),
    Exercise("V_UP", "V 字仰臥", "V-up", "core", "腹直肌全段", "rep", (5, 8)),
    Exercise("CABLE_WOODCHOP", "滑輪斜砍", "Cable Woodchop", "core", "腹斜肌/核心抗旋轉", "rep", (4, 7)),

    # ---------- cardio (+3) ----------
    Exercise("STAIR_CLIMBER", "階梯機", "Stair Climber", "cardio", "下肢/心肺", "min", (5, 8)),
    Exercise("BURPEE", "波比跳", "Burpee", "cardio", "全身/心肺", "rep", (7, 10)),
    Exercise("BATTLE_ROPE", "戰繩", "Battle Rope", "cardio", "上肢/心肺", "sec", (6, 9)),

    # ---------- mobility (+3) ----------
    Exercise("CAT_COW", "貓牛式", "Cat-Cow Stretch", "mobility", "脊椎活動度", "rep", (1, 3)),
    Exercise("COSSACK_SQUAT", "哥薩克深蹲", "Cossack Squat", "mobility", "髖內收/活動度", "rep", (2, 4)),
    Exercise("CHILD_POSE", "嬰兒式", "Child Pose", "mobility", "下背/髖部放鬆", "sec", (1, 2)),

    # ===== v3 擴充 (自由重量進階 / 機械 / 街健 / 瑜珈) =====

    # ---------- legs (+5) ----------
    Exercise("FRONT_SQUAT", "前蹲舉", "Front Squat", "legs", "股四頭/上背/核心", "rep", (6, 9)),
    Exercise("SUMO_DEADLIFT", "相撲硬舉", "Sumo Deadlift", "legs", "臀大肌/內收肌/下背", "rep", (7, 9)),
    Exercise("STEP_UP", "登階", "Step-up", "legs", "股四頭/臀大肌", "rep", (5, 8)),
    Exercise("GLUTE_BRIDGE", "臀橋", "Glute Bridge", "legs", "臀大肌/股二頭", "rep", (4, 7)),
    Exercise("NORDIC_CURL", "北歐腿彎舉", "Nordic Hamstring Curl", "legs", "股二頭", "rep", (7, 10)),

    # ---------- pull (+3) ----------
    Exercise("PENDLAY_ROW", "Pendlay 划船", "Pendlay Row", "pull", "中背/背闊肌/後三角", "rep", (6, 9)),
    Exercise("STRAIGHT_ARM_PULLDOWN", "直臂下拉", "Straight-arm Pulldown", "pull", "背闊肌", "rep", (4, 7)),
    Exercise("HIGH_PULL", "高拉", "High Pull", "pull", "斜方肌/後三角/全身爆發", "rep", (6, 9)),

    # ---------- push (+4) ----------
    Exercise("ARNOLD_PRESS", "阿諾肩推", "Arnold Press", "push", "三角肌/三頭", "rep", (5, 8)),
    Exercise("TRICEP_PUSHDOWN", "三頭下壓", "Tricep Pushdown", "push", "三頭", "rep", (4, 7)),
    Exercise("CLOSE_GRIP_BENCH", "窄握臥推", "Close-grip Bench Press", "push", "三頭/胸大肌", "rep", (6, 9)),
    Exercise("LANDMINE_PRESS", "Landmine 推", "Landmine Press", "push", "前三角/上胸/核心", "rep", (5, 8)),

    # ---------- core (+2) ----------
    Exercise("RUSSIAN_TWIST", "俄羅斯轉體", "Russian Twist", "core", "腹斜肌/核心旋轉", "rep", (4, 7)),
    Exercise("BIRD_DOG", "鳥狗式", "Bird Dog", "core", "核心穩定/下背", "rep", (2, 5)),

    # ---------- cardio (+2) ----------
    Exercise("SPRINT_INTERVAL", "衝刺間歇", "Sprint Interval", "cardio", "下肢/心肺", "sec", (8, 10)),
    Exercise("SKI_ERG", "滑雪機", "Ski Erg", "cardio", "上肢/核心/心肺", "m", (6, 9)),

    # ---------- mobility (+2) ----------
    Exercise("COUCH_STRETCH", "沙發伸展", "Couch Stretch", "mobility", "髖屈肌/股四頭", "sec", (1, 3)),
    Exercise("DOWNWARD_DOG", "下犬式", "Downward Dog", "mobility", "後鏈/肩部活動度", "sec", (1, 3)),

    # ===== v4 擴充 (孤立動作 / 機械 / 進階) =====

    # ---------- legs (+4) ----------
    Exercise("GOOD_MORNING", "早安式", "Good Morning", "legs", "股二頭/下背/臀大肌", "rep", (6, 8)),
    Exercise("REVERSE_LUNGE", "後弓步蹲", "Reverse Lunge", "legs", "股四頭/臀大肌", "rep", (5, 8)),
    Exercise("BOX_SQUAT", "箱上蹲", "Box Squat", "legs", "股四頭/臀大肌/下背", "rep", (6, 8)),
    Exercise("SINGLE_LEG_RDL", "單腿羅馬尼亞硬舉", "Single-leg RDL", "legs", "股二頭/臀中肌/平衡", "rep", (5, 8)),

    # ---------- pull (+4) ----------
    Exercise("SHRUG", "聳肩", "Barbell Shrug", "pull", "上斜方肌", "rep", (5, 8)),
    Exercise("BICEP_CURL", "二頭彎舉", "Bicep Curl", "pull", "肱二頭肌", "rep", (5, 8)),
    Exercise("HAMMER_CURL", "錘式彎舉", "Hammer Curl", "pull", "肱二頭肌/肱橈肌", "rep", (5, 8)),
    Exercise("RACK_PULL", "架上拉", "Rack Pull", "pull", "下背/臀大肌/斜方肌", "rep", (6, 9)),

    # ---------- push (+4) ----------
    Exercise("PUSH_PRESS", "借力推舉", "Push Press", "push", "三角肌/三頭/下肢爆發", "rep", (6, 9)),
    Exercise("SKULL_CRUSHER", "碎顱者", "Skull Crusher", "push", "肱三頭肌", "rep", (5, 8)),
    Exercise("PEC_DECK", "蝴蝶機夾胸", "Pec Deck", "push", "胸大肌", "rep", (5, 8)),
    Exercise("MACHINE_SHOULDER_PRESS", "機械肩推", "Machine Shoulder Press", "push", "三角肌/三頭", "rep", (5, 8)),

    # ---------- core (+2) ----------
    Exercise("REVERSE_CRUNCH", "反向捲腹", "Reverse Crunch", "core", "腹直肌下段", "rep", (4, 7)),
    Exercise("MOUNTAIN_CLIMBER", "登山者", "Mountain Climber", "core", "核心/髖屈肌/心肺", "rep", (5, 8)),

    # ---------- cardio (+2) ----------
    Exercise("ELLIPTICAL", "橢圓機", "Elliptical Trainer", "cardio", "全身/心肺", "min", (4, 7)),
    Exercise("SHADOW_BOXING", "空擊", "Shadow Boxing", "cardio", "上肢/核心/心肺", "min", (5, 8)),

    # ---------- mobility (+2) ----------
    Exercise("PIGEON_POSE", "鴿式", "Pigeon Pose", "mobility", "臀部/髖外旋", "sec", (1, 3)),
    Exercise("WALL_SLIDE", "靠牆滑臂", "Wall Slide", "mobility", "肩胛/胸椎活動度", "rep", (1, 3)),

    # ===== v5 擴充 (進階自由重量 / 機械 / 體操) =====

    # ---------- legs (+3) ----------
    Exercise("BELT_SQUAT", "腰帶深蹲", "Belt Squat", "legs", "股四頭/臀大肌", "rep", (6, 8)),
    Exercise("PISTOL_SQUAT", "單腿蹲", "Pistol Squat", "legs", "股四頭/臀大肌/平衡", "rep", (7, 9)),
    Exercise("JUMP_SQUAT", "跳躍深蹲", "Jump Squat", "legs", "股四頭/臀大肌/爆發力", "rep", (6, 9)),

    # ---------- pull (+3) ----------
    Exercise("SEAL_ROW", "海豹划船", "Seal Row", "pull", "中背/背闊肌", "rep", (5, 8)),
    Exercise("CABLE_CURL", "滑輪二頭彎舉", "Cable Curl", "pull", "肱二頭肌", "rep", (5, 8)),
    Exercise("MUSCLE_UP", "暴力上槓", "Muscle-up", "pull", "背闊肌/胸/三頭/全身", "rep", (8, 10)),

    # ---------- push (+3) ----------
    Exercise("FLOOR_PRESS", "地板臥推", "Floor Press", "push", "胸大肌/三頭", "rep", (6, 9)),
    Exercise("DIAMOND_PUSHUP", "鑽石伏地挺身", "Diamond Push-up", "push", "三頭/胸大肌", "rep", (5, 8)),
    Exercise("OVERHEAD_TRICEP_EXT", "過頭三頭伸展", "Overhead Tricep Extension", "push", "肱三頭肌", "rep", (5, 8)),

    # ---------- core (+3) ----------
    Exercise("HOLLOW_HOLD", "懸體", "Hollow Hold", "core", "核心/腹直肌", "sec", (5, 8)),
    Exercise("CABLE_CRUNCH", "滑輪捲腹", "Cable Crunch", "core", "腹直肌", "rep", (5, 8)),
    Exercise("DRAGON_FLAG", "龍旗", "Dragon Flag", "core", "核心/腹直肌全段", "rep", (8, 10)),

    # ---------- cardio (+3) ----------
    Exercise("VERSACLIMBER", "垂直攀爬機", "VersaClimber", "cardio", "全身/心肺", "min", (6, 9)),
    Exercise("INCLINE_WALK", "坡度健走", "Incline Walk", "cardio", "下肢/心肺", "min", (3, 6)),
    Exercise("JACOBS_LADDER", "雅各天梯", "Jacobs Ladder", "cardio", "全身/心肺", "min", (6, 9)),

    # ---------- mobility (+3) ----------
    Exercise("BAND_PULL_APART", "彈力帶分開", "Band Pull-apart", "mobility", "後三角/旋轉肌群", "rep", (1, 3)),
    Exercise("JEFFERSON_CURL", "傑佛森捲體", "Jefferson Curl", "mobility", "脊椎逐節活動度/後鏈", "rep", (2, 4)),
    Exercise("FOAM_ROLL", "滾筒放鬆", "Foam Rolling", "mobility", "筋膜放鬆", "sec", (1, 2)),

    # ===== v6 擴充 (進階變化 / 機械 / 負重行走) =====

    # ---------- legs (+3) ----------
    Exercise("ZERCHER_SQUAT", "Zercher 深蹲", "Zercher Squat", "legs", "股四頭/上背/核心", "rep", (6, 9)),
    Exercise("SEATED_CALF_RAISE", "坐姿提踵", "Seated Calf Raise", "legs", "比目魚肌", "rep", (5, 8)),
    Exercise("TERMINAL_KNEE_EXT", "末端伸膝", "Terminal Knee Extension", "legs", "股內側肌/膝穩定", "rep", (3, 6)),

    # ---------- pull (+3) ----------
    Exercise("CHEST_SUPPORTED_ROW", "胸靠划船", "Chest-supported Row", "pull", "中背/背闊肌/後三角", "rep", (5, 8)),
    Exercise("PREACHER_CURL", "牧師椅彎舉", "Preacher Curl", "pull", "肱二頭肌", "rep", (5, 8)),
    Exercise("REVERSE_FLY", "反向飛鳥", "Reverse Fly", "pull", "後三角/中斜方肌", "rep", (4, 7)),

    # ---------- push (+3) ----------
    Exercise("CABLE_CROSSOVER", "滑輪交叉", "Cable Crossover", "push", "胸大肌", "rep", (5, 8)),
    Exercise("BENCH_DIP", "椅上撐體", "Bench Dip", "push", "三頭/前三角", "rep", (5, 8)),
    Exercise("HANDSTAND_PUSHUP", "倒立伏地挺身", "Handstand Push-up", "push", "三角肌/三頭/全身", "rep", (8, 10)),

    # ---------- core (+3) ----------
    Exercise("SUITCASE_CARRY", "單邊行李走路", "Suitcase Carry", "core", "腹斜肌/核心抗側屈", "m", (5, 8)),
    Exercise("COPENHAGEN_PLANK", "哥本哈根側棒", "Copenhagen Plank", "core", "內收肌/核心", "sec", (6, 9)),
    Exercise("JACKKNIFE", "折刀", "Jackknife Sit-up", "core", "腹直肌全段", "rep", (5, 8)),

    # ---------- cardio (+3) ----------
    Exercise("SLED_PUSH", "雪橇推", "Sled Push", "cardio", "下肢/全身/心肺", "m", (7, 10)),
    Exercise("FARMERS_WALK", "農夫走路", "Farmer's Walk", "cardio", "握力/斜方肌/全身/心肺", "m", (6, 9)),
    Exercise("HILL_SPRINT", "坡道衝刺", "Hill Sprint", "cardio", "下肢/心肺", "sec", (8, 10)),

    # ---------- mobility (+3) ----------
    Exercise("THREAD_THE_NEEDLE", "穿針式", "Thread the Needle", "mobility", "胸椎旋轉活動度", "rep", (1, 3)),
    Exercise("FROG_STRETCH", "青蛙式伸展", "Frog Stretch", "mobility", "髖內收/髖活動度", "sec", (1, 3)),
    Exercise("HAMSTRING_STRETCH", "腿後肌伸展", "Hamstring Stretch", "mobility", "股二頭柔軟度", "sec", (1, 2)),

    # ===== v7 擴充 (專項變化 / 功能性 / 體操) =====

    # ---------- legs (+3) ----------
    Exercise("SAFETY_BAR_SQUAT", "安全槓深蹲", "Safety Bar Squat", "legs", "股四頭/臀大肌/上背", "rep", (6, 9)),
    Exercise("SPANISH_SQUAT", "西班牙蹲", "Spanish Squat", "legs", "股四頭/膝穩定", "rep", (5, 8)),
    Exercise("KICKSTAND_RDL", "支撐腳羅馬尼亞硬舉", "Kickstand RDL", "legs", "股二頭/臀大肌", "rep", (5, 8)),

    # ---------- pull (+3) ----------
    Exercise("KROC_ROW", "Kroc 划船", "Kroc Row", "pull", "背闊肌/中背/握力", "rep", (7, 10)),
    Exercise("INCLINE_CURL", "上斜二頭彎舉", "Incline Curl", "pull", "肱二頭肌長頭", "rep", (5, 8)),
    Exercise("DRAG_CURL", "拖曳彎舉", "Drag Curl", "pull", "肱二頭肌", "rep", (5, 8)),

    # ---------- push (+3) ----------
    Exercise("LARSEN_PRESS", "Larsen 臥推", "Larsen Press", "push", "胸大肌/三頭", "rep", (6, 9)),
    Exercise("BRADFORD_PRESS", "Bradford 推舉", "Bradford Press", "push", "三角肌", "rep", (5, 8)),
    Exercise("ARCHER_PUSHUP", "弓箭手伏地挺身", "Archer Push-up", "push", "胸大肌/三頭", "rep", (6, 9)),

    # ---------- core (+3) ----------
    Exercise("BICYCLE_CRUNCH", "腳踏車捲腹", "Bicycle Crunch", "core", "腹直肌/腹斜肌", "rep", (4, 7)),
    Exercise("V_SIT", "V 字坐姿", "V-sit Hold", "core", "核心/腹直肌", "sec", (5, 8)),
    Exercise("GHD_SITUP", "GHD 仰臥起坐", "GHD Sit-up", "core", "腹直肌全段/髖屈肌", "rep", (6, 9)),

    # ---------- cardio (+3) ----------
    Exercise("DEADBALL_SLAM", "藥球砸地", "Deadball Slam", "cardio", "全身/核心/心肺", "rep", (6, 9)),
    Exercise("TYRE_FLIP", "翻輪胎", "Tyre Flip", "cardio", "全身/爆發/心肺", "rep", (7, 10)),
    Exercise("PROWLER_DRAG", "雪橇拖行", "Prowler Drag", "cardio", "下肢/全身/心肺", "m", (7, 10)),

    # ---------- mobility (+3) ----------
    Exercise("DEAD_HANG", "死握懸吊", "Dead Hang", "mobility", "肩關節減壓/握力", "sec", (2, 5)),
    Exercise("ARM_CIRCLES", "繞臂", "Arm Circles", "mobility", "肩關節活動度", "rep", (1, 2)),
    Exercise("SCAPULAR_PULLUP", "肩胛引體", "Scapular Pull-up", "mobility", "肩胛控制/下斜方肌", "rep", (2, 5)),

    # ===== v8 擴充 (孤立 / 機械 / 增強式) =====

    # ---------- legs (+3) ----------
    Exercise("SISSY_SQUAT", "西西深蹲", "Sissy Squat", "legs", "股四頭", "rep", (6, 9)),
    Exercise("ATG_SPLIT_SQUAT", "ATG 分腿蹲", "ATG Split Squat", "legs", "股四頭/膝關節活動度", "rep", (5, 8)),
    Exercise("BOX_JUMP", "跳箱", "Box Jump", "legs", "股四頭/臀大肌/爆發力", "rep", (6, 9)),

    # ---------- pull (+3) ----------
    Exercise("GORILLA_ROW", "大猩猩划船", "Gorilla Row", "pull", "背闊肌/中背/核心", "rep", (6, 9)),
    Exercise("ZOTTMAN_CURL", "Zottman 彎舉", "Zottman Curl", "pull", "肱二頭肌/肱橈肌/前臂", "rep", (5, 8)),
    Exercise("CABLE_PULLOVER", "滑輪上拉", "Cable Pullover", "pull", "背闊肌/前鋸肌", "rep", (4, 7)),

    # ---------- push (+3) ----------
    Exercise("JM_PRESS", "JM 臥推", "JM Press", "push", "肱三頭肌/胸大肌", "rep", (6, 9)),
    Exercise("PIKE_PUSHUP", "屈體伏地挺身", "Pike Push-up", "push", "三角肌/三頭", "rep", (6, 9)),
    Exercise("SVEND_PRESS", "Svend 夾推", "Svend Press", "push", "胸大肌內側", "rep", (4, 7)),

    # ---------- core (+3) ----------
    Exercise("WINDSHIELD_WIPER", "雨刷", "Windshield Wiper", "core", "腹斜肌/核心旋轉", "rep", (7, 10)),
    Exercise("FLUTTER_KICK", "交替擺腿", "Flutter Kick", "core", "腹直肌下段/髖屈肌", "sec", (4, 7)),
    Exercise("L_SIT", "L 字支撐", "L-sit", "core", "核心/髖屈肌/三頭", "sec", (7, 10)),

    # ---------- cardio (+3) ----------
    Exercise("ROWING_SPRINT", "划船機衝刺", "Rowing Sprint", "cardio", "全身/心肺", "sec", (8, 10)),
    Exercise("AIRDYNE_SPRINT", "風扇車衝刺", "Airdyne Sprint", "cardio", "全身/心肺", "sec", (8, 10)),
    Exercise("STAIR_RUN", "跑樓梯", "Stair Run", "cardio", "下肢/心肺", "min", (6, 9)),

    # ---------- mobility (+3) ----------
    Exercise("SCORPION_STRETCH", "天蠍式伸展", "Scorpion Stretch", "mobility", "脊椎旋轉/髖屈肌", "rep", (1, 3)),
    Exercise("ANKLE_ROCK", "踝關節前後搖", "Ankle Rock", "mobility", "踝背屈活動度", "rep", (1, 3)),
    Exercise("NECK_CARS", "頸部繞環", "Neck CARs", "mobility", "頸椎活動度", "rep", (1, 2)),
]


_BY_CODE: dict[str, Exercise] = {e.code: e for e in EXERCISES}


def normalize_code(code: str) -> str:
    """正規化動作代碼:去空白、轉大寫、連字號視同底線。"""
    return code.strip().upper().replace("-", "_")


def lookup(code: str) -> Exercise | None:
    return _BY_CODE.get(normalize_code(code))


def all_exercises() -> list[Exercise]:
    return list(EXERCISES)


def by_category(category: str) -> list[Exercise]:
    return [e for e in EXERCISES if e.category == category]
