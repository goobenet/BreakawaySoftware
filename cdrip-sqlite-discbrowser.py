#!/usr/bin/env python3
"""
cdrip_db_browser.py
Tkinter desktop companion app to browse & edit c:\temp\cdrip\ripped.db

Requirements: Python 3 (no external packages).
Run: python cdrip_db_browser.py
"""

import os
import sqlite3
import csv
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

DB_PATH = r"c:\temp\cdrip\ripped.db"
BACKUP_DIR = r"c:\temp\cdrip\backups"

# Ensure DB exists (create with tables if not)
def ensure_db(path=DB_PATH):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    created = not os.path.exists(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS written_tracks (
        title TEXT,
        track_id TEXT,
        track_title TEXT,
        PRIMARY KEY (title, track_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS written_discs (
        title TEXT,
        cddb_id TEXT,
        PRIMARY KEY (title, cddb_id)
    )
    """)
    conn.commit()
    conn.close()
    return created

def make_backup(db_path=DB_PATH):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    basename = os.path.basename(db_path)
    import datetime
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"{basename}.{stamp}.bak")
    shutil.copy2(db_path, dest)
    return dest

class DB:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    # Tracks
    def get_tracks(self, filter_text=None):
        cur = self.conn.cursor()
        if filter_text:
            q = "%{}%".format(filter_text)
            cur.execute("SELECT title, track_id, track_title FROM written_tracks WHERE title LIKE ? OR track_id LIKE ? OR track_title LIKE ? ORDER BY title, track_id", (q,q,q))
        else:
            cur.execute("SELECT title, track_id, track_title FROM written_tracks ORDER BY title, track_id")
        return cur.fetchall()

    def insert_track(self, title, track_id, track_title):
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO written_tracks (title, track_id, track_title) VALUES (?, ?, ?)", (title, track_id, track_title))
        self.conn.commit()

    def delete_track(self, title, track_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM written_tracks WHERE title=? AND track_id=?", (title, track_id))
        self.conn.commit()

    # Discs
    def get_discs(self, filter_text=None):
        cur = self.conn.cursor()
        if filter_text:
            q = "%{}%".format(filter_text)
            cur.execute("SELECT title, cddb_id FROM written_discs WHERE title LIKE ? OR cddb_id LIKE ? ORDER BY title", (q,q))
        else:
            cur.execute("SELECT title, cddb_id FROM written_discs ORDER BY title")
        return cur.fetchall()

    def insert_disc(self, title, cddb_id):
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO written_discs (title, cddb_id) VALUES (?, ?)", (title, cddb_id))
        self.conn.commit()

    def delete_disc(self, title, cddb_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM written_discs WHERE title=? AND cddb_id=?", (title, cddb_id))
        self.conn.commit()

class App(tk.Tk):
    def __init__(self, dbpath=DB_PATH):
        super().__init__()
        self.title("BreakawayCD DB Browser")
        self.geometry("900x600")
        self.dbpath = dbpath
        ensure_db(self.dbpath)
        self.db = DB(self.dbpath)

        self._build_ui()

    def _build_ui(self):
        # Top toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x")

        backup_btn = ttk.Button(toolbar, text="Backup DB", command=self._backup_db)
        backup_btn.pack(side="left", padx=4, pady=4)

        open_btn = ttk.Button(toolbar, text="Open DB...", command=self._open_db_file)
        open_btn.pack(side="left", padx=4, pady=4)

        help_btn = ttk.Button(toolbar, text="Help", command=self._show_help)
        help_btn.pack(side="right", padx=4, pady=4)

        # Tabs
        tab_control = ttk.Notebook(self)
        tab_control.pack(fill="both", expand=True)

        # Tracks tab
        self.tracks_tab = ttk.Frame(tab_control)
        tab_control.add(self.tracks_tab, text="Tracks")

        self._build_tracks_tab(self.tracks_tab)

        # Discs tab
        self.discs_tab = ttk.Frame(tab_control)
        tab_control.add(self.discs_tab, text="Discs")

        self._build_discs_tab(self.discs_tab)

        # status bar
        self.status = tk.StringVar(value=f"DB: {self.dbpath}")
        statusbar = ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w")
        statusbar.pack(side="bottom", fill="x")

        # load initial data
        self.load_tracks()
        self.load_discs()

    # ----------------- Tracks Tab -----------------
    def _build_tracks_tab(self, parent):
        top = ttk.Frame(parent)
        top.pack(side="top", fill="x", padx=6, pady=6)

        search_lbl = ttk.Label(top, text="Search:")
        search_lbl.pack(side="left")
        self.tracks_search = ttk.Entry(top)
        self.tracks_search.pack(side="left", padx=4)
        self.tracks_search.bind("<Return>", lambda e: self.load_tracks())

        search_btn = ttk.Button(top, text="Filter", command=self.load_tracks)
        search_btn.pack(side="left", padx=2)

        clear_btn = ttk.Button(top, text="Clear", command=lambda: (self.tracks_search.delete(0, tk.END), self.load_tracks()))
        clear_btn.pack(side="left", padx=2)

        add_btn = ttk.Button(top, text="Add Track", command=self.add_track)
        add_btn.pack(side="left", padx=8)

        edit_btn = ttk.Button(top, text="Edit Selected", command=self.edit_selected_track)
        edit_btn.pack(side="left", padx=2)

        del_btn = ttk.Button(top, text="Delete Selected", command=self.delete_selected_track)
        del_btn.pack(side="left", padx=2)

        export_btn = ttk.Button(top, text="Export CSV", command=lambda: self.export_csv(kind="tracks"))
        export_btn.pack(side="right", padx=4)

        # Treeview
        cols = ("title", "track_id", "track_title")
        self.tracks_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tracks_tree.heading(c, text=c.replace("_"," ").title())
            self.tracks_tree.column(c, width=250 if c=="title" else 200, anchor="w")
        self.tracks_tree.pack(fill="both", expand=True, padx=6, pady=(0,6))
        self.tracks_tree.bind("<Double-1>", lambda e: self.edit_selected_track())

    def load_tracks(self):
        for r in self.tracks_tree.get_children():
            self.tracks_tree.delete(r)
        q = self.tracks_search.get().strip()
        rows = self.db.get_tracks(filter_text=q if q else None)
        for row in rows:
            self.tracks_tree.insert("", "end", values=(row["title"], row["track_id"], row["track_title"]))
        self.status.set(f"Loaded {len(rows)} tracks. DB: {self.dbpath}")

    def add_track(self):
        dlg = TrackDialog(self, title="Add Track")
        if dlg.result:
            title, track_id, track_title = dlg.result
            try:
                make_backup(self.dbpath)
                self.db.insert_track(title, track_id, track_title)
                self.load_tracks()
            except Exception as e:
                messagebox.showerror("Error", f"Insert failed: {e}")

    def edit_selected_track(self):
        cur = self.tracks_tree.selection()
        if not cur:
            messagebox.showinfo("Edit Track", "Select a track first.")
            return
        values = self.tracks_tree.item(cur[0], "values")
        dlg = TrackDialog(self, title="Edit Track", initial=values)
        if dlg.result:
            title, track_id, track_title = dlg.result
            try:
                make_backup(self.dbpath)
                self.db.insert_track(title, track_id, track_title)
                self.load_tracks()
            except Exception as e:
                messagebox.showerror("Error", f"Update failed: {e}")

    def delete_selected_track(self):
        cur = self.tracks_tree.selection()
        if not cur:
            messagebox.showinfo("Delete Track", "Select a track first.")
            return
        values = self.tracks_tree.item(cur[0], "values")
        title, track_id = values[0], values[1]
        if messagebox.askyesno("Confirm Delete", f"Delete track {track_id} from '{title}'?"):
            try:
                bak = make_backup(self.dbpath)
                self.db.delete_track(title, track_id)
                self.load_tracks()
                messagebox.showinfo("Deleted", f"Deleted. Backup created: {bak}")
            except Exception as e:
                messagebox.showerror("Error", f"Delete failed: {e}")

    # ----------------- Discs Tab -----------------
    def _build_discs_tab(self, parent):
        top = ttk.Frame(parent)
        top.pack(side="top", fill="x", padx=6, pady=6)

        search_lbl = ttk.Label(top, text="Search:")
        search_lbl.pack(side="left")
        self.discs_search = ttk.Entry(top)
        self.discs_search.pack(side="left", padx=4)
        self.discs_search.bind("<Return>", lambda e: self.load_discs())

        search_btn = ttk.Button(top, text="Filter", command=self.load_discs)
        search_btn.pack(side="left", padx=2)

        clear_btn = ttk.Button(top, text="Clear", command=lambda: (self.discs_search.delete(0, tk.END), self.load_discs()))
        clear_btn.pack(side="left", padx=2)

        add_btn = ttk.Button(top, text="Add Disc", command=self.add_disc)
        add_btn.pack(side="left", padx=8)

        edit_btn = ttk.Button(top, text="Edit Selected", command=self.edit_selected_disc)
        edit_btn.pack(side="left", padx=2)

        del_btn = ttk.Button(top, text="Delete Selected", command=self.delete_selected_disc)
        del_btn.pack(side="left", padx=2)

        export_btn = ttk.Button(top, text="Export CSV", command=lambda: self.export_csv(kind="discs"))
        export_btn.pack(side="right", padx=4)

        # Treeview
        cols = ("title", "cddb_id")
        self.discs_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.discs_tree.heading(c, text=c.replace("_"," ").title())
            self.discs_tree.column(c, width=400 if c=="title" else 300, anchor="w")
        self.discs_tree.pack(fill="both", expand=True, padx=6, pady=(0,6))
        self.discs_tree.bind("<Double-1>", lambda e: self.edit_selected_disc())

    def load_discs(self):
        for r in self.discs_tree.get_children():
            self.discs_tree.delete(r)
        q = self.discs_search.get().strip()
        rows = self.db.get_discs(filter_text=q if q else None)
        for row in rows:
            self.discs_tree.insert("", "end", values=(row["title"], row["cddb_id"]))
        self.status.set(f"Loaded {len(rows)} discs. DB: {self.dbpath}")

    def add_disc(self):
        dlg = DiscDialog(self, title="Add Disc")
        if dlg.result:
            title, cddb_id = dlg.result
            try:
                make_backup(self.dbpath)
                self.db.insert_disc(title, cddb_id)
                self.load_discs()
            except Exception as e:
                messagebox.showerror("Error", f"Insert failed: {e}")

    def edit_selected_disc(self):
        cur = self.discs_tree.selection()
        if not cur:
            messagebox.showinfo("Edit Disc", "Select a disc first.")
            return
        values = self.discs_tree.item(cur[0], "values")
        dlg = DiscDialog(self, title="Edit Disc", initial=values)
        if dlg.result:
            title, cddb_id = dlg.result
            try:
                make_backup(self.dbpath)
                self.db.insert_disc(title, cddb_id)
                self.load_discs()
            except Exception as e:
                messagebox.showerror("Error", f"Update failed: {e}")

    def delete_selected_disc(self):
        cur = self.discs_tree.selection()
        if not cur:
            messagebox.showinfo("Delete Disc", "Select a disc first.")
            return
        values = self.discs_tree.item(cur[0], "values")
        title, cddb_id = values[0], values[1]
        if messagebox.askyesno("Confirm Delete", f"Delete disc {cddb_id} ('{title}')?"):
            try:
                bak = make_backup(self.dbpath)
                self.db.delete_disc(title, cddb_id)
                self.load_discs()
                messagebox.showinfo("Deleted", f"Deleted. Backup created: {bak}")
            except Exception as e:
                messagebox.showerror("Error", f"Delete failed: {e}")

    # ----------------- Utilities -----------------
    def export_csv(self, kind="tracks"):
        if kind == "tracks":
            rows = self.db.get_tracks(filter_text=self.tracks_search.get().strip() or None)
            default_name = os.path.join(os.path.expanduser("~"), "cdrip_tracks_export.csv")
            columns = ["title", "track_id", "track_title"]
        else:
            rows = self.db.get_discs(filter_text=self.discs_search.get().strip() or None)
            default_name = os.path.join(os.path.expanduser("~"), "cdrip_discs_export.csv")
            columns = ["title", "cddb_id"]

        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=os.path.basename(default_name),
                                            filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for r in rows:
                    writer.writerow([r[c] for c in columns])
            messagebox.showinfo("Exported", f"Exported {len(rows)} rows to {path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _backup_db(self):
        try:
            dest = make_backup(self.dbpath)
            messagebox.showinfo("Backup Created", f"Backup created: {dest}")
        except Exception as e:
            messagebox.showerror("Backup Failed", str(e))

    def _open_db_file(self):
        path = filedialog.askopenfilename(title="Open SQLite DB", filetypes=[("SQLite DB","*.db;*.sqlite;*.sqlite3"),("All files","*.*")])
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showerror("Error", "File not found.")
            return
        # close current and open new
        try:
            self.db.close()
            self.dbpath = path
            self.db = DB(self.dbpath)
            self.status.set(f"DB: {self.dbpath}")
            self.load_tracks()
            self.load_discs()
        except Exception as e:
            messagebox.showerror("Open Failed", str(e))

    def _show_help(self):
        messagebox.showinfo("Help", "Use the tabs to view Tracks or Discs.\nSelect a row and use Edit or Delete.\nBackups are created automatically before destructive changes.")

    def on_closing(self):
        try:
            self.db.close()
        except:
            pass
        self.destroy()

# ---------------- Dialogs ----------------
class TrackDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial=None):
        self.initial = initial
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text="Album Title:").grid(row=0, column=0, sticky="w")
        self.e_title = ttk.Entry(master, width=80)
        self.e_title.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(master, text="Track ID:").grid(row=1, column=0, sticky="w")
        self.e_id = ttk.Entry(master, width=80)
        self.e_id.grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(master, text="Track Title:").grid(row=2, column=0, sticky="w")
        self.e_ttl = ttk.Entry(master, width=80)
        self.e_ttl.grid(row=2, column=1, padx=6, pady=4)

        if self.initial:
            self.e_title.insert(0, self.initial[0])
            self.e_id.insert(0, self.initial[1])
            self.e_ttl.insert(0, self.initial[2])
        return self.e_title

    def apply(self):
        title = self.e_title.get().strip()
        track_id = self.e_id.get().strip()
        track_title = self.e_ttl.get().strip()
        if not title or not track_id:
            messagebox.showerror("Invalid", "Album Title and Track ID are required.")
            self.result = None
            return
        self.result = (title, track_id, track_title)

class DiscDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial=None):
        self.initial = initial
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text="Album Title:").grid(row=0, column=0, sticky="w")
        self.e_title = ttk.Entry(master, width=80)
        self.e_title.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(master, text="CDDB ID:").grid(row=1, column=0, sticky="w")
        self.e_id = ttk.Entry(master, width=80)
        self.e_id.grid(row=1, column=1, padx=6, pady=4)

        if self.initial:
            self.e_title.insert(0, self.initial[0])
            self.e_id.insert(0, self.initial[1])
        return self.e_title

    def apply(self):
        title = self.e_title.get().strip()
        cddb_id = self.e_id.get().strip()
        if not title or not cddb_id:
            messagebox.showerror("Invalid", "Album Title and CDDB ID are required.")
            self.result = None
            return
        self.result = (title, cddb_id)

# ----------------- Main -----------------
def main():
    ensure_db(DB_PATH)
    app = App(DB_PATH)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

if __name__ == "__main__":
    main()
