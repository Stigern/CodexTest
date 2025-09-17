import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk


DB_FILE = "printer_service.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def initialize_database():
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                printer_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                manufacturer TEXT,
                model TEXT,
                hours INTEGER DEFAULT 0,
                nozzle_type TEXT,
                ams INTEGER DEFAULT 0
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                printer_id_fk INTEGER NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(printer_id_fk) REFERENCES printers(id) ON DELETE CASCADE
            );
            """
        )
        # Migrate existing DBs by adding missing columns
        cols = {row[1] for row in conn.execute("PRAGMA table_info(printers)").fetchall()}
        if "nozzle_type" not in cols:
            conn.execute("ALTER TABLE printers ADD COLUMN nozzle_type TEXT;")
        if "ams" not in cols:
            conn.execute("ALTER TABLE printers ADD COLUMN ams INTEGER DEFAULT 0;")


class PrinterServiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Printer Service Logger")
        self.geometry("1180x720")
        self.minsize(1050, 600)
        self.configure(padx=8, pady=8)

        self.sort_hours = None  # None | 'asc' | 'desc'

        self._build_ui()
        self.refresh_printers()

    # UI construction
    def _build_ui(self):
        # Split into left (list) and right (form + logs)
        container = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        container.pack(fill=tk.BOTH, expand=True)

        # Left pane: printers list
        left_frame = ttk.Frame(container)
        container.add(left_frame, weight=1)

        self.printer_tree = ttk.Treeview(
            left_frame,
            columns=("printer_id", "name", "manufacturer", "model", "hours", "nozzle_type", "ams"),
            show="headings",
            selectmode="browse",
        )
        for col, text, width in [
            ("printer_id", "Printer ID", 120),
            ("name", "Name", 160),
            ("manufacturer", "Manufacturer", 140),
            ("model", "Model", 140),
            ("hours", "Hours", 80),
            ("nozzle_type", "Nozzle", 100),
            ("ams", "AMS", 60),
        ]:
            self.printer_tree.heading(col, text=text)
            self.printer_tree.column(col, width=width, anchor=tk.W)
        self.printer_tree.pack(fill=tk.BOTH, expand=True)
        self.printer_tree.bind("<<TreeviewSelect>>", lambda e: self.on_select_printer())
        # Right-click context menu for printers list
        self.printer_menu = tk.Menu(self, tearoff=0)
        self.printer_menu.add_command(label="Duplicate", command=lambda: self.duplicate_selected_printer())
        self.printer_tree.bind("<Button-3>", self._on_printer_right_click)

        btns_frame = ttk.Frame(left_frame)
        btns_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns_frame, text="Add", command=self.add_printer_dialog).pack(side=tk.LEFT)
        ttk.Button(btns_frame, text="Edit", command=self.edit_selected_printer).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns_frame, text="Delete", command=self.delete_selected_printer).pack(side=tk.LEFT)
        ttk.Button(btns_frame, text="Hours ▲", command=lambda: self.set_sort_hours('asc')).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(btns_frame, text="Hours ▼", command=lambda: self.set_sort_hours('desc')).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btns_frame, text="Refresh", command=self.refresh_printers).pack(side=tk.RIGHT)

        # Right pane: details + logs
        right_frame = ttk.Frame(container)
        container.add(right_frame, weight=2)

        # Details form
        form = ttk.LabelFrame(right_frame, text="Printer Details")
        form.pack(fill=tk.X)

        self.var_printer_id = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_manufacturer = tk.StringVar()
        self.var_model = tk.StringVar()
        self.var_hours = tk.StringVar()
        self.var_nozzle_type = tk.StringVar()
        self.var_ams = tk.BooleanVar()

        def add_row(row, label, entry_var, width=40):
            ttk.Label(form, text=label).grid(row=row, column=0, padx=6, pady=6, sticky=tk.E)
            e = ttk.Entry(form, textvariable=entry_var, width=width)
            e.grid(row=row, column=1, padx=6, pady=6, sticky=tk.W)
            return e

        self.entry_printer_id = add_row(0, "Printer ID:", self.var_printer_id)
        self.entry_name = add_row(1, "Name:", self.var_name)
        self.entry_manufacturer = add_row(2, "Manufacturer:", self.var_manufacturer)
        self.entry_model = add_row(3, "Model:", self.var_model)
        self.entry_hours = add_row(4, "Hours:", self.var_hours)
        self.entry_nozzle = add_row(5, "Nozzle Type:", self.var_nozzle_type)
        ttk.Label(form, text="AMS:").grid(row=6, column=0, padx=6, pady=6, sticky=tk.E)
        ttk.Checkbutton(form, variable=self.var_ams).grid(row=6, column=1, padx=6, pady=6, sticky=tk.W)

        form_btns = ttk.Frame(form)
        form_btns.grid(row=0, column=2, rowspan=7, padx=6, pady=6, sticky=tk.N)
        ttk.Button(form_btns, text="Save As New", command=self.save_as_new_printer).pack(fill=tk.X)
        ttk.Button(form_btns, text="Update Selected", command=self.update_selected_printer).pack(fill=tk.X, pady=6)
        ttk.Button(form_btns, text="Clear Form", command=self.clear_form).pack(fill=tk.X)

        # Logs section
        logs = ttk.LabelFrame(right_frame, text="Service Logs for Selected Printer")
        logs.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.logs_tree = ttk.Treeview(
            logs, columns=("created_at", "note"), show="headings", selectmode="browse"
        )
        self.logs_tree.heading("created_at", text="Date")
        self.logs_tree.heading("note", text="Note / Task")
        self.logs_tree.column("created_at", width=150, anchor=tk.W)
        self.logs_tree.column("note", width=500, anchor=tk.W)
        self.logs_tree.pack(fill=tk.BOTH, expand=True)

        logs_btns = ttk.Frame(logs)
        logs_btns.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(logs_btns, text="Add Note", command=self.add_log_dialog).pack(side=tk.LEFT)
        ttk.Button(logs_btns, text="Edit Note", command=self.edit_selected_log).pack(side=tk.LEFT, padx=6)
        ttk.Button(logs_btns, text="Delete Note", command=self.delete_selected_log).pack(side=tk.LEFT)
        ttk.Button(logs_btns, text="Refresh", command=self.refresh_logs).pack(side=tk.RIGHT)

    # DB helpers
    def fetch_printers(self):
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            order_clause = "ORDER BY name"
            if self.sort_hours == 'asc':
                order_clause = "ORDER BY hours ASC, name"
            elif self.sort_hours == 'desc':
                order_clause = "ORDER BY hours DESC, name"
            rows = conn.execute(
                f"SELECT id, printer_id, name, manufacturer, model, hours, nozzle_type, ams FROM printers {order_clause}"
            ).fetchall()
            return rows

    def insert_printer(self, printer_id, name, manufacturer, model, hours, nozzle_type, ams):
        try:
            hours_val = int(hours) if str(hours).strip() != "" else 0
        except ValueError:
            raise ValueError("Hours must be an integer")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO printers (printer_id, name, manufacturer, model, hours, nozzle_type, ams) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    printer_id.strip(),
                    name.strip(),
                    manufacturer.strip(),
                    model.strip(),
                    hours_val,
                    (nozzle_type or "").strip(),
                    1 if ams else 0,
                ),
            )

    def update_printer(self, db_id, printer_id, name, manufacturer, model, hours, nozzle_type, ams):
        try:
            hours_val = int(hours) if str(hours).strip() != "" else 0
        except ValueError:
            raise ValueError("Hours must be an integer")
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE printers
                SET printer_id = ?, name = ?, manufacturer = ?, model = ?, hours = ?, nozzle_type = ?, ams = ?
                WHERE id = ?
                """,
                (
                    printer_id.strip(),
                    name.strip(),
                    manufacturer.strip(),
                    model.strip(),
                    hours_val,
                    (nozzle_type or "").strip(),
                    1 if ams else 0,
                    db_id,
                ),
            )

    def delete_printer(self, db_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM printers WHERE id = ?", (db_id,))

    def get_printer_by_db_id(self, db_id):
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT printer_id, name, manufacturer, model, hours, nozzle_type, ams
                FROM printers WHERE id = ?
                """,
                (db_id,),
            ).fetchone()
            return row

    def ensure_unique_printer_id(self, base_printer_id):
        base = base_printer_id.strip() or "printer"
        candidate = base
        idx = 1
        with get_connection() as conn:
            while True:
                exists = conn.execute(
                    "SELECT 1 FROM printers WHERE printer_id = ? LIMIT 1", (candidate,)
                ).fetchone()
                if not exists:
                    return candidate
                idx += 1
                candidate = f"{base}-{idx}"

    def fetch_logs_for(self, db_id):
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            rows = conn.execute(
                "SELECT id, created_at, note FROM service_logs WHERE printer_id_fk = ? ORDER BY created_at DESC",
                (db_id,),
            ).fetchall()
            return rows

    def insert_log(self, db_id, note):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO service_logs (printer_id_fk, note) VALUES (?, ?)",
                (db_id, note.strip()),
            )

    def update_log(self, log_id, note):
        with get_connection() as conn:
            conn.execute(
                "UPDATE service_logs SET note = ? WHERE id = ?",
                (note.strip(), log_id),
            )

    def delete_log(self, log_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM service_logs WHERE id = ?", (log_id,))

    # UI actions
    def refresh_printers(self):
        for item in self.printer_tree.get_children():
            self.printer_tree.delete(item)
        for row in self.fetch_printers():
            db_id, printer_id, name, manufacturer, model, hours, nozzle_type, ams = row
            self.printer_tree.insert(
                "",
                tk.END,
                iid=str(db_id),
                values=(
                    printer_id,
                    name,
                    manufacturer or "",
                    model or "",
                    hours or 0,
                    nozzle_type or "",
                    "Yes" if (ams or 0) else "No",
                ),
            )
        self.on_select_printer()

    def on_select_printer(self):
        selection = self.printer_tree.selection()
        if not selection:
            self.clear_form()
            self.clear_logs()
            return
        iid = selection[0]
        values = self.printer_tree.item(iid, "values")
        self.var_printer_id.set(values[0])
        self.var_name.set(values[1])
        self.var_manufacturer.set(values[2])
        self.var_model.set(values[3])
        self.var_hours.set(str(values[4]))
        self.var_nozzle_type.set(values[5])
        self.var_ams.set(True if str(values[6]).lower() == "yes" else False)
        self.refresh_logs()

    def clear_form(self):
        self.var_printer_id.set("")
        self.var_name.set("")
        self.var_manufacturer.set("")
        self.var_model.set("")
        self.var_hours.set("")
        self.var_nozzle_type.set("")
        self.var_ams.set(False)

    def get_selected_printer_db_id(self):
        selection = self.printer_tree.selection()
        return int(selection[0]) if selection else None

    def save_as_new_printer(self):
        try:
            self.insert_printer(
                self.var_printer_id.get(),
                self.var_name.get(),
                self.var_manufacturer.get(),
                self.var_model.get(),
                self.var_hours.get(),
                self.var_nozzle_type.get(),
                self.var_ams.get(),
            )
            self.refresh_printers()
            messagebox.showinfo("Success", "Printer added.")
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Error", f"Integrity error: {e}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_selected_printer(self):
        db_id = self.get_selected_printer_db_id()
        if not db_id:
            messagebox.showwarning("No selection", "Please select a printer to update.")
            return
        try:
            self.update_printer(
                db_id,
                self.var_printer_id.get(),
                self.var_name.get(),
                self.var_manufacturer.get(),
                self.var_model.get(),
                self.var_hours.get(),
                self.var_nozzle_type.get(),
                self.var_ams.get(),
            )
            self.refresh_printers()
            messagebox.showinfo("Updated", "Printer updated.")
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Error", f"Integrity error: {e}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def set_sort_hours(self, order):
        self.sort_hours = order
        self.refresh_printers()

    def add_printer_dialog(self):
        self.clear_form()
        self.entry_printer_id.focus_set()

    def edit_selected_printer(self):
        # Form already reflects selection; just ensure something is selected
        if not self.get_selected_printer_db_id():
            messagebox.showwarning("No selection", "Select a printer to edit.")
            return
        self.entry_name.focus_set()

    def delete_selected_printer(self):
        db_id = self.get_selected_printer_db_id()
        if not db_id:
            messagebox.showwarning("No selection", "Select a printer to delete.")
            return
        if not messagebox.askyesno("Confirm", "Delete selected printer and all its logs?"):
            return
        try:
            self.delete_printer(db_id)
            self.refresh_printers()
            messagebox.showinfo("Deleted", "Printer removed.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_printer_right_click(self, event):
        iid = self.printer_tree.identify_row(event.y)
        if iid:
            self.printer_tree.selection_set(iid)
            try:
                self.printer_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.printer_menu.grab_release()

    def duplicate_selected_printer(self):
        db_id = self.get_selected_printer_db_id()
        if not db_id:
            messagebox.showwarning("No selection", "Select a printer to duplicate.")
            return
        try:
            row = self.get_printer_by_db_id(db_id)
            if not row:
                messagebox.showerror("Error", "Selected printer not found.")
                return
            src_printer_id, name, manufacturer, model, hours, nozzle_type, ams = row
            new_printer_id = self.ensure_unique_printer_id(f"{src_printer_id}-copy")
            new_name = (name or "").strip() + " (Copy)"
            self.insert_printer(
                new_printer_id,
                new_name,
                manufacturer or "",
                model or "",
                hours or 0,
                nozzle_type or "",
                bool(ams),
            )
            self.refresh_printers()
            messagebox.showinfo("Duplicated", f"Printer duplicated as {new_printer_id}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Logs
    def clear_logs(self):
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

    def refresh_logs(self):
        self.clear_logs()
        db_id = self.get_selected_printer_db_id()
        if not db_id:
            return
        for log_id, created_at, note in self.fetch_logs_for(db_id):
            self.logs_tree.insert("", tk.END, iid=f"log-{log_id}", values=(created_at, note))

    def get_selected_log_id(self):
        sel = self.logs_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if not iid.startswith("log-"):
            return None
        return int(iid.split("-", 1)[1])

    def add_log_dialog(self):
        db_id = self.get_selected_printer_db_id()
        if not db_id:
            messagebox.showwarning("No printer", "Select a printer first.")
            return
        self._open_log_editor(title="Add Service Note", on_submit=lambda text: self._add_log(db_id, text))

    def _add_log(self, db_id, text):
        if not text.strip():
            return
        try:
            self.insert_log(db_id, text)
            self.refresh_logs()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def edit_selected_log(self):
        log_id = self.get_selected_log_id()
        if not log_id:
            messagebox.showwarning("No selection", "Select a note to edit.")
            return
        # preload existing text
        note_text = self.logs_tree.item(f"log-{log_id}", "values")[1]
        self._open_log_editor(
            title="Edit Service Note",
            initial=note_text,
            on_submit=lambda text: self._update_log(log_id, text),
        )

    def _update_log(self, log_id, text):
        if not text.strip():
            return
        try:
            self.update_log(log_id, text)
            self.refresh_logs()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_selected_log(self):
        log_id = self.get_selected_log_id()
        if not log_id:
            messagebox.showwarning("No selection", "Select a note to delete.")
            return
        if not messagebox.askyesno("Confirm", "Delete selected note?"):
            return
        try:
            self.delete_log(log_id)
            self.refresh_logs()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_log_editor(self, title, on_submit, initial=""):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.grab_set()
        dlg.transient(self)
        dlg.geometry("680x460")
        dlg.minsize(620, 380)

        txt = tk.Text(dlg, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        if initial:
            txt.insert("1.0", initial)

        btns = ttk.Frame(dlg)
        btns.pack(fill=tk.X, padx=8, pady=8)

        def submit():
            on_submit(txt.get("1.0", tk.END).strip())
            dlg.destroy()

        ttk.Button(btns, text="OK", command=submit).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT, padx=(0, 8))

        # Ensure the dialog is large enough to show buttons even on high DPI
        dlg.update_idletasks()
        req_w = max(dlg.winfo_reqwidth(), 680)
        req_h = max(dlg.winfo_reqheight(), 420)
        dlg.minsize(req_w, req_h)
        dlg.geometry(f"{req_w}x{req_h}")


def main():
    initialize_database()
    app = PrinterServiceApp()
    app.mainloop()


if __name__ == "__main__":
    main()


