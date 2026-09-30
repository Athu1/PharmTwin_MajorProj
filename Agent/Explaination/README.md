# Explanation folder

| File | Description |
|------|-------------|
| **`PharmTwinAI_Notes_Colour.pdf`** | **Expanded colour teaching pack (Modules 0–11 + deep dives)** — ~40+ pages / 100KB+ text-heavy PDF. Same pedagogy as MU Sem-VII PLM colour notes (navy / crimson / green / purple / orange). Dense student notes: definitions, formulae, worked numericals, comparison tables, ASCII diagrams, glossary, 60+ viva Qs. |
| `PharmTwinAI_Student_Guide.docx` | Older plain Word draft (superseded by the PDF) |

Regenerate PDF:

```powershell
cd e:\MajorProject_4th_Yr\Agent
py -3 scripts/generate_explanation_doc.py
```

### Modules in the expanded PDF
0 Cover / colour legend / how to study / viva marking / what NOT to claim  
1 Problem & digital twin definition (D1–D8, twin vs dashboard)  
2 Architecture (stack, MySQL tables, UI→services→DB, folder map)  
3 Data foundation (253,973 vs ~3,000, synthetic Tx, clone flow, schema)  
4 Forecasting (Croston/SBA/TSB, WMAPE/MASE, LightGBM quantiles, D5)  
5 Inventory science (SS/ROP numericals, FEFO, markdown, simulation)  
6 Substitutes (TF-IDF + H1/AWaRe/CDSCO/habit gates)  
7 Desktop & ops (every page, commands, failure modes)  
8 Pipeline Steps 1–5 (diagram + outputs per step)  
9 Glossary, acronyms, formula sheet  
10 Viva bank (40+ with short hints)  
11 Limitations, ethics, gated anemia, future work  

### Colour key (same as your PLM notes)
- **Navy** — module banners & table headers  
- **Crimson** — definitions  
- **Green** — formulae (WMAPE, MASE, SS, ROP, cosine)  
- **Purple** — worked numericals  
- **Orange** — comparison tables & cautions  
- **Bordered panels** — flowcharts to redraw in viva  
