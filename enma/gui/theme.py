"""Colours, tooltips, scrollable frames and form helpers shared by the GUI."""

from __future__ import annotations

import sys

import tkinter as tk
from tkinter import ttk


BG = "#f4f5f7"
PANEL = "#ffffff"
TEXT = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
DANGER = "#dc2626"
OK = "#15803d"
WARN = "#b45309"
HEADER = "#111827"
LOG_COLORS = {"info": "#374151", "warn": "#b45309", "error": "#dc2626", "cov": "#7c3aed",
              "router": "#0369a1", "device": "#047857", "write": "#9d174d", "traffic": "#9ca3af"}


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tw = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _e=None):
        if self.tw or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tw = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", background=HEADER, foreground="white",
                 wraplength=360, padx=8, pady=6, font=("TkDefaultFont", 11)).pack()

    def hide(self, _e=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None


def tip(widget, text):
    Tooltip(widget, text)
    return widget


class ScrollFrame(ttk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=BG, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.canvas.bind("<Enter>", lambda e: (self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units")),
                                               self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))), add="+")

    def _wheel(self, e):
        if sys.platform == "darwin":
            self.canvas.yview_scroll(-e.delta, "units")
        else:
            self.canvas.yview_scroll(-int(e.delta / 120) * 2, "units")


def parse_num(var, label, lo=None, hi=None, integer=False):
    raw = str(var.get()).strip()
    try:
        v = int(float(raw)) if integer else float(raw)
    except ValueError:
        raise ValueError(f"{label}: '{raw}' is not a number")
    if lo is not None and v < lo:
        raise ValueError(f"{label} must be at least {lo}")
    if hi is not None and v > hi:
        raise ValueError(f"{label} must be at most {hi}")
    return v


# ── Add devices dialog ──────────────────────────────────────────────────────
