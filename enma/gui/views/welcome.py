"""Start page shown when nothing is selected."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from enma.gui.theme import ACCENT


class WelcomeView(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, padding=24)
        self.app = app
        ttk.Label(self, text="Simulate a BACnet site", font=(app.font, 18, "bold")).pack(anchor="w")
        ttk.Label(self, text="Create devices by count, give them COV or not, make values change fast or go "
                             "stale, and switch faults on to see how your BACnet client copes.",
                  wraplength=620, style="Sub.TLabel").pack(anchor="w", pady=(4, 16))
        steps = [("1", "Add devices", "Choose how many, routed (behind a router) or direct BACnet/IP, points, "
                                      "change intervals, COV support and faults."),
                 ("2", "Start the simulation", "Opens UDP port 47808 (and one port per direct device)."),
                 ("3", "Point your client at this computer", "Discover with a global Who-Is, then read, write and "
                                                             "subscribe. Watch the COV and activity tabs."),
                 ("4", "Change things live", "Take devices offline, reboot them, freeze points, force Router-Busy "
                                             "or make a network unreachable.")]
        for n, title, text in steps:
            row = ttk.Frame(self)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=n, background=ACCENT, foreground="white", width=3,
                     font=(app.font, 12, "bold")).pack(side="left", anchor="n", padx=(0, 10))
            col = ttk.Frame(row)
            col.pack(side="left", fill="x", expand=True)
            ttk.Label(col, text=title, font=(app.font, 13, "bold")).pack(anchor="w")
            ttk.Label(col, text=text, wraplength=560, style="Sub.TLabel").pack(anchor="w")
        bar = ttk.Frame(self)
        bar.pack(anchor="w", pady=(18, 0))
        ttk.Button(bar, text="＋ Add devices", style="Accent.TButton", command=app.add_devices).pack(side="left")
        ttk.Button(bar, text="Browse problem scenarios", command=lambda: app.nb.select(app.tab_scen)).pack(side="left", padx=8)

    def refresh(self):
        pass
