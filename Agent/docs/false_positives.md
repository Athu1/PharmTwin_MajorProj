# False Positives and False Negatives — PharmTwinAI

Answers the review question *"what are the false positives, how are they countered, and
what is recommended to the end user if they pose a threat?"*

A forecast is a number, so on its own it has no false positive. Every **decision** the
system makes from that number is binary, and each one can be wrong in two directions.
This document names every such decision, says which error is worse and why, lists what
already guards against it in code, and states what the pharmacist is shown.

---

## 1. The five decision points

| # | Decision | False positive (cries wolf) | False negative (misses it) | Worse error | Why |
|---|---|---|---|---|---|
| 1 | **Substitute suggestion** | Suggests a medicine that is not an acceptable alternative | Offers nothing when a valid alternative is in stock | **False positive** | A wrong substitute can harm a patient. A missing one costs a sale. |
| 2 | **Reorder (REORDER)** | Orders stock that was not needed | Stays silent while stock runs out | **False negative** | Overstock costs money; a stockout sends a patient away, possibly mid-course. |
| 3 | **Stockout-risk alert** | Alert for a medicine that was never going to run short | Misses a real stockout | **False negative**, up to a point | Past roughly 1 alert per 5 medicines per week, staff stop reading them and recall collapses in practice. |
| 4 | **Expiry warning** | Flags a batch that would have sold at full price | Misses a batch that then expires | **False positive** | Early discounting throws away margin on stock that would have sold anyway. |
| 5 | **Sales-import product match** | Matches a row to the wrong medicine | Leaves the row unmatched | **False positive** | A wrong match corrupts the demand history of two medicines at once; an unmatched row is merely absent and is reported. |

The table is the point. **There is no single threshold that is right for the whole
system**, because the cost of being wrong is not the same at each decision.

---

## 2. Measured: the stockout classifier

`src/stockout_classifier.py` (Step 6) predicts whether a medicine will have unmet
demand in the coming week. Being a true binary task, it produces a real confusion
matrix — numbers in `data/processed/step6_summary.json`.

### 2.1 Choosing the cut-off from cost, not from habit

A probability model outputs a number between 0 and 1. Turning it into an alert needs a
threshold, and **0.5 is an arbitrary default that silently assumes both mistakes cost the
same.** They do not. The project's working assumption:

> One missed stockout costs about the same as **five** unnecessary reorders.

So the threshold is chosen to minimise expected cost:

```latex
\text{cost} = n_{FP} + 5 \cdot n_{FN}
```

`scripts/run_step6.py --cost-ratio N` re-runs the whole sweep for any other ratio, and
`step6_threshold_sweep.csv` shows what every cut-off would have cost. **The ratio is an
assumption to be challenged, not a measurement** — that is exactly why it is a visible
parameter rather than a hidden constant.

Results on 3,000 medicines, the same 27 held-out weeks:

| Model | ROC-AUC | PR-AUC | Base rate (random guessing) |
|---|---|---|---|
| **LightGBM classifier** | **0.758** | **0.713** | 0.419 |
| Logistic regression | 0.680 | 0.637 | 0.419 |

Both beat random guessing, and the tree model beats the linear one — the same ordering
as in the demand benchmark, which is a consistency check worth stating.

### 2.2 What the threshold does to the two errors

| Cut-off | Recall (stockouts caught) | Precision (alerts that were right) | False alarms | Missed stockouts |
|---|---|---|---|---|
| 0.01 | 92.3% | 48.0% | 33,957 | 2,594 |
| 0.05 | 55.8% | 68.4% | 8,754 | 14,987 |
| 0.10 | 37.1% | 78.2% | 3,496 | 21,340 |
| 0.50 (naive default) | 7.5% | 93.9% | 167 | 31,345 |

This single table is the answer to "what are the false positives and how are they
countered": **you do not remove them, you choose them.** Every row trades one error for
the other, and the choice belongs to whoever bears the cost.

### 2.3 A finding that matters more than the accuracy

The stockout rate is **13.2% in the training weeks and 41.9% in the test weeks**. The
synthetic generator starts the shop with a fixed opening stock that depletes over two
years, so shortages become far more common later in the series.

Consequences, all of which are reported rather than smoothed over:

- The model is **miscalibrated** on the test period: at the default 0.5 threshold it
  catches only 7.5% of real stockouts, because it learned a world where they were rare.
- The cost-based sweep compensates by pushing the cut-off to the bottom of the grid
  (0.01). That is a *symptom*, not a tuned setting.
- At that cut-off the system would alert on **81% of medicine-weeks**, which in practice
  means staff stop reading alerts entirely.

**The code says this itself.** `run_stockout_classifier()` emits three machine-generated
warnings — distribution shift, threshold at the grid edge, and alert-fatigue risk — into
`step6_summary.json` and the console. A model that reports when it should not be trusted
is worth more than one that reports a flattering number.

