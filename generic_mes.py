"""
MES Operator Screen Mockup — Any process
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
BUILD_INFO_DIR = os.path.join(BASE_DIR, "build_info")
INVENTORY_FILE = os.path.join(BASE_DIR, "inventory_tracker.csv")
INVENTORY_FIELDS = [
    "Container ID", "Drawing Number", "Description",
    "Vendor", "Batch", "Quantity", "Units", "Status",
]
REQUEST_FILE = os.path.join(BASE_DIR, "component_requests.csv")
REQUEST_FIELDS = [
    "drawing number", "description", "station ID", "request status"
]


LOG_FIELDS = ["timestamp", "operator_id", "build_number", "batch_number", "event_type", "field", "value", "notes"]

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


# ---------------------------------------------------------------------------
# Build order helpers
# ---------------------------------------------------------------------------

def write_component_request(drawing_number: str, description: str, station_id: str) -> None:
    lock = FileLock(REQUEST_FILE + ".lock")
    with lock:
        file_exists = os.path.exists(REQUEST_FILE)
        with open(REQUEST_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=REQUEST_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "drawing number": drawing_number,
                "description":    description,
                "station ID":     station_id,
                "request status": "not complete",
            })


def lookup_container(container_id: str) -> dict | None:
    if not os.path.exists(INVENTORY_FILE):
        return None
    with open(INVENTORY_FILE, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Container ID", "").strip() == container_id.strip():
                return row
    return None


def load_build_order(build_number: str) -> dict | None:
    filepath = os.path.join(BUILD_INFO_DIR, f"{build_number}.yaml")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return yaml.safe_load(f)
    return None


def update_build_order(build_number: str, parts_completed: int, station_name: str) -> dict:
    """Overwrite parts_completed and recalculate status for the given process."""
    filepath = os.path.join(BUILD_INFO_DIR, f"{build_number}.yaml")
    lock = FileLock(filepath + ".lock")
    with lock:
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        station = next((p for p in data["Processes"] if p["Name"] == station_name), None)
        if station is None:
            return data

        station["Parts Completed"] = parts_completed
        if parts_completed == 0:
            station["Status"] = "Not Started"
        elif parts_completed < station["Total Parts"]:
            station["Status"] = "In Progress"
        else:
            station["Status"] = "Complete"

        processes = data["Processes"]
        if processes and all(p["Status"] == "Complete" for p in processes):
            data["Status"] = "Complete"
        elif processes and any(p["Status"] == "In Progress" for p in processes):
            data["Status"] = "In Progress"
        else:
            data["Status"] = "Not Started"

        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return data


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


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class MESApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.wm_title("MES — Operator Console")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 680)

        # --- state ---
        self.station_id    = tk.StringVar()
        self.station_number = tk.StringVar()
        self.station_locked = False

        self.operator_id   = tk.StringVar()
        self.clocked_in    = False
        self.clock_in_time = None

        self.build_number   = tk.StringVar()
        self.build_name     = tk.StringVar(value="—")
        self.build_quantity = tk.StringVar(value="—")
        self.build_status   = tk.StringVar(value="—")
        self.build_locked   = False
        self.build_order    = None

        self.equipment_id  = tk.StringVar()
        self.batch_locked  = False
        self._comp_scan_state   = []   # {"var": StringVar, "confirmed": bool, "drawing_number": str}
        self._comp_scan_widgets = []   # {"entry": Entry, "btn": Button, "indicator": Label}
        self.equip_locked  = False

        self.cycle_running = False
        self.cycle_start   = None
        self.parts_count   = tk.IntVar(value=0)

        self.defect_type   = tk.StringVar(value="Flash")
        self.defect_qty    = tk.StringVar(value="1")
        self.notes_var     = tk.StringVar()

        self.lbl_drawing_var     = tk.StringVar(value="—")
        self.lbl_description_var = tk.StringVar(value="—")
        self.lbl_vendor_var      = tk.StringVar(value="—")
        self.lbl_batch_var       = tk.StringVar(value="—")

        self._build_ui()
        self._tick()   # live clock

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_filepath(self) -> str:
        return os.path.join(BASE_DIR, f"logs/{self.station_id.get()}_{self.station_number.get()}_mes_log.csv")

    def _status(self, msg: str):
        self.status_var.set(f"{datetime.now().strftime('%H:%M:%S')}  {msg}")

    def _tick(self):
        self.clock_label.config(text=datetime.now().strftime("%Y-%m-%d   %H:%M:%S"))
        self.after(1000, self._tick)

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── top bar ─────────────────────────────────────────────────────
        top = tk.Frame(self, bg="#111418", pady=6)
        top.pack(fill="x")
        self.station_header = tk.Label(top, text="MES OPERATOR CONSOLE",
                 bg="#111418", fg=ACCENT, font=("Courier New", 14, "bold"))
        self.station_header.pack(side="left", padx=16)
        self.clock_label = tk.Label(top, text="", bg="#111418", fg=TEXT_DIM,
                                    font=("Courier New", 11))
        self.clock_label.pack(side="right", padx=16)

        # ── main columns ────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        left  = scrollable_column(body, padx=(0, 4))
        right = scrollable_column(body, padx=(4, 0))

        # left column
        self._build_clock_section(left)
        self._build_job_section(left)
        self._build_production_section(left)

        # right column
        self._build_defect_section(right)
        self._build_print_labels_section(right)
        self._build_log_section(right)

        # ── status bar ──────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready — please scan station and clock in.")
        status = tk.Label(self, textvariable=self.status_var, bg="#111418",
                          fg=TEXT_DIM, font=("Courier New", 9), anchor="w", padx=10)
        status.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # Section: Clock In / Out
    # ------------------------------------------------------------------

    def _build_clock_section(self, parent):
        outer, f = section_frame(parent, "1 — OPERATOR CLOCK IN/OUT")
        outer.pack(fill="x", pady=(0, 6))

        # Station scan row
        styled_label(f, "Station ID:").grid(row=0, column=0, sticky="w", pady=4)
        self.station_entry = styled_entry(f, textvariable=self.station_id, width=18)
        self.station_entry.grid(row=0, column=1, padx=8)
        self.station_entry.bind("<Return>", lambda e: self._scan_station())
        self.btn_scan_station = accent_button(f, "SCAN / CONFIRM", self._scan_station, width=18)
        self.btn_scan_station.grid(row=0, column=2, padx=4)
        self.station_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.station_indicator.grid(row=0, column=3, padx=6)

        # Station number scan row
        styled_label(f, "Station Number:").grid(row=1, column=0, sticky="w", pady=4)
        self.station_number_entry = styled_entry(f, textvariable=self.station_number, width=18)
        self.station_number_entry.grid(row=1, column=1, padx=8)
        self.station_number_entry.bind("<Return>", lambda e: self._scan_station_number())
        self.btn_scan_station_number = accent_button(f, "SCAN / CONFIRM", self._scan_station_number, width=18)
        self.btn_scan_station_number.grid(row=1, column=2, padx=4)
        self.station_number_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.station_number_indicator.grid(row=1, column=3, padx=6)

        # Separator
        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=2, column=0, columnspan=4,
                                                 sticky="ew", pady=6)

        # Operator scan row
        styled_label(f, "Operator ID:").grid(row=3, column=0, sticky="w", pady=4)
        self.op_entry = styled_entry(f, textvariable=self.operator_id, width=18)
        self.op_entry.grid(row=3, column=1, padx=8)

        self.btn_clockin = accent_button(f, "CLOCK IN", self._clock_in, color=ACCENT2)
        self.btn_clockin.grid(row=4, column=2, padx=4)
        self.btn_clockout = accent_button(f, "CLOCK OUT", self._clock_out, color=DANGER, state="disabled")
        self.btn_clockout.grid(row=4, column=3, padx=4)

        self.op_status = styled_label(f, "Not clocked in", color=TEXT_DIM)
        self.op_status.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

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

    def _scan_station_number(self):
        station = self.station_id.get().strip()
        station_number = self.station_number.get().strip()
        if not station_number:
            messagebox.showwarning("Missing", "Enter or scan a station number.")
            return
        self.station_locked = True
        self.station_number_entry.config(state="disabled")
        self.btn_scan_station_number.config(state="disabled")
        self.station_number_indicator.config(text="[OK]", fg=ACCENT2)
        self.station_header.config(text=f"MES - {station.upper()} - {station_number.upper()}")
        self.wm_title(f"MES - {station} - {station_number}")
        self.log_label.config(text=f"Logging to: {self._log_filepath()}")
        self._status(f"Station Number {station_number}.")

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
        if self.cycle_running:
            messagebox.showwarning("Cycle running", "Stop the production cycle before clocking out.")
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
    # Section: Job Setup (batch + equipment)
    # ------------------------------------------------------------------

    def _build_job_section(self, parent):
        outer, f = section_frame(parent, "2 — JOB SETUP")
        outer.pack(fill="x", pady=(0, 6))

        # Build Info
        styled_label(f, "Build Number:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=4)
        styled_label(f, "Build Name:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        styled_label(f, "Build Quantity:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=2)
        styled_label(f, "Build Status:").grid(row=3, column=0, sticky="w", padx=(0, 4), pady=2)

        self.build_number_entry = styled_entry(f, textvariable=self.build_number, width=18)
        self.build_number_entry.grid(row=0, column=1, padx=8)
        self.build_number_entry.bind("<Return>", lambda e: self._scan_build_info())

        self.btn_scan_build = accent_button(f, "SCAN / CONFIRM", self._scan_build_info, width=18)
        self.btn_scan_build.grid(row=0, column=2, padx=4)
        self.build_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.build_indicator.grid(row=0, column=3, padx=6)

        tk.Label(f, textvariable=self.build_name, bg=PANEL_BG, fg=ACCENT,
                 font=("Courier New", 10)).grid(row=1, column=1, columnspan=2, sticky="w", padx=8)
        tk.Label(f, textvariable=self.build_quantity, bg=PANEL_BG, fg=ACCENT,
                 font=("Courier New", 10)).grid(row=2, column=1, columnspan=2, sticky="w", padx=8)
        self.build_status_label = tk.Label(f, textvariable=self.build_status, bg=PANEL_BG,
                                           fg=TEXT_DIM, font=("Courier New", 10, "bold"))
        self.build_status_label.grid(row=3, column=1, columnspan=2, sticky="w", padx=8)

        styled_label(f, "Components:").grid(row=4, column=0, sticky="nw", padx=(0, 4), pady=(4, 2))
        self.components_label = tk.Label(f, text="—", bg=PANEL_BG, fg=TEXT_DIM,
                                         font=("Courier New", 9), justify="left", anchor="w")
        self.components_label.grid(row=4, column=1, columnspan=2, sticky="w", padx=8, pady=(4, 2))
        self.btn_request_comp = accent_button(f, "REQUEST\nCOMPONENTS", self._request_components,
                                              color=WARNING, width=14)
        self.btn_request_comp.grid(row=4, column=3, sticky="n", padx=4, pady=(4, 2))

        tk.Frame(f, bg=TEXT_DIM, height=1).grid(row=5, column=0, columnspan=4,
                                                 sticky="ew", pady=6)

        # Dynamic per-component container scan rows (populated in _build_container_scan_rows)
        self._container_frame = tk.Frame(f, bg=PANEL_BG)
        self._container_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=2)

        # Equipment
        styled_label(f, "Equipment ID:").grid(row=7, column=0, sticky="w", pady=4)
        self.equip_entry = styled_entry(f, textvariable=self.equipment_id, width=18)
        self.equip_entry.grid(row=7, column=1, padx=8)
        self.equip_entry.bind("<Return>", lambda e: self._scan_equip())
        self.btn_scan_equip = accent_button(f, "SCAN / CONFIRM", self._scan_equip, width=18)
        self.btn_scan_equip.grid(row=7, column=2, padx=4)
        self.equip_indicator = styled_label(f, "[ ]", color=TEXT_DIM)
        self.equip_indicator.grid(row=7, column=3, padx=6)

        btn_reset = accent_button(f, "RESET JOB", self._reset_job, color=WARNING, width=12)
        btn_reset.grid(row=8, column=2, sticky="e", pady=(8, 0))

    def _require_clockin(self):
        if not self.clocked_in:
            messagebox.showwarning("Not clocked in", "You must clock in before recording data.")
            return False
        return True

    def _scan_build_info(self):
        if not self._require_clockin():
            return
        build_num = self.build_number.get().strip()
        if not build_num:
            messagebox.showwarning("Missing", "Enter or scan a Build Number.")
            return

        order = load_build_order(build_num)
        if order is None:
            messagebox.showerror("Not Found", f"Build number '{build_num}' not found.")
            return
        self._build_order = order

        station_name = self.station_id.get().strip()
        station = next((p for p in order["Processes"] if p["Name"] == station_name), None)
        if station is None:
            messagebox.showerror("Error", f"Build {build_num} has no '{station_name}' process.")
            return

        qty       = int(station["Total Parts"])
        completed = int(station["Parts Completed"])

        self.build_name.set(order["Name"])
        self.build_quantity.set(f"{completed} / {qty}")
        self.build_status.set(station["Status"])
        self._refresh_build_status_color(station["Status"])

        comp_lines = [
            f"{c['Name']}  {c['Quantity']} {c.get('Units', '')}  [{c['Drawing Number']}]"
            for c in station.get("Components", [])
        ]
        self.components_label.config(
            text="\n".join(comp_lines) if comp_lines else "—",
            fg=TEXT_DIM,
        )

        self._build_container_scan_rows(station)

        self.build_locked = True
        self.build_number_entry.config(state="disabled")
        self.btn_scan_build.config(state="disabled")
        self.build_indicator.config(text="[OK]", fg=ACCENT2)

        row = self._log("BUILD_SCAN", "build_number", build_num)
        self._status(f"Build {build_num} — {order['Name']} loaded.")
        self._append_feed(row)

    def _refresh_build_status_color(self, status: str):
        color_map = {
            "Not Started": TEXT_DIM,
            "In Progress": WARNING,
            "Complete":    ACCENT2,
        }
        self.build_status_label.config(fg=color_map.get(status, TEXT))

    def _build_container_scan_rows(self, station: dict):
        for w in self._container_frame.winfo_children():
            w.destroy()
        self._comp_scan_state.clear()
        self._comp_scan_widgets.clear()
        self.batch_locked = False

        components = station.get("Components", [])
        if not components:
            styled_label(self._container_frame, "No components required.").grid(row=0, column=0, sticky="w")
            self.batch_locked = True
            return

        for i, comp in enumerate(components):
            var = tk.StringVar()
            self._comp_scan_state.append({
                "var": var,
                "confirmed": False,
                "drawing_number": comp["Drawing Number"],
            })
            lbl_text = f"{comp['Name']} [{comp['Drawing Number']}]:"
            styled_label(self._container_frame, lbl_text).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 4))
            entry = styled_entry(self._container_frame, textvariable=var, width=18)
            entry.grid(row=i, column=1, padx=8)
            entry.bind("<Return>", lambda _, idx=i: self._scan_component_container(idx))
            btn = accent_button(self._container_frame, "SCAN", lambda idx=i: self._scan_component_container(idx), width=12)
            btn.grid(row=i, column=2, padx=4)
            indicator = styled_label(self._container_frame, "[ ]", color=TEXT_DIM)
            indicator.grid(row=i, column=3, padx=6)
            self._comp_scan_widgets.append({"entry": entry, "btn": btn, "indicator": indicator})

    def _scan_component_container(self, index: int):
        if not self._require_clockin():
            return
        state   = self._comp_scan_state[index]
        widgets = self._comp_scan_widgets[index]
        container_id = state["var"].get().strip()
        if not container_id:
            messagebox.showwarning("Missing", "Enter or scan a Container ID.")
            return

        record = lookup_container(container_id)
        if record is None:
            messagebox.showerror("Not Found", f"Container '{container_id}' not in inventory.")
            widgets["indicator"].config(text="[??]", fg=DANGER)
            return

        required_dwg = state["drawing_number"]
        actual_dwg   = record.get("Drawing Number", "").strip()
        if actual_dwg != required_dwg:
            messagebox.showwarning(
                "DWG Mismatch",
                f"Container {container_id}: drawing {actual_dwg}, expected {required_dwg}.",
            )
            widgets["indicator"].config(text="[DWG!]", fg=DANGER)
            state["confirmed"] = False
            return

        state["confirmed"] = True
        widgets["entry"].config(state="disabled")
        widgets["btn"].config(state="disabled")
        widgets["indicator"].config(text="[OK]", fg=ACCENT2)

        row = self._log("CONTAINER_SCAN", "container_id", container_id)
        self._status(f"Container {container_id} confirmed — {record.get('Description', '')}.")
        self._append_feed(row)

        if all(s["confirmed"] for s in self._comp_scan_state):
            self.batch_locked = True
            self._status("All component containers confirmed.")

    def _scan_equip(self):
        if not self._require_clockin():
            return
        val = self.equipment_id.get().strip()
        if not val:
            messagebox.showwarning("Missing", "Enter or scan an equipment ID.")
            return
        row = self._log("EQUIP_SCAN", "equipment_id", val)
        self.equip_locked = True
        self.equip_entry.config(state="disabled")
        self.btn_scan_equip.config(state="disabled")
        self.equip_indicator.config(text="[OK]", fg=ACCENT2)
        self._status(f"Equipment {val} confirmed.")
        self._append_feed(row)

    def _reset_job(self):
        if self.cycle_running:
            messagebox.showwarning("Cycle running", "Stop the production cycle before resetting the job.")
            return
        self.build_number.set("")
        self.build_name.set("—")
        self.build_quantity.set("—")
        self.build_status.set("—")
        self.components_label.config(text="—", fg=TEXT_DIM)
        self.build_locked = False
        self.build_number_entry.config(state="normal")
        self.btn_scan_build.config(state="normal")
        self.build_indicator.config(text="[ ]", fg=TEXT_DIM)
        self.build_status_label.config(fg=TEXT_DIM)
        for w in self._container_frame.winfo_children():
            w.destroy()
        self._comp_scan_state.clear()
        self._comp_scan_widgets.clear()
        self.batch_locked = False
        self.equipment_id.set("")
        self.equip_locked = False
        self.equip_entry.config(state="normal")
        self.btn_scan_equip.config(state="normal")
        self.equip_indicator.config(text="[ ]", fg=TEXT_DIM)
        self.parts_count.set(0)
        self._status("Job reset.")

    def _request_components(self):
        if not self._require_clockin():
            return
        if not self.build_locked:
            messagebox.showwarning("No build", "Scan and confirm a Build Number first.")
            return

        station_name = self.station_id.get().strip()
        station_num  = self.station_number.get().strip()
        station_full = f"{station_name}_{station_num}" if station_num else station_name

        station = next(
            (p for p in self._build_order["Processes"] if p["Name"] == station_name), None
        )
        if station is None:
            return

        components = station.get("Components", [])
        if not components:
            messagebox.showinfo("No components", "No components listed for this process.")
            return

        for comp in components:
            write_component_request(comp["Drawing Number"], comp["Name"], station_full)

        names = ", ".join(c["Name"] for c in components)
        row = self._log("COMP_REQUEST", "components", f"{names}  →  {station_full}")
        self._status(f"Requested {len(components)} component(s): {names}")
        self._append_feed(row)

    # ------------------------------------------------------------------
    # Section: Production cycle
    # ------------------------------------------------------------------

    def _build_production_section(self, parent):
        outer, f = section_frame(parent, "3 — PRODUCTION")
        outer.pack(fill="x", pady=(0, 6))

        self.btn_start = accent_button(f, "START CYCLE", self._start_cycle, color=ACCENT2)
        self.btn_start.grid(row=0, column=0, padx=4, pady=4)
        self.btn_stop  = accent_button(f, "STOP CYCLE",  self._stop_cycle,  color=DANGER, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=4)

        styled_label(f, "Parts Produced:").grid(row=0, column=2, padx=(20, 4))
        tk.Label(f, textvariable=self.parts_count, bg=PANEL_BG, fg=ACCENT,
                 font=("Courier New", 22, "bold")).grid(row=0, column=3)

        btn_inc = accent_button(f, "+1 Part", self._increment_part, width=10)
        btn_inc.grid(row=0, column=4, padx=8)

        self.cycle_status = styled_label(f, "Cycle stopped.", color=TEXT_DIM)
        self.cycle_status.grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))

        self.equip_info_var = tk.StringVar(value="")
        self.equip_info_label = tk.Label(f, textvariable=self.equip_info_var,
                                         bg=PANEL_BG, fg=ACCENT,
                                         font=("Courier New", 9), anchor="w")
        self.equip_info_label.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(4, 0))

        styled_label(f, "Notes:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        notes_entry = styled_entry(f, textvariable=self.notes_var, width=48)
        notes_entry.grid(row=3, column=1, columnspan=4, sticky="ew", padx=4, pady=(8, 0))

    # ------------------------------------------------------------------
    # Core logger
    # ------------------------------------------------------------------

    def _log(self, event_type: str, field: str, value: str) -> dict:
        row = {
            "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "operator_id":  self.operator_id.get().strip(),
            "build_number": self.build_number.get().strip(),
            "batch_number": ",".join(
                s["var"].get().strip() for s in self._comp_scan_state if s["confirmed"]
            ),
            "event_type":   event_type,
            "field":        field,
            "value":        value,
            "notes":        self.notes_var.get().strip(),
        }
        write_log_row(row, self._log_filepath())
        self.notes_var.set("")
        return row

    def _ready_for_production(self):
        if not self._require_clockin():
            return False
        if not self.build_locked:
            messagebox.showwarning("Job incomplete", "Scan and confirm the Build Number first.")
            return False
        if not self.batch_locked:
            messagebox.showwarning("Job incomplete", "Confirm all component containers first.")
            return False
        # if not self.equip_locked:
        #     messagebox.showwarning("Job incomplete", "Confirm the equipment ID first.")
        #     return False
        return True

    def _start_cycle(self):
        if not self._ready_for_production():
            return
        if self.cycle_running:
            return
        self.cycle_running = True
        self.cycle_start   = datetime.now()
        row = self._log("CYCLE_START", "cycle", "started")
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.cycle_status.config(text=f"Cycle running since {row['timestamp']}", fg=ACCENT2)
        self._status("Production cycle started.")
        self._append_feed(row)

    def _stop_cycle(self):
        if not self.cycle_running:
            return
        self.cycle_running = False
        elapsed = (datetime.now() - self.cycle_start).seconds
        row = self._log("CYCLE_STOP", "cycle", f"elapsed_sec={elapsed} parts={self.parts_count.get()}")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.cycle_status.config(text=f"Cycle stopped. Duration: {elapsed}s", fg=TEXT_DIM)
        self._status(f"Cycle stopped after {elapsed}s.")
        self._append_feed(row)

    def _read_equipment_info(self) -> str:
        equip_id = self.equipment_id.get().strip()
        if not equip_id:
            return ""
        path = os.path.join(BASE_DIR, "equipment", f"{equip_id}.csv")
        if not os.path.exists(path):
            return ""
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            return ""
        last = rows[-1]
        parts = [
            f"{k}: {v}"
            for k, v in last.items()
            if k and k.lower() != "timestamp" and v.strip()
        ]
        return "  |  ".join(parts)

    def _increment_part(self):
        if not self.cycle_running:
            messagebox.showwarning("No cycle", "Start a production cycle first.")
            return
        new_count = self.parts_count.get() + 1
        self.parts_count.set(new_count)

        build_num    = self.build_number.get().strip()
        station_name = self.station_id.get().strip()
        if build_num:
            updated = update_build_order(build_num, new_count, station_name)
            if updated:
                station = next((p for p in updated["Processes"] if p["Name"] == station_name), None)
                if station:
                    self.build_quantity.set(f"{new_count} / {station['Total Parts']}")
                    self.build_status.set(station["Status"])
                    self._refresh_build_status_color(station["Status"])

        self.equip_info_var.set(self._read_equipment_info())

        row = self._log("PART_COUNT", "parts_produced", str(new_count))
        self._append_feed(row)

    # ------------------------------------------------------------------
    # Section: Defect logging
    # ------------------------------------------------------------------

    DEFECT_TYPES = [
        "Flash", "Short Shot", "Sink Mark", "Weld Line", "Burn Mark",
        "Warping", "Jetting", "Silver Streaks", "Delamination",
        "Voids / Bubbles", "Discoloration", "Other",
    ]

    def _build_defect_section(self, parent):
        outer, f = section_frame(parent, "4 — DEFECT LOG")
        outer.pack(fill="x", pady=(0, 6))

        styled_label(f, "Defect Type:").grid(row=0, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(f, textvariable=self.defect_type, values=self.DEFECT_TYPES,
                             state="readonly", width=22, font=("Courier New", 11))
        combo.grid(row=0, column=1, padx=8)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=ENTRY_BG, background=ENTRY_BG,
                        foreground=ENTRY_FG, selectbackground=ACCENT, selectforeground="#ffffff")

        styled_label(f, "Qty:").grid(row=0, column=2, padx=(10, 4))
        qty_entry = styled_entry(f, textvariable=self.defect_qty, width=5)
        qty_entry.grid(row=0, column=3)

        btn_log = accent_button(f, "LOG DEFECT", self._log_defect, color=WARNING, width=14)
        btn_log.grid(row=0, column=4, padx=8)

        self.defect_tally_frame = tk.Frame(f, bg=PANEL_BG)
        self.defect_tally_frame.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        self.defect_tally: dict[str, int] = {}
        self.defect_labels: dict[str, tk.Label] = {}

    def _log_defect(self):
        if not self._ready_for_production():
            return
        dtype = self.defect_type.get().strip()
        try:
            qty = int(self.defect_qty.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid qty", "Defect quantity must be a positive integer.")
            return
        row = self._log("DEFECT", "defect_type", f"{dtype} x{qty}")
        self.defect_tally[dtype] = self.defect_tally.get(dtype, 0) + qty
        self._refresh_tally()
        self._status(f"Defect logged: {dtype} × {qty}")
        self._append_feed(row)

    def _refresh_tally(self):
        for w in self.defect_tally_frame.winfo_children():
            w.destroy()
        col = 0
        for dtype, count in sorted(self.defect_tally.items()):
            color = WARNING if count < 5 else DANGER
            lbl = tk.Label(self.defect_tally_frame, text=f"{dtype}: {count}",
                           bg=PANEL_BG, fg=color, font=("Courier New", 9, "bold"),
                           padx=6, pady=2, relief="groove")
            lbl.grid(row=0, column=col, padx=4, pady=2)
            col += 1

    
    # ------------------------------------------------------------------
    # Section: Print labels for containers
    # ------------------------------------------------------------------
    def _build_print_labels_section(self, parent):
        outer, f = section_frame(parent, "PRINT CONTAINER LABELS")
        outer.pack(fill="both", expand=True)

        
        # self.btn_print_unused_partials = accent_button(f, "PRINT UNUSED PARTIALS LABEL", self._print_unused_partials, width=30)
        # self.btn_print_unused_partials.grid(row=0, column=0, padx=4)
        
        self.btn_print_finished_parts = accent_button(f, "PRINT FINISHED PARTS LABEL", self._print_finished_parts, width=30)
        self.btn_print_finished_parts.grid(row=1, column=0, padx=4)

        self.btn_print_scrap = accent_button(f, "PRINT SCRAP LABEL", self._print_scrap, width=30)
        self.btn_print_scrap.grid(row=2, column=0, padx=4)

        def val_label(var):
            return tk.Label(f, textvariable=var, bg=PANEL_BG, fg=ACCENT,
                            font=("Courier New", 10))

        styled_label(f, "Drawing Number:").grid(row=3, column=0, sticky="w", padx=(0, 4), pady=2)
        val_label(self.lbl_drawing_var).grid(row=3, column=1, sticky="w", padx=8)
        styled_label(f, "Description:").grid(row=4, column=0, sticky="w", padx=(0, 4), pady=2)
        val_label(self.lbl_description_var).grid(row=4, column=1, sticky="w", padx=8)
        styled_label(f, "Vendor:").grid(row=5, column=0, sticky="w", padx=(0, 4), pady=2)
        val_label(self.lbl_vendor_var).grid(row=5, column=1, sticky="w", padx=8)
        styled_label(f, "Batch:").grid(row=6, column=0, sticky="w", padx=(0, 4), pady=2)
        val_label(self.lbl_batch_var).grid(row=6, column=1, sticky="w", padx=8)

        self.btn_request_trolley = accent_button(f, "REQUEST TROLLEY", self._request_trolley, width=20)
        self.btn_request_trolley.grid(row=7, column=0, padx=4)

        self.btn_request_bin = accent_button(f, "REQUEST BIN", self._request_bin, width=20)
        self.btn_request_bin.grid(row=7, column=1, padx=4)

    def _request_trolley(self):
        return
    
    def _request_bin(self):
        return
    # def _print_unused_partials(self):
    #     if not self._require_clockin():
    #         return
    #     if not self.build_locked:
    #         messagebox.showwarning("No build", "Scan and confirm a Build Number first.")
    #         return
    #     station_name = self.station_id.get().strip()
    #     station = next(
    #         (p for p in self._build_order["Processes"] if p["Name"] == station_name), None
    #     )
    #     if station is None:
    #         return
    #     output_comp = next(
    #         (c for c in station.get("Components", [])
    #          if c["Name"].lower().startswith("output")),
    #         None,
    #     )
    #     if output_comp is None:
    #         messagebox.showwarning("Not found", "No output component found for this process.")
    #         return
    #     self.lbl_drawing_var.set(output_comp["Drawing Number"])
    #     self.lbl_description_var.set(output_comp["Name"])
    #     self._status(f"Label: {output_comp['Name']} [{output_comp['Drawing Number']}]")
    #     self.lbl_vendor_var.set("Internal")
    #     self.lbl_batch_var.set(self.build_number.get().strip())

    def _print_finished_parts(self):
        if not self._require_clockin():
            return
        if not self.build_locked:
            messagebox.showwarning("No build", "Scan and confirm a Build Number first.")
            return
        station_name = self.station_id.get().strip()
        station = next(
            (p for p in self._build_order["Processes"] if p["Name"] == station_name), None
        )
        if station is None:
            return
        
        finished_comp_number = self._build_order["Top Assembly Drawing Number"]
        finished_comp_name = self._build_order["Top Assembly Drawing Name"]

        self.lbl_drawing_var.set(finished_comp_number)
        self.lbl_description_var.set(finished_comp_name)
        self._status(f"Label: {finished_comp_name} [{finished_comp_number}]")
        self.lbl_vendor_var.set("Internal")
        self.lbl_batch_var.set(self.build_number.get().strip())


        # finished_comp = next(
        #     (c for c in station.get("Components", [])
        #      if c["Name"].lower().startswith("scrap")),
        #     None,
        # )
        # if scrap_comp is None:
        #     messagebox.showwarning("Not found", "No scrap component found for this process.")
        #     return
        # self.lbl_drawing_var.set(scrap_comp["Drawing Number"])
        # self.lbl_description_var.set(scrap_comp["Name"])
        # self._status(f"Label: {scrap_comp['Name']} [{scrap_comp['Drawing Number']}]")
        # self.lbl_vendor_var.set("Internal")
        # self.lbl_batch_var.set(self.build_number.get().strip())

    def _print_scrap(self):
        if not self._require_clockin():
            return
        if not self.build_locked:
            messagebox.showwarning("No build", "Scan and confirm a Build Number first.")
            return
        station_name = self.station_id.get().strip()
        station = next(
            (p for p in self._build_order["Processes"] if p["Name"] == station_name), None
        )
        if station is None:
            return
        scrap_comp = next(
            (c for c in station.get("Components", [])
             if c["Name"].lower().startswith("scrap")),
            None,
        )
        if scrap_comp is None:
            messagebox.showwarning("Not found", "No scrap component found for this process.")
            return
        self.lbl_drawing_var.set(scrap_comp["Drawing Number"])
        self.lbl_description_var.set(scrap_comp["Name"])
        self._status(f"Label: {scrap_comp['Name']} [{scrap_comp['Drawing Number']}]")
        self.lbl_vendor_var.set("Internal")
        self.lbl_batch_var.set(self.build_number.get().strip())

    # ------------------------------------------------------------------
    # Section: Event feed / log viewer
    # ------------------------------------------------------------------

    def _build_log_section(self, parent):
        outer, f = section_frame(parent, "EVENT FEED")
        outer.pack(fill="both", expand=True)

        self.feed_text = tk.Text(f, bg="#0d1117", fg=TEXT, font=("Courier New", 9),
                                 state="disabled", wrap="word",
                                 relief="flat", highlightthickness=0)
        self.feed_text.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(f, command=self.feed_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.feed_text.config(yscrollcommand=scrollbar.set)

        self.feed_text.tag_config("ts",    foreground=TEXT_DIM)
        self.feed_text.tag_config("event", foreground=ACCENT)
        self.feed_text.tag_config("defect",foreground=WARNING)
        self.feed_text.tag_config("cycle", foreground=ACCENT2)
        self.feed_text.tag_config("clock", foreground="#bb88ff")

        self.log_label = styled_label(f, "Logging to: (scan station to set)", size=8, color=TEXT_DIM)
        self.log_label.pack(anchor="w", pady=(4, 0))

    def _append_feed(self, row: dict):
        tag_map = {
            "DEFECT":       "defect",
            "CYCLE_START":  "cycle",
            "CYCLE_STOP":   "cycle",
            "CLOCK_IN":     "clock",
            "CLOCK_OUT":    "clock",
            "BUILD_SCAN":   "event",
            "COMP_REQUEST": "warning",
        }
        event_tag = tag_map.get(row["event_type"], "event")
        self.feed_text.config(state="normal")
        self.feed_text.insert("end", f"[{row['timestamp']}] ", "ts")
        self.feed_text.insert("end", f"{row['event_type']:<12} ", event_tag)
        self.feed_text.insert("end",
                              f"{row['field']}: {row['value']}"
                              + (f"  ({row['notes']})" if row['notes'] else "") + "\n")
        self.feed_text.see("end")
        self.feed_text.config(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = MESApp()
    app.mainloop()
