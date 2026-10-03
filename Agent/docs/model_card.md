# Model Card — PharmTwinAI

What every model in the system is trained on, with which parameters, and how it is
validated. Answers the review question *"what parameters are used to train the models,
on which data, and how is it trained?"*

**Data status:** all figures below come from **DEV SYNTHETIC** sales (2 years, 3,000
medicines, Navi Mumbai seasonality). They are not Bhagyashree Medical sales. The
sponsor's export loads through `scripts/ingest_sales_export.py` without code changes.

---

## 1. Models at a glance

| # | Model | Task | Type | Trained? | Code |
|---|-------|------|------|----------|------|
| 1 | LightGBM quantile ×3 (q50, q90, q95) | Weekly demand per medicine | Gradient-boosted trees | **Yes** | `src/forecast_env_lgbm.py` |
| 2 | LightGBM ablation ×3 (no weather) | Same, for comparison | Gradient-boosted trees | **Yes** | same |
| 3 | XGBoost (MAE) | Weekly demand | Gradient-boosted trees | **Yes** | `src/benchmark_models.py` |
| 4 | Random forest | Weekly demand | Bagged trees | **Yes** | same |
| 5 | Poisson GLM | Weekly demand | Generalised linear model | **Yes** | same |
| 6 | Blend of 1 + 3–5 | Weekly demand | Stacking ensemble | **Yes** (weights) | same |
| 7 | Croston, SBA, TSB, moving average | Weekly demand | Statistical smoothing | Fitted per medicine | `src/forecast_intermittent.py` |
| 8 | TF-IDF + cosine similarity | Substitute shortlist | Text similarity | Vocabulary fitted | `src/substitutes_nlp.py` |
| 9 | Safety stock / reorder point | Order decision | Formula, not learned | No | `src/safety_stock.py` |
| 10 | FEFO/FIFO policy simulator | What-if scenarios | Rule-based replay | No | `src/run_inventory_sim.py` |

Items 9 and 10 are **not** machine learning. Say so plainly; they consume the model
output rather than learning anything.

---

## 2. Training data

| Property | Value |
|---|---|
| Unit of observation | one medicine × one ISO week |
| Panel size | 318,000 rows (3,000 medicines × 106 weeks) |
| Target (`demand`) | units sold that week, **plus unmet demand** so stockouts are not read as zero demand |
| Zero weeks | **55.9%** of all rows — this is why the problem is called *intermittent* |
| Mean weekly demand | 2.30 units (5.22 on weeks with any sale) |
| Demand patterns (Syntetos–Boylan classification) | intermittent 1,685 · lumpy 753 · erratic 303 · smooth 204 |

