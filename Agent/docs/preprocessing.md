# Data Preprocessing — PharmTwinAI

Answers the review question *"how was preprocessing done, and what was prioritised?"*
Part 1 is what the code does today on synthetic data. Part 2 is the plan for the
sponsor's real export, in priority order, with the reasoning for that order.

---

## Part 1 — What runs today

### 1.1 Reference catalog (Step 1)

| Step | What happens | Why |
|---|---|---|
| Load | Kaggle A–Z India medicines CSV | Brand, composition, manufacturer, price, therapeutic class |
| De-duplicate | Collapse repeated brand + pack rows | The raw file repeats the same product across sources |
| Normalise text | Case, whitespace, punctuation | Needed for both matching and TF-IDF |
| Result | **253,973 unique medicines**, 3,000 sampled as the shop's assortment | Marked `source_system='reference'` and made immutable |

### 1.2 Sales into a model-ready panel (Steps 1 and 3)

| Step | What happens | Code |
|---|---|---|
| Daily events → weekly | Sum per medicine per ISO week (Monday start) | `src/series.py` |
| **Dense grid** | Every medicine × every week, missing weeks filled with 0 | `to_weekly_demand()` |
| **Demand ≠ sales** | Target = units sold **+ unmet demand** | `load_demand_events(use_unmet=True)` |
| Lag features | 1, 2, 4-week lags, 4 and 8-week means, weeks since last sale — all `shift(1)` | `src/features_env.py` |
| Covariates | Rain, PM2.5 and alerts aggregated to the same weeks, then joined | same |
| Encoding | Therapeutic class and cohort → integer codes; price → `log(1+p)` | same |
| Missing values | Lag and environment columns filled with 0 after shifting | same |
| Split | By time: first 75% train (last 8 weeks for validation), last 25% test | `time_split()` |

**The two decisions that matter most here:**

1. **Zeros are kept.** 55.9% of SKU-weeks are zero. Dropping them would turn an
   intermittent-demand problem into a dense one and make every forecast far too high.
2. **Unmet demand is added back.** If a medicine was out of stock, the sale that did not
   happen is still demand. Training on sold units alone teaches the model that
   stockouts are low-demand weeks, which suppresses exactly the reorder signal the shop
   needs. This is the single most consequential preprocessing choice in the project.

### 1.3 Sales-export import (already built, awaiting real data)

`services/sales_ingest.py` already handles the POS "Customer wise sales Report" layout:

| Stage | Behaviour |
|---|---|
| Header detection | Finds the header row; the file has title and customer rows above it |
| Column allowlist | Only mapped columns are read — **patient, doctor, address and phone fields are never loaded** |
| Date parsing | Standard dates, plus `MM/YY` expiry expanded to the month's last day |
| Validation | Rejects unparseable dates, non-positive quantities, empty product names; rejects go to `ingest_rejects.csv` |
| Product matching | Normalised-name match against working inventory, then the reference catalog |
| Idempotency | A voucher hash per invoice; re-running imports nothing twice |
| Labelling | Rows written as `dev_synthetic` unless `--source-system sponsor` is passed |
| Dry run | Default; `--commit` is required to write |

**Current match rate on the sample files: 93 of 191 rows (48%).** The unmatched products
are listed in `ingest_unmatched_products.csv`. This is the biggest known gap.

---

## Part 2 — Plan for the sponsor's real export

Priority order. The reasoning behind the order: **a mistake early in this list silently
biases every model downstream; a mistake late in it is visible and fixable.**

### Priority 1 — Separate "sold nothing" from "no data"

The highest-risk preprocessing decision, and the one most often got wrong.

A zero in a weekly panel can mean four different things:

| Meaning | Correct handling | If handled wrong |
|---|---|---|
| Genuine: nobody asked for it | Keep as 0 — real information | — |
| Shop was closed (holiday, festival) | **Exclude the day** from the denominator | Forecasts biased low; the shop looks like it has falling demand |
| Export incomplete / file missing | **Exclude and flag** | Same, plus invisible gaps |
| Out of stock, demand existed | **Keep, and record unmet demand** | Reorder point too low exactly where it matters |

