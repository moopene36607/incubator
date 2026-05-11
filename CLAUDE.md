# Incubator — AI 新創原型索引

本 repo 是一個自動孵化器。排程的 `/loop` 任務每 20 分鐘觸發一次，
要求模型執行：

1. 掃描既有原型（本索引 + 資料夾清單）以避免重複
2. 研究一個利基型 AI 新創點子 — **亞洲市場優先**
   （台灣 / 日本 / 韓國 / 東南亞 / 中港）；只有在亞洲找不到對應題目、
   且該題目特別強時，才退而求其次選 US/EU
3. 挑出勝率最高、且競爭缺口有證據支撐的題目
4. 在新資料夾中建出一個可運作的原型
5. Commit + push 到 `origin/main`（每一輪一個 commit）

每個原型都有相同結構：
- `README.md` — 痛點、競爭分析、定價、通路、風險
- 單檔 CLI（Python、Anthropic SDK、prompt caching）
- `samples/` — 擬真的合成輸入
- `examples/` — 預生成輸出（讓 demo 不需 API key 也能跑）
- `requirements.txt`

---

## 輪次索引

每一輪的詳細資料（痛點、競爭缺口、架構模式、市場規模、通路）
放在 [`rounds/`](rounds/) — 每輪一個檔案。挑下一個點子時，
請掃描 AI 模式欄位，避免重複既有手法。