Medicine attributes come from the de-duplicated India A–Z catalog (253,973 SKUs; 3,000
sampled as the shop's assortment). Weather and air-quality covariates are synthetic
Navi Mumbai series.

---

## 3. Features (29 columns)

Built by `src/features_env.py: build_feature_panel()`. Every demand feature is shifted
back one week (`shift(1)`), so the row for week *t* can only use information available
at the end of week *t−1*. This is what prevents target leakage.

### 3.1 Recent-sales features (6)

| Feature | Meaning |
|---|---|
| `demand_lag1`, `demand_lag2`, `demand_lag4` | units sold 1, 2 and 4 weeks earlier |
| `demand_roll4`, `demand_roll8` | mean of the previous 4 and 8 weeks |
| `weeks_since_demand` | weeks since the last non-zero sale (capped at 99) |

### 3.2 Product and calendar features (5)

| Feature | Meaning |
|---|---|
| `price_log` | log(1 + price in ₹) |
| `cohort_code` | demand cohort (respiratory, vector-borne, …) as an integer code |
| `theraclass_code` | therapeutic class as an integer code |
| `month`, `weekofyear` | seasonality |

### 3.3 Environment features (18) — research only (decision D5)

| Group | Features |
|---|---|
| Rainfall | `rain_mm_sum`, `rain_mm_max`, `rain_cum_7d_mean`, `rain_cum_14d_mean`, `rain_gt20_lag7_any`, `rain_gt20_lag14_any`, `rain_cum_lag7_mean`, `rain_cum_lag14_mean` |
| Air quality | `pm25_mean`, `pm25_max`, `high_pm25_days` |
| Health alerts | `alert_leptospirosis_any`, `alert_dengue_any`, `alert_air_quality_any`, `health_alert_any` |

Missing values in lag and environment columns are filled with 0 after shifting.

---

## 4. Hyperparameters

### 4.1 LightGBM (production forecast)

| Parameter | Value | Why |
|---|---|---|
| `objective` | `quantile` | Produces a range, not just an average — safety stock needs the spread |
| `alpha` | 0.50 / 0.90 / 0.95 | One model per quantile; α sets how much under-prediction is punished |
| `n_estimators` | 400 | Enough trees; early stopping cuts it short when it stops helping |
| `learning_rate` | 0.05 | Small steps, more stable than a large rate with few trees |
| `num_leaves` | 63 | Lets the model learn interactions such as *monsoon × anti-infective* |
| `min_child_samples` | 40 | A leaf must rest on ≥ 40 rows, so rare weeks cannot drive a rule |
| `subsample` | 0.8 | Each tree sees 80% of rows — reduces overfitting |
| `colsample_bytree` | 0.8 | Each tree sees 80% of features — decorrelates the trees |
| `reg_lambda` | 1.0 | L2 penalty keeps leaf values small |
| `random_state` | 42 | Reproducible |
| early stopping | 40 rounds | Stops when 8 held-out validation weeks stop improving |

**These values were hand-set from standard practice, not found by a hyperparameter
search.** Say that if asked; a tuning study is listed as future work.

### 4.2 Pinball (quantile) loss — why three models differ

For error *e = actual − predicted*:

```latex
L_\alpha(e) = \begin{cases} \alpha \cdot e & e > 0 \ (\text{under-predicted}) \\ (\alpha - 1) \cdot e & e \le 0 \ (\text{over-predicted}) \end{cases}
```

| Model | Penalty if too low | Penalty if too high | Behaviour |
|---|---|---|---|
| q50 | 0.50 | 0.50 | lands in the middle (median) |
| q90 | 0.90 | 0.10 | aims high (9× asymmetry) |
| q95 | 0.95 | 0.05 | aims higher (19× asymmetry) |

Predictions are clipped at 0 (demand cannot be negative). **`yhat` shown in the app is `q50`.**

### 4.3 Benchmark models

| Model | Key parameters | Objective |
|---|---|---|
| XGBoost | 400 trees, lr 0.05, max_depth 6, subsample 0.8, colsample 0.8, λ=1 | `reg:absoluteerror` |
| Random forest | 120 trees, min_samples_leaf 20, max_features 0.5 | squared error |
| Poisson GLM | StandardScaler + `PoissonRegressor(alpha=1e-3)`, 400 iterations | Poisson deviance |
| Blend | weights ≥ 0 summing to 1, fitted by SLSQP | **mean absolute error** — the same loss used for scoring |

### 4.4 Classical baselines

Croston, SBA and TSB with smoothing α = 0.1 (TSB also β = 0.1); moving average over an
8-week window. Each is fitted per medicine on its own history, one-step-ahead rolling.

### 4.5 Substitutes (TF-IDF)

| Parameter | Value |
|---|---|
| Vectoriser | `TfidfVectorizer`, `ngram_range=(1, 2)` on name + composition text |
| Minimum cosine similarity | 0.55 |
| Hard gates | Schedule H1 blocked · WHO AWaRe group flagged · CDSCO banned combinations excluded · must be in stock |

---

## 5. How training and validation work

Split by **time**, never at random — a random split would let the model see the future.

```
106 weeks total
|<----------- train: first 75% (79 weeks) ----------->|<-- test: 27 weeks -->|
|<--- fit: 71 weeks --->|<-- validation: last 8 -->|
```

| Block | Used for |
|---|---|
| **Fit** | fitting trees / coefficients |
| **Validation** | early stopping, and fitting the ensemble blend weights |
| **Test** | final scoring only; never seen during training. These are the weeks shown on the app's *Sales predictions* page |

The first 8 weeks of the panel are dropped from training because their lag features have
no history behind them.

**Forecast horizon: one week ahead.** The strongest inputs are the previous week's actual
sales, so the model is not a multi-week forecaster. Extending it would require feeding
predictions back as inputs, which is not implemented.

---

## 6. Metrics

| Metric | Formula | Why |
|---|---|---|
| **WMAPE** | Σ\|actual − predicted\| ÷ Σ actual | Works when many weeks are zero |
| **MASE** | mean\|error\| ÷ mean\|yₜ − yₜ₋₁\| on the training weeks | < 1 means better than a "same as last week" guess |
| MAE, bias | mean absolute error; mean(predicted) − mean(actual) | Bias shows systematic over/under-ordering |

**MAPE is never used.** It divides each week's error by that week's sales, and 55.9% of
weeks are zero, so it is undefined. Acceptance check **D02** fails the build if a MAPE
metric appears in any summary file.

---

## 7. Results (synthetic data, same 27 test weeks)

All nine comparable models, 3,000 medicines, the same 27 held-out weeks:

| Rank | Model | Family | Global WMAPE | Mean MASE | Blend weight |
|---|---|---|---|---|---|
| 1 | **LightGBM q50 (env)** | Gradient-boosted trees | **0.714** | **0.775** | 1.00 |
| 1= | Blend (absolute-error) | Ensemble | 0.714 | 0.775 | — |
| 3 | XGBoost (MAE) | Gradient-boosted trees | 0.747 | 0.924 | 0.00 |
| 4 | Random forest | Bagged trees | 0.813 | 1.156 | 0.00 |
| 5 | Moving average (8 wk) | Statistical | 0.835 | 0.965 | — |
| 6 | TSB | Statistical | 0.850 | 0.963 | — |
| 7 | SBA | Statistical | 0.854 | 0.969 | — |
| 8 | Croston | Statistical | 0.862 | 0.983 | — |
| 9 | Poisson GLM | Linear model | 0.922 | 1.484 | 0.00 |

Three findings worth stating out loud, because each one is the opposite of what a
reader might assume:

1. **The ensemble did not help.** The blend optimiser put 100% of the weight on
   LightGBM. To rule out a stuck optimiser we also searched blends directly on the test
   set — which would be cheating if used for selection — and the best four-way mix
   scored 0.719, still worse than LightGBM's 0.714. Averaging a median-optimal model
   with mean-optimal ones pulls predictions off the median, and absolute-error metrics
   punish that. Stacking is reported as *built, measured, and not adopted*.
2. **The plain 8-week moving average beats all three specialised intermittent-demand
   methods** (Croston, SBA, TSB). This matches published results for series with
   moderate intermittency and is reported rather than hidden.
3. **Only the tree ensembles beat the classical baselines.** The Poisson GLM is worse
   than a moving average, which says the gain comes from learning interactions across
   medicines, not from using more features in a linear way.

Raw numbers: `data/processed/step3b_model_benchmark.csv` and `step2_metrics_summary.csv`
(both snapshotted to `data/originals/`). Regenerate with `scripts/run_benchmark.py`.

---

## 8. Known limitations

1. One week ahead only.
2. Weather features cannot be validated on synthetic data — the data was generated with
   weather effects, so recovering them is partly circular. The no-weather ablation exists
   for comparison; only sponsor data can settle it.
3. Hyperparameters are hand-set, not tuned.
4. The three quantile models are trained independently, so q90 can occasionally fall
   below q50 for a row. Not corrected in code yet.
5. Retraining is a manual step (`scripts/run_step3.py`); sales recorded in the desktop
   app do not update the model.
6. TF-IDF matches text, not pharmacology. It cannot tell that two different salts treat
   the same condition, which is why a pharmacist reviews every suggestion.

---

## 9. Reproducing

Install the requirements first — the benchmark needs `xgboost` and `scipy`, which the
earlier steps do not:

```powershell
py -3 -m pip install -r requirements.txt
```

If a library is missing the benchmark reports that family as not benchmarked and
continues with the rest, rather than failing.

```powershell
py -3 scripts/run_step1.py --n-skus 3000   # data + covariates
py -3 scripts/run_step2.py                 # Croston / SBA / TSB / MA baselines
py -3 scripts/run_step3.py                 # LightGBM quantiles (+ no-env ablation)
py -3 scripts/run_benchmark.py             # XGBoost / RF / Poisson / blend
py -3 scripts/run_step4.py                 # safety stock + FEFO simulation
py -3 scripts/run_step5.py                 # substitutes + regulatory gates
```

All runs use `seed = 42`.
