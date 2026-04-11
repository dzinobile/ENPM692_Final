"""
Build Request — MES Console
Prompts for Top Assembly Drawing Number, Build Name, Quantity, Start Date.
Reads BOM from BOMS/<drawing_number>.yaml and checks inventory_tracker.csv.
If materials are sufficient, writes build_info/<build_number>.yaml.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import math
import yaml
from datetime import datetime, timedelta

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
BOMS_DIR       = os.path.join(BASE_DIR, "BOMS")
BUILD_INFO_DIR = os.path.join(BASE_DIR, "build_info")
INVENTORY_FILE = os.path.join(BASE_DIR, "inventory_tracker.csv")

# inventory_tracker.csv has 9 columns but only 8 headers (Version Number is missing)
INVENTORY_FIELDS = [
    "Component Name", "Drawing Number",
    "Vendor", "Batch Number", "Quantity", "units", "Status", "Reorder Level",
]

DATE_FORMATS = ["%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]

# ---------------------------------------------------------------------------
# Colour palette — matches MES screens
# ---------------------------------------------------------------------------

BG        = "#1e2227"
PANEL_BG  = "#262b33"
ACCENT    = "#00aaff"
ACCENT2   = "#00cc88"
WARNING   = "#ff9900"
DANGER    = "#e03030"
TEXT      = "#e8eaf0"
TEXT_DIM  = "#8892a4"
ENTRY_BG  = "#2e3440"
ENTRY_FG  = "#eceff4"
BTN_ACTIVE= "#005fa3"


def styled_label(parent, text, size=10, bold=False, color=TEXT, **kw):
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text, bg=PANEL_BG, fg=color,
                    font=("Courier New", size, weight), **kw)


def styled_entry(parent, textvariable=None, width=20):
    return tk.Entry(parent, textvariable=textvariable, width=width,
                    bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ACCENT,
                    relief="flat", font=("Courier New", 11),
                    highlightthickness=1, highlightbackground=ACCENT,
                    highlightcolor=ACCENT)


def accent_button(parent, text, command, color=ACCENT, width=16, **kw):
    return tk.Button(parent, text=text, command=command, width=width,
                     bg=color, fg="#ffffff", activebackground=BTN_ACTIVE,
                     activeforeground="#ffffff", relief="flat",
                     font=("Courier New", 10, "bold"), cursor="hand2", **kw)


def section_frame(parent, title):
    outer = tk.Frame(parent, bg=BG, padx=4, pady=4)
    header = tk.Label(outer, text=f"  {title}  ", bg=ACCENT, fg="#000000",
                      font=("Courier New", 10, "bold"), anchor="w")
    header.pack(fill="x")
    inner = tk.Frame(outer, bg=PANEL_BG, padx=10, pady=10)
    inner.pack(fill="both", expand=True)
    return outer, inner


# ---------------------------------------------------------------------------
# Business logic helpers
# ---------------------------------------------------------------------------

def next_build_number() -> str:
    os.makedirs(BUILD_INFO_DIR, exist_ok=True)
    nums = []
    for name in os.listdir(BUILD_INFO_DIR):
        stem = name.replace(".yaml", "").replace(".yml", "")
        try:
            nums.append(int(stem))
        except ValueError:
            pass
    return f"{(max(nums) + 1 if nums else 1):05d}"


def load_bom(drawing_number: str) -> dict | None:
    path = os.path.join(BOMS_DIR, f"{drawing_number}.yaml")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def load_inventory() -> dict:
    """Returns dict keyed by Component Name (lowercase) → row dict."""
    inv = {}
    if not os.path.exists(INVENTORY_FILE):
        return inv
    with open(INVENTORY_FILE, newline="") as f:
        reader = csv.DictReader(f, fieldnames=INVENTORY_FIELDS)
        next(reader)  # skip header row
        for row in reader:
            if row["Component Name"].strip():
                inv[row["Component Name"].strip().lower()] = row
    return inv


def parse_date(s: str) -> datetime | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def check_materials(bom: dict, quantity: int, inventory: dict) -> list[dict]:
    """
    Returns one result dict per BOM component:
      name, drawing_number, required, available, units, ok
    Matches inventory by Component Name (case-insensitive).
    """
    results = []
    for comp in bom.get("Components", []):
        required = comp["Quantity"] * quantity
        name_key = comp["Name"].strip().lower()
        inv_row  = inventory.get(name_key)

        if inv_row:
            try:
                available = float(inv_row["Quantity"])
            except (ValueError, TypeError):
                available = 0.0
        else:
            available = 0.0

        results.append({
            "name":           comp["Name"],
            "drawing_number": comp["Drawing Number"],
            "required":       required,
            "available":      available,
            "units":          comp.get("Units", ""),
            "ok":             available >= required,
        })
    return results


def calculate_end_date(start: datetime, bom: dict, quantity: int) -> datetime:
    total_hours = 0
    for proc in bom.get("Processes", []):
        pph = proc.get("Parts Per Hour", 1)
        total_hours += math.ceil(quantity / pph)
    return start + timedelta(hours=total_hours)


def generate_build_yaml(build_num: str, build_name: str, quantity: int,
                        start: datetime, end: datetime, bom: dict) -> str:
    processes = []
    for proc in bom.get("Processes", []):
        components = [
            {
                "Name":           c["Name"],
                "Drawing Number": c["Drawing Number"],
                "Quantity":       c["Quantity"] * quantity,
                "Units":          c.get("Units", ""),
            }
            for c in bom.get("Components", [])
        ]
        processes.append({
            "Name":            proc["Name"],
            "Parts Completed": 0,
            "Total Parts":     quantity,
            "Status":          "Scheduled",
            "Components":      components,
        })

    data = {
        "Name":       build_name,
        "Quantity":   quantity,
        "Start Date": start.strftime("%d-%b-%Y"),
        "End Date":   end.strftime("%d-%b-%Y"),
        "Status":     "Scheduled",
        "Processes":  processes,
    }

    os.makedirs(BUILD_INFO_DIR, exist_ok=True)
    path = os.path.join(BUILD_INFO_DIR, f"{build_num}.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return path


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class BuildRequestApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Build Request — MES Console")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 620)

        self.drawing_number = tk.StringVar()
        self.build_name     = tk.StringVar()
        self.quantity_var   = tk.StringVar()
        self.start_date_var = tk.StringVar()

        self._bom      = None   # loaded BOM dict
        self._mat_ok   = False  # True when all materials pass

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        top = tk.Frame(self, bg="#111418", pady=6)
        top.pack(fill="x")
        tk.Label(top, text="BUILD REQUEST — MES CONSOLE",
                 bg="#111418", fg=ACCENT,
                 font=("Courier New", 14, "bold")).pack(side="left", padx=16)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        left  = tk.Frame(body, bg=BG)
        right = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self._build_request_section(left)
        self._build_bom_section(left)
        self._build_material_section(right)
        self._build_output_section(right)

        self.status_var = tk.StringVar(value="Enter a Top Assembly Drawing Number and load the BOM.")
        tk.Label(self, textvariable=self.status_var, bg="#111418", fg=TEXT_DIM,
                 font=("Courier New", 9), anchor="w", padx=10).pack(fill="x", side="bottom")

    # -- Section 1: request inputs ----------------------------------------

    def _build_request_section(self, parent):
        outer, f = section_frame(parent, "1 — BUILD REQUEST")
        outer.pack(fill="x", pady=(0, 6))

        rows = [
            ("Top Assembly Drawing #:", self.drawing_number),
            ("Build Name:",             self.build_name),
            ("Quantity:",               self.quantity_var),
            ("Start Date:",             self.start_date_var),
        ]
        for r, (lbl, var) in enumerate(rows):
            styled_label(f, lbl).grid(row=r, column=0, sticky="w", pady=3)
            e = styled_entry(f, textvariable=var, width=22)
            e.grid(row=r, column=1, padx=8, pady=3)
            if r == 0:
                e.bind("<Return>", lambda _: self._load_bom())
                self._drw_entry = e

        styled_label(f, "(e.g. 01-Mar-2026)", size=8, color=TEXT_DIM).grid(
            row=3, column=2, sticky="w")

        btn_row = tk.Frame(f, bg=PANEL_BG)
        btn_row.grid(row=4, column=0, columnspan=3, sticky="e", pady=(10, 0))

        self.btn_load = accent_button(btn_row, "LOAD BOM", self._load_bom, color=ACCENT)
        self.btn_load.pack(side="left", padx=4)

        self.btn_check = accent_button(btn_row, "CHECK MATERIALS", self._check_materials,
                                       color=WARNING, state="disabled")
        self.btn_check.pack(side="left", padx=4)

        self.btn_submit = accent_button(btn_row, "SUBMIT BUILD", self._submit_build,
                                        color=ACCENT2, state="disabled")
        self.btn_submit.pack(side="left", padx=4)

    # -- Section 2: BOM summary -------------------------------------------

    def _build_bom_section(self, parent):
        outer, f = section_frame(parent, "2 — BOM SUMMARY")
        outer.pack(fill="both", expand=True, pady=(0, 6))

        self.bom_text = tk.Text(f, bg="#0d1117", fg=TEXT, font=("Courier New", 9),
                                state="disabled", wrap="word",
                                relief="flat", highlightthickness=0, height=10)
        self.bom_text.pack(fill="both", expand=True)
        self.bom_text.tag_config("head",    foreground=ACCENT,   font=("Courier New", 9, "bold"))
        self.bom_text.tag_config("ok",      foreground=ACCENT2)
        self.bom_text.tag_config("dim",     foreground=TEXT_DIM)
        self.bom_text.tag_config("warning", foreground=WARNING)

    # -- Section 3: material check table ----------------------------------

    def _build_material_section(self, parent):
        outer, f = section_frame(parent, "3 — MATERIAL CHECK")
        outer.pack(fill="x", pady=(0, 6))

        cols = ("Component", "Drw #", "Required", "Available", "Units", "")
        self.mat_tree = ttk.Treeview(f, columns=cols, show="headings", height=6)
        widths = [140, 110, 90, 90, 60, 80]
        for col, w in zip(cols, widths):
            self.mat_tree.heading(col, text=col)
            self.mat_tree.column(col, width=w, anchor="center")
        self.mat_tree.column("Component", anchor="w")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#0d1117", foreground=TEXT,
                        fieldbackground="#0d1117", rowheight=22,
                        font=("Courier New", 9))
        style.configure("Treeview.Heading",
                        background=PANEL_BG, foreground=ACCENT,
                        font=("Courier New", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])

        self.mat_tree.tag_configure("ok",   foreground=ACCENT2)
        self.mat_tree.tag_configure("fail", foreground=DANGER)
        self.mat_tree.tag_configure("warn", foreground=WARNING)

        self.mat_tree.pack(fill="x")

    # -- Section 4: output log --------------------------------------------

    def _build_output_section(self, parent):
        outer, f = section_frame(parent, "OUTPUT LOG")
        outer.pack(fill="both", expand=True)

        self.out_text = tk.Text(f, bg="#0d1117", fg=TEXT, font=("Courier New", 9),
                                state="disabled", wrap="word",
                                relief="flat", highlightthickness=0)
        self.out_text.pack(fill="both", expand=True)
        sb = tk.Scrollbar(f, command=self.out_text.yview)
        sb.pack(side="right", fill="y")
        self.out_text.config(yscrollcommand=sb.set)
        self.out_text.tag_config("ts",      foreground=TEXT_DIM)
        self.out_text.tag_config("ok",      foreground=ACCENT2)
        self.out_text.tag_config("error",   foreground=DANGER)
        self.out_text.tag_config("warning", foreground=WARNING)
        self.out_text.tag_config("info",    foreground=ACCENT)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_bom(self):
        drw = self.drawing_number.get().strip()
        if not drw:
            messagebox.showwarning("Missing", "Enter a Top Assembly Drawing Number.")
            return

        bom = load_bom(drw)
        if bom is None:
            self._log(f"BOM not found: BOMS/{drw}.yaml", "error")
            self._status(f"No BOM file found for '{drw}'.")
            messagebox.showerror("Not Found",
                                 f"No BOM file found for '{drw}'.\n"
                                 f"Expected: BOMS/{drw}.yaml")
            return

        self._bom = bom
        self._mat_ok = False
        self.btn_check.config(state="normal")
        self.btn_submit.config(state="disabled")

        # Auto-fill Build Name from BOM if blank
        if not self.build_name.get().strip():
            self.build_name.set(bom.get("Name", drw))

        self._render_bom(bom)
        self._log(f"BOM loaded: {drw}  →  {bom.get('Name', '?')}", "ok")
        self._status(f"BOM loaded. Enter quantity and start date, then check materials.")

    def _render_bom(self, bom: dict):
        t = self.bom_text
        t.config(state="normal")
        t.delete("1.0", "end")

        t.insert("end", f"{bom.get('Name', '?')}\n", "head")

        if bom.get("Components"):
            t.insert("end", "\nComponents:\n", "head")
            for c in bom["Components"]:
                t.insert("end",
                         f"  {c['Name']:<20}  {c['Quantity']} {c.get('Units','')}  "
                         f"[{c['Drawing Number']}]\n")

        if bom.get("Processes"):
            t.insert("end", "\nProcesses:\n", "head")
            for p in bom["Processes"]:
                pph = p.get("Parts Per Hour", "?")
                t.insert("end", f"  {p['Name']:<30}  {pph} parts/hr\n")

        t.config(state="disabled")

    def _check_materials(self):
        if self._bom is None:
            messagebox.showwarning("No BOM", "Load a BOM first.")
            return

        qty_str = self.quantity_var.get().strip()
        try:
            quantity = int(qty_str)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid Quantity", "Quantity must be a positive integer.")
            return

        date_str = self.start_date_var.get().strip()
        if not date_str:
            messagebox.showwarning("Missing", "Enter a Start Date.")
            return
        if parse_date(date_str) is None:
            messagebox.showwarning("Invalid Date",
                                   "Unrecognised date format.\n"
                                   "Use DD-Mon-YYYY, e.g. 01-Mar-2026.")
            return

        inventory = load_inventory()
        results   = check_materials(self._bom, quantity, inventory)

        # Populate treeview
        for row in self.mat_tree.get_children():
            self.mat_tree.delete(row)

        all_ok = True
        for r in results:
            badge = "OK" if r["ok"] else "INSUFFICIENT"
            tag   = "ok" if r["ok"] else "fail"
            if not r["ok"]:
                all_ok = False
            self.mat_tree.insert("", "end", values=(
                r["name"],
                r["drawing_number"],
                f"{r['required']:.2f}",
                f"{r['available']:.2f}",
                r["units"],
                badge,
            ), tags=(tag,))

        self._mat_ok = all_ok

        if all_ok:
            self.btn_submit.config(state="normal")
            self._log("Material check PASSED — all components available.", "ok")
            self._status("Materials OK. Click SUBMIT BUILD to generate the build file.")
        else:
            self.btn_submit.config(state="disabled")
            short = [r["name"] for r in results if not r["ok"]]
            self._log(f"Material check FAILED — insufficient: {', '.join(short)}", "error")
            self._status("Insufficient materials. Cannot submit build.")

    def _submit_build(self):
        if not self._mat_ok or self._bom is None:
            return

        qty_str  = self.quantity_var.get().strip()
        date_str = self.start_date_var.get().strip()
        name     = self.build_name.get().strip() or self._bom.get("Name", "Build")

        try:
            quantity = int(qty_str)
        except ValueError:
            messagebox.showwarning("Invalid Quantity", "Quantity must be a positive integer.")
            return

        start = parse_date(date_str)
        if start is None:
            messagebox.showwarning("Invalid Date", "Cannot parse start date.")
            return

        end        = calculate_end_date(start, self._bom, quantity)
        build_num  = next_build_number()
        path       = generate_build_yaml(build_num, name, quantity, start, end, self._bom)

        self._log(f"Build order created: {path}", "ok")
        self._log(f"  Build #:    {build_num}", "info")
        self._log(f"  Name:       {name}", "info")
        self._log(f"  Quantity:   {quantity}", "info")
        self._log(f"  Start:      {start.strftime('%d-%b-%Y')}", "info")
        self._log(f"  End:        {end.strftime('%d-%b-%Y')}", "info")
        self._status(f"Build {build_num} written to build_info/{build_num}.yaml")

        self.btn_submit.config(state="disabled")
        self._mat_ok = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str, tag: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        self.out_text.config(state="normal")
        self.out_text.insert("end", f"[{ts}]  ", "ts")
        self.out_text.insert("end", msg + "\n", tag or "")
        self.out_text.see("end")
        self.out_text.config(state="disabled")

    def _status(self, msg: str):
        self.status_var.set(f"{datetime.now().strftime('%H:%M:%S')}  {msg}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = BuildRequestApp()
    app.mainloop()