| # | Slug | 地區 | AI 模式 | 詳細 |
|---|------|-----|-----------|--------|
| 1 | `scopescribe/` | US 🇺🇸 | doc-gen | [round_01_scopescribe.md](rounds/round_01_scopescribe.md) |
| 2 | `laobao/` | Taiwan 🇹🇼 | doc-gen | [round_02_laobao.md](rounds/round_02_laobao.md) |
| 3 | `kosmelingo/` | Korea → Japan 🇰🇷→🇯🇵 | doc-gen | [round_03_kosmelingo.md](rounds/round_03_kosmelingo.md) |
| 4 | `mitsumori/` | Japan 🇯🇵 | doc-gen | [round_04_mitsumori.md](rounds/round_04_mitsumori.md) |
| 5 | `settlekit/` | Korea 🇰🇷 | doc-gen | [round_05_settlekit.md](rounds/round_05_settlekit.md) |
| 6 | `hoadon/` | Vietnam 🇻🇳 | doc-gen | [round_06_hoadon.md](rounds/round_06_hoadon.md) |
| 7 | `_nice/carepen/` ⭐ | Taiwan 🇹🇼 | doc-gen | [round_07_carepen.md](rounds/round_07_carepen.md) |
| 8 | `sudoc/` | Taiwan 🇹🇼 | doc-gen | [round_08_sudoc.md](rounds/round_08_sudoc.md) |
| 9 | `_nice/vetnote/` ⭐ | Taiwan 🇹🇼 | doc-gen | [round_09_vetnote.md](rounds/round_09_vetnote.md) |
| 10 | `_nice/monthrep/` ⭐ | Taiwan 🇹🇼 | doc-gen | [round_10_monthrep.md](rounds/round_10_monthrep.md) |
| 11 | `_nice/fitlog/` ⭐ | Taiwan 🇹🇼 | doc-gen | [round_11_fitlog.md](rounds/round_11_fitlog.md) |
| 12 | `motoval/` | Taiwan 🇹🇼 | 垂直定價模型 + NLP 解析 | [round_12_motoval.md](rounds/round_12_motoval.md) |
| 13 | `snaporder/` | Taiwan 🇹🇼 | NLP / OCR 多訊息彙整 | [round_13_snaporder.md](rounds/round_13_snaporder.md) |
| 14 | `_nice/subsidybot/` ⭐ | Taiwan 🇹🇼 | RAG 在地知識語料 | [round_14_subsidybot.md](rounds/round_14_subsidybot.md) |
| 15 | `shiftsync/` | Taiwan 🇹🇼 | 排班 + LINE Bot 對話式 | [round_15_shiftsync.md](rounds/round_15_shiftsync.md) |
| 16 | `weddingmatch/` | Taiwan 🇹🇼 | Embedding 相似度配對 | [round_16_weddingmatch.md](rounds/round_16_weddingmatch.md) |
| 17 | `_nice/tenderwatch/` ⭐ | Taiwan 🇹🇼 | 即時監控 + LLM 語意匹配評分 | [round_17_tenderwatch.md](rounds/round_17_tenderwatch.md) |
| 18 | `salonguard/` | Taiwan 🇹🇼 | 客戶事件流失預測 / 異常偵測 | [round_18_salonguard.md](rounds/round_18_salonguard.md) |
| 19 | `propvision/` | Taiwan 🇹🇼 | 垂直定價 + 視覺辨識組合 | [round_19_propvision.md](rounds/round_19_propvision.md) |
| 20 | `_nice/cropscan/` ⭐ | Taiwan 🇹🇼 | 純視覺分類 | [round_20_cropscan.md](rounds/round_20_cropscan.md) |
| 21 | `trailmatch/` | Taiwan 🇹🇼 | 行為個人化 | [round_21_trailmatch.md](rounds/round_21_trailmatch.md) |
| 22 | `wattmon/` | Taiwan 🇹🇼 | 時間序列異常偵測 | [round_22_wattmon.md](rounds/round_22_wattmon.md) |
| 23 | `stylescan/` | Taiwan 🇹🇼 | 文體計量比對 | [round_23_stylescan.md](rounds/round_23_stylescan.md) |
| 24 | `leasecheck/` | Taiwan 🇹🇼 | 雜亂真實文件的結構化抽取 | [round_24_leasecheck.md](rounds/round_24_leasecheck.md) |
| 25 | `retiremate/` | Taiwan 🇹🇼 | 帶工具的對話式 Agent | [round_25_retiremate.md](rounds/round_25_retiremate.md) |
| 26 | `cashpilot/` | Taiwan 🇹🇼 | 模擬 / Monte-Carlo | [round_26_cashpilot.md](rounds/round_26_cashpilot.md) |
| 27 | `bizradar/` | Taiwan 🇹🇼 | 圖 / 網路分析 + 實體解析 | [round_27_bizradar.md](rounds/round_27_bizradar.md) |
| 28 | `caselens/` | Taiwan 🇹🇼 | 向量檢索 + LLM 重排序 | [round_28_caselens.md](rounds/round_28_caselens.md) |
| 29 | `hirepath/` | Taiwan 🇹🇼 | A/B 決策建模 + 不確定區間 | [round_29_hirepath.md](rounds/round_29_hirepath.md) |
| 30 | `carlens/` | Taiwan 🇹🇼 | 多模態融合 / 跨來源一致性檢查 | [round_30_carlens.md](rounds/round_30_carlens.md) |
| 31 | `teachsay/` | Taiwan 🇹🇼 | 主動學習 / Human-in-the-loop | [round_31_teachsay.md](rounds/round_31_teachsay.md) |
| 32 | `liftlab/` | Taiwan 🇹🇼 | 因果推論 / Pearl do-calculus | [round_32_liftlab.md](rounds/round_32_liftlab.md) |
| 33 | `stayspan/` | Taiwan 🇹🇼 | 存活分析 / Time-to-Event | [round_33_stayspan.md](rounds/round_33_stayspan.md) |
| 34 | `daypart/` | Taiwan 🇹🇼 | 混合模型 / EM 演算法 | [round_34_daypart.md](rounds/round_34_daypart.md) |
| 35 | `stagetrack/` | Taiwan 🇹🇼 | 隱馬可夫模型 / 序列標註 | [round_35_stagetrack.md](rounds/round_35_stagetrack.md) |
| 36 | `lawmate/` | Taiwan 🇹🇼 | 資訊檢索 / BM25 + LLM 重排序 | [round_36_lawmate.md](rounds/round_36_lawmate.md) |
| 37 | `seatplan/` | Taiwan 🇹🇼 | 約束滿足 / 模擬退火 | [round_37_seatplan.md](rounds/round_37_seatplan.md) |
| 38 | `quotelab/` | Taiwan 🇹🇼 | 多臂吃角子老虎 / Thompson Sampling | [round_38_quotelab.md](rounds/round_38_quotelab.md) |
| 39 | `peakflow/` | Taiwan 🇹🇼 | 代理人式離散事件模擬 | [round_39_peakflow.md](rounds/round_39_peakflow.md) |
| 40 | `_nice/examready/` ⭐ | Taiwan 🇹🇼 | 馬可夫決策過程 / 動態規劃 + Rollout | [round_40_examready.md](rounds/round_40_examready.md) |
| 41 | `salaryci/` | Taiwan 🇹🇼 | Split-Conformal 預測 | [round_41_salaryci.md](rounds/round_41_salaryci.md) |
| 42 | `storehunt/` | Taiwan 🇹🇼 | 最佳停止 / 秘書問題 | [round_42_storehunt.md](rounds/round_42_storehunt.md) |
| 43 | `viewdrop/` | Taiwan 🇹🇼 | 貝氏線上變點偵測 | [round_43_viewdrop.md](rounds/round_43_viewdrop.md) |
| 44 | `reviewlens/` | Taiwan 🇹🇼 | Latent Dirichlet Allocation / Collapsed Gibbs Sampling | [round_44_reviewlens.md](rounds/round_44_reviewlens.md) |
| 45 | `gpscheck/` | Taiwan 🇹🇼 | 動態時間扭曲 (DTW) | [round_45_gpscheck.md](rounds/round_45_gpscheck.md) |
| 46 | `expsense/` | Taiwan 🇹🇼 | Isolation Forest | [round_46_expsense.md](rounds/round_46_expsense.md) |
| 47 | `furnimatch/` | Taiwan 🇹🇼 | Item-Item 協同過濾 | [round_47_furnimatch.md](rounds/round_47_furnimatch.md) |
| 48 | `crybabel/` | Taiwan 🇹🇼 | 隨機森林分類 | [round_48_crybabel.md](rounds/round_48_crybabel.md) |
| 49 | `phonefix/` | Taiwan 🇹🇼 | 加權編輯距離 / 音素感知替換成本的 Levenshtein | [round_49_phonefix.md](rounds/round_49_phonefix.md) |
| 50 | `groupbuzz/` | Taiwan 🇹🇼 | PageRank / 冪次迭代中心性 | [round_50_groupbuzz.md](rounds/round_50_groupbuzz.md) |
| 51 | `growcurve/` | Taiwan 🇹🇼 | Kalman 濾波 + RTS 平滑器 | [round_51_growcurve.md](rounds/round_51_growcurve.md) |
| 52 | `_nice/kindergrid/` ⭐ | Taiwan 🇹🇼 | 階層式凝聚分群 + DBSCAN | [round_52_kindergrid.md](rounds/round_52_kindergrid.md) |
| 53 | `clinicqueue/` | Taiwan 🇹🇼 | 梯度提升決策樹 (GBDT) | [round_53_clinicqueue.md](rounds/round_53_clinicqueue.md) |
| 54 | `constsim/` | Taiwan 🇹🇼 | 加權 k-近鄰回歸 | [round_54_constsim.md](rounds/round_54_constsim.md) |
| 55 | `cleanmate/` | Taiwan 🇹🇼 | 多項式單純貝氏 | [round_55_cleanmate.md](rounds/round_55_cleanmate.md) |
| 56 | `cramlead/` | Taiwan 🇹🇼 | L2 正則化邏輯回歸 | [round_56_cramlead.md](rounds/round_56_cramlead.md) |
| 57 | `_nice/petfeed/` ⭐ | Taiwan 🇹🇼 | 階層式貝氏回歸 / 經驗貝氏 James-Stein 收縮 | [round_57_petfeed.md](rounds/round_57_petfeed.md) |
| 58 | `rentquant/` | Taiwan 🇹🇼 | Pinball Loss 分位數回歸 | [round_58_rentquant.md](rounds/round_58_rentquant.md) |
| 59 | `petskin/` | Taiwan 🇹🇼 | 線性判別分析 + Gauss-Jordan 求解 | [round_59_petskin.md](rounds/round_59_petskin.md) |
| 60 | `cropforecast/` | Taiwan 🇹🇼 | 高斯過程回歸 RBF 核 + Gauss-Jordan 求解 | [round_60_cropforecast.md](rounds/round_60_cropforecast.md) |
| 61 | `staypulse/` | Taiwan 🇹🇼 | 馬可夫鏈蒙地卡羅 (Metropolis-Hastings) | [round_61_staypulse.md](rounds/round_61_staypulse.md) |
| 62 | `scampatrol/` | Taiwan 🇹🇼 | 弱監督 (Snorkel 風) + Dawid-Skene EM | [round_62_scampatrol.md](rounds/round_62_scampatrol.md) |
| 63 | `topiclens/` | Taiwan 🇹🇼 | 譜分群 (Shi-Malik 2000 / Ng-Jordan-Weiss 2002) | [round_63_topiclens.md](rounds/round_63_topiclens.md) |
| 64 | `careermap/` | Taiwan 🇹🇼 | 自組織映射圖 (Kohonen 1982) | [round_64_careermap.md](rounds/round_64_careermap.md) |
| 65 | `barktype/` | Taiwan 🇹🇼 | 語音訊號分析（真實音檔：Cooley-Tukey FFT + 自相關基頻 + kNN） | [round_65_barktype.md](rounds/round_65_barktype.md) |
| 66 | `cabbrain/` | Taiwan 🇹🇼 | 強化學習 + 函數近似（Q-learning + 線性 FA） | [round_66_cabbrain.md](rounds/round_66_cabbrain.md) |
| 67 | `kaigomatch/` | Japan 🇯🇵 | 圖嵌入 / 連結預測（DeepWalk + PPMI + cosine） | [round_67_kaigomatch.md](rounds/round_67_kaigomatch.md) |

