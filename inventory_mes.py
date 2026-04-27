"""
MES Operator Screen Mockup — Inventory
Operator scans the station name at startup, then clocks in.
Logs all events to {station}_mes_log.csv with timestamps.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
from datetime import datetime
import yaml
from filelock import FileLock

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
INVENTORY_FILE = os.path.join(BASE_DIR, "inventory_tracker.csv")
EQUIPMENT_DIR  = os.path.join(BASE_DIR, "equipment")
BOMS_DIR       = os.path.join(BASE_DIR, "BOMS")
INVENTORY_FIELDS = [
    "Container ID", "Drawing Number", "Description",
    "Vendor", "Batch", "Quantity", "Units", "Status",
]
REQUEST_FILE   = os.path.join(BASE_DIR, "component_requests.csv")
REQUEST_FIELDS = ["drawing number", "description", "station ID", "request status"]
LOG_FIELDS     = ["timestamp", "operator_id", "event_type", "field", "value", "notes"]

DATE_FORMATS = ["%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def ensure_log(filepath: str):
    if not os.path.exists(filepath):
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            writer.writeheader()


def write_log_row(row: dict, filepath: str) -> dict:
    ensure_log(filepath)
    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writerow(row)
    return row


def next_container_id() -> int:
    if not os.path.exists(INVENTORY_FILE):
        return 10001
    with open(INVENTORY_FILE, newline="") as f:
        reader = csv.DictReader(f)
        ids = []
        for row in reader:
            try:
                ids.append(int(row["Container ID"]))
            except (ValueError, KeyError):
                pass
    return (max(ids) + 1) if ids else 10001


def read_scale(scale_id: str) -> tuple[float, str] | None:
    """Read the latest row from equipment/{scale_id}.csv. Returns (reading, units) or None."""
    path = os.path.join(EQUIPMENT_DIR, f"{scale_id}.csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        last_row = None
        for last_row in csv.DictReader(f):
            pass
    if last_row is None:
        return None
    return float(last_row["reading"]), last_row["units"]


def load_bom(drawing_number: str) -> dict | None:
    path = os.path.join(BOMS_DIR, f"{drawing_number}.yaml")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def estimate_quantity(scale_reading: float, scale_units: str, drawing_number: str) -> tuple[float, str]:
    """Subtract container weight, then divide by per-unit weight if set (returns pcs).
    Falls back to raw net weight if BOM is missing or Per Unit Weight is None."""
    bom = load_bom(drawing_number)
    if bom is None:
        return scale_reading, scale_units
    container_weight = float(bom.get("Container Weight") or 0)
    per_unit_weight  = bom.get("Per Unit Weight")
    net = scale_reading - container_weight
    if per_unit_weight is not None and str(per_unit_weight).strip().lower() != "none":
        puw = float(per_unit_weight)
        if puw > 0:
            return round(net / puw), "pcs"
    return round(net, 4), scale_units


def load_requests() -> list[dict]:
    """Return all requests with status 'not complete'."""
    if not os.path.exists(REQUEST_FILE):
        return []
    with open(REQUEST_FILE, newline="") as f:
        return [r for r in csv.DictReader(f)
                if r["request status"].strip().lower() == "not complete"]


def lookup_container(container_id: str) -> dict | None:
    """Return the inventory row for a given Container ID, or None."""
    if not os.path.exists(INVENTORY_FILE):
        return None
    with open(INVENTORY_FILE, newline="") as f:
        for row in csv.DictReader(f):
            if row["Container ID"].strip() == container_id.strip():
                return row
    return None


def update_container_quantity_and_status(container_id: str, new_qty: float, new_status: str) -> bool:
    """Update Quantity and Status for a container in inventory_tracker.csv."""
    lock = FileLock(INVENTORY_FILE + ".lock")
    with lock:
        if not os.path.exists(INVENTORY_FILE):
            return False
        with open(INVENTORY_FILE, newline="") as f:
            rows = list(csv.DictReader(f))
        updated = False
        for row in rows:
            if row["Container ID"].strip() == container_id.strip():
                row["Quantity"] = new_qty
                row["Status"]   = new_status
                updated = True
                break
        if not updated:
            return False
        with open(INVENTORY_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return True


def update_container_status(container_id: str, new_status: str) -> bool:
    """Overwrite the Status field for a container in inventory_tracker.csv."""
    lock = FileLock(INVENTORY_FILE + ".lock")
    with lock:
        if not os.path.exists(INVENTORY_FILE):
            return False
        with open(INVENTORY_FILE, newline="") as f:
            rows = list(csv.DictReader(f))
        updated = False
        for row in rows:
            if row["Container ID"].strip() == container_id.strip():
                row["Status"] = new_status
                updated = True
                break
        if not updated:
            return False
        with open(INVENTORY_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return True


def mark_request_complete(drawing_number: str, station_id: str) -> bool:
    """Mark the first matching 'not complete' request as 'complete'."""
    lock = FileLock(REQUEST_FILE + ".lock")
    with lock:
        if not os.path.exists(REQUEST_FILE):
            return False
        with open(REQUEST_FILE, newline="") as f:
            rows = list(csv.DictReader(f))
        updated = False
        for row in rows:
            if (row["drawing number"].strip() == drawing_number.strip()
                    and row["station ID"].strip() == station_id.strip()
                    and row["request status"].strip().lower() == "not complete"):
                row["request status"] = "complete"
                updated = True
                break
        if not updated:
            return False
        with open(REQUEST_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=REQUEST_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return True


def add_container_to_inventory(container: dict) -> None:
    lock = FileLock(INVENTORY_FILE + ".lock")
    with lock:
        file_exists = os.path.exists(INVENTORY_FILE)
        with open(INVENTORY_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=INVENTORY_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(container)


# ---------------------------------------------------------------------------
# Colour palette (industrial dark theme)
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


def scrollable_column(parent, padx=(0, 0)):
    outer = tk.Frame(parent, bg=BG)
    outer.pack(side="left", fill="both", expand=True, padx=padx)
    canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
    sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    frame = tk.Frame(canvas, bg=BG)
    win = canvas.create_window((0, 0), window=frame, anchor="nw")
    frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
    canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>",
        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")))
    canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
    return frame


class InventoryMESApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.wm_title("MES — Inventory Console")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 680)

        # --- state ---
        self.station_id     = tk.StringVar()
        self.station_locked = False

        self.operator_id    = tk.StringVar()
        self.clocked_in     = False
        self.clock_in_time  = None

        # --- new container fields ---
        self.container_id   = tk.StringVar()
        self.description    = tk.StringVar()
        self.drawing        = tk.StringVar()
        self.vendor         = tk.StringVar()
        self.batch          = tk.StringVar()
        self.scale_id       = tk.StringVar()
        self.quantity_var   = tk.StringVar(value="—")
        self.units_var      = tk.StringVar(value="—")

        self._pending_id    = None   # ID shown on the printed label
        self._container_confirmed = False
        self._scale_confirmed     = False

        # --- check-in state ---
        self._checkin_container  = None
        self._ci_scale_confirmed = False
        self.checkin_cid_var     = tk.StringVar()
        self.ci_description_var  = tk.StringVar(value="—")
        self.ci_drawing_var      = tk.StringVar(value="—")
        self.ci_vendor_var       = tk.StringVar(value="—")
        self.ci_batch_var        = tk.StringVar(value="—")
        self.ci_old_qty_var      = tk.StringVar(value="—")
        self.ci_scale_id_var     = tk.StringVar()
        self.ci_new_qty_var      = tk.StringVar(value="—")
        self.ci_units_var        = tk.StringVar(value="—")

        # --- checkout state ---
        self._selected_request   = None   # request dict from the treeview
        self._checkout_container = None   # inventory row dict after container scan
        self.checkout_cid_var    = tk.StringVar()

        self.co_description_var  = tk.StringVar(value="—")
        self.co_drawing_var      = tk.StringVar(value="—")
        self.co_vendor_var       = tk.StringVar(value="—")
        self.co_batch_var        = tk.StringVar(value="—")
        self.co_qty_var          = tk.StringVar(value="—")
        self.co_status_var       = tk.StringVar(value="—")

        # --- checkin state ---
        self._checkin_container  = None
        self.checkin_cid_var     = tk.StringVar()
        self.ci_description_var  = tk.StringVar(value="—")
        self.ci_drawing_var      = tk.StringVar(value="—")
        self.ci_vendor_var       = tk.StringVar(value="—")
        self.ci_batch_var        = tk.StringVar(value="—")
        self.ci_qty_var          = tk.StringVar(value="—")
        self.ci_status_var       = tk.StringVar(value="—")

        self.notes_var      = tk.StringVar()

        self._build_ui()
        self._tick()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_filepath(self) -> str:
        return os.path.join(BASE_DIR, f"logs/{self.station_id.get()}_mes_log.csv")

    def _status(self, msg: str):
        self.status_var.set(f"{datetime.now().strftime('%H:%M:%S')}  {msg}")

    def _tick(self):
        self.clock_label.config(text=datetime.now().strftime("%Y-%m-%d   %H:%M:%S"))
        self.after(1000, self._tick)

    def _require_clockin(self):
        if not self.clocked_in:
            messagebox.showwarning("Not clocked in", "You must clock in before recording data.")
            return False
        return True

    def _log(self, event_type: str, field: str, value: str) -> dict:
        row = {
            "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "operator_id": self.operator_id.get().strip(),
            "event_type":  event_type,
            "field":       field,
            "value":       value,
            "notes":       self.notes_var.get().strip(),
        }
        write_log_row(row, self._log_filepath())
        self.notes_var.set("")
        return row

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self):
        top = tk.Frame(self, bg="#111418", pady=6)
        top.pack(fill="x")
        self.station_header = tk.Label(top, text="MES INVENTORY CONSOLE",
                 bg="#111418", fg=ACCENT, font=("Courier New", 14, "bold"))
        self.station_header.pack(side="left", padx=16)
        self.clock_label = tk.Label(top, text="", bg="#111418", fg=TEXT_DIM,
                                    font=("Courier New", 11))
        self.clock_label.pack(side="right", padx=16)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        left  = scrollable_column(body, padx=(0, 4))
        right = scrollable_column(body, padx=(4, 0))

        self._build_clock_section(left)
        self._build_container_section(left)

        self._build_requests_section(right)
        self._build_checkout_section(right)
        self._build_checkin_section(right)
        self._build_log_section(left)

        self.status_var = tk.StringVar(value="Ready — please scan station and clock in.")
        tk.Label(self, textvariable=self.status_var, bg="#111418",
                 fg=TEXT_DIM, font=("Courier New", 9), anchor="w", padx=10).pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # Section: Clock In / Out
    # ------------------------------------------------------------------

    def _build_clock_section(self, parent):
        outer, f = section_frame(parent, "1 — OPERATOR CLOCK IN/OUT")
        outer.pack(fill="x", pady=(0, 6))

        styled_label(f, "Station ID:").grid(row=0, column=0, sticky="w", pady=4)
        self.station_entry = styled_entry(f, textvariable=self.station_id, width=18)
        self.station_entry.grid(row=0, column=1, padx=8)
        self.station_entry.bind("<Return>", lambda _: self._scan_station())
        self.btn_scan_station = accent_button(f, "SCAN / CONFIRM", self._scan_station, width=18)
        self.btn_scan_station.grid(row=0, column=2, padx=4)
        self.station_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.station_indicator.grid(row=0, column=3, padx=6)

        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=1, column=0, columnspan=4, sticky="ew", pady=6)

        styled_label(f, "Operator ID:").grid(row=2, column=0, sticky="w", pady=4)
        self.op_entry = styled_entry(f, textvariable=self.operator_id, width=18)
        self.op_entry.grid(row=2, column=1, padx=8)

        self.btn_clockin = accent_button(f, "CLOCK IN", self._clock_in, color=ACCENT2)
        self.btn_clockin.grid(row=2, column=2, padx=4)
        self.btn_clockout = accent_button(f, "CLOCK OUT", self._clock_out, color=DANGER, state="disabled")
        self.btn_clockout.grid(row=2, column=3, padx=4)

        self.op_status = styled_label(f, "Not clocked in", color=TEXT_DIM)
        self.op_status.grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def _scan_station(self):
        station = self.station_id.get().strip()
        if not station:
            messagebox.showwarning("Missing", "Enter or scan a Station ID.")
            return
        self.station_locked = True
        self.station_entry.config(state="disabled")
        self.btn_scan_station.config(state="disabled")
        self.station_indicator.config(text="[OK]", fg=ACCENT2)
        self.station_header.config(text=f"MES — {station.upper()}")
        self.wm_title(f"MES — {station}")
        self.log_label.config(text=f"Logging to: {self._log_filepath()}")
        self._status(f"Station '{station}' confirmed.")

    def _clock_in(self):
        if not self.station_locked:
            messagebox.showwarning("No station", "Scan and confirm the Station ID before clocking in.")
            return
        op = self.operator_id.get().strip()
        if not op:
            messagebox.showwarning("Missing", "Enter an Operator ID before clocking in.")
            return
        if self.clocked_in:
            messagebox.showinfo("Already in", "You are already clocked in.")
            return
        self.clocked_in    = True
        self.clock_in_time = datetime.now()
        row = self._log("CLOCK_IN", "operator_id", op)
        self.op_entry.config(state="disabled")
        self.btn_clockin.config(state="disabled")
        self.btn_clockout.config(state="normal")
        self.op_status.config(text=f"Clocked in as  {op}  at {row['timestamp']}", fg=ACCENT2)
        self._status(f"Clock-in recorded for {op}.")
        self._append_feed(row)

    def _clock_out(self):
        if not self.clocked_in:
            return
        op  = self.operator_id.get().strip()
        row = self._log("CLOCK_OUT", "operator_id", op)
        self.clocked_in = False
        self.op_entry.config(state="normal")
        self.btn_clockin.config(state="normal")
        self.btn_clockout.config(state="disabled")
        self.op_status.config(text="Clocked out.", fg=TEXT_DIM)
        self._status(f"Clock-out recorded for {op}.")
        self._append_feed(row)

    # ------------------------------------------------------------------
    # Section: New Container Entry
    # ------------------------------------------------------------------

    def _build_container_section(self, parent):
        outer, f = section_frame(parent, "2 — NEW CONTAINER ENTRY")
        outer.pack(fill="x", pady=(0, 6))

        # Print label row
        self.btn_print = accent_button(f, "PRINT NEW CONTAINER ID LABEL",
                                       self._print_label, color=ACCENT, width=32)
        self.btn_print.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.pending_id_label = styled_label(f, "", color=WARNING, bold=True)
        self.pending_id_label.grid(row=0, column=2, columnspan=2, sticky="w", padx=8)

        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=1, column=0, columnspan=4, sticky="ew", pady=6)

        # Container ID confirm
        styled_label(f, "Container ID:").grid(row=2, column=0, sticky="w", pady=3)
        self.container_id_entry = styled_entry(f, textvariable=self.container_id, width=18)
        self.container_id_entry.grid(row=2, column=1, padx=8)
        self.container_id_entry.bind("<Return>", lambda _: self._confirm_container_id())
        self.btn_confirm_id = accent_button(f, "SCAN / CONFIRM", self._confirm_container_id, width=18)
        self.btn_confirm_id.grid(row=2, column=2, padx=4)
        self.container_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.container_indicator.grid(row=2, column=3, padx=6)

        # Info fields
        fields = [
            ("Description:", self.description, 3),
            ("Drawing #:",   self.drawing,     4),
            ("Vendor:",      self.vendor,      5),
            ("Batch:",       self.batch,       6),
        ]
        for lbl, var, row in fields:
            styled_label(f, lbl).grid(row=row, column=0, sticky="w", pady=3)
            styled_entry(f, textvariable=var, width=28).grid(row=row, column=1, columnspan=2,
                                                              sticky="w", padx=8)

        # Scale scan
        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=7, column=0, columnspan=4, sticky="ew", pady=6)
        styled_label(f, "Scale ID:").grid(row=8, column=0, sticky="w", pady=3)
        self.scale_entry = styled_entry(f, textvariable=self.scale_id, width=18)
        self.scale_entry.grid(row=8, column=1, padx=8)
        self.scale_entry.bind("<Return>", lambda _: self._scan_scale())
        self.btn_scan_scale = accent_button(f, "SCAN SCALE", self._scan_scale, width=18)
        self.btn_scan_scale.grid(row=8, column=2, padx=4)
        self.scale_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.scale_indicator.grid(row=8, column=3, padx=6)

        styled_label(f, "Quantity:").grid(row=9, column=0, sticky="w", pady=3)
        qty_frame = tk.Frame(f, bg=PANEL_BG)
        qty_frame.grid(row=9, column=1, columnspan=2, sticky="w", padx=8)
        tk.Label(qty_frame, textvariable=self.quantity_var, bg=PANEL_BG, fg=ACCENT,
                 font=("Courier New", 14, "bold")).pack(side="left")
        tk.Label(qty_frame, textvariable=self.units_var, bg=PANEL_BG, fg=TEXT_DIM,
                 font=("Courier New", 10)).pack(side="left", padx=(6, 0))

        # Submit
        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=10, column=0, columnspan=4, sticky="ew", pady=6)
        self.btn_add = accent_button(f, "ADD CONTAINER", self._add_container,
                                     color=ACCENT2, width=20)
        self.btn_add.grid(row=11, column=0, columnspan=2, sticky="w")
        self.btn_reset_form = accent_button(f, "RESET FORM", self._reset_form,
                                            color=WARNING, width=14)
        self.btn_reset_form.grid(row=11, column=2, sticky="w", padx=4)

    def _print_label(self):
        if not self._require_clockin():
            return
        self._pending_id = next_container_id()
        self.pending_id_label.config(text=f"Printed:  {self._pending_id}")
        self._status(f"Label printed — Container ID {self._pending_id}. Apply label and scan.")

    def _confirm_container_id(self):
        if not self._require_clockin():
            return
        scanned = self.container_id.get().strip()
        if not scanned:
            messagebox.showwarning("Missing", "Scan or enter the Container ID from the label.")
            return
        if self._pending_id is None:
            messagebox.showwarning("No label printed", "Click PRINT NEW CONTAINER ID LABEL first.")
            return
        if str(scanned) != str(self._pending_id):
            messagebox.showerror("ID Mismatch",
                                 f"Scanned ID '{scanned}' does not match printed ID '{self._pending_id}'.")
            return
        self._container_confirmed = True
        self.container_id_entry.config(state="disabled")
        self.btn_confirm_id.config(state="disabled")
        self.container_indicator.config(text="[OK]", fg=ACCENT2)
        row = self._log("CONTAINER_SCAN", "container_id", scanned)
        self._status(f"Container {scanned} confirmed.")
        self._append_feed(row)

    def _scan_scale(self):
        if not self._require_clockin():
            return
        scale = self.scale_id.get().strip()
        if not scale:
            messagebox.showwarning("Missing", "Scan or enter a Scale ID.")
            return
        result = read_scale(scale)
        if result is None:
            messagebox.showerror("Scale Not Found",
                                 f"No data file found for scale '{scale}'.\n"
                                 f"Expected: equipment/{scale}.csv")
            return
        reading, units = result
        drawing = self.drawing.get().strip()
        qty, qty_units = estimate_quantity(reading, units, drawing)
        self.quantity_var.set(str(qty))
        self.units_var.set(qty_units)
        self._scale_confirmed = True
        self.scale_entry.config(state="disabled")
        self.btn_scan_scale.config(state="disabled")
        self.scale_indicator.config(text="[OK]", fg=ACCENT2)
        row = self._log("SCALE_SCAN", "scale_id", f"{scale}  raw={reading} {units}  est={qty} {qty_units}")
        self._status(f"Scale {scale}: {reading} {units}  →  {qty} {qty_units}")
        self._append_feed(row)

    def _add_container(self):
        if not self._require_clockin():
            return

        missing = []
        if not self._container_confirmed:
            missing.append("Container ID (scan to confirm)")
        if not self.description.get().strip():
            missing.append("Description")
        if not self.drawing.get().strip():
            missing.append("Drawing #")
        if not self.vendor.get().strip():
            missing.append("Vendor")
        if not self.batch.get().strip():
            missing.append("Batch")
        if not self._scale_confirmed:
            missing.append("Scale reading")
        if missing:
            messagebox.showwarning("Incomplete", "Missing required fields:\n• " + "\n• ".join(missing))
            return

        container = {
            "Container ID":   self.container_id.get().strip(),
            "Drawing Number": self.drawing.get().strip(),
            "Description":    self.description.get().strip(),
            "Vendor":         self.vendor.get().strip(),
            "Batch":          self.batch.get().strip(),
            "Quantity":       self.quantity_var.get(),
            "Units":          self.units_var.get(),
            "Status":         "available",
        }

        add_container_to_inventory(container)

        row = self._log("CONTAINER_ADD", "container_id",
                        f"{container['Container ID']}  {container['Description']}  "
                        f"{container['Quantity']} {container['Units']}")
        self._status(f"Container {container['Container ID']} added to inventory.")
        self._append_feed(row)
        self._reset_form()

    def _reset_form(self):
        self._pending_id          = None
        self._container_confirmed = False
        self._scale_confirmed     = False

        self.pending_id_label.config(text="")
        self.container_id.set("")
        self.description.set("")
        self.drawing.set("")
        self.vendor.set("")
        self.batch.set("")
        self.scale_id.set("")
        self.quantity_var.set("—")
        self.units_var.set("—")

        self.container_id_entry.config(state="normal")
        self.btn_confirm_id.config(state="normal")
        self.container_indicator.config(text="[ ]", fg=TEXT_DIM)

        self.scale_entry.config(state="normal")
        self.btn_scan_scale.config(state="normal")
        self.scale_indicator.config(text="[ ]", fg=TEXT_DIM)

        self._status("Form reset — ready for next container.")

    # ------------------------------------------------------------------
    # Section: Component Requests
    # ------------------------------------------------------------------

    def _build_requests_section(self, parent):
        outer, f = section_frame(parent, "3 — COMPONENT REQUESTS")
        outer.pack(fill="x", pady=(0, 6))

        cols = ("Drawing #", "Description", "Station ID")
        self.req_tree = ttk.Treeview(f, columns=cols, show="headings", height=5)
        widths = [110, 150, 150]
        for col, w in zip(cols, widths):
            self.req_tree.heading(col, text=col)
            self.req_tree.column(col, width=w, anchor="w")

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

        self.req_tree.pack(fill="x")
        self.req_tree.bind("<<TreeviewSelect>>", self._on_request_select)

        btn_refresh = accent_button(f, "REFRESH", self._refresh_requests, width=12)
        btn_refresh.pack(anchor="e", pady=(6, 0))

        btn_row = tk.Frame(f, bg=PANEL_BG)
        btn_row.pack(anchor="w", pady=(6, 0))
        btn_request_trolley = accent_button(btn_row, "REQUEST TROLLEY", self._request_trolley, width=20)
        btn_request_trolley.pack(side="left", padx=(0, 6))
        btn_request_bin = accent_button(btn_row, "REQUEST BIN", self._request_bin, width=20)
        btn_request_bin.pack(side="left")

        self._refresh_requests()

    def _request_trolley(self):
        return
    
    def _request_bin(self):
        return

    def _refresh_requests(self):
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)
        for req in load_requests():
            self.req_tree.insert("", "end", values=(
                req["drawing number"],
                req["description"],
                req["station ID"],
            ))

    def _on_request_select(self, _event):
        sel = self.req_tree.selection()
        if not sel:
            return
        vals = self.req_tree.item(sel[0])["values"]
        self._selected_request = {
            "drawing number": vals[0],
            "description":    vals[1],
            "station ID":     vals[2],
        }
        self.selected_req_label.config(
            text=f"{vals[1]}  [{vals[0]}]  →  {vals[2]}", fg=WARNING)
        self._reset_checkout()
        self._status(f"Request selected: {vals[1]} [{vals[0]}] for {vals[2]}")

    # ------------------------------------------------------------------
    # Section: Check Out
    # ------------------------------------------------------------------

    def _build_checkout_section(self, parent):
        outer, f = section_frame(parent, "4 — CHECK OUT")
        outer.pack(fill="x", pady=(0, 6))

        # Selected request display
        styled_label(f, "Request:").grid(row=0, column=0, sticky="w", pady=3)
        self.selected_req_label = styled_label(f, "None selected", color=TEXT_DIM)
        self.selected_req_label.grid(row=0, column=1, columnspan=3, sticky="w", padx=8)

        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=1, column=0, columnspan=4, sticky="ew", pady=6)

        # Container scan
        styled_label(f, "Container ID:").grid(row=2, column=0, sticky="w", pady=3)
        self.co_id_entry = styled_entry(f, textvariable=self.checkout_cid_var, width=18)
        self.co_id_entry.grid(row=2, column=1, padx=8)
        self.co_id_entry.bind("<Return>", lambda _: self._scan_checkout_container())
        self.btn_co_scan = accent_button(f, "SCAN CONTAINER", self._scan_checkout_container, width=18)
        self.btn_co_scan.grid(row=2, column=2, padx=4)
        self.co_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.co_indicator.grid(row=2, column=3, padx=6)

        # Read-only info fields
        info_rows = [
            ("Description:", self.co_description_var, 3),
            ("Drawing #:",   self.co_drawing_var,      4),
            ("Vendor:",      self.co_vendor_var,        5),
            ("Batch:",       self.co_batch_var,         6),
            ("Qty:",         self.co_qty_var,           7),
            ("Status:",      self.co_status_var,        8),
        ]
        for lbl, var, row in info_rows:
            styled_label(f, lbl).grid(row=row, column=0, sticky="w", pady=2)
            tk.Label(f, textvariable=var, bg=PANEL_BG, fg=ACCENT,
                     font=("Courier New", 10)).grid(row=row, column=1, columnspan=2, sticky="w", padx=8)

        # DWG match indicator
        styled_label(f, "DWG Match:").grid(row=9, column=0, sticky="w", pady=3)
        self.dwg_match_label = styled_label(f, "—", color=TEXT_DIM)
        self.dwg_match_label.grid(row=9, column=1, columnspan=3, sticky="w", padx=8)

        # Buttons
        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=10, column=0, columnspan=4, sticky="ew", pady=6)
        self.btn_checkout = accent_button(f, "CHECK OUT", self._checkout,
                                          color=ACCENT2, width=16, state="disabled")
        self.btn_checkout.grid(row=11, column=0, columnspan=2, sticky="w")
        accent_button(f, "CLEAR", self._reset_checkout, color=WARNING, width=12).grid(
            row=11, column=2, sticky="w", padx=4)

    def _scan_checkout_container(self):
        if not self._require_clockin():
            return
        if self._selected_request is None:
            messagebox.showwarning("No request selected", "Select a component request first.")
            return
        cid = self.checkout_cid_var.get().strip()
        if not cid:
            messagebox.showwarning("Missing", "Scan or enter a Container ID.")
            return

        container = lookup_container(cid)
        if container is None:
            messagebox.showerror("Not Found", f"Container '{cid}' not found in inventory.")
            return

        self._checkout_container = container
        self.co_description_var.set(container["Description"])
        self.co_drawing_var.set(container["Drawing Number"])
        self.co_vendor_var.set(container["Vendor"])
        self.co_batch_var.set(container["Batch"])
        self.co_qty_var.set(f"{container['Quantity']} {container['Units']}")
        self.co_status_var.set(container["Status"])
        self.co_indicator.config(text="[OK]", fg=ACCENT2)
        self.co_id_entry.config(state="disabled")
        self.btn_co_scan.config(state="disabled")

        req_dwg = self._selected_request["drawing number"].strip()
        con_dwg = container["Drawing Number"].strip()

        if req_dwg != con_dwg:
            self.dwg_match_label.config(
                text=f"NO — container is {con_dwg}, request is {req_dwg}", fg=DANGER)
        elif container["Status"].strip().lower() != "available":
            self.dwg_match_label.config(
                text=f"YES — but status is '{container['Status']}' (not available)", fg=WARNING)
        else:
            self.dwg_match_label.config(text=f"YES — {con_dwg}", fg=ACCENT2)
            self.btn_checkout.config(state="normal")

        row = self._log("CONTAINER_SCAN", "container_id",
                        f"{cid}  {container['Description']}  [{container['Drawing Number']}]")
        self._status(f"Container {cid}: {container['Description']}")
        self._append_feed(row)

    def _checkout(self):
        if not self._require_clockin():
            return
        if self._selected_request is None or self._checkout_container is None:
            return

        cid        = self._checkout_container["Container ID"]
        station_id = self._selected_request["station ID"]
        new_status = f"in use - {station_id}"

        if not update_container_status(cid, new_status):
            messagebox.showerror("Error", f"Could not update status for container {cid}.")
            return

        mark_request_complete(
            self._selected_request["drawing number"],
            self._selected_request["station ID"],
        )

        row = self._log("CHECKOUT", "container_id",
                        f"{cid}  →  {station_id}  [{self._checkout_container['Description']}]")
        self._status(f"Container {cid} checked out to {station_id}.")
        self._append_feed(row)

        self._selected_request = None
        self.selected_req_label.config(text="None selected", fg=TEXT_DIM)
        self._refresh_requests()
        self._reset_checkout()

    def _reset_checkout(self):
        self._checkout_container = None
        self.checkout_cid_var.set("")
        self.co_description_var.set("—")
        self.co_drawing_var.set("—")
        self.co_vendor_var.set("—")
        self.co_batch_var.set("—")
        self.co_qty_var.set("—")
        self.co_status_var.set("—")
        self.dwg_match_label.config(text="—", fg=TEXT_DIM)
        self.co_indicator.config(text="[ ]", fg=TEXT_DIM)
        self.co_id_entry.config(state="normal")
        self.btn_co_scan.config(state="normal")
        self.btn_checkout.config(state="disabled")


    # ------------------------------------------------------------------
    # Section: Check In
    # ------------------------------------------------------------------

    def _build_checkin_section(self, parent):
        outer, f = section_frame(parent, "5 — CHECK IN")
        outer.pack(fill="x", pady=(0, 6))

        # Container scan
        styled_label(f, "Container ID:").grid(row=0, column=0, sticky="w", pady=3)
        self.ci_id_entry = styled_entry(f, textvariable=self.checkin_cid_var, width=18)
        self.ci_id_entry.grid(row=0, column=1, padx=8)
        self.ci_id_entry.bind("<Return>", lambda _: self._scan_checkin_container())
        self.btn_ci_scan = accent_button(f, "SCAN CONTAINER", self._scan_checkin_container, width=18)
        self.btn_ci_scan.grid(row=0, column=2, padx=4)
        self.ci_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.ci_indicator.grid(row=0, column=3, padx=6)

        # Read-only info
        info_rows = [
            ("Description:", self.ci_description_var, 1),
            ("Drawing #:",   self.ci_drawing_var,      2),
            ("Vendor:",      self.ci_vendor_var,        3),
            ("Batch:",       self.ci_batch_var,         4),
            ("Current Qty:", self.ci_old_qty_var,       5),
        ]
        for lbl, var, row in info_rows:
            styled_label(f, lbl).grid(row=row, column=0, sticky="w", pady=2)
            tk.Label(f, textvariable=var, bg=PANEL_BG, fg=ACCENT,
                     font=("Courier New", 10)).grid(row=row, column=1, columnspan=2, sticky="w", padx=8)

        # Scale scan
        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=6, column=0, columnspan=4, sticky="ew", pady=6)
        styled_label(f, "Scale ID:").grid(row=7, column=0, sticky="w", pady=3)
        self.ci_scale_entry = styled_entry(f, textvariable=self.ci_scale_id_var, width=18)
        self.ci_scale_entry.grid(row=7, column=1, padx=8)
        self.ci_scale_entry.bind("<Return>", lambda _: self._scan_checkin_scale())
        self.btn_ci_scale = accent_button(f, "SCAN SCALE", self._scan_checkin_scale, width=18)
        self.btn_ci_scale.grid(row=7, column=2, padx=4)
        self.ci_scale_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.ci_scale_indicator.grid(row=7, column=3, padx=6)

        styled_label(f, "New Qty:").grid(row=8, column=0, sticky="w", pady=3)
        qty_frame = tk.Frame(f, bg=PANEL_BG)
        qty_frame.grid(row=8, column=1, columnspan=2, sticky="w", padx=8)
        tk.Label(qty_frame, textvariable=self.ci_new_qty_var, bg=PANEL_BG, fg=ACCENT,
                 font=("Courier New", 14, "bold")).pack(side="left")
        tk.Label(qty_frame, textvariable=self.ci_units_var, bg=PANEL_BG, fg=TEXT_DIM,
                 font=("Courier New", 10)).pack(side="left", padx=(6, 0))

        # Buttons
        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=9, column=0, columnspan=4, sticky="ew", pady=6)
        self.btn_checkin = accent_button(f, "CHECK IN", self._checkin,
                                         color=ACCENT2, width=16, state="disabled")
        self.btn_checkin.grid(row=10, column=0, columnspan=2, sticky="w")
        accent_button(f, "CLEAR", self._reset_checkin, color=WARNING, width=12).grid(
            row=10, column=2, sticky="w", padx=4)

    def _scan_checkin_container(self):
        if not self._require_clockin():
            return
        cid = self.checkin_cid_var.get().strip()
        if not cid:
            messagebox.showwarning("Missing", "Scan or enter a Container ID.")
            return
        container = lookup_container(cid)
        if container is None:
            messagebox.showerror("Not Found", f"Container '{cid}' not found in inventory.")
            return
        if not container["Status"].strip().lower().startswith("in use"):
            messagebox.showwarning("Not checked out",
                                   f"Container {cid} has status '{container['Status']}'.\n"
                                   "Only 'in use' containers can be checked in.")
            return

        self._checkin_container = container
        self.ci_description_var.set(container["Description"])
        self.ci_drawing_var.set(container["Drawing Number"])
        self.ci_vendor_var.set(container["Vendor"])
        self.ci_batch_var.set(container["Batch"])
        self.ci_old_qty_var.set(f"{container['Quantity']} {container['Units']}")
        self.ci_indicator.config(text="[OK]", fg=ACCENT2)
        self.ci_id_entry.config(state="disabled")
        self.btn_ci_scan.config(state="disabled")

        row = self._log("CONTAINER_SCAN", "container_id",
                        f"{cid}  {container['Description']}  (check-in)")
        self._status(f"Container {cid} ready for check-in. Place on scale and scan.")
        self._append_feed(row)

    def _scan_checkin_scale(self):
        if not self._require_clockin():
            return
        if self._checkin_container is None:
            messagebox.showwarning("No container", "Scan the container first.")
            return
        scale = self.ci_scale_id_var.get().strip()
        if not scale:
            messagebox.showwarning("Missing", "Scan or enter a Scale ID.")
            return
        result = read_scale(scale)
        if result is None:
            messagebox.showerror("Scale Not Found",
                                 f"No data file found for scale '{scale}'.\n"
                                 f"Expected: equipment/{scale}.csv")
            return
        reading, units = result
        drawing = self._checkin_container.get("Drawing Number", "").strip()
        qty, qty_units = estimate_quantity(reading, units, drawing)
        self.ci_new_qty_var.set(str(qty))
        self.ci_units_var.set(qty_units)
        self._ci_scale_confirmed = True
        self.ci_scale_entry.config(state="disabled")
        self.btn_ci_scale.config(state="disabled")
        self.ci_scale_indicator.config(text="[OK]", fg=ACCENT2)
        self.btn_checkin.config(state="normal")

        row = self._log("SCALE_SCAN", "scale_id", f"{scale}  raw={reading} {units}  est={qty} {qty_units}")
        self._status(f"Scale {scale}: {reading} {units}  →  {qty} {qty_units}")
        self._append_feed(row)

    def _checkin(self):
        if not self._require_clockin():
            return
        if self._checkin_container is None or not self._ci_scale_confirmed:
            return

        cid     = self._checkin_container["Container ID"]
        new_qty = float(self.ci_new_qty_var.get())
        units   = self.ci_units_var.get()

        if not update_container_quantity_and_status(cid, new_qty, "available"):
            messagebox.showerror("Error", f"Could not update container {cid}.")
            return

        row = self._log("CHECKIN", "container_id",
                        f"{cid}  new qty={new_qty} {units}  [{self._checkin_container['Description']}]")
        self._status(f"Container {cid} checked in. New quantity: {new_qty} {units}")
        self._append_feed(row)
        self._reset_checkin()

    def _reset_checkin(self):
        self._checkin_container  = None
        self._ci_scale_confirmed = False
        self.checkin_cid_var.set("")
        self.ci_description_var.set("—")
        self.ci_drawing_var.set("—")
        self.ci_vendor_var.set("—")
        self.ci_batch_var.set("—")
        self.ci_old_qty_var.set("—")
        self.ci_scale_id_var.set("")
        self.ci_new_qty_var.set("—")
        self.ci_units_var.set("—")
        self.ci_indicator.config(text="[ ]", fg=TEXT_DIM)
        self.ci_id_entry.config(state="normal")
        self.btn_ci_scan.config(state="normal")
        self.ci_scale_indicator.config(text="[ ]", fg=TEXT_DIM)
        self.ci_scale_entry.config(state="normal")
        self.btn_ci_scale.config(state="normal")
        self.btn_checkin.config(state="disabled")


    # ------------------------------------------------------------------
    # Section: Event feed
    # ------------------------------------------------------------------

    def _build_log_section(self, parent):
        outer, f = section_frame(parent, "EVENT FEED")
        outer.pack(fill="both", expand=True)

        self.feed_text = tk.Text(f, bg="#0d1117", fg=TEXT, font=("Courier New", 9),
                                 state="disabled", wrap="word",
                                 relief="flat", highlightthickness=0)
        self.feed_text.pack(fill="both", expand=True)

        sb = tk.Scrollbar(f, command=self.feed_text.yview)
        sb.pack(side="right", fill="y")
        self.feed_text.config(yscrollcommand=sb.set)

        self.feed_text.tag_config("ts",    foreground=TEXT_DIM)
        self.feed_text.tag_config("event", foreground=ACCENT)
        self.feed_text.tag_config("ok",    foreground=ACCENT2)
        self.feed_text.tag_config("clock", foreground="#bb88ff")

        self.log_label = styled_label(f, "Logging to: (scan station to set)", size=8, color=TEXT_DIM)
        self.log_label.pack(anchor="w", pady=(4, 0))

    def _append_feed(self, row: dict):
        tag_map = {
            "CLOCK_IN":       "clock",
            "CLOCK_OUT":      "clock",
            "CONTAINER_ADD":  "ok",
            "CHECKOUT":       "ok",
            "CHECKIN":        "ok",
            "CONTAINER_SCAN": "event",
            "SCALE_SCAN":     "event",
        }
        event_tag = tag_map.get(row["event_type"], "event")
        self.feed_text.config(state="normal")
        self.feed_text.insert("end", f"[{row['timestamp']}] ", "ts")
        self.feed_text.insert("end", f"{row['event_type']:<16} ", event_tag)
        self.feed_text.insert("end",
                              f"{row['field']}: {row['value']}"
                              + (f"  ({row['notes']})" if row.get("notes") else "") + "\n")
        self.feed_text.see("end")
        self.feed_text.config(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = InventoryMESApp()
    app.mainloop()
