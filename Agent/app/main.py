"""PharmTwinAI desktop application (tkinter) — local pharmacy digital twin UI."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.alerts import compute_live_alerts
from services.db import get_meta, probe_database, set_password
from services.forecasts import forecast_counts, list_forecast_summary, list_forecast_weeks
from services.inventory import list_batches_for_medicine, list_stocked_medicines
from services.inventory_write import (
    DEFAULT_UNIT_FOR_FORM,
    FORM_TYPES,
    QTY_UNITS,
    InventoryGuardError,
    add_medicine_with_lot,
    count_by_source,
    remove_lot,
    remove_medicine,
    search_reference_catalog,
)
from services.recommendations import list_recommendations, recommendation_counts
from services.stock_ops import (
    StockError,
    adjust_batch_qty,
    customer_return,
    post_sale,
    receive_purchase,
    return_to_supplier,
    suggest_fefo,
    write_off_expired,
)
from services.simulations import (
    import_cached_step4,
    list_simulation_runs,
    get_run_results,
    run_whatif,
    verify_live_stock_untouched,
)
from services.substitutes import list_query_medicines, recommend_for_sku
from services.twin import build_live_summary, refresh_twin_snapshot

from app.labels import (
    ACTION,
    AWARE,
    MODEL,
    SEVERITY,
    SOURCE,
    SUB_SOURCE,
    alert_type_label,
    code_for,
    plain,
    plain_text,
    recommendation_story,
)

PAGE_OVERVIEW = "Shop summary (Overview / Twin)"
PAGE_INVENTORY = "Stock (Inventory)"
PAGE_FORECASTS = "Sales predictions (Forecasts)"
PAGE_RECS = "What to order (Recommendations)"
PAGE_ALERTS = "Warnings (Alerts)"
PAGE_SIMS = "What-if practice (Simulations)"
PAGE_SUBS = "Alternative medicines (Substitutes)"
PAGE_SETTINGS = "Settings"

PAGES = [
    PAGE_OVERVIEW,
    PAGE_INVENTORY,
    PAGE_FORECASTS,
    PAGE_RECS,
    PAGE_ALERTS,
    PAGE_SIMS,
    PAGE_SUBS,
    PAGE_SETTINGS,
]


def overview_text() -> str:
    ok, msg = probe_database()
    if not ok:
        ok_server, msg_server = probe_database(database_optional=True)
        if not ok_server and "1045" in msg_server:
            return (
                "Pharmacy Digital Twin (desktop)\n\n"
                "Database: not connected — MySQL password missing/wrong\n"
                f"{msg_server}\n\n"
                "Fix now:\n"
                "1) Click OK on the password dialog (or use Settings)\n"
                "2) Enter your MySQL root password\n"
                "3) Then click 'Load demo data (seed database)'\n"
                "4) Restart / refresh Overview\n"
            )
        if ok_server:
            return (
                "Pharmacy Digital Twin (desktop)\n\n"
                "MySQL server: OK, but database 'pharmtwinai' is missing or empty.\n"
                f"Server: {msg_server}\n"
                f"DB error: {msg}\n\n"
                "Run seed from Settings, or:\n"
                "  py -3 scripts/seed_mysql.py --apply-schema\n"
            )
        return (
            "Pharmacy Digital Twin (desktop)\n\n"
            f"Database: not connected\n{msg}\n\n"
            "Setup:\n"
            "1) Ensure MySQL 8 service is running\n"
            "2) Set MySQL password\n"
            "3) Click 'Load demo data (seed database)'\n"
            "4) Restart PharmTwinAI\n"
        )
    try:
        summary = build_live_summary()
        meta = get_meta()
        if summary.get("is_stale"):
            twin_status = (
                "Out of date (STALE) — stock or sales changed since the last update. "
                "Click 'Update shop snapshot'."
            )
        else:
            twin_status = "Up to date (IN SYNC)"
        return (
            "Shop summary — live (Pharmacy Digital Twin)\n\n"
            f"Medicines in the India reference list (catalog knowledge base): "
            f"{summary.get('n_catalog', summary.get('n_medicines', 0)):,}\n"
            f"Medicines this shop stocks (store SKUs): {summary.get('n_stocked', 0):,}\n"
            f"Batches on the shelf (open batches): {summary.get('n_batches', 0):,}\n"
            f"Total units in stock (on-hand units): {summary.get('on_hand_units', 0):,.0f}\n"
            f"Shop snapshot last updated (twin sync, UTC): {summary.get('synced_at', 'n/a')}\n"
            f"Snapshot status (twin status): {twin_status}\n"
            f"Type of data (data mode): {plain(SOURCE, meta.get('data_mode', 'unknown'))}\n"
            f"Data last loaded (last seed): {meta.get('last_seed_at', 'n/a')}\n\n"
            f"Note: {summary.get('label', '')}\n\n"
            "Stock changes only affect this shop's own list (pharmacy working copy) — "
            "the 250k+ India reference list is never changed.\n"
            "Pages: Stock · Sales predictions · What to order · Warnings · "
            "What-if practice · Alternative medicines"
        )
    except Exception as exc:  # noqa: BLE001
        return f"Connected, but twin summary failed:\n{exc}"


STUB_BODIES = {
    "Settings": (
        "Use the buttons below the page list:\n"
        "• Set MySQL password — database login, saved to .env\n"
        "• Load demo data — full reference list + demo shop stock (seed DEV synthetic database)\n"
        "• Load predictions — sales predictions + order suggestions, without reloading "
        "everything (analytics: forecasts + recommendations)\n"
        "• Update shop snapshot — mark the summary up to date (twin snapshot)\n"
        "• Back to summary (refresh Overview)\n\n"
        f"Env file: {ROOT / '.env'}\n"
        "CLI: py -3 scripts/load_analytics.py\n"
        "Originals freeze: py -3 scripts/snapshot_originals.py\n"
        "Inventory schema: py -3 scripts/apply_migration_002.py, then apply_migration_003.py"
    ),
}


class PharmTwinApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PharmTwinAI — Pharmacy Digital Twin")
        self.geometry("1180x740")
        self.minsize(960, 600)

        banner = tk.Label(
            self,
            text="DEMO DATA (DEV SYNTHETIC) — not real Bhagyashree Medical sales",
            bg="#7a3e00",
            fg="#fff8e8",
            font=("Segoe UI", 10, "bold"),
            pady=8,
        )
        banner.pack(fill=tk.X)

        body = tk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = tk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        self.nav = tk.Listbox(left, width=28, exportselection=False, font=("Segoe UI", 10))
        for name in PAGES:
            self.nav.insert(tk.END, name)
        self.nav.pack(fill=tk.Y, expand=True)
        self.nav.bind("<<ListboxSelect>>", self._on_nav)

        tk.Button(left, text="Set MySQL password", command=self._prompt_password).pack(
            fill=tk.X, pady=(8, 4)
        )
        tk.Button(left, text="Load demo data (seed database)", command=self._run_seed).pack(fill=tk.X, pady=4)
        tk.Button(left, text="Load predictions (analytics)", command=self._run_analytics).pack(fill=tk.X, pady=4)
        tk.Button(left, text="Back to summary (refresh)", command=self._refresh).pack(fill=tk.X, pady=4)
        tk.Button(left, text="Update shop snapshot (twin)", command=self._refresh_twin).pack(
            fill=tk.X, pady=4
        )

        self.content = tk.Frame(body)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.heading = tk.Label(
            self.content, text="", anchor="w", font=("Segoe UI", 16, "bold")
        )
        self.heading.pack(fill=tk.X, pady=(0, 8))

        self.page_host = tk.Frame(self.content)
        self.page_host.pack(fill=tk.BOTH, expand=True)

        self.status = tk.Label(self, text="", anchor="w", fg="#555555")
        self.status.pack(fill=tk.X, padx=8, pady=(0, 6))

        self._inv_med_id: int | None = None
        self._sub_sku: int | None = None

        self.nav.selection_set(0)
        self._show(PAGES[0])
        self._update_status()

        ok, msg = probe_database()
        if not ok and "1045" in msg:
            self.after(200, self._prompt_password)

    def _clear_page(self) -> None:
        for child in self.page_host.winfo_children():
            child.destroy()

    def _update_status(self) -> None:
        ok, msg = probe_database()
        self.status.config(
            text=f"DB: {'OK' if ok else 'OFFLINE'} — {msg} | Local desktop build (no cloud)"
        )

    def _on_nav(self, _event=None) -> None:
        sel = self.nav.curselection()
        if not sel:
            return
        self._show(PAGES[sel[0]])

    def _show(self, name: str) -> None:
        self.heading.config(text=name)
        self._clear_page()
        if name == PAGE_OVERVIEW:
            self._page_text(overview_text())
        elif name == PAGE_INVENTORY:
            self._page_inventory()
        elif name == PAGE_FORECASTS:
            self._page_forecasts()
        elif name == PAGE_RECS:
            self._page_recommendations()
        elif name == PAGE_ALERTS:
            self._page_alerts()
        elif name == PAGE_SIMS:
            self._page_simulations()
        elif name == PAGE_SUBS:
            self._page_substitutes()
        else:
            self._page_text(STUB_BODIES.get(name, ""))
        self._update_status()

    def _page_text(self, body: str) -> None:
        text = tk.Text(self.page_host, wrap=tk.WORD, font=("Segoe UI", 11), relief=tk.FLAT)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, body)
        text.config(state=tk.DISABLED)

    def _page_inventory(self) -> None:
        tip = tk.Label(
            self.page_host,
            text=(
                "This is the shop's own stock list (working inventory). "
                "The 250k India reference list (reference catalog) cannot be changed — "
                "'Add medicine' copies from it or creates a new entry."
            ),
            fg="#7a3e00",
            anchor="w",
            wraplength=920,
            justify=tk.LEFT,
        )
        tip.pack(fill=tk.X, pady=(0, 4))

        top = tk.Frame(self.page_host)
        top.pack(fill=tk.X, pady=(0, 6))
        tk.Label(top, text="Search stock:").pack(side=tk.LEFT)
        qvar = tk.StringVar()
        entry = tk.Entry(top, textvariable=qvar, width=32)
        entry.pack(side=tk.LEFT, padx=6)

        ops = tk.Frame(self.page_host)
        ops.pack(fill=tk.X, pady=(0, 6))
        tk.Label(ops, text="Daily work:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        paned = tk.PanedWindow(self.page_host, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)

        med_frame = tk.Frame(paned)
        batch_frame = tk.Frame(paned)
        paned.add(med_frame, height=300)
        paned.add(batch_frame)

        cols = (
            "sku_code",
            "name",
            "form",
            "unit",
            "qty",
            "batches",
            "nearest_expiry",
            "source",
            "mrp",
        )
        tree = ttk.Treeview(med_frame, columns=cols, show="headings", height=12)
        headings = {
            "sku_code": "Code (SKU)",
            "name": "Medicine",
            "form": "Form",
            "unit": "Counted in",
            "qty": "In stock",
            "batches": "Batches (lots)",
            "nearest_expiry": "Earliest expiry",
            "source": "Entry type (source)",
            "mrp": "MRP",
        }
        widths = {
            "sku_code": 90,
            "name": 240,
            "form": 90,
            "unit": 80,
            "qty": 70,
            "batches": 50,
            "nearest_expiry": 100,
            "source": 150,
            "mrp": 60,
        }
        for c in cols:
            tree.heading(c, text=headings[c])
            tree.column(c, width=widths[c], anchor=tk.W)
        ysb = ttk.Scrollbar(med_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(
            batch_frame,
            text="Batches of the selected medicine — sell the earliest expiry first (FEFO lots)",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=tk.X)
        bcols = ("batch_id", "batch_no", "mfg", "expiry", "days", "qty", "unit", "unit_cost")
        btree = ttk.Treeview(batch_frame, columns=bcols, show="headings", height=8)
        bhead = {
            "batch_id": "ID",
            "batch_no": "Batch no.",
            "mfg": "Made on (mfg)",
            "expiry": "Expiry",
            "days": "Days left",
            "qty": "Qty",
            "unit": "Counted in",
            "unit_cost": "Cost",
        }
        for c in bcols:
            btree.heading(c, text=bhead[c])
            btree.column(c, width=100 if c != "batch_no" else 140, anchor=tk.W)
        bysb = ttk.Scrollbar(batch_frame, orient=tk.VERTICAL, command=btree.yview)
        btree.configure(yscrollcommand=bysb.set)
        btree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bysb.pack(side=tk.RIGHT, fill=tk.Y)

        def load_meds(_event=None) -> None:
            tree.delete(*tree.get_children())
            btree.delete(*btree.get_children())
            try:
                rows = list_stocked_medicines(search=qvar.get(), limit=800)
                sources = count_by_source()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Inventory", str(exc))
                return
            tip.config(
                text=(
                    f"Shop stock list can be edited. India reference list is locked "
                    f"({sources.get('reference', 0):,} medicines, reference). "
                    f"In stock list: added in shop={sources.get('pharmacy', 0)} (pharmacy), "
                    f"demo data={sources.get('dev_synthetic', 0)} (dev_synthetic)."
                )
            )
            for r in rows:
                tree.insert(
                    "",
                    tk.END,
                    iid=str(r["medicine_id"]),
                    values=(
                        r.get("sku_code") or r.get("sku_id") or "",
                        r.get("name"),
                        r.get("form_type") or "",
                        r.get("qty_unit") or "",
                        f"{float(r.get('qty_on_hand') or 0):.0f}",
                        r.get("n_batches"),
                        r.get("nearest_expiry") or "",
                        plain(SOURCE, r.get("source_system")),
                        r.get("unit_mrp") or "",
                    ),
                )

        def on_select(_event=None) -> None:
            sel = tree.selection()
            btree.delete(*btree.get_children())
            if not sel:
                return
            mid = int(sel[0])
            self._inv_med_id = mid
            try:
                batches = list_batches_for_medicine(mid)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Lots", str(exc))
                return
            for b in batches:
                btree.insert(
                    "",
                    tk.END,
                    iid=str(b["batch_id"]),
                    values=(
                        b.get("batch_id"),
                        b.get("batch_no"),
                        b.get("mfg_date") or "",
                        b.get("expiry_date") or "",
                        b.get("days_to_expiry"),
                        f"{float(b.get('qty_on_hand') or 0):.0f}",
                        b.get("qty_unit") or "",
                        b.get("unit_cost") or "",
                    ),
                )

        def do_remove_med() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Remove", "Select a medicine in the list first.")
                return
            mid = int(sel[0])
            name = tree.item(sel[0], "values")[1]
            if not messagebox.askyesno(
                "Remove from stock",
                f"Remove this medicine from the shop stock list?\n\n{name}\n\n"
                "If it was ever sold, its sales history is KEPT (needed for predictions): "
                "it is hidden and its remaining stock is set to 0 (soft delete). "
                "Otherwise it is deleted completely.\n\n"
                "The India reference list (reference catalog) will NOT be changed.",
            ):
                return
            try:
                out = remove_medicine(mid)
            except InventoryGuardError as exc:
                messagebox.showerror("Blocked", str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Remove failed", str(exc))
                return
            if out.get("kept_history"):
                messagebox.showinfo(
                    "Removed (history kept)",
                    f"Removed from stock: {out.get('name')}\n"
                    f"{out.get('units_removed', 0):.0f} units taken off the shelf. "
                    "Sales history kept for predictions (is_active = 0).",
                )
            else:
                messagebox.showinfo("Removed", f"Removed: {out.get('name')}")
            load_meds()

        def do_remove_lot() -> None:
            sel = btree.selection()
            if not sel:
                messagebox.showinfo("Remove batch", "Select a batch row first.")
                return
            bid = int(sel[0])
            if not messagebox.askyesno("Remove batch", f"Delete batch (lot) ID {bid}?"):
                return
            try:
                remove_lot(bid)
            except InventoryGuardError as exc:
                messagebox.showerror("Blocked", str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Remove lot failed", str(exc))
                return
            on_select()
            load_meds()

        tk.Button(top, text="Search", command=load_meds).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Add medicine…", command=lambda: self._dialog_add_medicine(on_done=load_meds)).pack(
            side=tk.LEFT, padx=4
        )
        tk.Button(top, text="Remove medicine", command=do_remove_med).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Remove batch (lot)", command=do_remove_lot).pack(side=tk.LEFT, padx=4)

        def refresh_both() -> None:
            keep = tree.selection()
            load_meds()
            if keep and tree.exists(keep[0]):
                tree.selection_set(keep[0])
                on_select()

        def need_med() -> int | None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select medicine", "Select a medicine in the list first.")
                return None
            return int(sel[0])

        def need_batch() -> int | None:
            sel = btree.selection()
            if not sel:
                messagebox.showinfo("Select batch", "Select a batch in the lower list first.")
                return None
            return int(sel[0])

        def do_sell() -> None:
            mid = need_med()
            if mid is not None:
                self._dialog_sell(mid, tree.item(str(mid), "values")[1], refresh_both)

        def do_receive() -> None:
            mid = need_med()
            if mid is not None:
                self._dialog_receive(mid, tree.item(str(mid), "values")[1], refresh_both)

        def do_batch_op(kind: str) -> None:
            bid = need_batch()
            if bid is not None:
                self._dialog_batch_op(kind, bid, btree.item(str(bid), "values"), refresh_both)

        def do_writeoff_one() -> None:
            bid = need_batch()
            if bid is None:
                return
            if not messagebox.askyesno(
                "Write off expired batch",
                f"Remove all stock of expired batch ID {bid} from the shelf "
                "(write-off, WRITEOFF_EXPIRY)?",
            ):
                return
            self._run_stock_op(lambda: write_off_expired(bid), refresh_both,
                               lambda o: f"Wrote off {o['units']:.0f} expired units.")

        def do_writeoff_all() -> None:
            if not messagebox.askyesno(
                "Write off ALL expired stock",
                "Remove the stock of EVERY expired batch in the shop from the shelf?\n"
                "Each one is logged in the audit trail (WRITEOFF_EXPIRY).",
            ):
                return
            self._run_stock_op(write_off_expired, refresh_both,
                               lambda o: f"Wrote off {o['units']:,.0f} units from "
                               f"{o['batches']:,} expired batches.")

        for text, cmd in (
            ("Sell…", do_sell),
            ("Receive stock (purchase)…", do_receive),
            ("Customer return…", lambda: do_batch_op("return_in")),
            ("Return to supplier…", lambda: do_batch_op("return_out")),
            ("Correct quantity (adjust)…", lambda: do_batch_op("adjust")),
            ("Write off expired batch", do_writeoff_one),
            ("Write off ALL expired", do_writeoff_all),
        ):
            tk.Button(ops, text=text, command=cmd).pack(side=tk.LEFT, padx=3)
        entry.bind("<Return>", load_meds)
        tree.bind("<<TreeviewSelect>>", on_select)
        load_meds()

    def _run_stock_op(self, fn, on_done, success_msg, parent=None) -> bool:
        """Run a stock_ops call; friendly error on refusal; refresh lists on success."""
        try:
            out = fn()
        except (StockError, InventoryGuardError) as exc:
            messagebox.showwarning("Not saved", str(exc), parent=parent or self)
            return False
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error — nothing saved", str(exc), parent=parent or self)
            return False
        messagebox.showinfo(
            "Saved",
            success_msg(out) + "\n\nShop summary is now out of date until you click "
            "'Update shop snapshot'.",
            parent=parent or self,
        )
        if on_done:
            on_done()
        return True

    def _dialog_sell(self, medicine_id: int, name: str, on_done=None) -> None:
        win = tk.Toplevel(self)
        win.title("Sell medicine (sale)")
        win.geometry("560x380")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=name, font=("Segoe UI", 11, "bold"), anchor="w").pack(
            fill=tk.X, padx=10, pady=(10, 4)
        )
        form = tk.Frame(win)
        form.pack(fill=tk.X, padx=10)
        qty_var = tk.StringVar(value="1")
        price_var = tk.StringVar()
        tk.Label(form, text="Quantity to sell").grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(form, textvariable=qty_var, width=12).grid(row=0, column=1, sticky="w")
        tk.Label(form, text="Price per unit (blank = MRP)").grid(row=1, column=0, sticky="w", pady=3)
        tk.Entry(form, textvariable=price_var, width=12).grid(row=1, column=1, sticky="w")
        plan_lbl = tk.Label(win, text="", justify=tk.LEFT, anchor="w", wraplength=520)
        plan_lbl.pack(fill=tk.X, padx=10, pady=8)

        def preview(_e=None) -> None:
            try:
                plan = suggest_fefo(medicine_id, qty_var.get())
            except (StockError, InventoryGuardError) as exc:
                plan_lbl.config(text=str(exc))
                return
            lines = ["Take from these batches — earliest expiry first (FEFO):"]
            for a in plan["allocations"]:
                lines.append(
                    f"  • Batch {a['batch_no']}: {a['take']:.0f} units "
                    f"(expires {a['expiry_date']}, {a['days_to_expiry']} days left)"
                )
            if not plan["allocations"]:
                lines.append("  • No sellable stock.")
            if plan["short"] > 0:
                lines.append(
                    f"Short by {plan['short']:.0f} units — recorded as a lost sale "
                    "(unmet_qty) so predictions learn about it."
                )
            if plan["expired_qty_skipped"] > 0:
                lines.append(
                    f"{plan['expired_qty_skipped']:.0f} expired units were skipped "
                    "(never sold)."
                )
            plan_lbl.config(text="\n".join(lines))

        def confirm() -> None:
            price_raw = price_var.get().strip()
            try:
                price = float(price_raw) if price_raw else None
            except ValueError:
                messagebox.showwarning("Not saved", "Price must be a number.", parent=win)
                return

            def msg(o) -> str:
                m = f"Sale #{o['sale_id']}: sold {o['fulfilled']:.0f} units."
                if o["short"] > 0:
                    m += f"\n{o['short']:.0f} units short — recorded as a lost sale."
                return m

            if self._run_stock_op(
                lambda: post_sale(medicine_id, qty_var.get(), unit_price=price),
                on_done, msg, parent=win,
            ):
                win.destroy()

        btns = tk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(btns, text="Confirm sale", command=confirm).pack(side=tk.RIGHT)
        tk.Button(btns, text="Show batches", command=preview).pack(side=tk.RIGHT, padx=6)
        tk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT)
        preview()

    def _dialog_receive(self, medicine_id: int, name: str, on_done=None) -> None:
        win = tk.Toplevel(self)
        win.title("Receive stock from supplier (purchase)")
        win.geometry("480x300")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=name, font=("Segoe UI", 11, "bold"), anchor="w").pack(
            fill=tk.X, padx=10, pady=(10, 4)
        )
        form = tk.Frame(win)
        form.pack(fill=tk.X, padx=10)
        v = {
            "qty": tk.StringVar(value="100"),
            "batch_no": tk.StringVar(),
            "expiry": tk.StringVar(),
            "mfg": tk.StringVar(),
            "cost": tk.StringVar(),
        }
        for i, (label, key) in enumerate(
            (
                ("Quantity received", "qty"),
                ("Batch no. (same no. adds to that batch)", "batch_no"),
                ("Expiry (YYYY-MM-DD)", "expiry"),
                ("Made on (YYYY-MM-DD, optional)", "mfg"),
                ("Cost per unit (optional)", "cost"),
            )
        ):
            tk.Label(form, text=label, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            tk.Entry(form, textvariable=v[key], width=18).grid(row=i, column=1, sticky="w", padx=6)

        def save() -> None:
            cost_raw = v["cost"].get().strip()
            try:
                cost = float(cost_raw) if cost_raw else None
            except ValueError:
                messagebox.showwarning("Not saved", "Cost must be a number.", parent=win)
                return
            try:
                expiry = v["expiry"].get().strip()
                mfg = v["mfg"].get().strip() or None
                if not expiry:
                    raise StockError("Expiry date is required.")
                from datetime import date as _d

                _d.fromisoformat(expiry)
                if mfg:
                    _d.fromisoformat(mfg)
            except ValueError:
                messagebox.showwarning("Not saved", "Dates must look like 2027-03-31.", parent=win)
                return
            except StockError as exc:
                messagebox.showwarning("Not saved", str(exc), parent=win)
                return
            if self._run_stock_op(
                lambda: receive_purchase(
                    medicine_id, v["qty"].get(), expiry_date=expiry,
                    batch_no=v["batch_no"].get().strip() or None, mfg_date=mfg, unit_cost=cost,
                ),
                on_done,
                lambda o: (
                    f"Received {o['qty']:.0f} units into batch {o['batch_no']}"
                    + (" (added to existing batch)." if o["topped_up"] else " (new batch).")
                ),
                parent=win,
            ):
                win.destroy()

        tk.Button(win, text="Save receipt", command=save).pack(side=tk.RIGHT, padx=10, pady=10)
        tk.Button(win, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=10, pady=10)

    def _dialog_batch_op(self, kind: str, batch_id: int, bvals, on_done=None) -> None:
        titles = {
            "return_in": "Customer return (RETURN_IN)",
            "return_out": "Return to supplier (RETURN_OUT)",
            "adjust": "Correct batch quantity (ADJUST)",
        }
        win = tk.Toplevel(self)
        win.title(titles[kind])
        win.geometry("480x240")
        win.transient(self)
        win.grab_set()
        tk.Label(
            win,
            text=f"Batch {bvals[1]} · expiry {bvals[3]} · in stock {bvals[5]}",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=tk.X, padx=10, pady=(10, 6))
        form = tk.Frame(win)
        form.pack(fill=tk.X, padx=10)
        qty_label = "New counted quantity" if kind == "adjust" else "Quantity"
        qty_var = tk.StringVar(value=str(bvals[5]) if kind == "adjust" else "1")
        reason_var = tk.StringVar()
        tk.Label(form, text=qty_label).grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(form, textvariable=qty_var, width=12).grid(row=0, column=1, sticky="w", padx=6)
        tk.Label(
            form, text="Reason (required)" if kind == "adjust" else "Reason (optional)"
        ).grid(row=1, column=0, sticky="w", pady=3)
        tk.Entry(form, textvariable=reason_var, width=36).grid(row=1, column=1, sticky="w", padx=6)

        def save() -> None:
            reason = reason_var.get()
            if kind == "return_in":
                fn = lambda: customer_return(batch_id, qty_var.get(), reason=reason)  # noqa: E731
                msg = lambda o: f"{o['qty']:.0f} units returned to stock."  # noqa: E731
            elif kind == "return_out":
                fn = lambda: return_to_supplier(batch_id, qty_var.get(), reason=reason)  # noqa: E731
                msg = lambda o: f"{o['qty']:.0f} units sent back to supplier."  # noqa: E731
            else:
                fn = lambda: adjust_batch_qty(batch_id, qty_var.get(), reason=reason)  # noqa: E731
                msg = lambda o: (  # noqa: E731
                    f"Quantity corrected from {o['old_qty']:.0f} to {o['new_qty']:.0f}. "
                    "Reason saved in the audit trail."
                )
            if self._run_stock_op(fn, on_done, msg, parent=win):
                win.destroy()

        tk.Button(win, text="Save", command=save).pack(side=tk.RIGHT, padx=10, pady=10)
        tk.Button(win, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=10, pady=10)

    def _dialog_add_medicine(self, on_done=None) -> None:
        win = tk.Toplevel(self)
        win.title("Add medicine to shop stock")
        win.geometry("640x520")
        win.transient(self)
        win.grab_set()

        info = tk.Label(
            win,
            text=(
                "Adds a medicine to the shop stock list with its first batch (opening lot). "
                "Optional: search the India reference list and pick a medicine to copy its "
                "details (the reference list itself is not changed)."
            ),
            wraplength=600,
            justify=tk.LEFT,
            fg="#555555",
        )
        info.pack(fill=tk.X, padx=10, pady=8)

        cat_frame = tk.LabelFrame(win, text="Copy details from India reference list (clone from catalog) — optional")
        cat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        cq = tk.StringVar()
        crow = tk.Frame(cat_frame)
        crow.pack(fill=tk.X, padx=6, pady=4)
        tk.Entry(crow, textvariable=cq, width=40).pack(side=tk.LEFT)
        clone_id = tk.IntVar(value=0)
        ctree = ttk.Treeview(
            cat_frame, columns=("id", "name", "pack"), show="headings", height=5
        )
        for c, h, w in (("id", "ID", 60), ("name", "Name", 320), ("pack", "Pack", 160)):
            ctree.heading(c, text=h)
            ctree.column(c, width=w)
        ctree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        form = tk.LabelFrame(win, text="Medicine + first batch (opening lot)")
        form.pack(fill=tk.X, padx=10, pady=4)
        fields: dict[str, tk.Variable] = {
            "name": tk.StringVar(),
            "form_type": tk.StringVar(value="TABLET"),
            "qty_unit": tk.StringVar(value="TABLETS"),
            "quantity": tk.StringVar(value="100"),
            "mfg_date": tk.StringVar(value="2025-01-01"),
            "expiry_date": tk.StringVar(value="2027-01-01"),
            "batch_no": tk.StringVar(),
            "manufacturer": tk.StringVar(),
            "mrp": tk.StringVar(),
        }

        def grid_row(r: int, label: str, widget) -> None:
            tk.Label(form, text=label, width=16, anchor="w").grid(row=r, column=0, sticky="w", padx=6, pady=2)
            widget.grid(row=r, column=1, sticky="ew", padx=6, pady=2)

        form.columnconfigure(1, weight=1)
        grid_row(0, "Name", tk.Entry(form, textvariable=fields["name"], width=48))
        form_box = ttk.Combobox(
            form, textvariable=fields["form_type"], values=list(FORM_TYPES), state="readonly", width=20
        )
        grid_row(1, "Form (tablet, syrup…)", form_box)
        unit_box = ttk.Combobox(
            form, textvariable=fields["qty_unit"], values=list(QTY_UNITS), state="readonly", width=20
        )
        grid_row(2, "Counted in (unit)", unit_box)
        grid_row(3, "Quantity", tk.Entry(form, textvariable=fields["quantity"], width=20))
        grid_row(4, "Made on (YYYY-MM-DD)", tk.Entry(form, textvariable=fields["mfg_date"], width=20))
        grid_row(5, "Expiry (YYYY-MM-DD)", tk.Entry(form, textvariable=fields["expiry_date"], width=20))
        grid_row(6, "Batch no", tk.Entry(form, textvariable=fields["batch_no"], width=20))
        grid_row(7, "Manufacturer", tk.Entry(form, textvariable=fields["manufacturer"], width=40))
        grid_row(8, "MRP (optional)", tk.Entry(form, textvariable=fields["mrp"], width=20))

        def on_form_change(_event=None) -> None:
            ft = fields["form_type"].get()
            fields["qty_unit"].set(DEFAULT_UNIT_FOR_FORM.get(ft, "UNITS"))

        form_box.bind("<<ComboboxSelected>>", on_form_change)

        def search_cat() -> None:
            ctree.delete(*ctree.get_children())
            try:
                rows = search_reference_catalog(cq.get(), limit=40)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Catalog", str(exc), parent=win)
                return
            for r in rows:
                ctree.insert(
                    "",
                    tk.END,
                    iid=str(r["medicine_id"]),
                    values=(r["medicine_id"], r["name"], r.get("pack_size_label") or ""),
                )

        def on_cat_select(_event=None) -> None:
            sel = ctree.selection()
            if not sel:
                return
            mid = int(sel[0])
            clone_id.set(mid)
            vals = ctree.item(sel[0], "values")
            fields["name"].set(vals[1])
            try:
                rows = search_reference_catalog(vals[1][:20], limit=5)
                match = next((x for x in rows if int(x["medicine_id"]) == mid), None)
                if match:
                    from services.inventory_write import infer_form_from_text

                    ft, qu = infer_form_from_text(
                        f"{match.get('name','')} {match.get('pack_size_label') or ''}"
                    )
                    fields["form_type"].set(ft)
                    fields["qty_unit"].set(qu)
                    if match.get("unit_mrp") is not None:
                        fields["mrp"].set(str(match["unit_mrp"]))
            except Exception:  # noqa: BLE001
                pass

        tk.Button(crow, text="Search reference list", command=search_cat).pack(side=tk.LEFT, padx=4)
        ctree.bind("<<TreeviewSelect>>", on_cat_select)

        def save() -> None:
            try:
                mrp_raw = fields["mrp"].get().strip()
                out = add_medicine_with_lot(
                    name=fields["name"].get(),
                    form_type=fields["form_type"].get(),
                    qty_unit=fields["qty_unit"].get(),
                    quantity=float(fields["quantity"].get()),
                    mfg_date=fields["mfg_date"].get().strip() or None,
                    expiry_date=fields["expiry_date"].get().strip(),
                    batch_no=fields["batch_no"].get().strip() or None,
                    manufacturer_name=fields["manufacturer"].get().strip() or None,
                    unit_mrp=float(mrp_raw) if mrp_raw else None,
                    clone_from_medicine_id=clone_id.get() or None,
                )
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Add failed", str(exc), parent=win)
                return
            messagebox.showinfo(
                "Added",
                f"Medicine #{out['medicine_id']} (code {out['sku_code']}) added to shop stock.\n"
                f"Form: {out['form_type']} · Quantity: {out['quantity']} {out['qty_unit']}\n"
                "India reference list unchanged.",
                parent=win,
            )
            win.destroy()
            if on_done:
                on_done()

        btn = tk.Frame(win)
        btn.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(btn, text="Save to shop stock", command=save).pack(side=tk.RIGHT)
        tk.Button(btn, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=6)

    def _page_forecasts(self) -> None:
        top = tk.Frame(self.page_host)
        top.pack(fill=tk.X, pady=(0, 6))
        summary_lbl = tk.Label(top, text="", anchor="w")
        summary_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        paned = tk.PanedWindow(self.page_host, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)
        med_frame = tk.Frame(paned)
        week_frame = tk.Frame(paned)
        paned.add(med_frame, height=320)
        paned.add(week_frame)

        cols = ("sku_id", "name", "cohort", "model", "weeks", "avg_yhat", "avg_q95", "from_w", "to_w")
        tree = ttk.Treeview(med_frame, columns=cols, show="headings", height=14)
        heads = {
            "sku_id": "Code (SKU)",
            "name": "Medicine",
            "cohort": "Medicine group (cohort)",
            "model": "Prediction method (model)",
            "weeks": "Weeks checked",
            "avg_yhat": "Expected sales / week (avg yhat)",
            "avg_q95": "Busy-week sales / week (avg q95)",
            "from_w": "From",
            "to_w": "To",
        }
        widths = {
            "sku_id": 70,
            "name": 260,
            "cohort": 150,
            "model": 170,
            "weeks": 80,
            "avg_yhat": 190,
            "avg_q95": 200,
            "from_w": 100,
            "to_w": 100,
        }
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor=tk.W)
        ysb = ttk.Scrollbar(med_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(
            week_frame,
            text=(
                "Predicted vs actually sold, week by week, for the selected medicine — "
                "a test on recent weeks the model did not train on "
                "(backtest; yhat = q50 middle estimate; upper = q95)"
            ),
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=tk.X)
        wcols = ("start", "end", "yhat", "q50", "q95", "actual")
        wtree = ttk.Treeview(week_frame, columns=wcols, show="headings", height=8)
        for c, h, w in (
            ("start", "Week start", 110),
            ("end", "Week end", 110),
            ("yhat", "Expected sales (yhat)", 160),
            ("q50", "Middle estimate (q50)", 160),
            ("q95", "Busy-week upper (q95)", 170),
            ("actual", "Actually sold (actual)", 160),
        ):
            wtree.heading(c, text=h)
            wtree.column(c, width=w, anchor=tk.W)
        wysb = ttk.Scrollbar(week_frame, orient=tk.VERTICAL, command=wtree.yview)
        wtree.configure(yscrollcommand=wysb.set)
        wtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wysb.pack(side=tk.RIGHT, fill=tk.Y)

        def load() -> None:
            tree.delete(*tree.get_children())
            wtree.delete(*wtree.get_children())
            try:
                counts = forecast_counts()
                rows = list_forecast_summary(limit=500)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Forecasts", str(exc))
                summary_lbl.config(
                    text="No sales predictions loaded. Click 'Load predictions (analytics)' (or run scripts/load_analytics.py)."
                )
                return
            if counts["n_rows"] == 0:
                summary_lbl.config(
                    text="No sales predictions in the database. Click 'Load predictions (analytics)' (imports Step 3 forecasts)."
                )
                return
            summary_lbl.config(
                text=(
                    f"Weekly sales predictions for {counts['n_medicines']:,} medicines, "
                    "checked against what actually sold in recent weeks "
                    f"({counts['n_rows']:,} rows, Step 3 LightGBM with season/weather, "
                    "backtest). "
                    "Accuracy is checked with WMAPE/MASE (not MAPE)."
                )
            )
            for r in rows:
                tree.insert(
                    "",
                    tk.END,
                    iid=str(r["medicine_id"]),
                    values=(
                        r.get("sku_id"),
                        r.get("name"),
                        r.get("demand_cohort") or "",
                        plain(MODEL, r.get("model_name")),
                        r.get("n_weeks"),
                        r.get("avg_yhat"),
                        r.get("avg_q95"),
                        r.get("from_week") or "",
                        r.get("to_week") or "",
                    ),
                )

        def on_select(_event=None) -> None:
            sel = tree.selection()
            wtree.delete(*wtree.get_children())
            if not sel:
                return
            try:
                weeks = list_forecast_weeks(int(sel[0]))
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Forecasts", str(exc))
                return
            for w in weeks:
                mj = w.get("metrics_json") or {}
                if not isinstance(mj, dict):
                    mj = {}
                wtree.insert(
                    "",
                    tk.END,
                    values=(
                        w.get("horizon_start") or "",
                        w.get("horizon_end") or "",
                        f"{float(w.get('yhat') or 0):.3f}",
                        f"{float(w.get('yhat_lower') or 0):.3f}",
                        f"{float(w.get('yhat_upper') or 0):.3f}",
                        mj.get("actual", ""),
                    ),
                )

        tk.Button(top, text="Refresh", command=load).pack(side=tk.RIGHT)
        tree.bind("<<TreeviewSelect>>", on_select)
        load()

    def _page_recommendations(self) -> None:
        top = tk.Frame(self.page_host)
        top.pack(fill=tk.X, pady=(0, 6))
        tk.Label(top, text="Show:").pack(side=tk.LEFT)
        action_var = tk.StringVar(value=ACTION["REORDER"])
        action_box = ttk.Combobox(
            top,
            textvariable=action_var,
            values=[ACTION[a] for a in ("REORDER", "HOLD", "REVIEW_OVERSTOCK", "ALL")],
            width=32,
            state="readonly",
        )
        action_box.pack(side=tk.LEFT, padx=6)
        tk.Label(top, text="Search:").pack(side=tk.LEFT)
        qvar = tk.StringVar()
        entry = tk.Entry(top, textvariable=qvar, width=28)
        entry.pack(side=tk.LEFT, padx=6)
        counts_lbl = tk.Label(top, text="", anchor="e")
        counts_lbl.pack(side=tk.RIGHT)

        paned = tk.PanedWindow(self.page_host, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)
        list_frame = tk.Frame(paned)
        detail_frame = tk.Frame(paned)
        paned.add(list_frame, height=340)
        paned.add(detail_frame)

        cols = ("action", "sku_id", "name", "on_hand", "rop", "ss", "qty", "forecast", "cohort")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=14)
        heads = {
            "action": "What to do (action)",
            "sku_id": "Code (SKU)",
            "name": "Medicine",
            "on_hand": "In stock",
            "rop": "Order when stock falls to (ROP)",
            "ss": "Safety stock (SS)",
            "qty": "Suggested order qty",
            "forecast": "Expected sales till delivery (cover demand)",
            "cohort": "Medicine group (cohort)",
        }
        widths = {
            "action": 200,
            "sku_id": 80,
            "name": 240,
            "on_hand": 70,
            "rop": 200,
            "ss": 120,
            "qty": 130,
            "forecast": 260,
            "cohort": 150,
        }
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor=tk.W)
        ysb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(
            detail_frame,
            text="Why this suggestion — in plain words (SS = Z × σ × √(L+R))",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=tk.X)
        detail = tk.Text(detail_frame, wrap=tk.WORD, font=("Segoe UI", 10), height=8)
        detail.pack(fill=tk.BOTH, expand=True)

        row_by_id: dict[str, dict] = {}

        def load(_event=None) -> None:
            tree.delete(*tree.get_children())
            detail.delete("1.0", tk.END)
            row_by_id.clear()
            try:
                counts = recommendation_counts()
                rows = list_recommendations(
                    action=code_for(ACTION, action_var.get()), search=qvar.get(), limit=500
                )
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Recommendations", str(exc))
                counts_lbl.config(text="Click 'Load predictions (analytics)' first")
                return
            if counts.get("ALL", 0) == 0:
                counts_lbl.config(text="None yet — click 'Load predictions (analytics)'")
                detail.insert(
                    tk.END,
                    "No order suggestions in the database yet (recommendations).\n"
                    "Click 'Load predictions (analytics)' (imports Step 4 safety-stock settings).",
                )
                return
            counts_lbl.config(
                text=(
                    f"Order now={counts.get('REORDER', 0)} · "
                    f"Enough={counts.get('HOLD', 0)} · "
                    f"Too much={counts.get('REVIEW_OVERSTOCK', 0)} · "
                    f"Total={counts.get('ALL', 0)}"
                )
            )
            for r in rows:
                iid = str(r["recommendation_id"])
                row_by_id[iid] = r
                qty = r.get("qty_suggested")
                tree.insert(
                    "",
                    tk.END,
                    iid=iid,
                    values=(
                        plain(ACTION, r.get("action_type")),
                        r.get("sku_id"),
                        r.get("name"),
                        f"{float(r.get('current_stock') or 0):.1f}",
                        f"{float(r.get('reorder_point') or 0):.1f}",
                        f"{float(r.get('safety_stock') or 0):.1f}",
                        f"{float(qty):.1f}" if qty is not None else "",
                        f"{float(r.get('forecast_demand') or 0):.1f}",
                        r.get("demand_cohort") or "",
                    ),
                )

        def on_select(_event=None) -> None:
            sel = tree.selection()
            detail.delete("1.0", tk.END)
            if not sel:
                return
            r = row_by_id.get(sel[0], {})
            detail.insert(tk.END, recommendation_story(r))

        tk.Button(top, text="Refresh", command=load).pack(side=tk.LEFT, padx=4)
        entry.bind("<Return>", load)
        action_box.bind("<<ComboboxSelected>>", load)
        tree.bind("<<TreeviewSelect>>", on_select)
        load()

    def _page_alerts(self) -> None:
        top = tk.Frame(self.page_host)
        top.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            top,
            text="Live warnings from shop stock: expired or expiring within 90 days, or fewer than 20 units left",
        ).pack(side=tk.LEFT)

        cols = ("severity", "type", "sku_id", "name", "qty", "expiry", "days", "message")
        tree = ttk.Treeview(self.page_host, columns=cols, show="headings")
        heads = {
            "severity": "How urgent (severity)",
            "type": "Problem (type)",
            "sku_id": "Code (SKU)",
            "name": "Medicine",
            "qty": "In stock",
            "expiry": "Expiry",
            "days": "Days left",
            "message": "Details",
        }
        widths = {
            "severity": 140,
            "type": 190,
            "sku_id": 70,
            "name": 220,
            "qty": 60,
            "expiry": 100,
            "days": 60,
            "message": 360,
        }
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor=tk.W)
        ysb = ttk.Scrollbar(self.page_host, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)

        def load() -> None:
            tree.delete(*tree.get_children())
            try:
                rows = compute_live_alerts()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Alerts", str(exc))
                return
            for r in rows:
                tree.insert(
                    "",
                    tk.END,
                    values=(
                        plain(SEVERITY, r.get("severity")),
                        alert_type_label(r.get("alert_type"), r.get("days_to_expiry")),
                        r.get("sku_id"),
                        r.get("name"),
                        f"{float(r.get('qty_on_hand') or 0):.0f}",
                        r.get("expiry_date") or "",
                        r.get("days_to_expiry") if r.get("days_to_expiry") is not None else "",
                        r.get("message"),
                    ),
                )

        tk.Button(top, text="Refresh warnings", command=load).pack(side=tk.RIGHT)
        load()

    def _page_simulations(self) -> None:
        note = tk.Label(
            self.page_host,
            text=(
                "Practice 'what if' scenarios on a copy of the shop data (twin-isolated what-if). "
                "Your real stock is never changed (no writes to medicine_batches)."
            ),
            fg="#7a3e00",
            anchor="w",
            wraplength=900,
            justify=tk.LEFT,
        )
        note.pack(fill=tk.X, pady=(0, 6))

        controls = tk.Frame(self.page_host)
        controls.pack(fill=tk.X, pady=(0, 6))
        tk.Label(controls, text="Sales change (demand ×, 1.20 = +20%)").pack(side=tk.LEFT)
        demand_var = tk.StringVar(value="1.20")
        tk.Entry(controls, textvariable=demand_var, width=6).pack(side=tk.LEFT, padx=4)
        tk.Label(controls, text="Supplier delay, weeks (lead time)").pack(side=tk.LEFT, padx=(8, 0))
        lt_var = tk.StringVar(value="1")
        tk.Entry(controls, textvariable=lt_var, width=4).pack(side=tk.LEFT, padx=4)
        tk.Label(controls, text="Medicines to test (max SKUs)").pack(side=tk.LEFT, padx=(8, 0))
        sku_var = tk.StringVar(value="100")
        tk.Entry(controls, textvariable=sku_var, width=6).pack(side=tk.LEFT, padx=4)

        paned = tk.PanedWindow(self.page_host, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True)
        runs_frame = tk.Frame(paned)
        res_frame = tk.Frame(paned)
        paned.add(runs_frame, height=240)
        paned.add(res_frame)

        tk.Label(runs_frame, text="Past practice runs (simulation runs)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        rcols = ("run_id", "title", "created", "n_results")
        rtree = ttk.Treeview(runs_frame, columns=rcols, show="headings", height=8)
        for c, h, w in (
            ("run_id", "Run", 60),
            ("title", "Scenario (title)", 520),
            ("created", "Created", 160),
            ("n_results", "Saved results", 110),
        ):
            rtree.heading(c, text=h)
            rtree.column(c, width=w, anchor=tk.W)
        rysb = ttk.Scrollbar(runs_frame, orient=tk.VERTICAL, command=rtree.yview)
        rtree.configure(yscrollcommand=rysb.set)
        rtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rysb.pack(side=tk.RIGHT, fill=tk.Y)

        narrative = tk.Label(res_frame, text="", anchor="w", justify=tk.LEFT, wraplength=900)
        narrative.pack(fill=tk.X, pady=(0, 4))
        mcols = (
            "policy",
            "fill_rate",
            "unmet",
            "waste_cost",
            "markdown",
            "margin",
            "waste_vs_fifo",
        )
        mtree = ttk.Treeview(res_frame, columns=mcols, show="headings", height=10)
        mheads = {
            "policy": "Stock method (policy)",
            "fill_rate": "Customers served (fill rate)",
            "unmet": "Units we could not sell (unmet qty)",
            "waste_cost": "Loss from expired stock (waste cost)",
            "markdown": "Discount given near expiry (markdown)",
            "margin": "Profit (gross margin)",
            "waste_vs_fifo": "Less waste than oldest-first, % (vs FIFO)",
        }
        for c in mcols:
            mtree.heading(c, text=mheads[c])
            mtree.column(c, width=190 if c != "policy" else 380, anchor=tk.W)
        mysb = ttk.Scrollbar(res_frame, orient=tk.VERTICAL, command=mtree.yview)
        mtree.configure(yscrollcommand=mysb.set)
        mtree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mysb.pack(side=tk.RIGHT, fill=tk.Y)

        def load_runs() -> None:
            rtree.delete(*rtree.get_children())
            mtree.delete(*mtree.get_children())
            narrative.config(text="")
            try:
                runs = list_simulation_runs()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Simulations", str(exc))
                return
            for r in runs:
                rtree.insert(
                    "",
                    tk.END,
                    iid=str(r["run_id"]),
                    values=(
                        r.get("run_id"),
                        plain_text(r.get("title") or ""),
                        r.get("created_at") or "",
                        r.get("n_results"),
                    ),
                )

        def show_results(_event=None) -> None:
            sel = rtree.selection()
            mtree.delete(*mtree.get_children())
            narrative.config(text="")
            if not sel:
                return
            try:
                rows = get_run_results(int(sel[0]))
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Simulations", str(exc))
                return
            if rows:
                narrative.config(text=plain_text(rows[0].get("narrative") or ""))
            for r in rows:
                fr = r.get("fill_rate")
                mtree.insert(
                    "",
                    tk.END,
                    values=(
                        plain_text(r.get("policy") or ""),
                        f"{float(fr):.1%}" if fr is not None else "",
                        f"{float(r.get('unmet_qty') or 0):,.0f}",
                        f"{float(r.get('waste_cost') or 0):,.0f}",
                        f"{float(r.get('markdown_discount') or 0):,.0f}",
                        f"{float(r.get('gross_margin') or 0):,.0f}",
                        f"{float(r.get('waste_reduction_vs_fifo_pct') or 0):.2f}",
                    ),
                )

        def do_cached() -> None:
            try:
                out = import_cached_step4()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Import cached", str(exc))
                return
            messagebox.showinfo(
                "Saved results loaded (cached Step 4)",
                f"Run #{out['run_id']} saved. Best method: {plain_text(out['best'])}\n"
                "Your real stock was not changed.",
            )
            load_runs()
            rtree.selection_set(str(out["run_id"]))
            show_results()

        def do_whatif() -> None:
            try:
                demand = float(demand_var.get())
                lt = float(lt_var.get())
                max_skus = int(sku_var.get())
            except ValueError:
                messagebox.showwarning(
                    "Invalid input",
                    "Sales change, supplier delay and number of medicines must be numbers.",
                )
                return
            if not messagebox.askyesno(
                "Run practice scenario",
                f"Compare stock methods (FEFO/FIFO policies) with sales ×{demand}, "
                f"supplier delay {lt} week(s) (L), up to {max_skus} medicines (SKUs)?\n"
                "This may take 30–90 seconds. Your real stock will not change.",
            ):
                return
            before = verify_live_stock_untouched()
            self.config(cursor="watch")
            self.update_idletasks()
            try:
                out = run_whatif(
                    demand_multiplier=demand,
                    lead_time_weeks=lt,
                    max_skus=max_skus,
                )
                after = verify_live_stock_untouched(before["fingerprint"])
            except Exception as exc:  # noqa: BLE001
                self.config(cursor="")
                messagebox.showerror("What-if failed", str(exc))
                return
            self.config(cursor="")
            msg = (
                f"Run #{out['run_id']} complete. Best method: {plain_text(out['best'])}\n"
                f"Real stock unchanged: {'Yes' if after['unchanged'] else 'NO — check!'} "
                f"(batches={after['n_batches']}, units in stock={after['on_hand']:,.0f})"
            )
            messagebox.showinfo("Practice run complete", msg)
            load_runs()
            rtree.selection_set(str(out["run_id"]))
            show_results()

        tk.Button(controls, text="Load saved results (cached Step 4)", command=do_cached).pack(
            side=tk.LEFT, padx=8
        )
        tk.Button(controls, text="Run practice scenario (what-if)", command=do_whatif).pack(side=tk.LEFT, padx=4)
        tk.Button(controls, text="Refresh list", command=load_runs).pack(side=tk.LEFT, padx=4)
        rtree.bind("<<TreeviewSelect>>", show_results)
        load_runs()

    def _page_substitutes(self) -> None:
        top = tk.Frame(self.page_host)
        top.pack(fill=tk.X, pady=(0, 6))
        tk.Label(top, text="Find a medicine we stock:").pack(side=tk.LEFT)
        qvar = tk.StringVar()
        entry = tk.Entry(top, textvariable=qvar, width=36)
        entry.pack(side=tk.LEFT, padx=6)

        mid = tk.Frame(self.page_host)
        mid.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right = tk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(left, text="Medicine the customer asked for (query)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        qcols = ("sku_id", "name", "mrp")
        qtree = ttk.Treeview(left, columns=qcols, show="headings", height=18)
        for c, w, h in (
            ("sku_id", 90, "Code (SKU)"),
            ("name", 280, "Medicine"),
            ("mrp", 70, "MRP"),
        ):
            qtree.heading(c, text=h)
            qtree.column(c, width=w, anchor=tk.W)
        qtree.pack(fill=tk.BOTH, expand=True)

        info = tk.Label(right, text="", anchor="w", justify=tk.LEFT, wraplength=480)
        info.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            right,
            text="Alternatives in stock that pass the safety rules (gated substitutes)",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        rcols = ("sku_id", "name", "score", "source", "aware", "on_hand", "class")
        rtree = ttk.Treeview(right, columns=rcols, show="headings", height=14)
        for c, w, h in (
            ("sku_id", 90, "Code (SKU)"),
            ("name", 200, "Alternative"),
            ("score", 110, "How close (score)"),
            ("source", 170, "Why suggested (source)"),
            ("aware", 200, "Antibiotic group (AWaRe)"),
            ("on_hand", 70, "In stock"),
            ("class", 190, "Medicine group (class)"),
        ):
            rtree.heading(c, text=h)
            rtree.column(c, width=w, anchor=tk.W)
        rtree.pack(fill=tk.BOTH, expand=True)

        disclaimer = tk.Label(
            self.page_host,
            text=(
                "Stock alternatives for the pharmacist to check — not a prescription "
                "(pharmacist-reviewed, not clinical prescribing). Safety rules applied: "
                "strictly-controlled drugs blocked (Schedule H1), antibiotic groups checked "
                "(WHO AWaRe), banned combinations blocked (CDSCO)."
            ),
            fg="#7a3e00",
            anchor="w",
            wraplength=900,
            justify=tk.LEFT,
        )
        disclaimer.pack(fill=tk.X, pady=(6, 0))

        def load_queries(_event=None) -> None:
            qtree.delete(*qtree.get_children())
            try:
                rows = list_query_medicines(search=qvar.get(), limit=80)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Substitutes", str(exc))
                return
            for r in rows:
                qtree.insert(
                    "",
                    tk.END,
                    iid=str(r["sku_id"]),
                    values=(r.get("sku_id"), r.get("name"), r.get("unit_mrp") or ""),
                )

        def run_rec(_event=None) -> None:
            sel = qtree.selection()
            rtree.delete(*rtree.get_children())
            if not sel:
                return
            sku = int(sel[0])
            self._sub_sku = sku
            try:
                out = recommend_for_sku(sku, top_n=8)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Substitutes", str(exc))
                return
            if not out.get("ok"):
                info.config(text=out.get("error", "Failed"))
                return
            if out.get("h1_blocked"):
                info.config(
                    text=(
                        f"Asked for: {out.get('query_name')} (SKU {sku})\n"
                        "NOT ALLOWED — strictly-controlled prescription drug; no "
                        f"alternatives suggested (Schedule H1)\n{out.get('h1_message')}"
                    )
                )
                return
            info.config(
                text=(
                    f"Asked for: {out.get('query_name')} (SKU {sku})\n"
                    f"Medicine group (therapeutic class): {out.get('query_class') or 'n/a'}\n"
                    f"Alternatives in stock that pass the rules: {out.get('n_allowed', 0)}"
                )
            )
            for r in out.get("results", []):
                rtree.insert(
                    "",
                    tk.END,
                    values=(
                        r.get("candidate_sku_id"),
                        r.get("candidate_name"),
                        r.get("score"),
                        plain(SUB_SOURCE, r.get("source")),
                        plain(AWARE, r.get("aware")),
                        f"{float(r.get('on_hand') or 0):.0f}",
                        r.get("therapeutic_class"),
                    ),
                )

        tk.Button(top, text="Search", command=load_queries).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Suggest alternatives", command=run_rec).pack(side=tk.LEFT, padx=4)
        entry.bind("<Return>", load_queries)
        qtree.bind("<<TreeviewSelect>>", run_rec)
        load_queries()

    def _refresh(self) -> None:
        self.nav.selection_clear(0, tk.END)
        self.nav.selection_set(0)
        self._show(PAGE_OVERVIEW)

    def _refresh_twin(self) -> None:
        try:
            out = refresh_twin_snapshot()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Snapshot update failed", str(exc))
            return
        messagebox.showinfo(
            "Shop snapshot updated",
            f"Snapshot #{out['snapshot_id']} saved at {out['synced_at']} (UTC). "
            "Status is now up to date (IN SYNC).",
        )
        self._refresh()

    def _prompt_password(self) -> None:
        pwd = simpledialog.askstring(
            "MySQL password",
            "Enter MySQL password for user 'root' on localhost:\n"
            "(Saved to Agent\\.env for next launches)",
            show="*",
            parent=self,
        )
        if pwd is None:
            return
        set_password(pwd, persist=True)
        ok, msg = probe_database(database_optional=True)
        if ok:
            messagebox.showinfo(
                "Connected",
                "MySQL server login OK.\n\n"
                "If the summary still shows no data, click 'Load demo data (seed database)'.\n\n"
                f"{msg}",
            )
        else:
            messagebox.showerror("Still offline", f"Login failed:\n{msg}")
        self._refresh()

    def _run_seed(self) -> None:
        ok, msg = probe_database(database_optional=True)
        if not ok:
            messagebox.showwarning(
                "Set password first",
                "Cannot seed until MySQL accepts your password.\n"
                "Click Set MySQL password first.\n\n"
                f"{msg}",
            )
            self._prompt_password()
            return
        if not messagebox.askyesno(
            "Seed database",
            "This will create/reset the pharmtwinai DEV synthetic database.\n"
            "Full catalog (~254k) + active assortment stock will be reloaded.\nContinue?",
        ):
            return
        script = ROOT / "scripts" / "seed_mysql.py"
        try:
            import os

            completed = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=dict(os.environ),
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Seed failed", str(exc))
            return
        if completed.returncode != 0:
            messagebox.showerror(
                "Seed failed",
                (completed.stderr or completed.stdout or "Unknown error")[-2000:],
            )
        else:
            messagebox.showinfo(
                "Seed complete",
                "Demo data loaded (DEV synthetic).\nClick 'Back to summary'.",
            )
        self._refresh()

    def _run_analytics(self) -> None:
        ok, msg = probe_database()
        if not ok:
            messagebox.showwarning(
                "Database offline",
                "Connect / seed MySQL before loading analytics.\n\n" + msg,
            )
            return
        if not messagebox.askyesno(
            "Load analytics",
            "Import Step 3 forecasts + Step 4 recommendations into MySQL?\n"
            "(Does not reload the 254k catalog.)",
        ):
            return
        script = ROOT / "scripts" / "load_analytics.py"
        try:
            import os

            completed = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=dict(os.environ),
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Analytics failed", str(exc))
            return
        if completed.returncode != 0:
            messagebox.showerror(
                "Analytics failed",
                (completed.stderr or completed.stdout or "Unknown error")[-2000:],
            )
        else:
            messagebox.showinfo(
                "Analytics loaded",
                (completed.stdout or "OK")[-1500:] or "Forecasts + recommendations imported.",
            )
        self._refresh()


def main() -> int:
    app = PharmTwinApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