---

## 未來輪次的慣例

- **地區優先** — 使用者是台灣人，所以在證據相當時 **台灣優先**。
  接著是其他亞洲。已覆蓋的地區/垂直領域可在上面的輪次索引看到，
  不要重複佔位。在台灣的情況下，優先挑 *新鮮的垂直* 領域
  （宮廟 / 約會 / 殯葬 / 葬禮 / 中藥房），別再挖已開採過的領域。
- **架構多樣化** — 輪次索引中的 AI 模式欄位是已使用模式的權威清單。
  **不要** 重複任何一個。未來輪次應優先挑新鮮模式
  （例如：用於表格資料合成的 diffusion model、expectation propagation /
  variational inference、t-SNE / UMAP 降維），除非有極強證據才能重複。
- **數字留在純函數** — 每個原型都要把金錢 / 機率 / 門檻放在純 Python
  函數中。LLM 只負責散文、非結構化輸入的分類、或可讀的解釋。
  千萬不要讓 AI 算錢。
- **沒有 API key 也能 demo** — 每個專案都要附上預先生成的 `examples/`，
  讓 reviewer 不用設定 `ANTHROPIC_API_KEY` 也能看到輸出。
- **Commit 格式** — 每一輪一個 commit；訊息要說明痛點 + 競爭缺口 +
  驗證過的測試案例。每一輪結束後 push 到 `origin/main`。
- **更新本檔案** — 每個新輪次都必須：
  1. 新增一個 `rounds/round_NN_<slug>.md`，內含完整輪次說明，
  2. 在上面的輪次索引表格中加入一列。

---

*最後更新：第 67 輪（2026-05-11）。Loop 任務 ID：`6901dad6`（每 20 分鐘於 :08/:28/:48 觸發）。*
