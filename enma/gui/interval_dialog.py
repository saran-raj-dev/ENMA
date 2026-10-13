"""Dialog to change how often objects change value."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from enma.core.templates import UNIT_SECONDS
from enma.gui.theme import BG, parse_num


class IntervalDialog:
    def __init__(self, root, title):
        self.result = None
        self.top = top = tk.Toplevel(root)
        top.title(title)
        top.configure(background=BG)
        top.transient(root)
        f = ttk.Frame(top, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=title, font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, columnspan=5, sticky="w")
        self.lo = tk.StringVar(value="10")
        self.hi = tk.StringVar(value="60")
        self.unit = tk.StringVar(value="seconds")
        self.frozen = tk.BooleanVar(value=False)
        ttk.Label(f, text="Change every").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(f, width=6, textvariable=self.lo).grid(row=1, column=1)
        ttk.Label(f, text="to").grid(row=1, column=2, padx=4)
        ttk.Entry(f, width=6, textvariable=self.hi).grid(row=1, column=3)
        ttk.Combobox(f, width=8, state="readonly", textvariable=self.unit,
                     values=["seconds", "minutes", "hours"]).grid(row=1, column=4, padx=(6, 0))
        ttk.Checkbutton(f, text="Never change (frozen / stale)", variable=self.frozen).grid(row=2, column=0, columnspan=5, sticky="w")
        bar = ttk.Frame(f)
        bar.grid(row=3, column=0, columnspan=5, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="Cancel", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Apply", style="Accent.TButton", command=self.ok).pack(side="right")
        top.grab_set()
        top.wait_window()

    def ok(self):
        try:
            m = UNIT_SECONDS[self.unit.get()]
            lo = parse_num(self.lo, "Low limit", 0.1) * m
            hi = parse_num(self.hi, "High limit", 0.1) * m
        except ValueError as e:
            messagebox.showerror("Check the values", str(e), parent=self.top)
            return
        self.result = (min(lo, hi), max(lo, hi), self.frozen.get())
        self.top.destroy()