The lesson belongs to preprocessing (`docs/preprocessing.md`, Priority 7): **a model is
only valid while the future resembles the training period.** The fix is to retrain on a
rolling recent window and monitor the base rate, not to tune the threshold harder.

---

## 3. Guards already in the code

### 3.1 Substitutes — the safety-critical path

| Guard | Where | Effect |
|---|---|---|
| Schedule H1 block | `src/regulatory/schedule_h1.py` | Habit-forming / restricted drugs return **no** suggestions at all |
| WHO AWaRe group | `src/regulatory/aware.py` | Watch and Reserve antibiotics are flagged; Reserve is never offered casually |
| CDSCO banned list | `src/regulatory/cdsco_banned.py` | Banned fixed-dose combinations are excluded |
| Similarity floor | `src/substitutes_nlp.py` | Cosine similarity below **0.55** is discarded |
| In-stock requirement | `services/substitutes.py` | Only suggests what the shop can actually dispense |
| Pharmacist framing | `app/main.py` | Labelled "for the pharmacist to check", never "recommended" |
| No auto-substitution | whole system | Nothing is ever dispensed or billed automatically |

### 3.2 Stock and ordering

| Guard | Effect |
|---|---|
| `CHECK (qty_on_hand >= 0)` in the database | Stock can never go negative, whatever the code does |
| FEFO allocation | Earliest-expiry batch sells first; expired stock is never sold |
| `unmet_qty` recorded | A shortfall is stored as lost demand instead of vanishing |
| Mandatory reason on quantity corrections | Every manual adjustment is attributable |
| `inventory_audit` with old/new values | Every edit is reversible in evidence, if not in data |
| Simulation fingerprint check | A what-if run proves it did not touch live stock |
| Reference catalog immutable | 250k-row catalog cannot be edited from the app |

### 3.3 Data import

| Guard | Effect |
|---|---|
| PII columns dropped at read | Patient, doctor and phone fields never reach staging |
| Voucher-level idempotency | Re-running an import does not duplicate sales |
| Rejected rows written to CSV | Bad dates, zero quantities and unknown products are listed, not silently dropped |
| Unmatched products reported | The 52% that did not match a catalog entry are visible for review |

---

## 4. What the pharmacist is shown when an error could harm them

The principle: **never show a bare number for a decision that carries risk.** Show the
decision, the evidence behind it, and the way to disagree with it.

| Decision | What is shown now | What is still to add |
|---|---|---|
| Substitute | Similarity score, source (known equivalent vs similar composition), AWaRe group, therapeutic class, stock on hand, and a standing note that a pharmacist must review | **Why a candidate was blocked**, and an explicit "differs in strength / salt / form" warning |
| Reorder | Plain-language explanation: stock now, expected sales to delivery, safety stock, reorder point, and the formula | The uncertainty band (q50–q95) shown beside the suggestion; an override button that records a reason |
| Stockout alert | Low-stock and stockout rows with severity | Severity tiers from the model's probability; snooze-with-reason; suppress when a purchase order is already open |
| Expiry | Days remaining, batch, quantity | Expected sell-through before expiry, so a "will sell anyway" batch is not discounted |
| Import | Reject and unmatched reports | A confirmation screen for fuzzy matches before they are committed |

### 4.1 Rules for anything safety-related

1. **Suggest, never act.** No substitution, order or write-off happens without a person.
2. **Show the reason, including the reason against.** A blocked alternative is more
   informative than a missing one.
3. **Make disagreement cheap and recorded.** An override with a reason is a training
   signal; an override with no record is lost information.
4. **Prefer silence to a confident wrong answer.** Below the similarity floor the system
   says it has nothing, rather than offering the closest text match.

---

## 5. What is not yet measured

Stated plainly, because a panel will ask:

1. **The substitute false-positive rate is unknown.** There is no labelled ground truth
   of "this really is an acceptable alternative". Establishing it needs a pharmacist to
   review a sample — that is the correct next step, and it is a human task, not a
   modelling one.
2. **Alert fatigue is not measured**, because the system has no users yet. The alert rate
   per threshold is in the sweep table and is the number to watch in a pilot.
3. **Expiry-warning precision is not measured**, since it needs the sell-through a batch
   would have had — observable only in a pilot.
4. **The cost ratio of 5:1 is an assumption.** The sponsor can replace it with their own
   margin and lost-customer figures, and the threshold recomputes.

---

## 6. Reproducing

```powershell
py -3 scripts/run_step6.py                  # classifier + threshold sweep
py -3 scripts/run_step6.py --cost-ratio 10  # if a stockout is judged 10x worse
```

Outputs: `step6_classifier_models.csv`, `step6_threshold_sweep.csv`, `step6_summary.json`.
All figures are from **DEV SYNTHETIC** data.
