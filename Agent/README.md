# Navi Mumbai Pharmacy Inventory Optimization Agent

> **PharmTwinAI note (2026-09):** This folder currently holds the **ML / analytics prototype** (synthetic Navi Mumbai pipeline). The full industry digital-twin product plan for Bhagyashree Medical lives in [`docs/`](docs/) — start with [`docs/research.md`](docs/research.md), [`docs/architecture.md`](docs/architecture.md), and [`docs/implementation_roadmap.md`](docs/implementation_roadmap.md). Synthetic outputs remain **DEV-labeled**, not real pharmacy sales.

End-to-end documentation for the analytics agent at `e:\MajorProject_4th_Yr\Agent`.

This system treats the India A–Z medicines catalog as a product master, generates realistic Navi Mumbai retail transactions conditioned on weather and air quality, forecasts intermittent demand, optimizes inventory with FEFO and probabilistic safety stock, and recommends legally filtered substitutes during stockouts.

---

## 1. What this agent is

| Role | Description |
|------|-------------|
| **Domain** | Retail pharmacy inventory & demand intelligence (Navi Mumbai) |
| **Input** | India medicines catalog (~254k SKUs after dedupe) |
| **Output** | Synthetic POS data, forecasts, reorder params, policy KPIs, substitute lists |
| **Compliance lens** | Schedule H1, WHO AWaRe, CDSCO banned FDC / discontinued checks |

It is a **batch analytics + decision-support pipeline** (Python scripts), not a chat bot UI. You run steps from the command line; each step writes artifacts under `data/processed/`.

---

## 2. What has been done (five steps)

```text
Catalog CSV
    │
    ▼
[Step 1] Synthetic transactions + Navi Mumbai covariates + FEFO batches
    │
    ▼
[Step 2] Intermittent baselines: Croston / SBA / TSB (+ MA) — WMAPE / MASE
    │
    ▼
[Step 3] LightGBM quantile model + rain / PM2.5 / health alerts
    │
    ▼
[Step 4] Probabilistic safety stock + FEFO vs FIFO + OTC markdown simulation
    │
    ▼
[Step 5] TF-IDF substitutes gated by Schedule H1 / AWaRe / CDSCO
```

### Step 1 — Synthetic longitudinal data

**Done**
- Deduped catalog: **253,973** unique SKUs
- Stratified retail assortment: **3,000** active SKUs (heavy on respiratory & vector-borne)
- Daily covariates **2023-01-01 → 2024-12-31** (731 days): rainfall, lagged heavy-rain flags, PM2.5 / AQI, public-health alerts
- Sparse intermittent transactions: **~254k** demand events, **~356k** units, **~₹4.73 Cr** revenue
- **9,138** batches with expiry dates for FEFO

**How**
- `src/catalog.py` — load, coerce types, dedupe, cohort tags
- `src/covariates.py` — monsoon rain & winter PM2.5 generators for Navi Mumbai
- `src/generate_transactions.py` — Bernoulli demand × size, env multipliers, FEFO allocation
- CLI: `scripts/run_step1.py`

### Step 2 — Intermittent demand forecasting

**Done**
- Dense weekly demand panel (zeros filled): **55.9%** zero weeks
- Methods: **Croston, SBA, TSB**, vs moving-average baseline
- Metrics: **WMAPE** and **MASE only** (MAPE forbidden — breaks on zero-sale weeks)
- Syntetos–Boylan demand patterns: intermittent / lumpy / erratic / smooth

**Key result**
- On **intermittent** SKUs (ADI > 1.32, CV² ≤ 0.49): **SBA best** (global WMAPE ≈ 1.173) vs MA ≈ 1.194
- Overall pool includes smooth SKUs where MA can win — pattern slicing is required for a fair pharmacy story

**How**
- `src/forecast_intermittent.py`, `src/metrics.py`, `src/series.py`, `src/run_forecast_eval.py`
- CLI: `scripts/run_step2.py`

### Step 3 — Environment-conditioned LightGBM

**Done**
- Weekly features: demand lags + rain / PM2.5 / alerts + SKU encodings
- Quantile LightGBM: **q50 / q90 / q95** (probabilistic forecasts for safety stock)
- Ablation: with vs without env features
- Comparison vs SBA / TSB / MA on the same test window

**Key result**
- **lgbm_env WMAPE ≈ 0.714** vs SBA/TSB ≈ 0.85 and MA ≈ 0.835
- Strongest lift on **vector-borne** and **high-PM / rain-lag** slices
- Top env gains: `pm25_max`, `high_pm25_days`, `pm25_mean`

**How**
- `src/features_env.py`, `src/forecast_env_lgbm.py`, `src/run_env_forecast.py`
- CLI: `scripts/run_step3.py`
- Models saved under `data/processed/models_step3/`

### Step 4 — Inventory optimization (FEFO + SS + markdown)

**Done**
- Safety stock: \(SS = Z \times \sigma_{LT} \times \sqrt{L + R}\) with \(\sigma\) from quantile spreads, \(Z \approx 1.645\) (95% service), \(L = R = 1\) week
- Policies: `fifo_static`, `fefo_static`, `fefo_ss`, `fefo_ss_markdown`
- OTC near-expiry markdown tiers (10% / 25% / 40% / 50%); Rx-heavy / anti-infective classes excluded from auto-markdown

