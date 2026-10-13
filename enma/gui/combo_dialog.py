"""Dialog to build one combined scenario from several scenarios ("Everything at once" and "Custom")."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from enma.core import user_scenarios
from enma.core.scenarios import SCENARIO_BY_ID, SCENARIOS
from enma.core.templates import DEFAULT_PARAMS, TYPE_PARAM
from enma.gui.theme import ACCENT_DARK, BG, DANGER, MUTED, PANEL, TEXT, ScrollFrame, parse_num, tip


class ComboDialog:
    """preset: None (custom, nothing chosen), the EVERYTHING dict, or a saved scenario dict."""

    def __init__(self, app, preset=None, title="Custom scenario", intro=None):
        self.app, self.sim = app, app.sim
        chosen = {p["id"]: p["count"] for p in (preset or {}).get("parts", [])}
        self.saved_name = preset.get("name") if preset and "name" in preset else None

        self.top = top = tk.Toplevel(app.root)
        top.title(title)
        top.configure(background=BG)
        top.transient(app.root)
        h = min(820, app.root.winfo_screenheight() - 80)
        top.geometry(f"980x{h}+{app.root.winfo_rootx() + 60}+{max(0, app.root.winfo_rooty() - 10)}")

        banner = tk.Frame(top, background="#eff6ff", highlightbackground="#bfdbfe", highlightthickness=1)
        banner.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(banner, text=title, background="#eff6ff", foreground=ACCENT_DARK,
                 font=(app.font, 13, "bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(banner, text=intro or "Tick the problems you want in one site and set how many devices each one "
                                       "gets. Each problem gets its own group, so their faults do not cancel each "
                                       "other out.",
                 background="#eff6ff", foreground=TEXT, wraplength=930, justify="left",
                 anchor="w").pack(fill="x", padx=10, pady=(0, 8))

        head = ttk.Frame(top)
        head.pack(fill="x", padx=12, pady=(10, 0))
        ttk.Label(head, text="Scenario name").pack(side="left")
        self.name = tk.StringVar(value=self.saved_name or ("Everything" if preset else "Custom"))
        ttk.Entry(head, width=22, textvariable=self.name).pack(side="left", padx=(6, 18))
        ttk.Label(head, text="Directly on BACnet/IP").pack(side="left")
        self.direct = tk.StringVar(value=f"{(preset or {}).get('direct_pct', 50):g}")
        tip(ttk.Spinbox(head, from_=0, to=100, width=5, textvariable=self.direct),
            "Share of the devices of every part that sit directly on BACnet/IP; the rest are behind the router. "
            "Router faults (busy trunk, unreachable network, duplicate network) only affect the routed share."
            ).pack(side="left", padx=(6, 3))
        ttk.Label(head, text="%").pack(side="left")
        ttk.Button(head, text="Select none", command=lambda: self._select(False)).pack(side="right")
        ttk.Button(head, text="Select all", command=lambda: self._select(True)).pack(side="right", padx=6)

        bottom = ttk.Frame(top)
        bottom.pack(side="bottom", fill="x", padx=12, pady=10)
        self.summary = ttk.Label(bottom, text="", style="Sub.TLabel")
        self.summary.pack(side="left")
        ttk.Button(bottom, text="Cancel", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Create scenario", style="Accent.TButton", command=self.create).pack(side="right")
        self.save_var = tk.BooleanVar(value=False)
        tip(ttk.Checkbutton(bottom, text="Also save it to the Scenarios tab", variable=self.save_var),
            "Keeps this combination under 'Your scenarios' so you can set it up again with one click."
            ).pack(side="right", padx=12)

        sf = ScrollFrame(top)
        sf.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.rows = []
        for sc in SCENARIOS:
            card = tk.Frame(sf.body, background=PANEL, highlightbackground="#e5e7eb", highlightthickness=1)
            card.pack(fill="x", pady=3)
            on = tk.BooleanVar(value=sc["id"] in chosen)
            count = tk.StringVar(value=str(chosen.get(sc["id"], sc["params"].get("count", 10))))
            line = tk.Frame(card, background=PANEL)
            line.pack(fill="x", padx=8, pady=(6, 0))
            tk.Checkbutton(line, text=sc["title"], variable=on, background=PANEL, foreground=TEXT,
                           activebackground=PANEL, font=(app.font, 12, "bold"), anchor="w",
                           command=self._update).pack(side="left")
            cf = tk.Frame(line, background=PANEL)
            cf.pack(side="right")
            tk.Label(cf, text="devices", background=PANEL, foreground=MUTED).pack(side="right", padx=(4, 0))
            ttk.Spinbox(cf, from_=1, to=50000, width=6, textvariable=count).pack(side="right")
            desc = tk.Label(card, text=sc["problem"], background=PANEL, foreground=MUTED, justify="left",
                            anchor="w", wraplength=880)
            desc.pack(fill="x", padx=34, pady=(0, 6))
            card.bind("<Configure>", lambda e, d=desc: d.configure(wraplength=max(200, e.width - 60)))
            on.trace_add("write", lambda *a: self._update())
            count.trace_add("write", lambda *a: self._update())
            self.rows.append((sc, on, count))
        self.direct.trace_add("write", lambda *a: self._update())
        self._update()
        top.grab_set()
        top.focus_set()

    def _select(self, value):
        for _, on, _ in self.rows:
            on.set(value)

    def parts(self):
        out = []
        for sc, on, count in self.rows:
            if on.get():
                out.append(dict(id=sc["id"], count=parse_num(count, f"Devices for '{sc['title']}'", 1, 50000, True)))
        return out

    def _update(self):
        try:
            parts = self.parts()
            pct = max(0.0, min(100.0, float(self.direct.get() or 0)))
        except (ValueError, tk.TclError):
            self.summary.configure(text="Check the numbers", foreground=DANGER)
            return
        devices = sum(p["count"] for p in parts)
        objects = sum(p["count"] * sum(int(SCENARIO_BY_ID[p["id"]]["params"].get(k, DEFAULT_PARAMS[k]))
                                       for k in TYPE_PARAM.values())
                      for p in parts)
        direct = sum(int(round(p["count"] * pct / 100.0)) for p in parts)
        self.summary.configure(
            text=f"{len(parts)} of {len(self.rows)} problems · {devices:,} devices ({devices - direct:,} routed, "
                 f"{direct:,} direct) · about {objects:,} objects", foreground=MUTED)

    def create(self):
        try:
            parts = self.parts()
            pct = parse_num(self.direct, "Directly on BACnet/IP", 0, 100)
        except ValueError as e:
            messagebox.showerror("Check the form", str(e), parent=self.top)
            return
        name = self.name.get().strip()
        if not parts:
            messagebox.showerror("Nothing chosen", "Tick at least one problem.", parent=self.top)
            return
        if not name:
            messagebox.showerror("Name", "Give the scenario a name.", parent=self.top)
            return
        try:
            gids, warnings = self.sim.query(self.sim.add_composite, name, parts, pct, timeout=300)
        except ValueError as e:
            messagebox.showerror("Cannot create the scenario", str(e), parent=self.top)
            return
        if self.save_var.get():
            try:
                user_scenarios.save(name, parts, pct)
            except OSError as e:
                messagebox.showwarning("Not saved", f"The scenario was created but could not be saved:\n{e}",
                                       parent=self.top)
            self.app.rebuild_scenarios()
        self.top.destroy()
        self.app.after_structure_change(select=f"g{gids[0]}")
        if self.sim.running:
            errs = self.sim.run_coro(self.sim.open_all())
            if errs:
                messagebox.showwarning("Some ports could not be opened", "\n".join(errs[:15]), parent=self.app.root)
        if warnings:
            messagebox.showinfo("Note", "\n\n".join(dict.fromkeys(warnings)), parent=self.app.root)