The schema already has the table for this and **nothing writes to it yet**:

```sql
demand_coverage (medicine_id, day, status)
  status ∈ OBSERVED | STORE_CLOSED | MISSING_EXPORT | STOCKOUT_UNMET
```

Plan: populate `demand_coverage` during import by comparing the days present in the
export against a shop calendar, then have the panel builder use only `OBSERVED` and
`STOCKOUT_UNMET` days as the denominator. Until this exists, any accuracy figure on real
data carries an unknown bias.

### Priority 2 — Product-name matching

48% is not good enough; the other half of the rows would be dropped from demand history.

| Technique | Purpose |
|---|---|
| Normalise strengths and forms | `PAN 20* TAB` → `PAN 20`; `625 Duo` vs `625` |
| Alias table | Shop shorthand → catalog name, built once and reused |
| Fuzzy match with a confidence score | Token-set ratio; above a high cut-off accept, in a middle band **ask**, below reject |
| **Pharmacist confirmation screen** | A fuzzy match below the automatic cut-off is confirmed by a person before it is committed, because a wrong match corrupts two medicines' histories at once (see `docs/false_positives.md`, decision 5) |
| Learn from confirmations | Every confirmed match is added to the alias table |

### Priority 3 — Returns, cancellations and corrections

Real POS data contains negative quantities and reversed invoices. Plan: treat a return as
a separate movement, not as negative demand; net returns against the original week when
they can be linked; never let a return create negative weekly demand.

### Priority 4 — Units

A row may be in strips, tablets, bottles or packs, and `Unit` and `Pack` columns disagree
in the sample files. Plan: convert everything to the medicine's base counting unit using
the pack size, keep the original values alongside, and refuse to import a row whose unit
cannot be resolved rather than guessing.

### Priority 5 — Outliers

| Pattern | Handling |
|---|---|
| Bulk / institutional purchase | Flag and exclude from the retail demand series, or model separately |
| Data-entry slips (e.g. 1000 instead of 100) | Winsorise at a high per-SKU percentile; report what was capped |
| One-off epidemic spikes | **Keep.** These are real demand and are what safety stock exists for |

The rule: cap what is implausible, never what is merely inconvenient.

### Priority 6 — Series eligibility

Not every medicine deserves a model. Plan: require a minimum history (say 26 weeks) and a
minimum number of non-zero weeks (say 3) before fitting; everything else falls back to a
simple average with a wide interval, clearly labelled as low-confidence.

### Priority 7 — Drift monitoring

Shown to be necessary by the classifier result: in the synthetic data the stockout rate is
**11.2% in training weeks and 40.1% in test weeks**, which miscalibrates the model. Plan:
record the base rate and feature distributions at training time, compare them on each
scoring run, and warn when they diverge. Retrain on a rolling recent window rather than
all history.

---

## 3. Privacy

The sponsor's file contains patient names, addresses, phone numbers and prescribing
doctors. Rules already enforced in code and to be kept:

1. Those columns are **never read into staging** — a column allowlist, not a drop after
   loading.
2. Real exports live in `data/raw/sponsor/`, which is gitignored.
3. Everything runs locally; no cloud service sees the data.
4. Any extract used in the report or the viva is aggregated, never row-level.

---

## 4. Order of work when the export arrives

1. Profile the file: columns, date range, row count, missing values, unit columns.
2. Build the shop calendar and populate `demand_coverage` (Priority 1).
3. Raise the match rate and add the confirmation screen (Priority 2).
4. Import to staging, dry run, review rejects and unmatched.
5. Commit with `--source-system sponsor`.
6. Re-run Steps 2, 3, 3b, 4, 5 and 6 and compare every number against the synthetic
   baseline, **expecting it to be worse** — real data always is.
7. Only then update any accuracy claim in the report.
