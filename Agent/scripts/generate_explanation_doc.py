"""
Generate PharmTwinAI student notes in the same colour pedagogy as
MU Sem-VII PLM colour notes (navy / crimson / green / purple / orange).

Long teaching-pack style (Modules 0–11). Aim: dense 40–60 page notes.
Output: Explaination/PharmTwinAI_Notes_Colour.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Explaination" / "PharmTwinAI_Notes_Colour.pdf"

# Colour system (matched to PLM notes legend)
NAVY = colors.HexColor("#1A365D")
CRIMSON = colors.HexColor("#9B2C2C")
GREEN = colors.HexColor("#276749")
GREEN_BG = colors.HexColor("#E6F4EA")
PURPLE = colors.HexColor("#6B46C1")
PURPLE_BG = colors.HexColor("#F3E8FF")
ORANGE = colors.HexColor("#C05600")
ORANGE_BG = colors.HexColor("#FFFAF0")
NAVY_BG = colors.HexColor("#EBF2FA")
LIGHT = colors.HexColor("#F7FAFC")
BORDER = colors.HexColor("#2D3748")


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=8,
            leading=26,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#4A5568"),
            alignment=TA_CENTER,
            leading=14,
            spaceAfter=4,
        ),
        "banner": ParagraphStyle(
            "banner",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.white,
            alignment=TA_LEFT,
            leading=15,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=5,
            leading=15,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            textColor=CRIMSON,
            spaceBefore=8,
            spaceAfter=3,
            leading=13,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            alignment=TA_JUSTIFY,
            leading=12,
            spaceAfter=4,
        ),
        "def_label": ParagraphStyle(
            "def_label",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=CRIMSON,
            leading=12,
        ),
        "def_body": ParagraphStyle(
            "def_body",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=colors.black,
            leading=12,
            spaceAfter=3,
        ),
        "formula": ParagraphStyle(
            "formula",
            parent=base["Normal"],
            fontName="Courier-Bold",
            fontSize=9.5,
            textColor=GREEN,
            alignment=TA_CENTER,
            leading=13,
        ),
        "formula_note": ParagraphStyle(
            "formula_note",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=GREEN,
            leading=10.5,
            spaceAfter=2,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7,
            leading=9.2,
            textColor=BORDER,
        ),
        "caution": ParagraphStyle(
            "caution",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=ORANGE,
            leading=11,
        ),
        "worked": ParagraphStyle(
            "worked",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=PURPLE,
            leading=11,
        ),
        "th": ParagraphStyle(
            "th",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
            leading=10,
        ),
        "td": ParagraphStyle(
            "td",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.black,
            leading=10,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11.5,
            leftIndent=12,
            spaceAfter=2,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=3,
        ),
    }
    return s


S = styles()


def banner(text: str):
    data = [[Paragraph(text, S["banner"])]]
    t = Table(data, colWidths=[17 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return t


def def_box(title: str, body: str):
    data = [
        [Paragraph(title, S["def_label"])],
        [Paragraph(body, S["def_body"])],
    ]
    t = Table(data, colWidths=[17 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF5F5")),
                ("BOX", (0, 0), (-1, -1), 1.5, CRIMSON),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ]
        )
    )
    return t


def green_formula(lines: list[str], note: str = ""):
    cells = [[Paragraph(ln, S["formula"])] for ln in lines]
    if note:
        cells.append([Paragraph(note, S["formula_note"])])
    t = Table(cells, colWidths=[17 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GREEN_BG),
                ("BOX", (0, 0), (-1, -1), 1.5, GREEN),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def purple_box(title: str, body_paras: list[str]):
    rows = [[Paragraph(f"<b>{title}</b>", S["worked"])]]
    for b in body_paras:
        rows.append([Paragraph(b, S["worked"])])
    t = Table(rows, colWidths=[17 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PURPLE_BG),
                ("BOX", (0, 0), (-1, -1), 1.5, PURPLE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def orange_caution(text: str):
    t = Table(
        [[Paragraph(f"<b>CAUTION / EXAMINER TRAP — </b>{text}", S["caution"])]],
        colWidths=[17 * cm],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ORANGE_BG),
                ("BOX", (0, 0), (-1, -1), 1.5, ORANGE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def diagram(text: str, title: str = "DIAGRAM — practise redrawing"):
    rows = [
        [Paragraph(f"<b>{title}</b>", S["def_label"])],
        [Preformatted(text.rstrip("\n"), S["mono"])],
    ]
    t = Table(rows, colWidths=[17 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 1.2, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def grid(headers: list[str], rows: list[list[str]], orange=False):
    head_bg = ORANGE if orange else NAVY
    data = [[Paragraph(h, S["th"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(c, S["td"]) for c in row])
    n = len(headers)
    if n == 2:
        widths = [5.2 * cm, 11.8 * cm]
    elif n == 3:
        widths = [4.0 * cm, 6.5 * cm, 6.5 * cm]
    elif n == 4:
        widths = [3.4 * cm, 4.5 * cm, 4.5 * cm, 4.6 * cm]
    elif n == 5:
        widths = [2.8 * cm, 3.5 * cm, 3.5 * cm, 3.6 * cm, 3.6 * cm]
    else:
        widths = [17 * cm / n] * n
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), head_bg),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, NAVY_BG if not orange else ORANGE_BG],
                ),
            ]
        )
    )
    return t


def bullets(items: list[str], story: list):
    for i, t in enumerate(items, 1):
        story.append(Paragraph(f"{i}. {t}", S["bullet"]))


def four_points(title: str, items: list[str], story: list):
    story.append(Paragraph(f"<b>Four points examiners look for — {title}</b>", S["body"]))
    bullets(items, story)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#718096"))
    canvas.drawCentredString(
        A4[0] / 2,
        1.2 * cm,
        f"PharmTwinAI | Capstone Explanation Notes (Colour Teaching Pack) | Page {doc.page}",
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# MODULE BUILDERS
# ---------------------------------------------------------------------------


def module_0(story: list):
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("UNIVERSITY CAPSTONE · COMPUTER ENGINEERING", S["cover_sub"]))
    story.append(Paragraph("PharmTwinAI", S["cover_title"]))
    story.append(
        Paragraph(
            "AI-Powered Pharmacy Digital Twin — Colour Student Teaching Pack<br/>"
            "Modules 0–11 · Architecture · Formulae · Worked Numericals · Viva Bank",
            S["cover_sub"],
        )
    )
    story.append(
        Paragraph(
            "Industry context: Bhagyashree Medical (Juinagar, Navi Mumbai) — retail pharmacy operations<br/>"
            "DEV data mode: explicitly labeled <b>dev_synthetic</b> — NOT live sponsor POS sales<br/>"
            "Stack: Python tkinter desktop + MySQL 8 · Offline pipeline Steps 1–5 · services/ online layer",
            S["cover_sub"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    story.append(banner("MODULE 0 — COVER: COLOUR LEGEND, HOW TO STUDY, VIVA MARKING"))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("0.1 Colour pedagogy (same as MU PLM colour notes)", S["h1"]))
    story.append(
        grid(
            ["Colour", "What it marks", "How you should use it"],
            [
                [
                    "<b>Navy</b>",
                    "Module banners, section spine, table headers",
                    "Scan first — structural map of the pack",
                ],
                [
                    "<b>Crimson</b>",
                    "Definitions and key terms",
                    "Quote in viva / report; examiners look here first",
                ],
                [
                    "<b>Green</b>",
                    "Formulae and exact identities",
                    "Reproduce exactly — WMAPE, MASE, SS, ROP, cosine",
                ],
                [
                    "<b>Purple</b>",
                    "Worked numericals / mini examples",
                    "Practise end-to-end; easy viva points",
                ],
                [
                    "<b>Orange</b>",
                    "Comparison tables &amp; exam cautions",
                    "“Differentiate…” traps and common mistakes",
                ],
                [
                    "<b>Bordered panels</b>",
                    "ASCII flowcharts / architecture traces",
                    "Redraw in ~90 seconds in a demo or viva",
                ],
            ],
        )
    )

    story.append(Paragraph("0.2 How to study this pack (fresher plan)", S["h1"]))
    story.append(
        Paragraph(
            "Treat this like a laboratory teaching pack, not a novel. First pass: read every navy banner "
            "and every crimson definition box — that alone covers the viva vocabulary. Second pass: "
            "copy every green formula onto one A4 sheet (Module 9 has a summary page). Third pass: "
            "solve every purple numerical without looking, then check. Fourth pass: redraw the bordered "
            "diagrams from memory. Fifth pass: answer Module 10 viva hints out loud in 30–45 seconds each.",
            S["body"],
        )
    )
    story.append(
        grid(
            ["Day", "Focus", "Deliverable you should be able to produce"],
            [
                ["1", "Modules 0–2", "Twin definition + D1–D8 table + architecture redraw"],
                ["2", "Modules 3–4", "Catalog vs working stock + Croston/SBA/TSB + WMAPE/MASE"],
                ["3", "Module 5", "Three SS/ROP numericals + FEFO vs FIFO + sim policies"],
                ["4", "Modules 6–7", "Gate logic + every desktop page walkthrough"],
                ["5", "Modules 8–11", "Pipeline I/O + glossary + 40 viva Qs + limitations honesty"],
            ],
        )
    )

    story.append(Paragraph("0.3 Viva / evaluation marking scheme (what separates marks)", S["h1"]))
    four_points(
        "where marks separate",
        [
            "<b>Named methods</b> — Croston, SBA (Syntetos–Boylan), TSB (Teunter–Syntetos–Babai), "
            "LightGBM pinball quantiles, FEFO, TF-IDF cosine — say the full names once.",
            "<b>Green formulae written correctly</b> — WMAPE, MASE, SS, ROP, σ from quantiles, cosine. "
            "Wrong MAPE claim = automatic trap.",
            "<b>One concrete pharmacy example</b> — Navi Mumbai monsoon rain&gt;20 mm, PM2.5 winter, "
            "Schedule H1 register duty, FEFO near-expiry lot.",
            "<b>Honesty boundaries</b> — data is <b>dev_synthetic</b>; anemia screening is gated (D7); "
            "substitutes are pharmacist-reviewed not auto-prescribe (D4); env features are research (D5).",
        ],
        story,
    )
    story.append(
        grid(
            ["Band", "Typical evidence", "What goes wrong"],
            [
                ["High", "Formula + numerical + diagram + limitation sentence", "Overclaims rare"],
                ["Mid", "Correct vocabulary but no numerical / no diagram", "Vague “AI predicts demand”"],
                ["Low", "Calls twin a chatbot / claims real POS data / uses MAPE", "Examiner trap hit"],
            ],
            orange=True,
        )
    )

    story.append(Paragraph("0.4 What NOT to claim (honesty sheet)", S["h1"]))
    story.append(
        orange_caution(
            "Never claim synthetic DEV transactions are real Bhagyashree Medical POS sales. "
            "Never claim the system auto-prescribes or diagnoses. Never claim weather/PM2.5 "
            "causally proven on sponsor data (D5). Never mutate the ~253,973 reference catalog "
            "from the Inventory UI. Never use MAPE as the headline metric for intermittent demand."
        )
    )
    story.append(
        def_box(
            "Definition — What PharmTwinAI is (one sentence for cover / abstract)",
            "A desktop pharmacy digital twin that mirrors retail inventory and intermittent demand "
            "state in MySQL, forecasts with Croston-family and LightGBM quantiles (WMAPE/MASE), "
            "computes probabilistic safety stock and FEFO policies in isolated simulation, and "
            "suggests legally gated medicine substitutes for pharmacist review — using explicitly "
            "labeled synthetic DEV data until sponsor POS arrives.",
        )
    )
    story.append(Paragraph("0.5 Pack map (Modules 0–11)", S["h1"]))
    story.append(
        grid(
            ["Module", "Title", "Must-know artefact"],
            [
                ["0", "Cover / study / marking", "Colour legend + honesty sheet"],
                ["1", "Problem &amp; twin definition", "D1–D8 + twin vs dashboard table"],
                ["2", "Architecture", "UI→services→DB path + folder map"],
                ["3", "Data foundation", "253,973 vs ~3,000 + clone flow"],
                ["4", "Forecasting", "Croston/SBA/TSB steps + WMAPE/MASE"],
                ["5", "Inventory science", "SS/ROP numericals + FEFO + sim"],
                ["6", "Substitutes", "TF-IDF + H1/AWaRe/CDSCO gates"],
                ["7", "Desktop &amp; ops", "Every page + failure modes"],
                ["8", "Pipeline Steps 1–5", "Diagram + outputs per step"],
                ["9", "Glossary &amp; formula sheet", "Large glossary + green summary"],
                ["10", "Viva bank (40+)", "Short model-answer hints"],
                ["11", "Limitations &amp; ethics", "D7 anemia gate + future work"],
            ],
        )
    )
    story.append(PageBreak())


def module_1(story: list):
    story.append(banner("MODULE 1 — PROBLEM &amp; DIGITAL TWIN DEFINITION"))
    story.append(Paragraph("1.1 Why a retail pharmacy needs this system", S["h1"]))
    story.append(
        Paragraph(
            "A neighbourhood medical store (example context: Bhagyashree Medical, Juinagar, Navi Mumbai) "
            "faces four recurring operational pains: (a) intermittent SKU demand — many weeks with zero "
            "sales then a spike; (b) dated lots that expire and become waste if picked poorly; "
            "(c) stockouts that lose sales and push patients elsewhere; (d) pressure to suggest an "
            "alternative when a brand is out, without breaking Schedule H1 / antibiotic stewardship / "
            "banned FDC rules. Classic “dashboard-only” software shows yesterday’s numbers but does not "
            "hold a what-if twin, probabilistic buffers, or gated substitutes.",
            S["body"],
        )
    )
    story.append(
        def_box(
            "Definition — Pharmacy Digital Twin (PharmTwinAI)",
            "A living software mirror of a retail pharmacy’s inventory, demand and decision state — "
            "kept in sync with operational data (MySQL), able to forecast intermittent sales, recommend "
            "reorders with explainable safety stock, run what-if simulations without touching live stock, "
            "and suggest legally gated medicine substitutes for pharmacist review.",
        )
    )
    four_points(
        "unpacking the twin definition",
        [
            "<b>Business system, not a chatbot.</b> Inventory truth + forecasts + policy simulation.",
            "<b>Entire stock lifecycle of lots</b> — receipt, sale, expiry write-off, reorder — not just a drug list.",
            "<b>Manages information and decisions</b> about stock, not clinical diagnosis.",
            "<b>Regulatory gates on substitutes</b> — Schedule H1 / WHO AWaRe / CDSCO — human pharmacist remains in the loop.",
        ],
        story,
    )

    story.append(Paragraph("1.2 Stakeholders and what each needs", S["h1"]))
    story.append(
        grid(
            ["Stakeholder", "Need", "How PharmTwinAI addresses it"],
            [
                ["Retail pharmacist", "Know what to reorder &amp; what expires", "Recs + alerts + FEFO lots"],
                ["Store owner", "Reduce waste &amp; stockouts", "Policy sim fill-rate / waste KPIs"],
                ["Project team / college", "Reproducible offline science", "Steps 1–5 scripts + metrics"],
                ["Industry sponsor", "Safe demo without live POS leak", "dev_synthetic label + D3"],
                ["Examiner / viva panel", "Named methods + honesty", "This pack + acceptance checks"],
                ["Patient (indirect)", "Availability + legal dispensing", "Stockouts→substitutes review UI"],
            ],
        )
    )

    story.append(Paragraph("1.3 Scope — in vs out", S["h1"]))
    story.append(
        grid(
            ["In scope (built / demoable)", "Out of scope / gated"],
            [
                [
                    "Desktop twin UI, MySQL stock, Steps 1–5 offline pipeline, intermittent FC, "
                    "SS/ROP, FEFO sims, gated substitutes, inventory clone CRUD",
                    "Live sponsor POS ingest (until export), clinical diagnosis, auto-prescribe, "
                    "paid cloud deploy (D6), anemia screening product (D7), other screening (D8)",
                ],
            ],
            orange=True,
        )
    )

    story.append(Paragraph("1.4 Locked design decisions D1–D8 (memorise with reasons)", S["h1"]))
    story.append(
        Paragraph(
            "These are project locks documented in <b>docs/decisions_locked.md</b>. In a viva, "
            "naming the ID (D2, D3…) plus a one-line reason scores higher than vague “we chose desktop”.",
            S["body"],
        )
    )
    story.append(
        grid(
            ["ID", "Decision", "Explanation / viva reason"],
            [
                [
                    "D1",
                    "Evolve in place under Agent/; restructure into app/, db/, services/",
                    "Keep one repo; clear layers for UI / schema / business logic",
                ],
                [
                    "D2",
                    "Native desktop app (tkinter now; PySide6 optional later) — not Streamlit-first",
                    "Pharmacy software culture expects an installable desktop tool",
                ],
                [
                    "D3",
                    "No sponsor export yet → build explicitly labeled synthetic data",
                    "Academic honesty + NDA; banner shows SYNTHETIC DEV DATA",
                ],
                [
                    "D4",
                    "Pharmacist-reviewed inventory alternatives only (gated)",
                    "Not clinical auto-prescribe; human remains accountable",
                ],
                [
                    "D5",
                    "Weather / epi covariates = research/DEV until proven on real sales",
                    "Do not overclaim causality from monsoon/PM2.5 features",
                ],
                [
                    "D6",
                    "Local / college lab only (no paid cloud for ~6 months)",
                    "Cost and data-control constraint",
                ],
                [
                    "D7",
                    "Anemia: research docs only; no product implementation until core acceptance",
                    "Scope control — core twin must land first",
                ],
                [
                    "D8",
                    "Other screening: research-only until per-condition approval",
                    "Avoid feature creep into clinical product claims",
                ],
            ],
        )
    )
    story.append(
        orange_caution(
            "If asked “is this an anemia detection project?” — answer No for the shipped product (D7). "
            "Core acceptance is inventory twin + forecast + FEFO + gated substitutes."
        )
    )

    story.append(Paragraph("1.5 Goals mapped to features", S["h1"]))
    story.append(
        grid(
            ["Goal", "In plain words", "Feature in PharmTwinAI"],
            [
                ["Stock truth", "What is on the shelf; which lot dies first?", "Inventory + FEFO lots"],
                [
                    "Demand foresight",
                    "How many units next week under uncertainty?",
                    "Croston/SBA/TSB + LightGBM q50/q90/q95",
                ],
                ["Reorder science", "How much buffer against lead-time risk?", "SS = Z·σ·√(L+R), ROP"],
                ["Safe experimentation", "What if demand ×1.2 in monsoon?", "Isolated simulations"],
                ["Stockout recovery", "What else can we dispense legally?", "TF-IDF substitutes + gates"],
            ],
        )
    )

    story.append(Paragraph("1.6 Comparison — Digital twin vs dashboard vs plain inventory software", S["h1"]))
    story.append(
        grid(
            ["Basis", "Plain inventory SW", "Analytics dashboard", "PharmTwinAI digital twin"],
            [
                ["State mirror", "Current stock list", "Charts of past KPIs", "Stock + demand + decision state"],
                ["Forecasting", "Rare / manual", "Maybe external BI", "Built-in intermittent + quantiles"],
                ["What-if", "Usually none", "Filters only", "Cloned sim; live stock untouched"],
                ["Safety stock science", "Rule-of-thumb", "Hidden in spreadsheet", "Explainable SS/ROP in recs"],
                ["Substitutes", "Staff memory", "None", "TF-IDF + H1/AWaRe/CDSCO gates"],
                ["Data honesty", "Live POS assumed", "Live POS assumed", "dev_synthetic labeled (D3)"],
            ],
            orange=True,
        )
    )
    story.append(
        def_box(
            "Definition — Twin isolation invariant",
            "A simulation or what-if run must never mutate live medicine_batches quantities. "
            "The project fingerprints SUM(qty_on_hand) before/after; if it changes, isolation is broken.",
        )
    )
    story.append(PageBreak())


def module_2(story: list):
    story.append(banner("MODULE 2 — SYSTEM ARCHITECTURE"))
    story.append(Paragraph("2.1 Full stack at a glance", S["h1"]))
    story.append(
        Paragraph(
            "PharmTwinAI splits into an <b>offline science pipeline</b> (Steps 1–5 under src/ + scripts/) "
            "that writes CSV/Parquet under data/processed/, and an <b>online desktop twin</b> "
            "(app/main.py + services/) that reads/writes MySQL database <b>pharmtwinai</b>. "
            "Heavy LightGBM training stays offline; the UI never trains models live.",
            S["body"],
        )
    )
    story.append(
        diagram(
            """
  INPUTS                         CORE (Digital Twin)                    OUTPUTS
 +------------------+           +------------------------+           +------------------+
 | MySQL pharmtwinai|           | Inventory working state|           | Desktop Overview |
 | Catalog ~253,973 |  -------> | Forecast + SS/ROP      |  -------> | Inventory CRUD   |
 | Synthetic sales  |           | Isolated simulations   |           | Forecasts / Recs |
 | Env covariates*  |           | Gated substitutes      |           | Alerts / Sims    |
 +------------------+           +------------------------+           +------------------+
  * DEV/research only (D5)         never write live stock from sims     Substitutes UI
