# Incubator — AI Startup Prototype Index

This repository is an automated incubator. A scheduled `/loop` job fires
every 20 minutes and asks the model to:

1. Survey existing prototypes (this index + folder list) to avoid duplicates
2. Research a niche AI startup idea — **Asia-first markets prioritized**
   (台灣 / 日本 / 韓國 / 東南亞 / 中港); fall back to US/EU only when no
   Asian equivalent exists and the topic is unusually strong
3. Pick the highest-probability winner with evidence-backed competitive gap
4. Build a working prototype in a new folder
5. Commit + push to `origin/main` (one commit per round)

Each prototype has the same shape:
- `README.md` — pain, competitor analysis, pricing, distribution, risk
- single-file CLI(s) (Python, Anthropic SDK, prompt caching)
- `samples/` — realistic synthetic input
- `examples/` — pre-generated output (so demo works without API key)
- `requirements.txt`

---

## Round index

Per-round details (pain, competitor gap, architecture pattern, market sizing,
distribution) live in [`rounds/`](rounds/) — one file per round. When picking
the next idea, scan the AI-pattern column to avoid duplicating an approach.

| # | Slug | Geo | AI pattern | Detail |
|---|------|-----|-----------|--------|
| 1 | `scopescribe/` | US 🇺🇸 | doc-gen | [round_01_scopescribe.md](rounds/round_01_scopescribe.md) |
| 2 | `laobao/` | Taiwan 🇹🇼 | doc-gen | [round_02_laobao.md](rounds/round_02_laobao.md) |
| 3 | `kosmelingo/` | Korea → Japan 🇰🇷→🇯🇵 | doc-gen | [round_03_kosmelingo.md](rounds/round_03_kosmelingo.md) |
| 4 | `mitsumori/` | Japan 🇯🇵 | doc-gen | [round_04_mitsumori.md](rounds/round_04_mitsumori.md) |
| 5 | `settlekit/` | Korea 🇰🇷 | doc-gen | [round_05_settlekit.md](rounds/round_05_settlekit.md) |
| 6 | `hoadon/` | Vietnam 🇻🇳 | doc-gen | [round_06_hoadon.md](rounds/round_06_hoadon.md) |
| 7 | `carepen/` | Taiwan 🇹🇼 | doc-gen | [round_07_carepen.md](rounds/round_07_carepen.md) |
| 8 | `sudoc/` | Taiwan 🇹🇼 | doc-gen | [round_08_sudoc.md](rounds/round_08_sudoc.md) |
| 9 | `vetnote/` | Taiwan 🇹🇼 | doc-gen | [round_09_vetnote.md](rounds/round_09_vetnote.md) |
| 10 | `monthrep/` | Taiwan 🇹🇼 | doc-gen | [round_10_monthrep.md](rounds/round_10_monthrep.md) |
| 11 | `fitlog/` | Taiwan 🇹🇼 | doc-gen | [round_11_fitlog.md](rounds/round_11_fitlog.md) |
| 12 | `motoval/` | Taiwan 🇹🇼 | Vertical Pricing Model + NLP parsing | [round_12_motoval.md](rounds/round_12_motoval.md) |
| 13 | `snaporder/` | Taiwan 🇹🇼 | NLP / OCR Multi-message Aggregation | [round_13_snaporder.md](rounds/round_13_snaporder.md) |
| 14 | `subsidybot/` | Taiwan 🇹🇼 | RAG over Local-knowledge Corpus | [round_14_subsidybot.md](rounds/round_14_subsidybot.md) |
| 15 | `shiftsync/` | Taiwan 🇹🇼 | Scheduling + LINE Bot Conversational | [round_15_shiftsync.md](rounds/round_15_shiftsync.md) |
| 16 | `weddingmatch/` | Taiwan 🇹🇼 | Matching with Embedding Similarity | [round_16_weddingmatch.md](rounds/round_16_weddingmatch.md) |
| 17 | `tenderwatch/` | Taiwan 🇹🇼 | Real-time Monitoring + LLM Semantic-match Scoring | [round_17_tenderwatch.md](rounds/round_17_tenderwatch.md) |
| 18 | `salonguard/` | Taiwan 🇹🇼 | Churn Prediction / Anomaly Detection on Customer Events | [round_18_salonguard.md](rounds/round_18_salonguard.md) |
| 19 | `propvision/` | Taiwan 🇹🇼 | Vertical Pricing + Vision Identification Combo | [round_19_propvision.md](rounds/round_19_propvision.md) |
| 20 | `cropscan/` | Taiwan 🇹🇼 | Pure Vision Classification | [round_20_cropscan.md](rounds/round_20_cropscan.md) |
| 21 | `trailmatch/` | Taiwan 🇹🇼 | Behavioral Personalization | [round_21_trailmatch.md](rounds/round_21_trailmatch.md) |
| 22 | `wattmon/` | Taiwan 🇹🇼 | Time-Series Anomaly Detection | [round_22_wattmon.md](rounds/round_22_wattmon.md) |
| 23 | `stylescan/` | Taiwan 🇹🇼 | Stylometric Matching | [round_23_stylescan.md](rounds/round_23_stylescan.md) |
| 24 | `leasecheck/` | Taiwan 🇹🇼 | Structured-Output Extraction from Messy Real-World Docs | [round_24_leasecheck.md](rounds/round_24_leasecheck.md) |
| 25 | `retiremate/` | Taiwan 🇹🇼 | Conversational Agent with Tools | [round_25_retiremate.md](rounds/round_25_retiremate.md) |
| 26 | `cashpilot/` | Taiwan 🇹🇼 | Simulation / Monte-Carlo | [round_26_cashpilot.md](rounds/round_26_cashpilot.md) |
| 27 | `bizradar/` | Taiwan 🇹🇼 | Graph / Network Analysis + Entity Resolution | [round_27_bizradar.md](rounds/round_27_bizradar.md) |
| 28 | `caselens/` | Taiwan 🇹🇼 | Vector Retrieval with LLM Re-ranking | [round_28_caselens.md](rounds/round_28_caselens.md) |
| 29 | `hirepath/` | Taiwan 🇹🇼 | A/B Decision Modeling with Uncertainty Bands | [round_29_hirepath.md](rounds/round_29_hirepath.md) |
| 30 | `carlens/` | Taiwan 🇹🇼 | Multi-modal Fusion / Cross-source Consistency Checking | [round_30_carlens.md](rounds/round_30_carlens.md) |
| 31 | `teachsay/` | Taiwan 🇹🇼 | Active Learning / Human-in-the-loop | [round_31_teachsay.md](rounds/round_31_teachsay.md) |
| 32 | `liftlab/` | Taiwan 🇹🇼 | Causal Inference / Pearl do-calculus | [round_32_liftlab.md](rounds/round_32_liftlab.md) |
| 33 | `stayspan/` | Taiwan 🇹🇼 | Survival Analysis / Time-to-Event | [round_33_stayspan.md](rounds/round_33_stayspan.md) |
| 34 | `daypart/` | Taiwan 🇹🇼 | Mixture Models / EM Algorithm | [round_34_daypart.md](rounds/round_34_daypart.md) |
| 35 | `stagetrack/` | Taiwan 🇹🇼 | Hidden Markov Models / Sequence Labeling | [round_35_stagetrack.md](rounds/round_35_stagetrack.md) |
| 36 | `lawmate/` | Taiwan 🇹🇼 | Information Retrieval / BM25 + LLM Re-ranking | [round_36_lawmate.md](rounds/round_36_lawmate.md) |
| 37 | `seatplan/` | Taiwan 🇹🇼 | Constraint Satisfaction / Simulated Annealing | [round_37_seatplan.md](rounds/round_37_seatplan.md) |
| 38 | `quotelab/` | Taiwan 🇹🇼 | Multi-armed Bandit / Thompson Sampling | [round_38_quotelab.md](rounds/round_38_quotelab.md) |
| 39 | `peakflow/` | Taiwan 🇹🇼 | Agent-based Discrete-Event Simulation | [round_39_peakflow.md](rounds/round_39_peakflow.md) |
| 40 | `examready/` | Taiwan 🇹🇼 | Markov Decision Process / Dynamic Programming with Rollout | [round_40_examready.md](rounds/round_40_examready.md) |
| 41 | `salaryci/` | Taiwan 🇹🇼 | Split-Conformal Prediction | [round_41_salaryci.md](rounds/round_41_salaryci.md) |
| 42 | `storehunt/` | Taiwan 🇹🇼 | Optimal Stopping / Secretary Problem | [round_42_storehunt.md](rounds/round_42_storehunt.md) |
| 43 | `viewdrop/` | Taiwan 🇹🇼 | Bayesian Online Changepoint Detection | [round_43_viewdrop.md](rounds/round_43_viewdrop.md) |
| 44 | `reviewlens/` | Taiwan 🇹🇼 | Latent Dirichlet Allocation / Collapsed Gibbs Sampling | [round_44_reviewlens.md](rounds/round_44_reviewlens.md) |
| 45 | `gpscheck/` | Taiwan 🇹🇼 | Dynamic Time Warping | [round_45_gpscheck.md](rounds/round_45_gpscheck.md) |
| 46 | `expsense/` | Taiwan 🇹🇼 | Isolation Forest | [round_46_expsense.md](rounds/round_46_expsense.md) |
| 47 | `furnimatch/` | Taiwan 🇹🇼 | Item-Item Collaborative Filtering | [round_47_furnimatch.md](rounds/round_47_furnimatch.md) |
| 48 | `crybabel/` | Taiwan 🇹🇼 | Random Forest classification | [round_48_crybabel.md](rounds/round_48_crybabel.md) |
| 49 | `phonefix/` | Taiwan 🇹🇼 | Weighted Edit Distance / Levenshtein with phoneme-aware substitution costs | [round_49_phonefix.md](rounds/round_49_phonefix.md) |
| 50 | `groupbuzz/` | Taiwan 🇹🇼 | PageRank / Power Iteration Centrality | [round_50_groupbuzz.md](rounds/round_50_groupbuzz.md) |
| 51 | `growcurve/` | Taiwan 🇹🇼 | Kalman Filter + RTS Smoother | [round_51_growcurve.md](rounds/round_51_growcurve.md) |
| 52 | `kindergrid/` | Taiwan 🇹🇼 | Hierarchical Agglomerative Clustering + DBSCAN | [round_52_kindergrid.md](rounds/round_52_kindergrid.md) |
| 53 | `clinicqueue/` | Taiwan 🇹🇼 | Gradient Boosting Decision Trees (GBDT) | [round_53_clinicqueue.md](rounds/round_53_clinicqueue.md) |
| 54 | `constsim/` | Taiwan 🇹🇼 | Weighted k-Nearest Neighbors regression | [round_54_constsim.md](rounds/round_54_constsim.md) |
| 55 | `cleanmate/` | Taiwan 🇹🇼 | Multinomial Naive Bayes | [round_55_cleanmate.md](rounds/round_55_cleanmate.md) |
| 56 | `cramlead/` | Taiwan 🇹🇼 | Logistic Regression with L2 regularization | [round_56_cramlead.md](rounds/round_56_cramlead.md) |
| 57 | `petfeed/` | Taiwan 🇹🇼 | Hierarchical Bayesian Regression / Empirical-Bayes James-Stein Shrinkage | [round_57_petfeed.md](rounds/round_57_petfeed.md) |
| 58 | `rentquant/` | Taiwan 🇹🇼 | Quantile Regression with Pinball Loss | [round_58_rentquant.md](rounds/round_58_rentquant.md) |
| 59 | `petskin/` | Taiwan 🇹🇼 | Linear Discriminant Analysis with Gauss-Jordan Solve | [round_59_petskin.md](rounds/round_59_petskin.md) |
| 60 | `cropforecast/` | Taiwan 🇹🇼 | Gaussian Process Regression with RBF kernel + Gauss-Jordan Solve | [round_60_cropforecast.md](rounds/round_60_cropforecast.md) |
| 61 | `staypulse/` | Taiwan 🇹🇼 | Markov Chain Monte Carlo (Metropolis-Hastings) | [round_61_staypulse.md](rounds/round_61_staypulse.md) |
| 62 | `scampatrol/` | Taiwan 🇹🇼 | Weak Supervision (Snorkel-style) with Dawid-Skene EM | [round_62_scampatrol.md](rounds/round_62_scampatrol.md) |
| 63 | `topiclens/` | Taiwan 🇹🇼 | Spectral Clustering (Shi-Malik 2000 / Ng-Jordan-Weiss 2002) | [round_63_topiclens.md](rounds/round_63_topiclens.md) |
| 64 | `careermap/` | Taiwan 🇹🇼 | Self-Organizing Map (Kohonen 1982) | [round_64_careermap.md](rounds/round_64_careermap.md) |
| 65 | `barktype/` | Taiwan 🇹🇼 | Voice Signal Analysis (real audio: Cooley-Tukey FFT + autocorrelation pitch + kNN) | [round_65_barktype.md](rounds/round_65_barktype.md) |
| 66 | `cabbrain/` | Taiwan 🇹🇼 | Reinforcement Learning with Function Approximation (Q-learning + linear FA) | [round_66_cabbrain.md](rounds/round_66_cabbrain.md) |
| 67 | `kaigomatch/` | Japan 🇯🇵 | Graph Embedding / Link Prediction (DeepWalk + PPMI + cosine) | [round_67_kaigomatch.md](rounds/round_67_kaigomatch.md) |

