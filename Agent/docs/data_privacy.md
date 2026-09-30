# Data Privacy & Confidentiality — PharmTwinAI

**Sponsor:** Bhagyashree Medical, Juinagar, Navi Mumbai  
**Principle:** Operational pharmacy data is confidential by default.

---

## 1. Classification

| Class | Examples | Handling |
|-------|----------|----------|
| **Confidential — Sponsor** | Sales, stock, purchases, suppliers, customers, phone numbers | Local/encrypted storage; no public git; no upload to external AI without written authorization |
| **Internal — DEV** | Synthetic Agent transactions | May live in private repo if stripped of sponsor data; must be labeled SYNTHETIC |
| **Public reference** | WHO AWaRe Excel, published NVBDCP aggregates | Cite source; respect license |
| **Restricted — Clinical images** | Conjunctiva photos (future) | Separate store; ethics/consent; never mix with POS training without approval |

---

## 2. Mandatory practices

1. **Do not** commit Bhagyashree raw exports to GitHub/public remotes.
2. **Do not** paste sponsor rows into ChatGPT/Claude/Cursor Cloud unless the sponsor explicitly authorizes that tool and retention mode.
3. Prefer **local** model training on sponsor machines or approved college lab PCs.
4. Strip or hash customer identifiers at ingest; pharmacy twin does not need patient identity for inventory forecasting.
5. Use `.gitignore` for `data/raw/sponsor/`, `*.xlsx` dumps, DB dumps, `.env`.
6. Document every external transfer in a simple data-handling log.

---

## 3. Suggested folder policy

```text
data/
  raw/sponsor/     # gitignored — Bhagyashree only
  raw/public/      # optional public downloads
  reference/       # AWaRe etc. (license notes)
  processed/       # derived; no PII
  synthetic/       # clearly labeled DEV
```

---

## 4. Access control (application)

| Role | Access |
|------|--------|
| Owner / manager | Full dashboard, recommendations, simulations, reports |
| Pharmacist / staff | Inventory ops, alerts, limited recommendations |
| Analyst (student) | Anonymized extracts, model metrics — not full customer PII |
| Public | None |

---

## 5. Screening module (future)

Anemia (and other) screening outputs are **experimental**, non-diagnostic, and stored separately from inventory recommendations. No automatic medicine advice from image predictions.

---

## 6. Incident response

If sponsor data is accidentally pushed to a remote: rotate credentials, purge history or revoke repo, notify team mentor and sponsor contact, document the incident.
