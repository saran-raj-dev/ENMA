"""Detail view of one routed network."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from enma.gui.theme import DANGER, OK, parse_num, tip


class NetworkView(ttk.Frame):
    def __init__(self, app, parent, port, num):
        super().__init__(parent, padding=(14, 10))
        self.app, self.sim, self.port, self.num = app, app.sim, port, num
        snap = self.sim.query(self.sim.snapshot_network, port, num)
        if snap is None:
            return
        head = ttk.Frame(self)
        head.pack(fill="x")
        ttk.Label(head, text=f"Network {num}", font=(app.font, 17, "bold")).pack(side="left")
        self.state_lbl = tk.Label(head, text="", font=(app.font, 11, "bold"), padx=8, pady=2, foreground="white")
        self.state_lbl.pack(side="left", padx=10)
        ttk.Label(self, text=f"MS/TP-style trunk behind the simulated router on UDP port {port} "
                             f"({self.sim.my_ip}:{port}) · group '{snap['group']}'",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 8))
        form = ttk.LabelFrame(self, text="Router and trunk", padding=(10, 6))
        form.pack(fill="x")
        self.v = dict(trunk_ms=tk.StringVar(value=f"{snap['trunk_ms']:g}"), buffer=tk.StringVar(value=str(snap["buffer"])),
                      unreachable=tk.BooleanVar(value=snap["unreachable"]), offline=tk.BooleanVar(value=snap["offline"]))
        ttk.Label(form, text="Trunk time per message (ms)").grid(row=0, column=0, sticky="w", pady=2)
        tip(ttk.Entry(form, width=8, textvariable=self.v["trunk_ms"]),
            "0 = instant. Every request, answer and notification on this network takes this long.").grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Router buffer (messages)").grid(row=1, column=0, sticky="w", pady=2)
        tip(ttk.Entry(form, width=8, textvariable=self.v["buffer"]),
            "0 = unlimited. When full: messages dropped, Router-Busy-To-Network sent.").grid(row=1, column=1, sticky="w")
        tip(ttk.Checkbutton(form, text="Unreachable (router stops announcing it; Reject-Message-To-Network)",
                            variable=self.v["unreachable"]),
            "Clients get 'unknown route' / reject for this network.").grid(row=2, column=0, columnspan=3, sticky="w")
        tip(ttk.Checkbutton(form, text="Trunk down (router still announces it, no device answers)",
                            variable=self.v["offline"]),
            "Like a cut MS/TP cable: the route exists but every device is silent.").grid(row=3, column=0, columnspan=3, sticky="w")
        ttk.Button(form, text="Apply", style="Accent.TButton", command=self.apply).grid(row=4, column=0, sticky="w", pady=(8, 0))

        acts = ttk.LabelFrame(self, text="Actions", padding=(10, 6))
        acts.pack(fill="x", pady=(10, 0))
        self.busy_s = tk.StringVar(value="30")
        fr = ttk.Frame(acts)
        fr.pack(anchor="w")
        tip(ttk.Button(fr, text="Force Router-Busy for", command=self.busy),
            "The router answers Router-Busy-To-Network and drops traffic to this network for the given time, "
            "then sends Router-Available-To-Network.").pack(side="left")
        ttk.Entry(fr, width=5, textvariable=self.busy_s).pack(side="left", padx=4)
        ttk.Label(fr, text="s").pack(side="left")
        fr = ttk.Frame(acts)
        fr.pack(anchor="w", pady=(6, 0))
        tip(ttk.Button(fr, text="Announce route (I-Am-Router-To-Network)",
                       command=lambda: self.op("announce")), "Broadcast I-Am-Router-To-Network now.").pack(side="left")
        tip(ttk.Button(fr, text="I-Am storm (all devices)", command=lambda: self.op("storm")),
            "Every device on this network broadcasts I-Am at once (through the trunk).").pack(side="left", padx=6)

        st = ttk.LabelFrame(self, text="Live", padding=(10, 6))
        st.pack(fill="x", pady=(10, 0))
        self.lbls = {}
        for i, (k, lbl) in enumerate([("devices", "Devices"), ("queue", "Waiting for trunk"), ("peak", "Peak queue"),
                                      ("routed", "Messages routed"), ("dropped", "Dropped"),
                                      ("busy_events", "Router-Busy events")]):
            r, c = divmod(i, 3)
            ttk.Label(st, text=lbl + ":", style="Sub.TLabel").grid(row=r, column=c * 2, sticky="w", padx=(0, 4))
            l = ttk.Label(st, text="-", width=10)
            l.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 16))
            self.lbls[k] = l
        self.refresh(snap)

    def apply(self):
        try:
            s = dict(trunk_ms=parse_num(self.v["trunk_ms"], "Trunk time", 0, 10000),
                     buffer=parse_num(self.v["buffer"], "Router buffer", 0, 100000, True),
                     unreachable=self.v["unreachable"].get(), offline=self.v["offline"].get())
        except ValueError as e:
            messagebox.showerror("Check the values", str(e), parent=self.app.root)
            return
        self.sim.query(self.sim.apply_network, self.port, self.num, s)
        self.app.refresh_now()

    def busy(self):
        try:
            secs = parse_num(self.busy_s, "Seconds", 1, 3600)
        except ValueError as e:
            messagebox.showerror("Check the value", str(e), parent=self.app.root)
            return
        self.op("busy", secs)

    def op(self, op, arg=None):
        if not self.sim.running:
            messagebox.showinfo("Not running", "Start the simulation first.", parent=self.app.root)
            return
        self.sim.query(self.sim.network_op, self.port, self.num, op, arg)

    def refresh(self, snap=None):
        snap = snap or self.sim.query(self.sim.snapshot_network, self.port, self.num)
        if snap is None:
            self.app.show_welcome()
            return
        s = snap["busy"]
        self.state_lbl.configure(text=s, background=OK if s in ("OK",) or s.startswith("Queue") else DANGER)
        for k, l in self.lbls.items():
            l.configure(text=str(snap[k]))