---

## Conventions for future rounds

- **Geography priority** — user is Taiwanese, so **Taiwan first** when evidence is
  comparable. Then other Asia. Already-covered geographies/verticals are visible in
  the round index above; don't re-pick a slot. For Taiwan, prefer *fresh verticals*
  (宮廟 / dating / 殯葬 / 葬禮 / 中藥房) over already-mined sectors.
- **Architecture diversification** — the AI-pattern column in the round index is
  the authoritative list of patterns already used. Do **not** repeat one. Future
  rounds should prefer fresh patterns (e.g. diffusion models for tabular synthesis,
  expectation propagation / variational inference, t-SNE / UMAP dimensionality
  reduction) unless extraordinary evidence justifies a repeat.
- **Numbers stay in pure functions** — every prototype keeps money / probabilities /
  thresholds in pure Python functions. LLM is only for prose, classification of
  unstructured input, or human-readable explanation. Never let AI calculate money.
- **Demo without API key** — every project ships pre-generated `examples/` so
  reviewers can see output without setting `ANTHROPIC_API_KEY`.
- **Commit format** — one commit per round; message explains pain + competitor gap +
  verified test cases. Push to `origin/main` after each round.
- **Update this file** — every new round must:
  1. add a `rounds/round_NN_<slug>.md` file with the full round write-up,
  2. append a row to the Round index table above.

---

*Last updated: round 67 (2026-05-11). Loop job ID: `6901dad6` (every 20 min at :08/:28/:48).*
