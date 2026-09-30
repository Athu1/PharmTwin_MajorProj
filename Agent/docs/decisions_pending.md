# Decisions Requiring Your Approval — PharmTwinAI

Please reply with choices (A/B/…) so implementation can proceed without rework.

---

### D1. Project root layout
- **A)** Keep evolving under `e:\MajorProject_4th_Yr\Agent` (docs + later `app/`, `db/`)  
- **B)** Create new `e:\MajorProject_4th_Yr\PharmTwinAI` and vendor/import Agent ML as a package  

### D2. Frontend
- **A)** Streamlit-first (faster demo, per brief)  
- **B)** Flask + simple HTML/JS templates  
- **C)** React SPA (more work; only if you need a polished web product early)

### D3. Bhagyashree data handoff
- Expected format? **Excel / CSV / SQL dump / other**  
- Approximate date available?  
- May students use **anonymized** extracts in private Git? **Yes / No**

### D4. Scope of “medicine substitutes”
- **A)** Keep as **pharmacist-reviewed inventory alternatives** (current Agent Step 5)  
- **B)** Remove from v1 core (purchasing recommendations only)  
- **C)** Expand clinical decision support (⚠️ higher regulatory risk — not recommended for v1)

### D5. External weather / epi features in production forecasts
- **A)** DEV/research only until association proven on sponsor sales  
- **B)** Enable Open-Meteo + optional NVBDCP aggregates from day one (disclosed as experimental)

### D6. Cloud
- **A)** Local / lab only for six months  
- **B)** Allowed free-tier cloud (specify provider) for demos  

### D7. Anemia timeline
- **A)** Strict gate: Month 6 only if core acceptance green  
- **B)** Allow parallel **research docs** now, still no implementation until gate  

*(Brief already implies B for research / A for implementation — confirm.)*

### D8. Secondary screening beyond anemia
- Confirm: **research-only until you explicitly approve each condition** (recommended: Yes)

---

## Recommended defaults (if you want a single “approve defaults” reply)

D1=A, D2=A, D4=A, D5=A, D6=A, D7=B (research now / implement after gate), D8=Yes.  
D3 = please fill when sponsor responds.