""",
            "Architecture trace — Inputs → Twin → Desktop outputs",
        )
    )

    story.append(Paragraph("2.2 Technology stack with fresher rationale", S["h1"]))
    story.append(
        grid(
            ["Layer", "Choice", "Fresher rationale"],
            [
                ["DB", "MySQL 8 localhost", "ACID stock + sales; familiar college stack"],
                ["UI", "Python tkinter desktop (D2)", "Installable; pharmacy-software expectation"],
                ["Services", "services/*.py in-process", "UI calls Python helpers; no separate API server required"],
                ["Science", "src/ offline Steps 1–5", "Reproducible ML; seed=42 default"],
                ["Models", "LightGBM quantile regressors", "q50 point + q90/q95 for σ"],
                ["NLP", "sklearn TF-IDF + cosine", "Composition text similarity for substitutes"],
                ["Config", ".env + app_meta", "DB password; data_mode=dev_synthetic"],
            ],
        )
    )

    story.append(Paragraph("2.3 Offline vs online split", S["h1"]))
    story.append(
        grid(
            ["Concern", "Offline (scripts/src)", "Online (app/services/MySQL)"],
            [
                ["Train LightGBM", "Yes (Step 3)", "No — reads forecasts table"],
                ["Generate synthetic Tx", "Yes (Step 1)", "No"],
                ["Edit working stock", "Seed only", "Yes — inventory_write guards"],
                ["Run FEFO policy grid", "Yes (Step 4)", "Import cached / what-if clone"],
                ["Substitute gates", "Step 5 audit CSVs", "Live lookup in Substitutes page"],
            ],
            orange=True,
        )
    )

    story.append(Paragraph("2.4 Request path — UI → services → DB", S["h1"]))
    story.append(
        diagram(
            """
 [ttk Page in app/main.py]
        |  user clicks Refresh / Add lot / Lookup substitute
        v
 [services/*.py]  -- SQL / business rules -->  [MySQL pharmtwinai]
        |                                         |
        |  e.g. inventory_write.add_medicine()     |  medicines, medicine_batches,
        |       forecasts.list_forecasts()         |  forecasts, recommendations,
        |       substitutes.suggest()              |  alerts, simulation_runs, ...
        v                                         v
 [UI table / messagebox]                    [inventory_audit on mutations]
""",
            "Request path redraw",
        )
    )
    story.append(
        Paragraph(
            "There is no separate REST microservice in the default demo. The desktop process imports "
            "services modules directly. That simplifies college-lab install (D6) but means the PC "
            "running the UI must reach localhost MySQL.",
            S["body"],
        )
    )

    story.append(Paragraph("2.5 MySQL main tables — what each holds", S["h1"]))
    story.append(
        grid(
            ["Table", "Purpose", "Exam one-liner"],
            [
                ["medicines", "Catalog + working SKUs", "source_system separates reference vs shelf"],
                ["medicine_batches", "Lots with qty/mfg/expiry", "FEFO picks earliest expiry"],
                ["sales_transactions / sales_items", "Tx header + lines", "unmet_qty captures stockout demand"],
                ["forecasts", "yhat / bounds / model", "Loaded by load_analytics from Step 3"],
                ["recommendations", "REORDER etc + SS fields", "explanation_text shows formula"],
                ["simulation_runs / results", "What-if metadata + KPIs", "Must not touch batches"],
                ["alerts", "LOW_STOCK / EXPIRY…", "Near-expiry ≤90d typical"],
                ["inventory_audit", "ADD/REMOVE trail", "Migration 002"],
                ["app_meta", "data_mode flag", "dev_synthetic banner"],
                ["digital_twin_snapshots", "Sync hash / state_json", "Staleness signal"],
            ],
        )
    )

    story.append(Paragraph("2.6 Folder map — purpose of major paths", S["h1"]))
    story.append(
        grid(
            ["Path", "Role"],
            [
                ["src/", "Catalog, covariates, Croston/SBA/TSB, LightGBM, FEFO, substitutes, regulatory"],
                ["services/", "Twin summary, inventory R/W, forecasts, alerts, simulations, substitutes"],
                ["app/main.py", "Desktop navigation pages (Overview…Settings)"],
                ["db/migrations/", "001 schema; 002 form_type/qty_unit/pharmacy/audit"],
                ["scripts/", "run_step1..5, seed_mysql, load_analytics, snapshot_originals, migrate, demo"],
                ["data/originals/", "Frozen pipeline copies — do not edit"],
                ["data/processed/", "Working pipeline outputs (overwriteable)"],
                ["docs/", "architecture, decisions_locked, acceptance_checklist, data dictionary"],
            ],
        )
    )

    story.append(Paragraph("2.6.1 Important src/ files (name in viva)", S["h2"]))
    story.append(
        grid(
            ["File", "Purpose"],
            [
                ["src/catalog.py", "Dedupe India A–Z catalog; stratified assortment sampling"],
                ["src/generate_transactions.py", "Step 1 synthetic intermittent sales + batches"],
                ["src/forecast_intermittent.py", "Croston, SBA, TSB, moving average"],
                ["src/metrics.py", "WMAPE, MASE (MAPE excluded on purpose)"],
                ["src/forecast_env_lgbm.py", "LightGBM quantile q50/q90/q95"],
                ["src/safety_stock.py", "σ from quantiles; SS; ROP; order-up-to"],
                ["src/inventory_fefo.py", "FEFO/FIFO allocate; OTC markdown tiers"],
                ["src/substitutes_nlp.py", "TF-IDF engine + gate pipeline"],
                ["src/regulatory/*.py", "Schedule H1, WHO AWaRe, CDSCO banned FDC"],
            ],
        )
    )

    story.append(Paragraph("2.6.2 Important services/ files", S["h2"]))
    story.append(
        grid(
            ["File", "Purpose"],
            [
                ["services/db.py", "MySQL connect from .env; probe"],
                ["services/twin.py", "Catalog vs stocked counts; data_mode banner"],
                ["services/inventory.py", "List stocked medicines / lots"],
                ["services/inventory_write.py", "Guarded add/remove; block reference mutation"],
                ["services/forecasts.py", "Read forecasts table"],
                ["services/recommendations.py", "Reorder recommendations"],
                ["services/alerts.py", "Expiry / low-stock alerts"],
                ["services/simulations.py", "Cached Step 4 import; what-if; isolation"],
                ["services/substitutes.py", "Live gated substitute lookup"],
            ],
        )
    )

    story.append(
        orange_caution(
            "Do not tell the examiner that Streamlit is the primary UI. D2 locks desktop-first. "
            "Streamlit may appear in older notes as a rejected option."
        )
    )
    story.append(PageBreak())


def module_3(story: list):
    story.append(banner("MODULE 3 — DATA FOUNDATION"))
    story.append(Paragraph("3.1 Three layers of “medicine data”", S["h1"]))
    story.append(
        def_box(
            "Definition — Reference catalog vs working inventory vs DEV synthetic sales",
            "The India medicines knowledge base (~253,973 deduped SKUs, source_system='reference') "
            "is immutable. The pharmacy’s sellable shelf is a separate working set "
            "(source_system ∈ {dev_synthetic, pharmacy, sponsor}) with lots carrying quantity, "
            "manufacturing date and expiry. Sales used in DEV are generated synthetically and "
            "labeled — they are not Bhagyashree POS exports.",
        )
    )
    story.append(
        grid(
            ["Store", "Approx. size", "Mutable?", "Purpose"],
            [
                ["reference medicines", "~253,973", "NO", "Search / clone / NLP knowledge"],
                ["working medicines", "~3,000", "YES", "Shelf assortment"],
                ["medicine_batches", "thousands", "YES*", "Qty + mfg + expiry (*working meds only)"],
                ["sales_* (DEV)", "~254k Tx header scale", "seeded", "Intermittent demand + unmet_qty"],
                ["data/originals/", "file snapshot", "NO", "Integrity freeze of pipeline inputs"],
            ],
            orange=True,
        )
    )

    story.append(Paragraph("3.2 Kaggle / India A–Z → dedupe → assortment", S["h1"]))
    story.append(
        Paragraph(
            "External catalog path (not committed in the git repo): an Extensive A–Z medicines dataset "
            "of India (~2.5L+ rows). Step 1 loads and dedupes to <b>253,973</b> unique reference SKUs "
            "(catalog_deduped.parquet). Then stratified sampling by demand cohort / therapeutic tags "
            "builds an active retail assortment of <b>~3,000</b> SKUs (assortment_3k.csv). "
            "Cohorts matter because intermittent slow-movers dominate pharmacy shelves; sampling must "
            "not keep only fast movers.",
            S["body"],
        )
    )
    story.append(
        diagram(
            """
 [India A-Z CSV ~2.5L+]
        |  load + normalize names/composition keys
        v
 [catalog_deduped.parquet]  -------- 253,973 reference SKUs
        |  stratified sample by cohort / class
        v
 [assortment_3k.csv]  -------------- ~3,000 working SKUs
        |  + covariates_navi_mumbai + Bernoulli/Poisson sales process
        v
 [transactions_synthetic + batches_fefo] --> seed_mysql (reference + working)
""",
            "Catalog → assortment → synthetic Tx",
        )
    )

    story.append(Paragraph("3.3 Synthetic transaction generation idea", S["h1"]))
    story.append(
        Paragraph(
            "Retail pharmacy demand is intermittent: most SKU–days are zero. The generator (Step 1) "
            "builds a daily panel conditioned on covariates (day-of-week, monsoon rain flags, "
            "PM2.5 spikes, health-alert flags) and SKU cohort. Conceptually: a Bernoulli (or sparse "
            "point-process) draw decides whether a demand event occurs; conditional on an event, a "
            "Poisson (or similar count) draw decides units. When on-hand is insufficient, unmet "
            "demand is recorded (unmet_qty) so forecasting trains on latent demand, not only fulfilled sales.",
            S["body"],
        )
    )
    four_points(
        "synthetic data honesty",
        [
            "Always say <b>dev_synthetic</b> — never “our pharmacy’s real sales”.",
            "Purpose: unblock ML + UI until sponsor POS export arrives (D3).",
            "Seed default 42 → reproducible demos / acceptance.",
            "Covariates are Navi Mumbai–style synthetic weather/epi series for research features (D5).",
        ],
        story,
    )

    story.append(Paragraph("3.4 Batches and FEFO fields", S["h1"]))
    story.append(
        grid(
            ["Field", "Meaning", "Why FEFO needs it"],
            [
                ["batch_no", "Lot identifier", "Traceability"],
                ["mfg_date", "Manufacturing date", "Secondary sort / audits"],
                ["expiry_date", "Use-before date", "Primary FEFO sort key"],
                ["qty_on_hand", "Sellable units in lot", "Allocation depletes this"],
                ["unit_cost", "Cost basis", "COGS / waste valuation in sim"],
                ["qty_unit", "TABLETS/ML/…", "Display + form consistency (002)"],
                ["received_at", "Receipt timestamp", "FIFO sort key"],
            ],
        )
    )

    story.append(Paragraph("3.5 form_type and qty_unit", S["h1"]))
    story.append(
        grid(
            ["Form (type)", "Default qty unit", "Quantity means"],
            [
                ["TABLET / CAPSULE", "TABLETS / CAPSULES", "Count of units"],
                ["SYRUP / DROPS", "ML", "Volume"],
                ["INJECTION", "VIALS", "Number of vials/amps"],
                ["CREAM / INHALER", "UNITS / PACKS", "Pack count"],
            ],
        )
    )
    story.append(
        Paragraph(
            "Migration 002 adds form_type, qty_unit, cloned_from_medicine_id on medicines, "
            "qty_unit on batches, pharmacy in source_system enum, and inventory_audit. "
            "Apply with: py -3 scripts/apply_migration_002.py",
            S["small"],
        )
    )

    story.append(Paragraph("3.6 Clone flow — add from catalog without mutating reference", S["h1"]))
    story.append(
        diagram(
            """
 Add-from-catalog (safe clone):
   [Search reference] --copy fields--> [INSERT pharmacy/dev_synthetic medicine]
         |                                      |
         |                                      +--> [INSERT lot: qty, mfg, expiry]
         |
         +---- NEVER UPDATE/DELETE reference row ----+
               InventoryGuardError if attempted
""",
            "Working-copy add flow",
        )
    )
    story.append(
        orange_caution(
            "Inventory “Add medicine” CLONES from catalog into a new working row. "
            "Deleting or editing a reference row is blocked. Favourite viva trap."
        )
    )

    story.append(Paragraph("3.7 Originals snapshot", S["h1"]))
    story.append(
        Paragraph(
            "scripts/snapshot_originals.py copies critical processed artefacts into data/originals/ "
            "as a frozen integrity baseline. Students / demos should not hand-edit originals. "
            "Use --force only when intentionally refreshing the freeze after a deliberate re-pipeline.",
            S["body"],
        )
    )

    story.append(Paragraph("3.8 Schema fields students should recognise", S["h1"]))
    story.append(Paragraph("3.8.1 medicines (selected)", S["h2"]))
    story.append(
        grid(
            ["Field", "Notes"],
            [
                ["medicine_id", "PK"],
                ["name / generic_name", "Display + search"],
                ["rx_schedule", "OTC / H / H1 / X / UNKNOWN"],
                ["demand_cohort", "Sampling / metrics slices"],
                ["source_system", "reference | dev_synthetic | pharmacy | sponsor"],
                ["form_type / qty_unit", "Added in 002"],
                ["cloned_from_medicine_id", "Lineage to reference"],
                ["unit_mrp", "Pricing display / markdown base"],
            ],
        )
    )
    story.append(Paragraph("3.8.2 forecasts / recommendations / simulation_runs", S["h2"]))
    story.append(
        grid(
            ["Table.field", "Meaning"],
            [
                ["forecasts.yhat / yhat_lower / yhat_upper", "Point and interval-ish bounds"],
                ["forecasts.model_name", "e.g. lgbm_env / sba"],
                ["forecasts.metrics_json", "WMAPE/MASE crumbs"],
                ["recommendations.action_type", "REORDER / HOLD / REVIEW_EXPIRY / …"],
                ["recommendations.safety_stock / reorder_point", "From SS maths"],
                ["recommendations.explanation_text", "Human-readable formula narrative"],
                ["simulation_runs.scenario_json", "What-if knobs"],
                ["simulation_results.metrics_json", "Fill rate, waste, etc."],
            ],
        )
    )
    story.append(PageBreak())


def module_4(story: list):
    story.append(banner("MODULE 4 — INTERMITTENT DEMAND FORECASTING"))
    story.append(Paragraph("4.1 Why pharmacy demand is intermittent", S["h1"]))
    story.append(
        def_box(
            "Definition — Intermittent demand",
            "A demand series with many zeros (no sale that week) and occasional positive spikes. "
            "Typical of slow-moving pharmacy SKUs. Classic MAPE fails because division by zero "
            "(or near-zero) actuals is undefined / explosive.",
        )
    )
    story.append(
        Paragraph(
            "In a 3,000-SKU neighbourhood assortment, antibiotics and chronic meds may move weekly, "
            "but many dermatology / specialty packs sit idle for weeks. Forecasting must (1) model "
            "the probability of a non-zero week and (2) model the size when demand occurs. "
            "That is exactly why Croston-style methods exist.",
            S["body"],
        )
    )

    story.append(Paragraph("4.2 ADI / CV² demand patterns (Syntetos–Boylan)", S["h1"]))
    story.append(
        Paragraph(
            "Average Demand Interval (ADI) measures how many periods between non-zero demands. "
            "CV² is the squared coefficient of variation of demand sizes. Crossing literature "
            "thresholds (commonly ADI=1.32 and CV²=0.49 in the classic SB classification) yields "
            "four patterns. PharmTwinAI reports metrics by pattern slice so a method that “wins overall” "
            "is not hiding failure on lumpy SKUs.",
            S["body"],
        )
    )
    story.append(
        grid(
            ["Pattern", "ADI &amp; CV² idea", "Why slice metrics", "Method intuition"],
            [
                ["Smooth", "Frequent demand, steady size", "Easier baselines", "MA can compete"],
                ["Erratic", "Frequent, wild sizes", "Variance-driven error", "Quantiles help tails"],
                ["Intermittent", "Long gaps, steady size", "Croston family shines", "SBA/TSB strong"],
                ["Lumpy", "Long gaps + wild sizes", "Hardest; report separately", "Expect higher WMAPE"],
            ],
            orange=True,
        )
    )

    story.append(Paragraph("4.3 Croston — step-by-step", S["h1"]))
    story.append(
        Paragraph(
            "Croston (1972 idea family): do not smooth the raw zero-inflated series as if it were "
            "continuous. Instead maintain two smoothed states updated only when demand occurs.",
            S["body"],
        )
    )
    story.append(
        diagram(
            """
 On non-zero demand at time t (size y_t, periods since last demand = q):
   z_t = z_{t-1} + α (y_t - z_{t-1})     # smoothed demand size
   p_t = p_{t-1} + α (q - p_{t-1})       # smoothed inter-demand interval
 Forecast for next period:  yhat = z_t / p_t
 On zero demand: do not update z,p; still emit yhat = z/p
""",
            "Croston update sketch",
        )
    )
    story.append(
        green_formula(
            ["Croston point forecast:  ŷ = z / p"],
            "z = smoothed demand size; p = smoothed interval between demands; α typically small (e.g. 0.1).",
        )
    )

    story.append(Paragraph("4.4 SBA — Syntetos–Boylan Approximation", S["h1"]))
    story.append(
        Paragraph(
            "Croston’s ŷ = z/p is known to be positively biased for intermittent series. "
            "Syntetos–Boylan Approximation applies a correction factor using the same α:",
            S["body"],
        )
    )
    story.append(
        green_formula(
            ["SBA:  ŷ = (1 − α/2) × (z / p)"],
            "Same z,p updates as Croston; multiply by (1 − α/2). Implemented in src/forecast_intermittent.py.",
        )
    )

    story.append(Paragraph("4.5 TSB — Teunter–Syntetos–Babai", S["h1"]))
    story.append(
        Paragraph(
            "TSB updates a demand <b>probability</b> π every period (including zeros), and a size z "
            "on positive demands. Forecast = π × z. This reacts faster after long zero runs because "
            "π decays toward zero when no demand arrives.",
            S["body"],
        )
    )
    story.append(
        diagram(
            """
 Each period:
   if y_t > 0:  z <- z + α_size (y_t - z)
                π <- π + α_prob (1 - π)
   else:        π <- π + α_prob (0 - π)     # probability decays
                z unchanged
   ŷ = π * z
""",
            "TSB update sketch",
        )
    )

    story.append(Paragraph("4.6 Moving average baseline", S["h1"]))
    story.append(
        Paragraph(
            "Trailing mean over a fixed window (project uses an 8-week style MA). Simple, transparent, "
            "often surprisingly competitive on smooth SKUs, weak on long zero gaps (it smears zeros "
            "and spikes together).",
            S["body"],
        )
    )

    story.append(Paragraph("4.7 Mandatory metrics — WMAPE and MASE", S["h1"]))
    story.append(
        green_formula(
            [
                "WMAPE  =  Σ | y − ŷ |   /   Σ | y |",
                "MASE   =  mean(|y − ŷ|)  /  mean(|y_t − y_{t−1}|)   [naive seasonal/lag-1 scale]",
            ],
            "Project rule: evaluate with WMAPE and MASE only — never MAPE on intermittent retail series. "
            "Demand y includes unmet_qty so stockouts do not hide true demand.",
        )
    )
    story.append(
        Paragraph(
            "WMAPE weights errors by total absolute demand — a miss on a high-volume week hurts more "
            "than on a tiny week, and zeros in the denominator of classical MAPE are avoided because "
            "the denominator is the sum across the evaluation window. MASE scales error by a naive "
            "benchmark (lag-1 absolute changes), so a score &lt; 1 means “better than naive”.",
            S["body"],
        )
    )

    story.append(Paragraph("4.8 Why MAPE fails — purple numerical", S["h1"]))
    story.append(
        purple_box(
            "WORKED NUMERICAL — MAPE blow-up on intermittent demand",
            [
                "Week demands y = [0, 0, 0, 10]. Forecasts ŷ = [1, 1, 1, 8].",
                "Classical MAPE averages |y−ŷ|/|y| only on weeks with y≠0, or worse, tries to divide by y=0.",
                "If someone naively uses ε=0.01 instead of 0 for zeros: "
                "errors ≈ |0−1|/0.01 = 100 (×3 weeks) + |10−8|/10 = 0.2 → absurd “MAPE”.",
                "WMAPE = (|0−1|+|0−1|+|0−1|+|10−8|) / (0+0+0+10) = (1+1+1+2)/10 = 0.50 (50%).",
                "Moral: report WMAPE/MASE; never headline MAPE for this project.",
            ],
        )
    )
    story.append(
        orange_caution(
            "Examiner trap: “Why not MAPE?” — Answer: zeros make MAPE undefined/unstable; "
            "project metrics module intentionally excludes MAPE."
        )
    )

    story.append(Paragraph("4.9 Train / test weekly panel", S["h1"]))
    story.append(
        Paragraph(
            "Step 2/3 build a dense weekly panel (missing weeks filled with zero demand). "
            "Default split ~75% train / 25% test by time (not random SKU shuffle — that would leak future). "
            "Rolling one-step-ahead evaluation is used for intermittent baselines. "
            "Demand definition: qty + unmet_qty.",
            S["body"],
        )
    )
    story.append(
        diagram(
            """
 Daily sales_items (qty, unmet_qty)
        |  aggregate to week per medicine_id
        v
 Dense weekly panel (zeros filled)
        |  time split ~75/25
        v
 Train intermittent / LGBM --> score WMAPE+MASE on test weeks
        |
        +--> step2_*.csv / step3_forecasts_weekly.parquet
""",
            "Weekly panel flow",
        )
    )

    story.append(Paragraph("4.10 LightGBM quantile / pinball loss", S["h1"]))
    story.append(
        def_box(
            "Definition — Pinball (quantile) loss",
            "A loss that asymmetrically penalises over- vs under-prediction so the model converges "
            "to a conditional quantile (e.g. 0.5, 0.9, 0.95) rather than only the mean.",
        )
    )
    story.append(
        Paragraph(
            "PharmTwinAI trains three LightGBM regressors with objective='quantile' at α∈{0.5,0.9,0.95}. "
            "q50 is the planning point forecast; q90/q95 feed σ estimation for safety stock. "
            "Ablation: lgbm_env vs lgbm_noenv compares environmental features.",
            S["body"],
        )
    )

    story.append(Paragraph("4.11 Environmental features (D5 caution)", S["h1"]))
    story.append(
        grid(
            ["Feature family", "Example", "Intuition"],
            [
                ["Rainfall", "rain &gt; 20 mm day flag; 7/14-day lags", "Monsoon footfall / illness patterns"],
                ["Air quality", "PM2.5 spikes (winter)", "Respiratory OTC / related demand"],
                ["Health alerts", "civic alert flags", "Short bursts of related SKUs"],
                ["Calendar", "DOW / week-of-year", "Routine refill rhythms"],
                ["Demand lags", "lag-1..k weekly qty", "Autoregression backbone"],
            ],
        )
    )
    story.append(
        orange_caution(
            "D5: env covariates are research/DEV until validated on real sponsor sales. "
            "You may say “we engineered monsoon and PM2.5 features”; do NOT say “we proved rain causes sales”."
        )
    )

    story.append(Paragraph("4.12 Feature importance interpretation", S["h1"]))
    story.append(
        Paragraph(
            "Step 3 writes step3_feature_importance.csv. High importance on demand lags is expected. "
            "Non-trivial importance on rain/PM2.5 is interesting but not causal proof. "
            "In viva: “importance ≠ causation; D5 applies.”",
            S["body"],
        )
    )

    story.append(Paragraph("4.13 How results land in MySQL forecasts", S["h1"]))
    story.append(
        Paragraph(
            "After Steps 2–3, scripts/load_analytics.py (or full seed_mysql) inserts rows into "
            "forecasts with grain W, yhat from q50 (or chosen model), bounds from quantiles, "
            "model_name, trained_through, metrics_json. Desktop Forecasts page reads this table — "
            "it does not retrain.",
            S["body"],
        )
    )
    story.append(
        purple_box(
            "WORKED MINI-EXAMPLE — Reading a quantile forecast",
            [
                "Suppose for SKU A next week: q50 = 8, q90 = 18, q95 = 24 (units).",
                "Point forecast for planning ≈ 8. Upper stress ≈ 24.",
                "Rough σ from (q95−q50)/Z_0.95 ≈ (24−8)/1.645 ≈ 9.7 units "
                "(then blended with q90 spread in code — see Module 5).",
                "This σ feeds the safety-stock formula.",
            ],
        )
    )
    story.append(PageBreak())


def module_5(story: list):
    story.append(banner("MODULE 5 — INVENTORY SCIENCE (SS, ROP, FEFO, SIM)"))
    story.append(Paragraph("5.1 Service level → Z", S["h1"]))
    story.append(
        def_box(
            "Definition — Cycle service level &amp; Z",
            "Cycle service level is the target probability of not stocking out during a replenishment "
            "cycle. For a normal demand approximation, Z is the standard normal quantile of that "
            "probability. At 95%, Z ≈ 1.645.",
        )
    )
    story.append(
        green_formula(
            ["Z ≈ 1.645  for service level 95%"],
            "Configured in Step 4 defaults (--service-level 0.95). Higher service level → higher Z → more SS.",
        )
    )

    story.append(Paragraph("5.2 σ from quantile spreads", S["h1"]))
    story.append(
        green_formula(
            [
                "σ̂_q95 = (q95 − q50) / Z_0.95",
                "σ̂_q90 = (q90 − q50) / Z_0.90",
                "σ_weekly ≈ blend(σ̂_q95, σ̂_q90)   with floor ≈ 0.15 × μ",
            ],
            "Implemented in src/safety_stock.py. Blending two spreads is more stable than one noisy tail.",
        )
    )

    story.append(Paragraph("5.3 Core inventory formulae", S["h1"]))
    story.append(
        green_formula(
            [
                "SS   =  Z  ×  σ_LT  ×  √(L + R)",
                "ROP  =  μ × (L + R)  +  SS",
                "Order-up-to  ≈  ROP + review replenishment logic (see params CSV)",
            ],
            "L = lead time (weeks), R = review period (weeks). Defaults L=R=1. μ = mean weekly demand (avg q50).",
        )
    )
    story.append(
        grid(
            ["Symbol", "Meaning", "Typical DEV value"],
            [
                ["Z", "Normal z for cycle service level", "1.645 @ 95%"],
                ["σ_LT", "Demand uncertainty scale used with √(L+R)", "From q90/q95 vs q50"],
                ["L", "Supplier lead time", "1 week"],
                ["R", "Review period", "1 week"],
                ["μ", "Mean demand per week", "Avg q50"],
                ["SS", "Safety stock buffer", "Z·σ·√(L+R)"],
                ["ROP", "Reorder when inventory position ≤ ROP", "μ(L+R)+SS"],
            ],
        )
    )

    story.append(Paragraph("5.4 Worked numericals (practise all three)", S["h1"]))
    story.append(
        purple_box(
            "WORKED NUMERICAL 1 — Basic SS and ROP",
            [
                "Given: μ = 10 units/week, σ_LT = 4, L = 1, R = 1, service 95% (Z = 1.645).",
                "Cover weeks = L+R = 2.",
                "SS = 1.645 × 4 × √2 ≈ 1.645 × 4 × 1.414 ≈ 9.30 units.",
                "ROP = 10×2 + 9.30 = 29.30 → order when on-hand + on-order ≤ ~29.",
                "If on-hand = 12 and nothing on order → replenish toward order-up-to.",
            ],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        purple_box(
            "WORKED NUMERICAL 2 — σ from quantiles then SS",
            [
                "Given weekly quantiles: q50 = 12, q90 = 22, q95 = 28. Z_0.95 = 1.645, Z_0.90 ≈ 1.282.",
                "σ̂_q95 = (28−12)/1.645 ≈ 9.73;  σ̂_q90 = (22−12)/1.282 ≈ 7.80.",
                "Blend (simple average for hand calc): σ ≈ (9.73+7.80)/2 ≈ 8.77. Floor 0.15×12 = 1.8 (not binding).",
                "L=R=1, Z=1.645 → SS = 1.645 × 8.77 × √2 ≈ 1.645 × 8.77 × 1.414 ≈ 20.4.",
                "ROP = 12×2 + 20.4 = 44.4 units.",
            ],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        purple_box(
            "WORKED NUMERICAL 3 — Compare two service levels",
            [
                "Same μ=6, σ=3, L+R=2. Compare 90% (Z≈1.282) vs 95% (Z≈1.645).",
                "SS_90 = 1.282 × 3 × 1.414 ≈ 5.44;  ROP_90 = 12 + 5.44 = 17.44.",
                "SS_95 = 1.645 × 3 × 1.414 ≈ 6.98;  ROP_95 = 12 + 6.98 = 18.98.",
                "Lesson: higher service level buys fewer stockouts at the cost of more average inventory.",
                "In sim KPIs, watch fill rate up vs waste/holding pressure.",
            ],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        purple_box(
            "WORKED NUMERICAL 4 — Inventory position trigger",
            [
                "ROP = 40. On-hand = 25, on-order = 10 → inventory position = 35 ≤ 40 → place PO.",
                "If on-order were 20 → position = 45 &gt; 40 → do not double-order.",
                "FEFO does not change ROP maths; it changes which lots are depleted and expiry waste.",
            ],
        )
    )

    story.append(Paragraph("5.5 FEFO vs FIFO — deep comparison", S["h1"]))
    story.append(
        grid(
            ["Basis", "FIFO", "FEFO"],
            [
                ["Pick order", "Oldest receipt first", "Earliest expiry first"],
                ["Expiry waste", "Can leave near-expiry untouched", "Prioritises dying lots"],
                ["Pharmacy fit", "Generic warehouses / non-dated", "Medicines with dated lots"],
                ["Secondary key", "Often receipt only", "Expiry then receipt"],
                ["In project", "fifo_static baseline", "fefo_* policies in Step 4"],
                ["Risk if ignored", "Hidden expiry write-offs", "Slightly more complex picks"],
            ],
            orange=True,
        )
    )
    story.append(
        Paragraph(
            "In src/inventory_fefo.py, allocate_demand() sorts lots by the policy, depletes qty_on_hand, "
            "and returns sold, unmet, revenue, COGS, markdown discount. FEFO reduces expiry write-offs "
            "when multiple lots coexist — common after overlapping purchases.",
            S["body"],
        )
    )

    story.append(Paragraph("5.6 OTC markdown tiers", S["h1"]))
    story.append(
        grid(
            ["Days to expiry", "Markdown (OTC eligible)", "Notes"],
            [
                ["&gt; 90", "0%", "Full price"],
                ["61–90", "10%", "Early nudge"],
                ["31–60", "25%", "Clearance begins"],
                ["15–30", "40%", "Aggressive"],
                ["&lt; 15", "50%", "Last chance"],
                ["Rx / H1 / habit-forming", "0% auto", "No automatic clinical discounting"],
            ],
            orange=True,
        )
    )
    story.append(
        Paragraph(
            "Markdown applies only to eligible OTC classes (e.g. respiratory, pain analgesics, "
            "GI, vitamins, derma — as coded). Policy fefo_ss_markdown combines FEFO + SS reorder + "
            "these tiers and may uplift clearance demand in the simulator.",
            S["body"],
        )
    )

    story.append(Paragraph("5.7 Simulation loop", S["h1"]))
    story.append(
        diagram(
            """
 Weekly sim loop (cloned state — live DB untouched):
   1) receive any POs due this week
   2) write off expired lots (waste KPI)
   3) realise demand; allocate FEFO or FIFO
   4) record sold / unmet / revenue / markdown
   5) if inventory_position <= ROP: place PO arriving in L weeks
   6) advance week; repeat over test horizon
""",
            "FEFO simulation loop",
        )
    )

    story.append(Paragraph("5.8 Policy comparison — how to read results", S["h1"]))
    story.append(
        grid(
            ["Policy", "What it adds", "Typical DEV lesson"],
            [
                ["fifo_static", "FIFO + static / no dynamic SS reorder", "Baseline fill / waste"],
                ["fefo_static", "FEFO picks", "Small waste improvement"],
                ["fefo_ss", "FEFO + probabilistic SS/ROP", "Fill rate jumps"],
                ["fefo_ss_markdown", "OTC near-expiry discounts", "Best waste+fill combo (DEV)"],
            ],
        )
    )
    story.append(
        Paragraph(
            "Documented DEV ballpark from step4_summary style runs: fifo fill rate often ~mid-80%; "
            "fefo_ss / fefo_ss_markdown can reach ~mid-90% fill. Quote your own step4_summary.json "
            "in the report — do not invent new digits.",
            S["body"],
        )
    )
    story.append(
        def_box(
            "Definition — Fill rate",
            "Demand satisfied ÷ total demand (including unmet). Higher is better. "
            "Pair with waste/expiry KPIs — fill rate alone can hide overstock.",
        )
    )

    story.append(Paragraph("5.9 Isolation fingerprint", S["h1"]))
    story.append(
        orange_caution(
            "Simulations fingerprint SUM(qty_on_hand) before/after. If it changes, the twin isolation "
            "invariant is broken — automatic acceptance failure."
        )
    )

    story.append(Paragraph("5.10 Recommendations explanation text structure", S["h1"]))
    story.append(
        Paragraph(
            "Each REORDER recommendation typically carries: current_stock, forecast_demand, "
            "safety_stock, reorder_point, qty_suggested, and explanation_text that narrates the "
            "SS = Z·σ·√(L+R) assumption set (service level, L, R). In demo, open Recommendations "
            "and read the explanation aloud — that is free viva credit.",
            S["body"],
        )
    )
    story.append(PageBreak())


def module_6(story: list):
    story.append(banner("MODULE 6 — REGULATED SUBSTITUTE ENGINE"))
    story.append(
        def_box(
            "Definition — Pharmacist-reviewed substitute",
            "An inventory alternative ranked by composition/class similarity (TF-IDF + cosine), "
            "then filtered by Indian regulatory hard gates. Output is for pharmacist review — "
            "not automatic clinical prescribing (D4).",
        )
    )

    story.append(Paragraph("6.1 Explicit catalog substitutes vs TF-IDF", S["h1"]))
    story.append(
        grid(
            ["Path", "How it works", "When used"],
            [
                [
                    "Explicit",
                    "Catalog columns substitute0–substitute4 if in stock",
                    "Prefer when curated links exist",
                ],
                [
                    "TF-IDF fallback",
                    "Vectorise composition/chemical/therapeutic text; cosine rank",
                    "When explicit list empty / insufficient",
                ],
            ],
            orange=True,
        )
    )

    story.append(Paragraph("6.2 TF-IDF + cosine similarity", S["h1"]))
    story.append(
        green_formula(
            [
                "cosine(a,b)  =  (a · b)  /  ( ||a||  ||b|| )",
                "a,b = TF-IDF vectors of composition / class text",
            ],
            "Higher cosine ⇒ more similar salt / therapeutic tokens. Default min_cosine ≈ 0.55 in Step 5.",
        )
    )
    story.append(
        Paragraph(
            "TF (term frequency) upweights tokens that appear often in a medicine’s composition text; "
            "IDF downweights tokens that appear in almost every medicine (poor discriminators). "
            "Vectors are L2-normalised so cosine equals a simple dot product in the engine.",
            S["body"],
        )
    )

    story.append(Paragraph("6.3 Full gate logic", S["h1"]))
    story.append(
        diagram(
            """
 Query SKU
   -> gather explicit substitutes + TF-IDF neighbours
   -> keep in-stock candidates only
   -> GATE pipeline (any fail => block candidate or whole query):
        Schedule H1?  -> hard block + register/Rx notice
        AWaRe Watch/Reserve antibiotic path? -> block OTC auto-sub
        CDSCO banned FDC / discontinued? -> hard block
        Habit-forming flag? -> block
   -> return top-N allowed OR single H1 block message
   -> pharmacist reviews (D4) — system does not dispense
""",
            "Substitute pipeline",
        )
    )
    story.append(
        grid(
            ["Gate", "Action", "Fresher meaning"],
            [
                ["Schedule H1", "Hard block + notice", "Strict Rx; 3-year dispensing record duty"],
                ["AWaRe Access", "Allowed (stewardship-friendly)", "Prefer if antibiotic path"],
                ["AWaRe Watch/Reserve", "Block auto-sub", "Higher AMR risk"],
                ["CDSCO banned FDC", "Hard block", "Irrational / withdrawn combinations"],
                ["Discontinued", "Hard block", "Is_discontinued flag"],
                ["Habit forming", "Hard block", "No casual substitution"],
            ],
            orange=True,
        )
    )
    story.append(
        Paragraph(
            "Lists are curated project subsets for demo coverage — say that honestly in viva "
            "(see Module 11 limitations). WHO AWaRe and CDSCO are real frameworks; the embedded "
            "pattern tables are not the entire national database.",
            S["body"],
        )
    )

    story.append(Paragraph("6.4 Pharmacist-reviewed only (D4)", S["h1"]))
    four_points(
        "substitute ethics",
        [
            "UI label is Substitutes (review) — not “auto switch”.",
            "No dose/diagnosis logic — inventory alternatives only.",
            "H1 block must show educational notice, not a silent empty list.",
            "Final dispensing decision remains with the registered pharmacist.",
        ],
        story,
    )

    story.append(Paragraph("6.5 Worked example — blocked vs allowed", S["h1"]))
    story.append(
        purple_box(
            "WORKED EXAMPLE — Gate outcomes",
            [
                "Case A — Query is Schedule H1 antibiotic: engine returns HARD BLOCK with RMP Rx / "
                "register notice. Even high-cosine neighbours are not offered for auto-sub.",
                "Case B — Query is OTC vitamin, candidate same salts, cosine 0.78, in stock, "
                "not habit-forming, not banned FDC: ALLOWED → listed in top-N for pharmacist review.",
                "Case C — Candidate is WHO AWaRe Watch while query path requires stewardship gate: "
                "BLOCKED despite high cosine.",
                "Case D — Explicit substitute listed but out of stock: skipped; TF-IDF may fill.",
            ],
        )
    )

    story.append(Paragraph("6.6 Audit metrics meaning", S["h1"]))
    story.append(
        grid(
            ["Metric (Step 5)", "Meaning"],
            [
                ["n queries", "Stockout substitute lookups run in batch audit"],
                ["% with ≥1 allowed", "How often the engine finds a legal in-stock alt"],
                ["H1 fully blocked", "Queries where H1 gate stopped suggestions"],
                ["Flag counts H1/Watch/Reserve", "Assortment regulatory annotation volume"],
            ],
        )
    )
    story.append(
        Paragraph(
            "Example DEV summary style (quote your step5_summary.json): on the order of 200 queries, "
            "majority with ≥1 allowed substitute, dozens of H1 fully blocked — exact numbers come from "
            "your run artefacts, not from memory.",
            S["small"],
        )
    )
    story.append(PageBreak())


def module_7(story: list):
    story.append(banner("MODULE 7 — DESKTOP APPLICATION &amp; OPERATIONS"))
    story.append(Paragraph("7.1 Launch and navigation", S["h1"]))
    story.append(
        Paragraph(
            "Entry: py -3 scripts/run_desktop.py → app/main.py. Tkinter + ttk pages. "
            "Nav also exposes Set MySQL password, Seed database, Load analytics, Refresh Overview.",
            S["body"],
        )
    )

    story.append(Paragraph("7.2 Every page — what to demonstrate", S["h1"]))
    story.append(
        grid(
            ["Page", "Student must demonstrate", "Pass signal"],
            [
                [
                    "Overview / Twin",
                    "Catalog ~254k vs stocked ~3k; synthetic banner; twin sync",
                    "data_mode=dev_synthetic visible",
                ],
                [
                    "Inventory",
                    "Search working meds; FEFO lots; add clone; add/remove lot",
                    "Reference not editable",
                ],
                ["Forecasts", "Pick SKU → weekly yhat/q50/q95 from MySQL", "Rows present after load_analytics"],
                ["Recommendations", "Filter REORDER; read SS formula explanation", "explanation_text non-empty"],
                ["Alerts", "Near-expiry ≤90d, low stock", "Open alerts list"],
                ["Simulations", "Import cached Step 4 / what-if; stock unchanged", "Fingerprint OK"],
                ["Substitutes", "Allowed list OR H1 block message", "No auto-dispense claim"],
                ["Settings", "Password, seed, load analytics", "Probe succeeds"],
            ],
        )
    )

    story.append(Paragraph("7.3 Add / remove inventory fields", S["h1"]))
    story.append(
        grid(
            ["Action", "Key fields / behaviour"],
            [
                ["Add medicine (clone)", "Search reference → copy name/generic/schedule/form → new working row"],
                ["Add lot", "batch_no, mfg_date, expiry_date, qty_on_hand, qty_unit"],
                ["Remove lot / med", "Working sources only; audited; reference blocked"],
                ["Guard", "InventoryGuardError on reference mutation attempts"],
            ],
        )
    )

    story.append(Paragraph("7.4 Demo script / acceptance checks", S["h1"]))
    story.append(
        Paragraph(
            "py -3 scripts/run_demo_acceptance.py runs the automated checklist (documented as 21 checks "
            "in docs/acceptance_checklist.md). Manual walkthrough still required for UI clarity. "
            "Targets include catalog ≥ ~250k, stocked toward 3000, synthetic banner, sim isolation.",
            S["body"],
        )
    )

    story.append(Paragraph("7.5 Operator commands cheat sheet", S["h1"]))
    story.append(
        diagram(
            """
 cd e:\\MajorProject_4th_Yr\\Agent
 py -3 scripts/run_step1.py
 py -3 scripts/run_step2.py
 py -3 scripts/run_step3.py
 py -3 scripts/run_step4.py
 py -3 scripts/run_step5.py
 py -3 scripts/seed_mysql.py --apply-schema
 py -3 scripts/apply_migration_002.py
 py -3 scripts/load_analytics.py
 py -3 scripts/snapshot_originals.py
 py -3 scripts/run_demo_acceptance.py
 py -3 scripts/run_desktop.py
""",
            "Operator cheat sheet",
        )
    )

    story.append(Paragraph("7.6 Common failure modes", S["h1"]))
    story.append(
        grid(
            ["Symptom", "Likely cause", "Fix"],
            [
                ["DB connection fails", "Wrong MySQL password / server down", "Settings password; check service"],
                ["Empty forecasts page", "Analytics not loaded", "load_analytics.py after Steps 2–3"],
                ["Tiny catalog count", "Seed without schema/files", "run_step1 then seed --apply-schema"],
                ["Cannot edit medicine", "It is a reference row", "Clone to working stock first"],
                ["Substitutes empty", "Gates blocked or no stock", "Check H1 notice; verify lots"],
                ["Sim changes stock", "Isolation bug / wrong service", "Fail acceptance; do not demo"],
                ["ImportError / missing parquet", "Pipeline not run", "run_step1..5 in order"],
            ],
            orange=True,
        )
    )
    story.append(
        orange_caution(
            "Wrong MySQL password is the #1 lab-day failure. Missing load_analytics is #2 "
            "(seed alone may not refresh forecast/recommendation tables the way you expect)."
        )
    )
    story.append(PageBreak())


def module_8(story: list):
    story.append(banner("MODULE 8 — PIPELINE STEPS 1–5 END-TO-END"))
    story.append(Paragraph("8.0 Master pipeline diagram", S["h1"]))
    story.append(
        diagram(
            """
 Kaggle CSV -> catalog_deduped (~253,973) -> sample assortment (3,000)
                     |                         |
                     v                         v
              MySQL reference           Tx + batches + covariates
                                               |
                    Step2 baselines  <---------+
                    Step3 LightGBM quantiles
                    Step4 SS + FEFO policies
                    Step5 gated substitutes
                                               |
                                               v
                         seed_mysql + load_analytics + desktop
""",
            "Pipeline redraw for viva",
        )
    )

    story.append(Paragraph("8.1 Step 1 — Synthetic world build", S["h1"]))
    story.append(
        diagram(
            """
 run_step1.py -> src/generate_transactions.py
   IN:  India A-Z CSV
   OUT: catalog_deduped.parquet (~253,973)
        assortment_3k.csv (~3,000)
        covariates_navi_mumbai.csv
        transactions_synthetic.*
        batches_fefo.*
        step1_summary.json
""",
            "Step 1 I/O",
        )
    )
    story.append(
        Paragraph(
            "Also produces counts for days, transactions, units sold, stockout events, batches, revenue "
            "in step1_summary.json — cite that file rather than inventing figures.",
            S["body"],
        )
    )

    story.append(Paragraph("8.2 Step 2 — Intermittent baselines", S["h1"]))
    story.append(
        diagram(
            """
 run_step2.py -> src/run_forecast_eval.py
   Methods: croston, sba, tsb, ma
   Metrics: WMAPE, MASE (+ pattern slices)
   OUT: step2_metrics_by_sku.csv
        step2_metrics_summary.csv
        step2_forecasts_weekly.*
        step2_summary.json
""",
            "Step 2 I/O",
        )
    )

    story.append(Paragraph("8.3 Step 3 — LightGBM quantiles + env ablation", S["h1"]))
    story.append(
        diagram(
            """
 run_step3.py -> src/run_env_forecast.py
   Models: lgbm_env & lgbm_noenv @ q50/q90/q95
   OUT: step3_forecasts_weekly.*  (feeds Step 4)
        step3_metrics_summary.csv
        step3_feature_importance.csv
        models_step3/*.txt
        step3_summary.json
""",
            "Step 3 I/O",
        )
    )

    story.append(Paragraph("8.4 Step 4 — Safety stock + FEFO policy simulation", S["h1"]))
    story.append(
        diagram(
            """
 run_step4.py -> src/run_inventory_sim.py
   Policies: fifo_static | fefo_static | fefo_ss | fefo_ss_markdown
   OUT: step4_safety_stock_params.csv
        step4_policy_comparison.csv
        step4_weekly_kpis.csv
        step4_sim_detail.parquet
        step4_summary.json
""",
            "Step 4 I/O",
        )
    )

    story.append(Paragraph("8.5 Step 5 — Substitutes audit", S["h1"]))
    story.append(
        diagram(
            """
 run_step5.py -> src/run_substitutes.py
   OUT: step5_assortment_regulatory.csv
        step5_stock_snapshot.csv
        step5_substitute_recommendations.csv
        step5_audit_counts.csv
        step5_summary.json
""",
            "Step 5 I/O",
        )
    )

    story.append(Paragraph("8.6 Seed, migrate, analytics, snapshot", S["h1"]))
    story.append(
        grid(
            ["Script", "Role"],
            [
                ["seed_mysql.py --apply-schema", "Create DB/tables; load reference+working+Tx"],
                ["apply_migration_002.py", "Editable inventory columns + audit"],
                ["load_analytics.py", "Refresh forecasts/recommendations without full reseed"],
                ["snapshot_originals.py", "Freeze processed artefacts to data/originals/"],
            ],
        )
    )
    story.append(PageBreak())


def module_9(story: list):
    story.append(banner("MODULE 9 — GLOSSARY, ACRONYMS, FORMULA SHEET"))
    story.append(Paragraph("9.1 Large glossary", S["h1"]))
    story.append(
        grid(
            ["Term", "One-line definition"],
            [
                ["SKU", "Stock-keeping unit — sellable pack identity"],
                ["Lot / batch", "Physical stock sharing mfg &amp; expiry"],
                ["Assortment", "Active shelf subset (~3,000) of full catalog"],
                ["Reference catalog", "Immutable ~253,973 knowledge base rows"],
                ["Working stock", "Editable pharmacy/dev_synthetic/sponsor rows"],
                ["Digital twin", "Software mirror of pharmacy operational state"],
                ["Intermittent demand", "Many zero periods + occasional spikes"],
                ["ADI", "Average demand interval between non-zero sales"],
                ["CV²", "Squared coefficient of variation of demand sizes"],
                ["Croston", "Smooth size &amp; interval separately"],
                ["SBA", "Syntetos–Boylan bias-corrected Croston"],
                ["TSB", "Teunter–Syntetos–Babai probability×size forecast"],
                ["WMAPE", "Σ|y−ŷ| / Σ|y| — scale-free intermittent-safe"],
                ["MASE", "Error scaled by naive lag-1 absolute changes"],
                ["MAPE", "Forbidden headline metric here (zero blow-up)"],
                ["Pinball loss", "Quantile regression training loss"],
                ["q50 / q90 / q95", "Predictive demand quantiles"],
                ["Service level", "Target non-stockout probability in a cycle"],
                ["Z", "Normal quantile of service level (~1.645 @ 95%)"],
                ["Safety stock (SS)", "Z × σ × √(L+R) buffer"],
                ["ROP", "μ(L+R)+SS reorder trigger"],
                ["Lead time L", "Wait until PO arrives"],
                ["Review period R", "How often stock position is reviewed"],
                ["Inventory position", "On-hand + on-order − backorders"],
                ["Fill rate", "Satisfied demand ÷ total demand"],
                ["Stockout", "Demand with no sellable quantity"],
                ["Unmet qty", "Recorded lost demand during stockout"],
                ["FEFO", "First-Expiry-First-Out picking"],
                ["FIFO", "First-In-First-Out picking"],
                ["Markdown tier", "OTC near-expiry discount schedule"],
                ["TF-IDF", "Term weighting for text importance"],
                ["Cosine similarity", "Angle-based vector similarity in [0,1] after L2"],
                ["Schedule H1", "Strict Indian Rx schedule with register duties"],
                ["WHO AWaRe", "Access / Watch / Reserve antibiotic groups"],
                ["CDSCO", "Indian drug regulator; banned FDC lists"],
                ["dev_synthetic", "Labeled DEV data mode — not live POS"],
                ["Twin isolation", "Sims must not mutate live batch qty"],
                ["Clone", "Insert working medicine copied from reference"],
            ],
        )
    )

    story.append(Paragraph("9.2 Acronyms quick list", S["h1"]))
    story.append(
        Paragraph(
            "WMAPE, MASE, MAPE, ADI, CV, SS, ROP, FEFO, FIFO, OTC, TF-IDF, LGBM/LightGBM, "
            "AWaRe, CDSCO, FDC, RMP, PO, KPI, NDA, SKU, UI, DB, CRUD, AMR.",
            S["body"],
        )
    )

    story.append(Paragraph("9.3 Formula sheet summary (copy to one A4)", S["h1"]))
    story.append(
        green_formula(
            [
                "WMAPE = Σ|y−ŷ| / Σ|y|",
                "MASE = mean(|e|) / mean(|y_t − y_{t−1}|)",
                "SBA ŷ = (1 − α/2)(z/p)     TSB ŷ = π·z",
                "σ̂ ≈ blend( (q95−q50)/Z0.95 , (q90−q50)/Z0.90 )",
                "SS = Z · σ · √(L+R)     ROP = μ(L+R) + SS     Z≈1.645 @ 95%",
                "cosine(a,b) = (a·b) / (||a|| ||b||)   on TF-IDF vectors",
            ],
            "NEVER MAPE for intermittent demand. Demand y includes unmet_qty in this project.",
        )
    )
    story.append(PageBreak())


def module_10(story: list):
    story.append(banner("MODULE 10 — VIVA / PROBABLE QUESTIONS (40+)"))
    story.append(
        Paragraph(
            "Each item: question, then a <b>short hint</b> (not a full essay). Practise answering "
            "aloud in under a minute. Expand only if the examiner probes.",
            S["body"],
        )
    )

    viva = [
        ("What is PharmTwinAI in one sentence?", "Desktop pharmacy digital twin: stock+forecast+SS/FEFO sim+gated substitutes; MySQL+tkinter."),
        ("Why call it a twin not a dashboard?", "Holds decision state + what-if isolation, not only charts."),
        ("What is D2?", "Desktop-first (tkinter), not Streamlit-first."),
        ("What is D3?", "Synthetic labeled data until sponsor POS; honesty banner."),
        ("What is D4?", "Pharmacist-reviewed substitutes only — no auto-prescribe."),
        ("What is D5?", "Env features research/DEV until proven on real sales."),
        ("What is D7?", "Anemia screening gated — not in core product yet."),
        ("Catalog size?", "~253,973 deduped reference SKUs."),
        ("Working assortment size?", "~3,000 SKUs."),
        ("Can Inventory UI edit reference rows?", "No — clone to working; InventoryGuardError."),
        ("What does source_system distinguish?", "reference vs dev_synthetic/pharmacy/sponsor."),
        ("Why intermittent methods?", "Many zero weeks; separate size vs interval/probability."),
        ("Croston in one line?", "Smooth z and p; ŷ=z/p; update on positive demand."),
        ("What does SBA fix?", "Croston positive bias via (1−α/2) factor."),
        ("TSB vs Croston?", "TSB updates π every period including zeros; ŷ=πz."),
        ("Write WMAPE.", "Σ|y−ŷ|/Σ|y|."),
        ("Write MASE idea.", "Mean abs error / mean abs naive lag-1 change."),
        ("Why not MAPE?", "Zeros undefined/explode; purple numerical blow-up."),
        ("What is unmet_qty for?", "Capture stockout demand so FC sees latent demand."),
        ("LightGBM quantiles used?", "q50, q90, q95 with pinball/quantile objective."),
        ("How is σ estimated?", "Blend (q95−q50)/Z0.95 and (q90−q50)/Z0.90; floor."),
        ("Write SS formula.", "Z·σ·√(L+R)."),
        ("Write ROP formula.", "μ(L+R)+SS."),
        ("Z at 95%?", "≈1.645."),
        ("Default L and R?", "1 week each in Step 4 defaults."),
        ("FEFO vs FIFO?", "Earliest expiry vs earliest receipt; pharmacy prefers FEFO."),
        ("Name four sim policies.", "fifo_static, fefo_static, fefo_ss, fefo_ss_markdown."),
        ("What KPI pair to read?", "Fill rate and expiry waste — not fill alone."),
        ("Prove sim isolation.", "Fingerprint SUM(qty_on_hand) unchanged."),
        ("OTC markdown idea?", "Tiered discounts as expiry nears; Rx/H1 not auto-markdown."),
        ("Substitute ranking?", "Explicit cols then TF-IDF cosine on composition text."),
        ("Write cosine formula.", "(a·b)/(||a|| ||b||)."),
        ("Schedule H1 gate?", "Hard block + Rx/register notice."),
        ("AWaRe Watch/Reserve?", "Block casual auto-sub on antibiotic stewardship path."),
        ("CDSCO gate?", "Block banned FDC / irrational combinations in curated list."),
        ("Offline vs online?", "Steps 1–5 train/export; UI reads MySQL via services."),
        ("Path of a click?", "app/main → services → MySQL."),
        ("load_analytics purpose?", "Refresh forecasts/recs without full reseed."),
        ("migration 002 adds?", "form_type, qty_unit, pharmacy source, inventory_audit…"),
        ("snapshot_originals?", "Freeze processed files to data/originals/."),
        ("Env feature examples?", "rain>20mm lags, PM2.5, health alerts + demand lags."),
        ("Feature importance caveat?", "Importance ≠ causation (D5)."),
        ("Who is the industry context?", "Bhagyashree Medical, Juinagar, Navi Mumbai — context only; DEV data synthetic."),
        ("Is this a chatbot?", "No — inventory/decision twin."),
        ("Acceptance entrypoint?", "scripts/run_demo_acceptance.py (~21 checks) + manual UI walk."),
        ("What if MySQL password wrong?", "Connection fail — fix in Settings / .env."),
        ("Empty Forecasts page?", "Run pipeline + load_analytics."),
        ("Order-up-to vs ROP?", "ROP triggers; order-up-to is target position in params."),
        ("Why weekly grain?", "Retail planning + intermittent stability vs noisy daily zeros."),
        ("Pinball loss one-liner?", "Asymmetric loss targeting a quantile."),
        ("What NOT to claim?", "Real POS used; auto-prescribe; proven weather causality; anemia product done."),
    ]

    story.append(Paragraph("10.1 Question bank with hints", S["h1"]))
    for i, (q, a) in enumerate(viva, 1):
        story.append(Paragraph(f"<b>Q{i}.</b> {q}", S["body"]))
        story.append(Paragraph(f"<i>Hint:</i> {a}", S["small"]))

    story.append(
        Paragraph(
            f"<b>Count:</b> {len(viva)} probable questions with hints. Add your own from the latest "
            "step*_summary.json numbers before the final viva.",
            S["body"],
        )
    )
    story.append(PageBreak())


def module_11(story: list):
    story.append(banner("MODULE 11 — LIMITATIONS, ETHICS, GATED WORK, FUTURE"))
    story.append(Paragraph("11.1 Technical limitations (say these unprompted)", S["h1"]))
    bullets(
        [
            "DEV demand is <b>synthetic</b> — metrics are for method comparison, not published clinical/ops claims on Bhagyashree sales.",
            "Regulatory lists (H1 patterns, AWaRe subset, CDSCO banned FDCs) are <b>curated subsets</b> for the project, not exhaustive national databases.",
            "Normal SS approximation and quantile-derived σ are practical engineering choices, not a full Bayesian inventory theory thesis.",
            "Desktop+localhost MySQL fits D6 lab constraint; not a multi-store cloud SaaS yet.",
            "TF-IDF substitutes use text similarity — they are not clinical equivalence certificates.",
        ],
        story,
    )

    story.append(Paragraph("11.2 Ethics &amp; professional boundaries", S["h1"]))
    story.append(
        def_box(
            "Definition — Human-in-the-loop dispensing",
            "PharmTwinAI may suggest inventory alternatives and show regulatory notices, but a "
            "registered pharmacist remains responsible for legality and appropriateness of dispensing (D4).",
        )
    )
    story.append(
        orange_caution(
            "Never demo the system as diagnosing disease, recommending therapy, or replacing a pharmacist. "
            "Never present synthetic sales as sponsor POS."
        )
    )

    story.append(Paragraph("11.3 Gated anemia &amp; other screening (D7/D8)", S["h1"]))
    story.append(
        Paragraph(
            "Anemia-related research notes may exist in docs, but <b>product implementation is gated "
            "until core twin acceptance</b> (D7). Other screening ideas are research-only until "
            "explicit per-condition approval (D8). In viva: core = catalog/stock twin + forecast + "
            "SS/FEFO + gated substitutes.",
            S["body"],
        )
    )

    story.append(Paragraph("11.4 Future work (realistic)", S["h1"]))
    story.append(
        grid(
            ["Theme", "Next step when unlocked"],
            [
                ["Sponsor POS", "Replace synthetic Tx; keep labels honest during transition"],
                ["Env validation", "Re-test D5 features on real sales; drop if no lift"],
                ["UI toolkit", "Optional PySide6 migration keeping D2 desktop"],
                ["Regulatory packs", "Expand gated lists with pharmacist-reviewed sources"],
                ["Multi-store", "Only after local single-store acceptance + data agreements"],
                ["Screening modules", "Only after D7/D8 unlock criteria"],
            ],
        )
    )

    story.append(Paragraph("11.5 Closing paragraph for reports", S["h1"]))
    story.append(
        Paragraph(
            "<b>Closing line:</b> PharmTwinAI is a desktop pharmacy digital twin that combines "
            "intermittent-demand forecasting (WMAPE/MASE; Croston/SBA/TSB; LightGBM quantiles), "
            "probabilistic safety stock and FEFO policy comparison in isolated simulation, and "
            "legally gated substitute suggestions for pharmacist review — with a clear separation "
            "between an immutable national medicine catalog (~253,973) and editable working stock "
            "(~3,000), and with explicitly labeled <b>dev_synthetic</b> data until sponsor POS arrives.",
            S["body"],
        )
    )
    four_points(
        "final honesty checklist before you submit",
        [
            "Named methods present in report + viva.",
            "Green formulae correct; MAPE not claimed.",
            "Diagram redrawn once from memory.",
            "Limitations + D3/D4/D5/D7 spoken aloud once.",
        ],
        story,
    )


def deep_dive_architecture(story: list):
    story.append(PageBreak())
    story.append(banner("MODULE 2B — ARCHITECTURE DEEP DIVE (TEACHING EXPANSION)"))
    story.append(Paragraph("2B.1 Why MySQL and not only Parquet files for the twin?", S["h1"]))
    story.append(
        Paragraph(
            "Parquet/CSV under data/processed/ are excellent for reproducible offline science: "
            "you can re-run Step 3 and diff metrics. But a retail twin needs concurrent-safe stock "
            "mutations, foreign keys from batches→medicines, audit rows, and a queryable forecasts "
            "table for the desktop. MySQL gives ACID updates when a pharmacist adds a lot or when "
            "seed loads sales_items. The twin’s “live state” is therefore MySQL; the pipeline’s "
            "“scientific artefacts” remain files. load_analytics bridges them.",
            S["body"],
        )
    )
    story.append(
        def_box(
            "Definition — Dual store pattern",
            "Offline artefacts (Parquet/CSV/JSON summaries) + online operational store (MySQL). "
            "Desktop reads MySQL; Steps 1–5 write files; seed/load_analytics copy science into MySQL.",
        )
    )
    story.append(Paragraph("2B.2 sales_items.unmet_qty — why examiners care", S["h1"]))
    story.append(
        Paragraph(
            "If you only record fulfilled qty, a stockout looks like “zero demand”, so the forecast "
            "learns to predict zero forever — a classic retail analytics bug. unmet_qty stores the "
            "portion of demand that could not be sold. Step 2/3 demand = qty + unmet_qty. "
            "In viva, draw a tiny table: demand 10, stock 4 → qty=4, unmet=6.",
            S["body"],
        )
    )
    story.append(
        purple_box(
            "WORKED MINI — unmet_qty",
            [
                "Customer wants 10 strips; on-hand 4 across lots.",
                "sales_items: qty=4, unmet_qty=6. Revenue on 4 only.",
                "Weekly demand used in FC: 10, not 4. Safety stock will not collapse falsely.",
            ],
        )
    )
    story.append(Paragraph("2B.3 app_meta and the synthetic banner", S["h1"]))
    story.append(
        Paragraph(
            "001_init_schema seeds app_meta with data_mode='dev_synthetic'. services/twin.py reads "
            "this for the Overview banner: SYNTHETIC DEV DATA — not Bhagyashree Medical sales. "
            "If a future sponsor load arrives, the mode string changes — the UI honesty signal must "
            "follow the data, not a hardcoded slide.",
            S["body"],
        )
    )
    story.append(Paragraph("2B.4 inventory_write guards (name the error)", S["h1"]))
    story.append(
        grid(
            ["Attempt", "Guard behaviour"],
            [
                ["UPDATE/DELETE medicines where source_system='reference'", "Blocked — InventoryGuardError"],
                ["Add lot on reference medicine_id", "Blocked — must clone first"],
                ["Add medicine from catalog search", "INSERT new working row + optional lot"],
                ["Remove working lot", "Allowed + inventory_audit row"],
            ],
            orange=True,
        )
    )
    story.append(Paragraph("2B.5 Simulation service contract", S["h1"]))
    story.append(
        diagram(
            """
 Desktop Simulations page
   -> services/simulations.py
        A) import cached Step 4 summary into simulation_runs/results
        B) what-if: clone in-memory / scenario_json demand shock
   -> NEVER UPDATE medicine_batches.qty_on_hand
   -> optional fingerprint: SELECT SUM(qty_on_hand) before/after
""",
            "Simulation service contract",
        )
    )
    story.append(Paragraph("2B.6 Digital twin snapshots", S["h1"]))
    story.append(
        Paragraph(
            "digital_twin_snapshots stores synced_at, source_hash, is_stale, state_json. "
            "Purpose: tell the Overview whether analytics are fresh relative to inventory mutations. "
            "You do not need to memorise every JSON key — memorise the idea: staleness is a first-class "
            "twin concept, not a vague “refresh the page”.",
            S["body"],
        )
    )
    four_points(
        "architecture viva pack",
        [
            "Say dual store: files for science, MySQL for twin state.",
            "Say unmet_qty prevents false zero demand.",
            "Name InventoryGuardError for reference immutability.",
            "Say simulations must fingerprint live stock.",
        ],
        story,
    )


def deep_dive_data(story: list):
    story.append(PageBreak())
    story.append(banner("MODULE 3B — DATA DEEP DIVE"))
    story.append(Paragraph("3B.1 Cohort-aware assortment sampling", S["h1"]))
    story.append(
        Paragraph(
            "src/catalog.py does not take the first 3,000 CSV rows. It stratifies so that slow-moving "
            "and fast-moving cohorts both appear. If you sampled only top sellers, Croston would look "
            "unnecessary and FEFO waste would be understated. Demand_cohort tags later support "
            "metric slicing (intermittent vs smooth).",
            S["body"],
        )
    )
    story.append(Paragraph("3B.2 Covariate series construction (Navi Mumbai style)", S["h1"]))
    story.append(
        grid(
            ["Series", "Construction idea", "Use"],
            [
                ["Daily rainfall", "Synthetic monsoon peaks; flag &gt;20 mm", "Lags in LightGBM"],
                ["PM2.5", "Winter elevation pattern", "Respiratory-related features"],
                ["Health alerts", "Sparse binary flags", "Short demand bursts"],
                ["Calendar", "DOW / week index", "Routine structure"],
            ],
        )
    )
    story.append(
        orange_caution(
            "These are engineered DEV series for method plumbing (D5), not scraped BMC claims. "
            "Do not cite fake municipal datasets."
        )
    )
    story.append(Paragraph("3B.3 Batch generation aligned to FEFO", S["h1"]))
    story.append(
        Paragraph(
            "Step 1 writes batches_fefo with staggered expiry dates so the simulator has something "
            "interesting to pick. If every lot shared one expiry, FEFO≡FIFO and the policy comparison "
            "would be vacuous. Multiple lots per SKU are intentional teaching structure.",
            S["body"],
        )
    )
    story.append(Paragraph("3B.4 Clone lineage field", S["h1"]))
    story.append(
        def_box(
            "Definition — cloned_from_medicine_id",
            "When Inventory clones a reference medicine into a working row, cloned_from_medicine_id "
            "stores the lineage. Useful for audits (“where did this shelf SKU come from?”) without "
            "mutating the reference row.",
        )
    )
    story.append(Paragraph("3B.5 stock_movements ledger idea", S["h1"]))
    story.append(
        Paragraph(
            "The schema includes stock_movements with movement_type ∈ {SALE, PURCHASE, RETURN_IN, "
            "RETURN_OUT, ADJUST, WRITEOFF_EXPIRY, TRANSFER}. Even if the demo path emphasises batches "
            "qty_on_hand, the ledger concept is how a production twin would explain every unit change. "
            "Mention it if asked “how do you audit stock?”.",
            S["body"],
        )
    )
    story.append(Paragraph("3B.6 demand_coverage statuses", S["h1"]))
    story.append(
        grid(
            ["Status", "Meaning"],
            [
                ["OBSERVED", "Normal observed demand day"],
                ["STORE_CLOSED", "No trading — do not treat as zero demand naively"],
                ["MISSING_EXPORT", "Gap in feed (future sponsor case)"],
                ["STOCKOUT_UNMET", "Demand existed but could not be filled"],
            ],
        )
    )
    story.append(
        purple_box(
            "WORKED MINI — why STORE_CLOSED ≠ zero demand",
            [
                "If Sunday closed is stored as y=0 without a coverage flag, models learn false zeros.",
                "Coverage status lets science distinguish “no customers” vs “shop shut” vs “stockout”.",
                "DEV synthetic path still teaches the schema even when calendar is simplified.",
            ],
        )
    )


def deep_dive_forecast(story: list):
    story.append(PageBreak())
    story.append(banner("MODULE 4B — FORECASTING DEEP DIVE"))
    story.append(Paragraph("4B.1 Croston worked numerical (hand calculation)", S["h1"]))
    story.append(
        purple_box(
            "WORKED NUMERICAL — Croston one update",
            [
                "Start: z=8, p=4, α=0.1. So prior ŷ = 8/4 = 2 per period.",
                "After 5 zero periods, a demand of y=10 arrives (q=5 since last demand).",
                "z_new = 8 + 0.1*(10−8) = 8.2",
                "p_new = 4 + 0.1*(5−4) = 4.1",
                "ŷ_new = 8.2/4.1 ≈ 2.00 (almost flat here — small α).",
                "SBA ŷ = (1−0.05)*2.00 = 0.95*2.00 = 1.90 (slightly lower than Croston).",
            ],
        )
    )
    story.append(Paragraph("4B.2 TSB worked numerical", S["h1"]))
    story.append(
        purple_box(
            "WORKED NUMERICAL — TSB probability decay",
            [
                "Let z=10, π=0.4, α_prob=0.2, α_size=0.2. Prior ŷ=4.",
                "Zero week: π ← 0.4 + 0.2*(0−0.4) = 0.32; z unchanged; ŷ=3.2.",
                "Another zero: π ← 0.32 + 0.2*(0−0.32) = 0.256; ŷ=2.56.",
                "Then y=12: z ← 10+0.2*(12−10)=10.4; π ← 0.256+0.2*(1−0.256)=0.4048; ŷ≈4.21.",
                "Lesson: TSB turns down forecasts during long zeros faster than Croston’s static z/p.",
            ],
        )
    )
    story.append(Paragraph("4B.3 WMAPE vs MASE — when each talks", S["h1"]))
    story.append(
        grid(
            ["Metric", "Strength", "Weakness"],
            [
                ["WMAPE", "Intuitive % of demand volume missed", "Can look great if few high-y weeks dominate"],
                ["MASE", "Comparable across SKUs; &lt;1 beats naive", "Needs enough history for naive scale"],
            ],
            orange=True,
        )
    )
    story.append(Paragraph("4B.4 Rolling origin evaluation (idea)", S["h1"]))
    story.append(
        Paragraph(
            "Step 2 style evaluation walks forward week by week: train on past, predict next week, "
            "score, advance. This matches how a pharmacy would actually use a weekly forecast. "
            "A single fixed split is simpler for LightGBM tabular training in Step 3, with metrics "
            "on the held-out tail — both appear in the project; know which artefact you are reading.",
            S["body"],
        )
    )
    story.append(Paragraph("4B.5 Pinball loss intuition", S["h1"]))
    story.append(
        green_formula(
            [
                "For quantile τ:  loss = τ·(y−ŷ) if y≥ŷ;  else (τ−1)·(y−ŷ)",
                "τ=0.5 → symmetric median;  τ=0.95 → heavy penalty if ŷ too low",
            ],
            "That is why q95 sits above q50: under-predicting the upper tail is costly in training.",
        )
    )
    story.append(Paragraph("4B.6 Ablation reading protocol", S["h1"]))
    story.append(
        Paragraph(
            "Compare lgbm_env vs lgbm_noenv WMAPE/MASE on the same test weeks, then vs SBA/TSB/MA. "
            "If env wins overall but loses on intermittent slice, say so — honesty &gt; vanity. "
            "Quote step3_metrics_summary.csv / step3_metrics_by_slice.csv numbers from your run.",
            S["body"],
        )
    )
    story.append(
        diagram(
            """
 Feature vector (week t, SKU i):
   [ lag1, lag2, ..., rolling means,
     rain_7, rain_14, pm25_*, alert_*, calendar_* ]
        |
        +--> LGBM q50 --> yhat / planning
        +--> LGBM q90 --> sigma ingredient
        +--> LGBM q95 --> sigma ingredient + stress
""",
            "Step 3 feature → quantile heads",
        )
    )
    story.append(Paragraph("4B.7 Teacher commentary — common student mistakes", S["h1"]))
    bullets(
        [
            "Calling LightGBM “neural net” — it is gradient-boosted trees.",
            "Saying MAPE was used — it was deliberately excluded.",
            "Reporting only overall WMAPE without pattern slices.",
            "Claiming rain features are production-validated (violates D5).",
        ],
        story,
    )


def deep_dive_inventory(story: list):
    story.append(PageBreak())
    story.append(banner("MODULE 5B — INVENTORY DEEP DIVE"))
    story.append(Paragraph("5B.1 Why √(L+R) appears", S["h1"]))
    story.append(
        Paragraph(
            "If weekly demand deviations are roughly independent with std σ_week, variance over "
            "H = L+R weeks adds: Var = H·σ²_week, so std = σ_week·√H. Safety stock Z·σ·√(L+R) "
            "is the classic normal approximation for the review/lead-time cover window. "
            "If your σ_LT is already defined over the cover horizon, do not multiply √H twice — "
            "read src/safety_stock.py naming carefully in code review.",
            S["body"],
        )
    )
    story.append(Paragraph("5B.2 Order-up-to narrative", S["h1"]))
    story.append(
        def_box(
            "Definition — Order-up-to level",
            "A target inventory position after ordering. When position falls below ROP/trigger, "
            "order quantity ≈ max(0, order_up_to − position). step4_safety_stock_params.csv "
            "materialises per-SKU parameters including order_up_to.",
        )
    )
    story.append(Paragraph("5B.3 FEFO allocation micro-example", S["h1"]))
    story.append(
        purple_box(
            "WORKED NUMERICAL — FEFO pick across two lots",
            [
                "Lots: A qty=5 expiry=2026-10-01; B qty=8 expiry=2026-11-15. Demand=7.",
                "FEFO: take 5 from A, then 2 from B. A emptied (good — nearer expiry gone).",
                "FIFO if A was received later than B could have left A sitting → higher expiry risk.",
                "Waste KPI improves when near-expiry lots are systematically preferred.",
            ],
        )
    )
    story.append(Paragraph("5B.4 Markdown + clearance uplift (policy 4)", S["h1"]))
    story.append(
        Paragraph(
            "fefo_ss_markdown applies tier discounts on eligible OTC lots and may increase realised "
            "demand in the simulator for discounted offers (clearance uplift). That is a modelling "
            "choice to show how commercial levers interact with FEFO — not a claim that patients "
            "always buy more when vitamins are 25% off. Keep the tone engineering-honest.",
            S["body"],
        )
    )
    story.append(Paragraph("5B.5 Reading step4_policy_comparison.csv", S["h1"]))
    story.append(
        grid(
            ["Column family", "What you say in viva"],
            [
                ["Fill rate", "% demand met — higher better"],
                ["Unmet / stockout", "Residual pain after policy"],
                ["Expiry waste", "Units/value written off"],
                ["Orders placed", "Replenishment activity under SS"],
                ["Revenue / markdown $", "Commercial side-effect of tiers"],
            ],
        )
    )
    story.append(
        orange_caution(
            "Do not memorise a single fill-rate percentage from an old chat. Open your "
            "step4_summary.json and quote that run."
        )
    )
    story.append(Paragraph("5B.6 Recommendations text — template anatomy", S["h1"]))
    story.append(
        diagram(
            """
 explanation_text roughly narrates:
   "Demand μ≈..; sigma≈..; service 95% (Z=1.645);
    L=1,R=1; SS=Z*sig*sqrt(L+R)=..; ROP=mu*(L+R)+SS=..;
    on-hand=..; suggest order qty≈.."
 Desktop Recommendations page: filter action_type=REORDER and read aloud.
""",
            "Recommendation narrative anatomy",
        )
    )


def deep_dive_substitutes_ops(story: list):
    story.append(PageBreak())
    story.append(banner("MODULE 6B–7B — SUBSTITUTES &amp; OPS DEEP DIVE"))
    story.append(Paragraph("6B.1 composition_text() role", S["h1"]))
    story.append(
        Paragraph(
            "Before TF-IDF, catalog helpers concatenate chemical composition / therapeutic class "
            "tokens into a normalised string. Garbage in (empty composition) ⇒ weak cosine neighbours. "
            "That is why explicit substitute0–4 columns remain valuable when curated.",
            S["body"],
        )
    )
    story.append(Paragraph("6B.2 min_cosine threshold trade-off", S["h1"]))
    story.append(
        grid(
            ["min_cosine", "Effect"],
            [
                ["Too low (e.g. 0.2)", "Noisy unrelated suggestions — dangerous UX"],
                ["Default ~0.55", "Project balance for demo precision"],
                ["Too high (e.g. 0.9)", "Many empty results even when reasonable alts exist"],
            ],
            orange=True,
        )
    )
    story.append(Paragraph("6B.3 Schedule H1 teaching points (India retail)", S["h1"]))
    story.append(
        Paragraph(
            "Schedule H1 drugs require prescription from a Registered Medical Practitioner and "
            "maintenance of supply records for a statutory period (commonly taught as three years). "
            "The engine’s hard block + notice is an educational/compliance UX pattern for the twin — "
            "not a full e-register product.",
            S["body"],
        )
    )
    story.append(Paragraph("7B.1 Demo day runbook (minute-by-minute idea)", S["h1"]))
    story.append(
        grid(
            ["Minute", "Action"],
            [
                ["0–2", "Overview: catalog vs stocked + synthetic banner"],
                ["2–5", "Inventory: show FEFO lots; clone add if time"],
                ["5–8", "Forecasts + Recommendations explanation_text"],
                ["8–11", "Simulations: import Step 4; prove stock unchanged"],
                ["11–14", "Substitutes: one allowed + one H1 block"],
                ["14–15", "Limitations sentence (D3/D4/D5/D7)"],
            ],
        )
    )
    story.append(Paragraph("7B.2 Seed vs load_analytics — decide which", S["h1"]))
    story.append(
        Paragraph(
            "Full seed_mysql rebuilds reference+working+transactions (slow, heavy). "
            "load_analytics refreshes forecast/recommendation flavoured tables from processed "
            "artefacts when inventory already exists. Lab tip: after changing only Step 3/4 outputs, "
            "prefer load_analytics.",
            S["body"],
        )
    )
    story.append(
        purple_box(
            "WORKED OPS SCENARIO — empty Forecasts page on demo morning",
            [
                "Symptom: Forecasts page blank; Overview shows 254k/3k OK.",
                "Diagnosis: seed ran, but analytics not loaded / Step 3 artefacts missing.",
                "Fix: ensure step3_forecasts_weekly exists → py -3 scripts/load_analytics.py → Refresh.",
                "Prevention: run_demo_acceptance.py before the panel arrives.",
            ],
        )
    )


def deep_dive_pipeline_glossary_viva(story: list):
    story.append(PageBreak())
    story.append(banner("MODULE 8B — PIPELINE TEACHING NOTES PER STEP"))
    story.append(Paragraph("8B.1 Step 1 acceptance numbers to verify", S["h1"]))
    story.append(
        Paragraph(
            "Open data/processed/step1_summary.json after a run. Expect catalog_deduped ≈ 253,973, "
            "assortment ≈ 3,000, multi-hundred-thousand synthetic transactions scale, thousands of "
            "batches. If assortment is 50, you passed the wrong CLI flag — do not demo.",
            S["body"],
        )
    )
    story.append(Paragraph("8B.2 Step 2 α/β knobs", S["h1"]))
    story.append(
        Paragraph(
            "CLI exposes --alpha/--beta style smoothing parameters for intermittent methods. "
            "Smaller α = smoother, slower reaction; larger α = jumpy. Default 0.1 is a teaching "
            "compromise. Do not retune live in viva unless asked.",
            S["body"],
        )
    )
    story.append(Paragraph("8B.3 Step 3 model files", S["h1"]))
    story.append(
        Paragraph(
            "models_step3/lgbm_env_q50.txt (and q90/q95, plus noenv twins) are LightGBM text model "
            "dumps. They prove training happened and support reload experiments. The desktop does "
            "not need these files if forecasts are already in MySQL.",
            S["body"],
        )
    )
    story.append(Paragraph("8B.4 Step 4 CLI defaults worth memorising", S["h1"]))
    story.append(
        green_formula(
            ["--lead-time-weeks 1   --review-period-weeks 1   --service-level 0.95"],
            "These match the SS numericals in Module 5. Changing them changes ROP — say so if you change them.",
        )
    )
    story.append(Paragraph("8B.5 Step 5 CLI defaults", S["h1"]))
    story.append(
        Paragraph(
            "Typical: --n-queries 200 --top-n 5 --min-cosine 0.55. Audit CSVs let you show gated "
            "vs allowed counts without clicking the UI fifty times.",
            S["body"],
        )
    )

    story.append(PageBreak())
    story.append(banner("MODULE 9B — EXTENDED GLOSSARY &amp; COMPARISON SHEETS"))
    story.append(
        grid(
            ["Term", "One-line definition"],
            [
                ["Pinball loss", "Asymmetric quantile training loss"],
                ["Ablation", "Remove a feature family to measure lift"],
                ["Rolling origin", "Walk-forward one-step evaluation"],
                ["Stratified sample", "Preserve cohort proportions when choosing 3k"],
                ["Immutability", "Reference catalog must not be UI-edited"],
                ["Fingerprint", "Checksum-like SUM(qty) isolation check"],
                ["Order-up-to", "Target position after replenishment"],
                ["Clearance uplift", "Simulated demand boost under markdown"],
                ["Stewardship", "Antibiotic responsibility (AWaRe)"],
                ["FDC", "Fixed-dose combination"],
                ["RMP", "Registered Medical Practitioner"],
                ["Grain W", "Weekly forecast grain in MySQL"],
                ["ttk", "Themed Tkinter widgets used in UI"],
                ["Parquet", "Columnar file format for pipeline outputs"],
                ["Acceptance pack", "Automated + manual demo checklist"],
                ["Stale twin", "Analytics/inventory sync lag signal"],
                ["Working copy", "Editable stocked medicine row"],
                ["Explicit substitute", "Curated substitute0–4 link"],
                ["Hard gate", "Non-negotiable regulatory block"],
                ["Soft rank", "Cosine ordering before gates"],
            ],
        )
    )
    story.append(Paragraph("9B.1 Method cheatsheet table", S["h1"]))
    story.append(
        grid(
            ["Method", "Updates on zeros?", "Core formula idea", "File"],
            [
                ["Croston", "No (z,p frozen)", "z/p", "forecast_intermittent.py"],
                ["SBA", "No", "(1−α/2)z/p", "same"],
                ["TSB", "Yes (π decays)", "π·z", "same"],
                ["MA", "Yes (window mean)", "mean(window)", "same"],
                ["LGBM qτ", "N/A (tabular)", "pinball@τ", "forecast_env_lgbm.py"],
            ],
            orange=True,
        )
    )

    story.append(PageBreak())
    story.append(banner("MODULE 10B — MORE VIVA DRILLS (SHORT HINTS)"))
    more = [
        ("Explain dual store in 20 seconds.", "Parquet science files + MySQL twin state; load_analytics bridges."),
        ("What breaks if unmet_qty ignored?", "Stockouts look like zero demand; SS/FC collapse."),
        ("Draw FEFO vs FIFO on two lots.", "Sort expiry vs receipt; allocate demand."),
        ("Why fingerprint sims?", "Prove isolation invariant; acceptance gate."),
        ("Difference D4 vs clinical CDSS?", "Inventory alt review vs diagnosing/prescribing."),
        ("What is pinball@0.95 doing?", "Punish under-prediction of upper demand tail."),
        ("Name migration 002 artefacts.", "form_type, qty_unit, pharmacy source, inventory_audit."),
        ("When use seed vs load_analytics?", "Seed rebuilds world; load refreshes FC/recs."),
        ("What does step4_safety_stock_params hold?", "Per-SKU μ,σ,SS,ROP,order_up_to,z…"),
        ("How does Overview know synthetic?", "app_meta data_mode + twin service banner."),
        ("Why stratified 3k?", "Keep intermittent cohorts; avoid only fast movers."),
        ("SBA correction factor at α=0.2?", "1−α/2=0.9."),
        ("Cosine of identical L2 vectors?", "1.0"),
        ("Cosine of orthogonal TF-IDF?", "0.0"),
        ("What is WRITEOFF_EXPIRY?", "stock_movements type for expired lot removal."),
        ("Name services/simulations promise.", "No live batch mutation."),
        ("Why q90 and q95 both?", "Blend more stable σ than one noisy quantile."),
        ("What is habit-forming gate?", "Block auto-sub candidates flagged habit forming."),
        ("Demo order of pages?", "Overview→Inventory→FC/Recs→Sim→Subs→limitations."),
        ("Where are decisions locked written?", "docs/decisions_locked.md"),
        ("External catalog in git?", "No — large CSV lives under MajorProject Data path."),
        ("What is STALE_TWIN alert?", "Twin sync/analytics freshness warning type."),
        ("Fill rate formula?", "Satisfied / (satisfied+unmet)."),
        ("Why not Streamlit-first?", "D2 pharmacy desktop expectation."),
        ("Can markdown apply to H1?", "No automatic OTC-style markdown on restricted Rx paths."),
    ]
    for i, (q, a) in enumerate(more, 1):
        story.append(Paragraph(f"<b>Q{i} (extra).</b> {q}", S["body"]))
        story.append(Paragraph(f"<i>Hint:</i> {a}", S["small"]))

    story.append(PageBreak())
    story.append(banner("MODULE 11B — ETHICS SCENARIOS &amp; REPORT LANGUAGE"))
    story.append(Paragraph("11B.1 Language that is safe vs unsafe", S["h1"]))
    story.append(
        grid(
            ["Unsafe claim", "Safe rewrite"],
            [
                ["“Trained on Bhagyashree sales”", "“Trained on labeled dev_synthetic demand”"],
                ["“AI prescribes alternatives”", "“Suggests inventory alternatives for pharmacist review”"],
                ["“Rain causes antibiotic sales”", "“Rain lags are exploratory features (D5)”"],
                ["“Detects anemia in patients”", "“Anemia product gated (D7); not shipped”"],
                ["“MAPE 12% proves accuracy”", "“WMAPE/MASE on intermittent panel”"],
            ],
            orange=True,
        )
    )
    story.append(Paragraph("11B.2 Scenario drills", S["h1"]))
    story.append(
        purple_box(
            "SCENARIO A — Examiner: “Show me patient diagnosis.”",
            [
                "Reply: Out of scope. Twin manages inventory/demand decisions, not clinical diagnosis (D4/D7/D8).",
                "Offer: Forecasts, SS recommendations, FEFO sim, gated substitutes instead.",
            ],
        )
    )
    story.append(Spacer(1, 0.12 * cm))
    story.append(
        purple_box(
            "SCENARIO B — Examiner: “Is FEFO always better?”",
            [
                "Reply: For dated medicine lots, FEFO targets expiry waste; FIFO may match if single lot.",
                "Evidence: compare fefo_* vs fifo_static KPIs in step4_policy_comparison.",
            ],
        )
    )
    story.append(Spacer(1, 0.12 * cm))
    story.append(
        purple_box(
            "SCENARIO C — Examiner: “Prove you did not touch live stock in sim.”",
            [
                "Reply: Isolation fingerprint on SUM(qty_on_hand); simulations write simulation_* tables only.",
                "Demo: note on-hand before/after what-if on Simulations page.",
            ],
        )
    )
    story.append(Paragraph("11B.3 One-page oral summary (60 seconds)", S["h1"]))
    story.append(
        Paragraph(
            "PharmTwinAI is a MySQL-backed desktop digital twin for retail pharmacy operations in a "
            "Navi Mumbai context. We keep ~253,973 reference medicines immutable and ~3,000 working "
            "SKUs editable. Offline Steps 1–5 build synthetic intermittent demand, score Croston/SBA/TSB "
            "and LightGBM quantiles with WMAPE/MASE, compute SS/ROP, compare FEFO policies, and audit "
            "gated substitutes. The UI explains reorders and never auto-prescribes. Data is "
            "dev_synthetic until sponsor POS arrives; anemia screening stays gated.",
            S["body"],
        )
    )


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    story: list = []

    module_0(story)
    module_1(story)
    module_2(story)
    deep_dive_architecture(story)
    module_3(story)
    deep_dive_data(story)
    module_4(story)
    deep_dive_forecast(story)
    module_5(story)
    deep_dive_inventory(story)
    module_6(story)
    module_7(story)
    deep_dive_substitutes_ops(story)
    module_8(story)
    deep_dive_pipeline_glossary_viva(story)
    module_9(story)
    module_10(story)
    module_11(story)

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.8 * cm,
        title="PharmTwinAI Colour Notes — Teaching Pack",
        author="PharmTwinAI Capstone",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUT


if __name__ == "__main__":
    path = build()
    size = path.stat().st_size
    print(f"Wrote {path}")
    print(f"Size: {size} bytes ({size / 1024:.1f} KB)")
