#!/usr/bin/env python3
"""Tkinter GUI: generate SQL configuration scripts from table metadata."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from metadata_loader import TableMeta, load_metadata
from sql_generator import GeneratorOptions, generate_script

APP_TITLE = "SQL Config Generator"
DEFAULT_SAMPLE = Path(__file__).resolve().parent / "samples" / "sample_metadata.json"


class SqlConfigApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.tables: list[TableMeta] = []
        self.metadata_path = tk.StringVar(value=str(DEFAULT_SAMPLE))
        self.dialect = tk.StringVar(value="mysql")
        self.include_drop = tk.BooleanVar(value=False)
        self.include_create = tk.BooleanVar(value=True)
        self.include_seed = tk.BooleanVar(value=True)
        self.seed_rows = tk.IntVar(value=2)
        self.config_prefix = tk.StringVar(value="cfg_")
        self.status = tk.StringVar(value="Load metadata to begin.")

        self._build_ui()
        if DEFAULT_SAMPLE.exists():
            self.load_metadata_file(DEFAULT_SAMPLE)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        # Top: file picker
        file_row = ttk.Frame(root)
        file_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(file_row, text="Metadata file:").pack(side=tk.LEFT)
        ttk.Entry(file_row, textvariable=self.metadata_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=8
        )
        ttk.Button(file_row, text="Browse…", command=self.browse_metadata).pack(side=tk.LEFT)
        ttk.Button(file_row, text="Load", command=self.reload_metadata).pack(side=tk.LEFT, padx=(6, 0))

        body = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        # Left pane: tables + options
        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        body.add(left, weight=1)

        ttk.Label(left, text="Tables", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        self.table_list = tk.Listbox(left, selectmode=tk.EXTENDED, exportselection=False, height=14)
        self.table_list.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self.table_list.bind("<<ListboxSelect>>", self.on_table_select)

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btns, text="Select All", command=self.select_all).pack(side=tk.LEFT)
        ttk.Button(btns, text="Clear", command=self.clear_selection).pack(side=tk.LEFT, padx=6)

        opts = ttk.LabelFrame(left, text="Generator options", padding=8)
        opts.pack(fill=tk.X)

        dialect_row = ttk.Frame(opts)
        dialect_row.pack(fill=tk.X, pady=2)
        ttk.Label(dialect_row, text="Dialect:").pack(side=tk.LEFT)
        ttk.Radiobutton(dialect_row, text="MySQL", value="mysql", variable=self.dialect).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Radiobutton(dialect_row, text="PostgreSQL", value="postgres", variable=self.dialect).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Checkbutton(opts, text="Include DROP TABLE", variable=self.include_drop).pack(anchor=tk.W)
        ttk.Checkbutton(opts, text="Include CREATE TABLE", variable=self.include_create).pack(anchor=tk.W)
        ttk.Checkbutton(opts, text="Include seed INSERT scripts", variable=self.include_seed).pack(
            anchor=tk.W
        )

        seed_row = ttk.Frame(opts)
        seed_row.pack(fill=tk.X, pady=4)
        ttk.Label(seed_row, text="Seed rows / table:").pack(side=tk.LEFT)
        ttk.Spinbox(seed_row, from_=1, to=20, textvariable=self.seed_rows, width=5).pack(
            side=tk.LEFT, padx=8
        )

        prefix_row = ttk.Frame(opts)
        prefix_row.pack(fill=tk.X, pady=2)
        ttk.Label(prefix_row, text="Config prefix:").pack(side=tk.LEFT)
        ttk.Entry(prefix_row, textvariable=self.config_prefix, width=12).pack(side=tk.LEFT, padx=8)

        ttk.Button(left, text="Generate SQL", command=self.generate).pack(fill=tk.X, pady=(10, 0))

        # Right pane: column preview + SQL output
        right = ttk.Frame(body)
        body.add(right, weight=2)

        ttk.Label(right, text="Column metadata", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        cols = ("column", "type", "nullable", "pk", "default")
        self.column_tree = ttk.Treeview(right, columns=cols, show="headings", height=8)
        for col, width in zip(cols, (140, 140, 80, 50, 140)):
            self.column_tree.heading(col, text=col)
            self.column_tree.column(col, width=width, anchor=tk.W)
        self.column_tree.pack(fill=tk.X, pady=(4, 8))

        ttk.Label(right, text="Generated SQL", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        self.sql_text = tk.Text(right, wrap=tk.NONE, font=("Consolas", 10))
        yscroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.sql_text.yview)
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.sql_text.xview)
        self.sql_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        sql_frame = ttk.Frame(right)
        sql_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.sql_text.pack(in_=sql_frame, side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(in_=sql_frame, side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(in_=right, fill=tk.X)

        action_row = ttk.Frame(right)
        action_row.pack(fill=tk.X, pady=8)
        ttk.Button(action_row, text="Copy SQL", command=self.copy_sql).pack(side=tk.LEFT)
        ttk.Button(action_row, text="Save SQL…", command=self.save_sql).pack(side=tk.LEFT, padx=6)

        ttk.Label(root, textvariable=self.status).pack(anchor=tk.W, pady=(8, 0))

    def browse_metadata(self) -> None:
        path = filedialog.askopenfilename(
            title="Select table metadata",
            filetypes=[("Metadata", "*.json *.csv"), ("JSON", "*.json"), ("CSV", "*.csv")],
        )
        if path:
            self.metadata_path.set(path)
            self.load_metadata_file(Path(path))

    def reload_metadata(self) -> None:
        self.load_metadata_file(Path(self.metadata_path.get()))

    def load_metadata_file(self, path: Path) -> None:
        try:
            self.tables = load_metadata(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Failed to load metadata:\n{exc}")
            return

        self.table_list.delete(0, tk.END)
        for table in self.tables:
            self.table_list.insert(tk.END, f"{table.schema}.{table.name} ({len(table.columns)} cols)")
        self.column_tree.delete(*self.column_tree.get_children())
        self.status.set(f"Loaded {len(self.tables)} table(s) from {path.name}")

    def on_table_select(self, _event=None) -> None:
        selection = self.table_list.curselection()
        self.column_tree.delete(*self.column_tree.get_children())
        if not selection:
            return
        table = self.tables[selection[0]]
        for col in table.columns:
            self.column_tree.insert(
                "",
                tk.END,
                values=(
                    col.name,
                    col.data_type,
                    "YES" if col.nullable else "NO",
                    "YES" if col.primary_key else "",
                    col.default or "",
                ),
            )

    def select_all(self) -> None:
        self.table_list.selection_set(0, tk.END)
        self.on_table_select()

    def clear_selection(self) -> None:
        self.table_list.selection_clear(0, tk.END)
        self.column_tree.delete(*self.column_tree.get_children())

    def selected_table_names(self) -> list[str]:
        return [self.tables[i].name for i in self.table_list.curselection()]

    def generate(self) -> None:
        selected = self.selected_table_names()
        if not selected:
            messagebox.showwarning(APP_TITLE, "Select one or more tables first.")
            return

        options = GeneratorOptions(
            dialect=self.dialect.get(),
            include_drop=self.include_drop.get(),
            include_create=self.include_create.get(),
            include_seed_inserts=self.include_seed.get(),
            config_prefix=self.config_prefix.get().strip() or "cfg_",
            seed_rows=max(1, int(self.seed_rows.get())),
        )
        sql = generate_script(self.tables, selected, options)
        self.sql_text.delete("1.0", tk.END)
        self.sql_text.insert(tk.END, sql)
        self.status.set(f"Generated SQL for {len(selected)} table(s).")

    def copy_sql(self) -> None:
        sql = self.sql_text.get("1.0", tk.END).strip()
        if not sql:
            messagebox.showinfo(APP_TITLE, "Nothing to copy. Generate SQL first.")
            return
        self.clipboard_clear()
        self.clipboard_append(sql)
        self.status.set("SQL copied to clipboard.")

    def save_sql(self) -> None:
        sql = self.sql_text.get("1.0", tk.END).strip()
        if not sql:
            messagebox.showinfo(APP_TITLE, "Nothing to save. Generate SQL first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save SQL script",
            defaultextension=".sql",
            initialfile="config_script.sql",
            filetypes=[("SQL", "*.sql"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(sql + "\n", encoding="utf-8")
        self.status.set(f"Saved: {path}")


def main() -> None:
    app = SqlConfigApp()
    app.mainloop()


if __name__ == "__main__":
    main()