**Key result** (Jul–Dec 2024 test weeks)

| Policy | Fill rate | Role |
|--------|-----------|------|
| fifo_static | ~86.4% | Baseline |
| fefo_static | ~86.4% | Pick by earliest expiry |
| fefo_ss | **~96.6%** | Probabilistic reorder points |
| **fefo_ss_markdown** | **~96.6%** | Best overall (+ clearance discounts) |

**How**
- `src/safety_stock.py`, `src/inventory_fefo.py`, `src/run_inventory_sim.py`
- CLI: `scripts/run_step4.py`

### Step 5 — Regulated substitute recommendations

**Done**
- Explicit `substitute0`–`substitute4` when in stock
- Else **TF-IDF + cosine similarity** on composition + chemical + therapeutic text
- Gates: **Schedule H1** hard-block, **WHO AWaRe** (Watch/Reserve blocked for OTC auto-path), **CDSCO banned FDC** + discontinued + habit-forming

**Key result** (200 stockout queries)
- **78.5%** of queries got ≥1 allowed substitute
- **34** H1 queries fully blocked with RMP + 3-year register message
- Assortment flags: 571 H1, 624 Watch, 21 Reserve
- Worked examples: respiratory OK, H1 block (e.g. moxifloxacin), Watch antibiotic block (e.g. azithromycin)

**How**
- `src/regulatory/` (`schedule_h1.py`, `aware.py`, `cdsco_banned.py`)
- `src/substitutes_nlp.py`, `src/run_substitutes.py`
- CLI: `scripts/run_step5.py`

---

## 3. How it has been done (design choices)

### Data philosophy
- Catalog = **master data only** (no real POS). Demand is **synthetic but structured** so methods are testable.
- Demand used in forecasting = `qty + unmet_qty` (captures true demand despite stockouts).
- Weekly aggregation balances intermittency with enough signal for LightGBM.

### Forecasting rules (enforced)
1. Separate **occurrence** vs **size** (Croston family) for zero-inflated series.
2. Condition on **lagged rain (>20 mm, 1–2 weeks)** and **winter PM2.5**.
3. Emit **distributions** (quantiles), not only point forecasts.
4. Evaluate with **WMAPE / MASE**, never MAPE.

### Inventory rules
- Pick **FEFO** (first-expired, first-out).
- Dynamic **ROP / order-up-to** from quantile-based \(\sigma\).
- Markdown only for **OTC-eligible** classes (e.g. RESPIRATORY, PAIN, GI, DERMA).

### Substitution rules
1. Prefer listed substitutes → else TF-IDF.
2. **Never** auto-substitute Schedule H1.
3. Antibiotics: Access allowed under stewardship path; Watch/Reserve blocked for OTC automation.
4. Never recommend discontinued or banned FDC patterns.

### Tech stack
- Python 3.11 (`py -3` on Windows)
- `pandas`, `numpy`, `scikit-learn`, `lightgbm`, `pyarrow`, `tqdm`

---

## 4. What can be achieved

| Goal | How this agent helps |
|------|----------------------|
| **Reduce stockouts** | Probabilistic SS raised fill rate ~86% → ~97% in simulation |
| **Cut expiry waste** | FEFO + near-expiry OTC markdown; params ready for live FEFO WMS |
| **Local seasonal planning** | Rain-lag / PM2.5 features for monsoon infections & winter respiratory spikes |
| **Stewardship & legal safety** | H1 / AWaRe / CDSCO gates on substitutes |
| **Thesis / demo evidence** | Reproducible metrics JSON/CSV per step; ablation (env on/off); policy table |
| **Future live deploy** | Swap synthetic POS for real sales; plug CPCB/IMD feeds into `covariates` schema |

### Honest limitations
- Covariates and sales are **synthetic proxies** (realistic structure, not station-grade weather or real POS).
- Schedule H1 / AWaRe / CDSCO lists are **curated subsets** for the project — expand before production.
- Opening-stock expiry in Step 4 dominates waste ₹; SS mainly wins on **service level**.
- Not a dispensing system of record; pharmacist / RMP judgment remains mandatory.

---

## 5. Project layout

```text
e:\MajorProject_4th_Yr\Agent\
├── README.md                 ← this document
├── requirements.txt
├── scripts/
│   ├── run_step1.py          # synthetic data
│   ├── run_step2.py          # Croston / SBA / TSB
│   ├── run_step3.py          # LightGBM + env
│   ├── run_step4.py          # FEFO + SS + markdown
│   └── run_step5.py          # substitutes + gates
├── src/
│   ├── catalog.py
│   ├── covariates.py
│   ├── generate_transactions.py
│   ├── series.py
│   ├── metrics.py
│   ├── forecast_intermittent.py
│   ├── run_forecast_eval.py
│   ├── features_env.py
│   ├── forecast_env_lgbm.py
│   ├── run_env_forecast.py
│   ├── safety_stock.py
│   ├── inventory_fefo.py
│   ├── run_inventory_sim.py
│   ├── substitutes_nlp.py
│   ├── run_substitutes.py
│   └── regulatory/
│       ├── schedule_h1.py
│       ├── aware.py
│       └── cdsco_banned.py
└── data/processed/           # all outputs (CSV / parquet / JSON / models)
```

**Source catalog (outside repo):**  
`e:\MajorProject_4th_Yr\Data\A-Z medicines 2.5L+\Extensive_A_Z_medicines_dataset_of_India.csv`

---

## 6. How to use the agent

### 6.1 One-time setup

```powershell
cd e:\MajorProject_4th_Yr\Agent
py -3 -m pip install -r requirements.txt
```

Use `py -3` on Windows if `python` is not on PATH.

### 6.2 Run the full pipeline (in order)

```powershell
cd e:\MajorProject_4th_Yr\Agent

py -3 scripts/run_step1.py
py -3 scripts/run_step2.py
py -3 scripts/run_step3.py
py -3 scripts/run_step4.py
py -3 scripts/run_step5.py
```

Each step reads prior artifacts from `data/processed/` and writes new ones. **Step 1 must run before 2–5.**

### 6.3 Useful CLI options

```powershell
# Smaller smoke tests
py -3 scripts/run_step1.py --n-skus 500
py -3 scripts/run_step2.py --max-skus 500
py -3 scripts/run_step3.py --max-skus 500
py -3 scripts/run_step4.py --max-skus 500 --service-level 0.95
py -3 scripts/run_step5.py --n-queries 50 --top-n 5
```

### 6.4 Where to look after a run

| Step | Primary outputs |
|------|-----------------|
| 1 | `assortment_3k.csv`, `covariates_navi_mumbai.csv`, `transactions_synthetic.csv`, `batches_fefo.csv`, `step1_summary.json` |
| 2 | `step2_metrics_summary.csv`, `step2_forecasts_weekly.parquet`, `step2_summary.json` |
| 3 | `step3_metrics_summary.csv`, `step3_forecasts_weekly.parquet`, `step3_feature_importance.csv`, `models_step3/` |
| 4 | `step4_safety_stock_params.csv`, `step4_policy_comparison.csv`, `step4_summary.json` |
| 5 | `step5_substitute_recommendations.csv`, `step5_assortment_regulatory.csv`, `step5_summary.json` |

### 6.5 Programmatic use (substitutes example)

```python
import pandas as pd
from src.substitutes_nlp import SubstituteEngine

assortment = pd.read_csv("data/processed/assortment_3k.csv")
stock = {int(r.sku_id): 10.0 for r in assortment.itertuples()}  # demo: all in stock
# mark one OOS
stock[57808] = 0.0

engine = SubstituteEngine.fit(assortment, stock=stock, min_cosine=0.55)
for rec in engine.recommend(57808, top_n=5, require_in_stock=True):
    print(rec.candidate_name, rec.score, rec.source, rec.aware, rec.blocked, rec.block_reason)
```

### 6.6 Safety stock params for purchasing

Open `data/processed/step4_safety_stock_params.csv` for per-SKU:

- `mu_weekly`, `sigma_weekly`
- `safety_stock`, `reorder_point`, `order_up_to`
- `service_level`, `z_score`, `lead_time_weeks`, `review_period_weeks`

### 6.7 Interpreting substitute results

- `blocked=True` + Schedule H1 message → **do not auto-dispense**; need RMP Rx and H1 register.
- `aware` in `{Watch, Reserve}` on antibiotic path → blocked for OTC automation.
- `source=explicit` → from catalog substitute columns; `tfidf` → composition similarity.

---

## 7. Suggested viva / report talking points

1. **Why not MAPE?** Zero-demand weeks make percentage error undefined; WMAPE/MASE are correct for pharmacy POS.
2. **Why Croston/SBA/TSB?** Separate demand probability from demand size under intermittency.
3. **Why LightGBM + env?** Non-linear thresholds (rain > 20 mm lag, high PM2.5) beat pure intermittent baselines (WMAPE 0.71 vs ~0.85).
4. **Why probabilistic SS?** Quantiles → \(\sigma\) → \(SS = Z\sigma\sqrt{L+R}\) → fill rate lift to ~97%.
5. **Why regulatory NLP?** Substitutes without H1/AWaRe/CDSCO gates would be unsafe and non-compliant.

---

## 8. Reproducibility

- Default random **seed = 42** across generators and samples.
- Regenerate everything by re-running Steps 1→5 in order.
- Large intermediates may be gitignored; summaries and scripts are the source of truth for methodology.

---

## 9. Next extensions (optional)

- Live weather/AQI APIs (IMD / CPCB) instead of synthetic covariates  
- Streamlit / FastAPI UI for pharmacist stockout lookup  
- Expand H1 / AWaRe / CDSCO lists to full gazetteer tables  
- Multi-echelon (distributor + store) inventory  
- End-to-end `scripts/run_all.py` wrapper  

---

*Agent root: `e:\MajorProject_4th_Yr\Agent` · Catalog: India Extensive A–Z medicines dataset · Locale: Navi Mumbai retail pharmacy*
