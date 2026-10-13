"""The 'Add devices' dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from enma.core.templates import DEFAULT_PARAMS, TYPE_PARAM
from enma.gui.theme import ACCENT_DARK, BG, DANGER, MUTED, ScrollFrame, TEXT, parse_num, tip


class AddDialog:
    def __init__(self, app, preset=None):
        self.app = app
        self.sim = app.sim
        self.preset = preset
        P = dict(DEFAULT_PARAMS)
        if preset:
            P.update(preset["params"])
        if P.get("router_port") == -1:
            P["router_port"] = self.sim.query(self.sim.next_free_port)
        if not P.get("start_instance"):
            P["start_instance"] = self.sim.query(self.sim.next_free_instance)
        if not P.get("first_port"):
            P["first_port"] = self.sim.query(self.sim.next_free_port)
        if not P.get("router_port"):
            P["router_port"] = self.sim.main_port
        if preset is None or "first_net" not in preset["params"]:
            P["first_net"] = self.sim.query(self.sim.next_free_network, int(P["router_port"]))
        self.v = {}
        for k, val in P.items():
            if isinstance(val, bool):
                self.v[k] = tk.BooleanVar(value=val)
            else:
                self.v[k] = tk.StringVar(value=str(val))

        self.top = top = tk.Toplevel(app.root)
        top.title("Add devices" + (f" — {preset['title']}" if preset else ""))
        top.configure(background=BG)
        top.transient(app.root)
        w, h = 1040, min(780, app.root.winfo_screenheight() - 80)
        top.geometry(f"{w}x{h}+{app.root.winfo_rootx() + 40}+{max(0, app.root.winfo_rooty() - 20)}")

        if preset:
            banner = tk.Frame(top, background="#eff6ff", highlightbackground="#bfdbfe", highlightthickness=1)
            banner.pack(fill="x", padx=12, pady=(12, 0))
            tk.Label(banner, text=preset["title"], background="#eff6ff", foreground=ACCENT_DARK,
                     font=(app.font, 13, "bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 0))
            tk.Label(banner, text="Recreates: " + preset["problem"], background="#eff6ff", foreground=TEXT,
                     wraplength=980, justify="left", anchor="w").pack(fill="x", padx=10)
            tk.Label(banner, text="A correct client should: " + preset["expect"], background="#eff6ff",
                     foreground=MUTED, wraplength=980, justify="left", anchor="w").pack(fill="x", padx=10, pady=(0, 8))

        bottom = ttk.Frame(top)
        bottom.pack(side="bottom", fill="x", padx=12, pady=10)
        self.summary = ttk.Label(bottom, text="", style="Sub.TLabel")
        self.summary.pack(side="left")
        ttk.Button(bottom, text="Cancel", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="Create devices", style="Accent.TButton", command=self.create).pack(side="right")

        sf = ScrollFrame(top)
        sf.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        body = sf.body
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # 1. devices
        f = self._section(left, "1 · Devices")
        self._entry(f, 0, "Group name", "name", 22, "A label for this batch of devices in the site tree.")
        self._entry(f, 1, "Number of devices", "count", 8, "How many devices to create in this group.")
        self._entry(f, 2, "Device name prefix", "prefix", 12, "Devices are named prefix + number, e.g. AHU-01.")
        self._entry(f, 3, "First device instance", "start_instance", 10,
                    "BACnet device instance of the first device; the rest count up from here. Must be unique.")
        ttk.Label(f, text="Connection").grid(row=4, column=0, sticky="w", pady=3)
        rf = ttk.Frame(f)
        rf.grid(row=4, column=1, columnspan=3, sticky="w")
        tip(ttk.Radiobutton(rf, text="Behind a BACnet router (MS/TP trunks)", value="routed",
                            variable=self.v["kind"], command=self._kind_changed),
            "Devices sit on remote networks behind one router UDP port. Clients reach them as network:MAC "
            "(DNET/DADR) through the router, like MS/TP controllers on a real site.").pack(anchor="w")
        tip(ttk.Radiobutton(rf, text="Directly on BACnet/IP (one UDP port each)", value="direct",
                            variable=self.v["kind"], command=self._kind_changed),
            "Each device gets its own UDP port on this computer (47809, 47810, ...).").pack(anchor="w")
        mf = ttk.Frame(rf)
        mf.pack(anchor="w")
        tip(ttk.Radiobutton(mf, text="Mixed:", value="mixed", variable=self.v["kind"], command=self._kind_changed),
            "Part of the devices directly on BACnet/IP, the rest behind the router. Faults are spread over "
            "both; router faults (trunk, buffer, unreachable) affect only the routed part.").pack(side="left")
        self.direct_pct_spin = ttk.Spinbox(mf, from_=0, to=100, width=4, textvariable=self.v["direct_pct"])
        self.direct_pct_spin.pack(side="left", padx=(4, 3))
        ttk.Label(mf, text="% directly on BACnet/IP, rest routed").pack(side="left")

        # 2. addressing
        self.addr_frame = f = self._section(left, "2 · Addressing")
        self.routed_rows = []
        self.routed_rows += self._entry(f, 0, "Router UDP port", "router_port", 8,
                                        "The UDP port of the simulated router. The main port is the standard "
                                        "47808. A different port behaves like a second router.")
        self.routed_rows += self._entry(f, 1, "First network number", "first_net", 8,
                                        "Network number of the first MS/TP trunk. More trunks are added as needed.")
        self.routed_rows += self._entry(f, 2, "Devices per network", "per_net", 8,
                                        "Devices per MS/TP trunk (MS/TP allows up to 127 masters). A new network "
                                        "number is used for every this-many devices.")
        self.routed_rows += self._entry(f, 3, "First MAC address", "first_mac", 8, "MS/TP MAC of the first device on each network.")
        self.direct_rows = self._entry(f, 4, "First UDP port", "first_port", 8,
                                       "UDP port of the first device; ports in use are skipped.")

        # 3. points
        f = self._section(left, "3 · Points per device")
        types = [("AI", "n_ai", "Analog inputs"), ("AO", "n_ao", "Analog outputs (commandable)"),
                 ("AV", "n_av", "Analog values (commandable)"), ("BI", "n_bi", "Binary inputs"),
                 ("BO", "n_bo", "Binary outputs (commandable)"), ("BV", "n_bv", "Binary values (commandable)"),
                 ("MSI", "n_msi", "Multi-state inputs"), ("MSV", "n_msv", "Multi-state values (commandable)")]
        for i, (short, key, desc) in enumerate(types):
            r, c = divmod(i, 4)
            cell = ttk.Frame(f)
            cell.grid(row=r, column=c, padx=(0, 10), pady=2, sticky="w")
            tip(ttk.Label(cell, text=short, width=4), desc).pack(side="left")
            ttk.Spinbox(cell, from_=0, to=5000, width=5, textvariable=self.v[key]).pack(side="left")
        self.pts_label = ttk.Label(f, text="", style="Sub.TLabel")
        self.pts_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        # 4. value changes
        f = self._section(left, "4 · Value changes")
        self._range(f, 0, "Normal points change every", "chg_min", "chg_max", "chg_unit",
                    "Each change happens after a random wait between the low and the high limit.")
        ttk.Label(f, text="Stale points").grid(row=1, column=0, sticky="w", pady=3)
        sp = ttk.Frame(f)
        sp.grid(row=1, column=1, columnspan=4, sticky="w")
        ttk.Spinbox(sp, from_=0, to=100, width=5, textvariable=self.v["stale_pct"]).pack(side="left")
        ttk.Label(sp, text="% of points").pack(side="left", padx=(4, 0))
        self._range(f, 2, "Stale points change every", "stale_min", "stale_max", "stale_unit",
                    "Stale points change rarely, e.g. every 30-120 minutes, so a client sees steady values.")
        tip(ttk.Checkbutton(f, text="Stale points never change (frozen)", variable=self.v["stale_frozen"]),
            "Frozen points keep the same value forever.").grid(row=3, column=1, columnspan=4, sticky="w")
        self._entry(f, 4, "COV increment (analog)", "cov_inc", 8,
                    "covIncrement of analog objects: COV notifications are sent when the value moves at least this much.")

        # 5. COV
        f = self._section(right, "5 · COV (change of value)")
        self._pct(f, 0, "Devices that support COV", "cov_pct",
                  "These devices list SubscribeCOV in protocolServicesSupported. The others answer "
                  "Reject: unrecognized-service.")
        self._entry(f, 1, "Max subscriptions per device", "max_subs", 8,
                    "0 = unlimited. Beyond the limit the device answers Error resources / "
                    "no-space-to-add-list-element.")
        self._pct(f, 2, "Objects that refuse COV", "refuse_pct",
                  "Share of objects (on COV devices) that answer Error object / optional-functionality-not-supported.")
        self._pct(f, 3, "COV devices that never notify", "mute_pct",
                  "Accept the subscription (SimpleACK) but never send a notification.")

        # 6. faults
        f = self._section(right, "6 · Faults")
        self._pct(f, 0, "Silent (offline) devices", "offline_pct", "Never answer anything, like a dead controller.")
        self._pct(f, 1, "Flapping devices", "flap_pct",
                  "Drop off the network now and then, then come back (sending I-Am).")
        fr = ttk.Frame(f)
        fr.grid(row=2, column=1, columnspan=4, sticky="w")
        ttk.Label(fr, text="every").pack(side="left")
        ttk.Entry(fr, width=4, textvariable=self.v["flap_every_min"]).pack(side="left", padx=2)
        ttk.Label(fr, text="to").pack(side="left")
        ttk.Entry(fr, width=4, textvariable=self.v["flap_every_max"]).pack(side="left", padx=2)
        ttk.Label(fr, text="min, down for").pack(side="left")
        ttk.Entry(fr, width=4, textvariable=self.v["flap_off_min"]).pack(side="left", padx=2)
        ttk.Label(fr, text="to").pack(side="left")
        ttk.Entry(fr, width=4, textvariable=self.v["flap_off_max"]).pack(side="left", padx=2)
        ttk.Label(fr, text="s").pack(side="left")
        tip(ttk.Checkbutton(f, text="Flapping is a reboot (forgets COV subscriptions)", variable=self.v["flap_clear"]),
            "On: the device restarts, loses its subscriptions and sends I-Am. Off: it only stops answering "
            "for a while (communication loss).").grid(row=3, column=1, columnspan=4, sticky="w")
        self._pct(f, 4, "Slow devices", "slow_pct", "Answer every request after a delay.")
        fr = ttk.Frame(f)
        fr.grid(row=5, column=1, columnspan=4, sticky="w")
        ttk.Label(fr, text="reply after").pack(side="left")
        ttk.Entry(fr, width=6, textvariable=self.v["slow_min"]).pack(side="left", padx=2)
        ttk.Label(fr, text="to").pack(side="left")
        ttk.Entry(fr, width=6, textvariable=self.v["slow_max"]).pack(side="left", padx=2)
        ttk.Label(fr, text="ms").pack(side="left")
        self._pct(f, 6, "Late Who-Is answer", "slowwhois_pct", "Answer Who-Is only after a long delay.")
        fr = ttk.Frame(f)
        fr.grid(row=7, column=1, columnspan=4, sticky="w")
        ttk.Label(fr, text="I-Am after").pack(side="left")
        ttk.Entry(fr, width=5, textvariable=self.v["slowwhois_min"]).pack(side="left", padx=2)
        ttk.Label(fr, text="to").pack(side="left")
        ttk.Entry(fr, width=5, textvariable=self.v["slowwhois_max"]).pack(side="left", padx=2)
        ttk.Label(fr, text="s").pack(side="left")
        self._pct(f, 8, "Packet loss (all devices)", "drop_pct", "Share of requests silently lost.")

        # 7. network & limits
        f = self._section(right, "7 · Router & device limits")
        self.net_rows = []
        self.net_rows += self._entry(f, 0, "Trunk time per message (ms)", "trunk_ms", 8,
                                     "0 = instant. Each request, reply or notification occupies the MS/TP trunk "
                                     "for this long (about 30-80 ms at 38,400 baud with a few masters).")
        self.net_rows += self._entry(f, 1, "Router buffer (messages)", "buffer", 8,
                                     "0 = unlimited. When this many messages wait for the trunk, the router "
                                     "drops new ones and sends Router-Busy-To-Network.")
        cb = tip(ttk.Checkbutton(f, text="Network unreachable (not announced, Reject-Message-To-Network)",
                                 variable=self.v["unreachable"]),
                 "The router stops announcing these networks and rejects traffic to them, so clients see "
                 "'unknown route'.")
        cb.grid(row=2, column=0, columnspan=4, sticky="w")
        self.net_rows.append(cb)
        ttk.Label(f, text="Max APDU").grid(row=3, column=0, sticky="w", pady=3)
        tip(ttk.Combobox(f, width=8, state="readonly", textvariable=self.v["max_apdu"],
                         values=["Auto", "50", "128", "206", "480", "1024", "1476"]),
            "Auto: 480 for routed (MS/TP) devices, 1476 for BACnet/IP devices.").grid(row=3, column=1, sticky="w")
        ttk.Label(f, text="Segmentation").grid(row=4, column=0, sticky="w", pady=3)
        tip(ttk.Combobox(f, width=8, state="readonly", textvariable=self.v["segmentation"],
                         values=["Auto", "Yes", "No"]),
            "Auto: no segmentation for routed devices, segmented-transmit for BACnet/IP devices. Without "
            "segmentation, answers longer than max APDU get Abort segmentation-not-supported."
            ).grid(row=4, column=1, sticky="w")

        for var in self.v.values():
            var.trace_add("write", lambda *a: self._update_summary())
        self._kind_changed()
        self._update_summary()
        top.grab_set()
        top.focus_set()

    # form helpers
    def _section(self, parent, title):
        f = ttk.LabelFrame(parent, text=title, padding=(10, 6))
        f.pack(fill="x", pady=(0, 10))
        return f

    def _entry(self, f, row, label, key, width, help_text):
        lbl = tip(ttk.Label(f, text=label), help_text)
        lbl.grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        e = tip(ttk.Entry(f, width=width, textvariable=self.v[key]), help_text)
        e.grid(row=row, column=1, columnspan=3, sticky="w")
        return [lbl, e]

    def _pct(self, f, row, label, key, help_text):
        tip(ttk.Label(f, text=label), help_text).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        fr = ttk.Frame(f)
        fr.grid(row=row, column=1, columnspan=3, sticky="w")
        tip(ttk.Spinbox(fr, from_=0, to=100, width=5, textvariable=self.v[key]), help_text).pack(side="left")
        ttk.Label(fr, text="%").pack(side="left", padx=(3, 0))

    def _range(self, f, row, label, kmin, kmax, kunit, help_text):
        tip(ttk.Label(f, text=label), help_text).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        fr = ttk.Frame(f)
        fr.grid(row=row, column=1, columnspan=4, sticky="w")
        ttk.Entry(fr, width=6, textvariable=self.v[kmin]).pack(side="left")
        ttk.Label(fr, text="to").pack(side="left", padx=4)
        ttk.Entry(fr, width=6, textvariable=self.v[kmax]).pack(side="left")
        ttk.Combobox(fr, width=8, state="readonly", textvariable=self.v[kunit],
                     values=["seconds", "minutes", "hours"]).pack(side="left", padx=(6, 0))

    def _kind_changed(self):
        kind = self.v["kind"].get()
        routed = kind in ("routed", "mixed")
        direct = kind in ("direct", "mixed")
        for w in self.routed_rows + getattr(self, "net_rows", []):
            w.configure(state="normal" if routed else "disabled")
        for w in self.direct_rows:
            w.configure(state="normal" if direct else "disabled")
        self.direct_pct_spin.configure(state="normal" if kind == "mixed" else "disabled")

    def _split(self, n):
        """(routed, direct) device counts for n devices with the current form values."""
        kind = self.v["kind"].get()
        if kind == "routed":
            return n, 0
        if kind == "direct":
            return 0, n
        pct = max(0.0, min(100.0, float(self.v["direct_pct"].get() or 0)))
        d = int(round(n * pct / 100.0))
        return n - d, d

    def _update_summary(self):
        try:
            n = int(float(self.v["count"].get() or 0))
            per = sum(int(float(self.v[k].get() or 0)) for k in TYPE_PARAM.values())
            self.pts_label.configure(text=f"{per} objects per device")
            txt = f"Will create {n:,} devices × {per} objects = {n * per:,} points"
            n_routed, n_direct = self._split(n)
            parts = []
            if n_routed:
                pn = max(1, int(float(self.v["per_net"].get() or 1)))
                nets = (n_routed + pn - 1) // pn
                first = int(float(self.v["first_net"].get() or 0))
                parts.append(f"{n_routed:,} routed on {nets} network{'s' if nets != 1 else ''} ({first}"
                             f"{'-' + str(first + nets - 1) if nets > 1 else ''}, router port "
                             f"{self.v['router_port'].get()})")
            if n_direct:
                parts.append(f"{n_direct:,} direct on UDP ports from {self.v['first_port'].get()}")
            txt += ": " + " + ".join(parts)
            self.summary.configure(text=txt, foreground=MUTED)
        except (ValueError, tk.TclError):
            self.summary.configure(text="Check the numbers", foreground=DANGER)

    def params(self):
        v = self.v
        P = {"name": v["name"].get().strip(), "prefix": v["prefix"].get(), "kind": v["kind"].get(),
             "chg_unit": v["chg_unit"].get(), "stale_unit": v["stale_unit"].get(),
             "stale_frozen": v["stale_frozen"].get(), "flap_clear": v["flap_clear"].get(),
             "unreachable": v["unreachable"].get(), "max_apdu": v["max_apdu"].get(),
             "segmentation": v["segmentation"].get()}
        P["count"] = parse_num(v["count"], "Number of devices", 1, 50000, True)
        P["direct_pct"] = parse_num(v["direct_pct"], "Share directly on BACnet/IP", 0, 100)
        P["start_instance"] = parse_num(v["start_instance"], "First device instance", 0, 4194302, True)
        P["router_port"] = parse_num(v["router_port"], "Router UDP port", 1, 65535, True)
        P["first_net"] = parse_num(v["first_net"], "First network number", 1, 65534, True)
        P["per_net"] = parse_num(v["per_net"], "Devices per network", 1, 254, True)
        P["first_mac"] = parse_num(v["first_mac"], "First MAC address", 0, 254, True)
        P["first_port"] = parse_num(v["first_port"], "First UDP port", 1, 65535, True)
        for k in TYPE_PARAM.values():
            P[k] = parse_num(v[k], f"{k[2:].upper()} count", 0, 5000, True)
        for k, lbl in (("chg_min", "Change interval (low)"), ("chg_max", "Change interval (high)"),
                       ("stale_min", "Stale interval (low)"), ("stale_max", "Stale interval (high)")):
            P[k] = parse_num(v[k], lbl, 0.1)
        if P["chg_max"] < P["chg_min"] or P["stale_max"] < P["stale_min"]:
            raise ValueError("The high limit of a change interval must not be below the low limit")
        P["cov_inc"] = parse_num(v["cov_inc"], "COV increment", 0)
        for k, lbl in (("stale_pct", "Stale points"), ("cov_pct", "COV devices"), ("refuse_pct", "Objects refusing COV"),
                       ("mute_pct", "Mute COV devices"), ("offline_pct", "Silent devices"), ("flap_pct", "Flapping devices"),
                       ("slow_pct", "Slow devices"), ("slowwhois_pct", "Late Who-Is"), ("drop_pct", "Packet loss")):
            P[k] = parse_num(v[k], lbl, 0, 100)
        P["max_subs"] = parse_num(v["max_subs"], "Max subscriptions", 0, 100000, True)
        for k in ("flap_every_min", "flap_every_max", "flap_off_min", "flap_off_max", "slow_min", "slow_max",
                  "slowwhois_min", "slowwhois_max"):
            P[k] = parse_num(v[k], k.replace("_", " "), 0)
        P["trunk_ms"] = parse_num(v["trunk_ms"], "Trunk time per message", 0, 10000)
        P["buffer"] = parse_num(v["buffer"], "Router buffer", 0, 100000, True)
        return P

    def create(self):
        try:
            P = self.params()
        except ValueError as e:
            messagebox.showerror("Check the form", str(e), parent=self.top)
            return
        if P["count"] * sum(P[k] for k in TYPE_PARAM.values()) > 2_000_000:
            messagebox.showerror("Too large", "Keep a group under 2 million points.", parent=self.top)
            return
        try:
            gid, warnings = self.sim.query(self.sim.add_group, P, timeout=120)
        except ValueError as e:
            messagebox.showerror("Cannot create devices", str(e), parent=self.top)
            return
        self.top.destroy()
        self.app.after_structure_change(select=f"g{gid}")
        if self.sim.running:
            errs = self.sim.run_coro(self.sim.open_all())
            if errs:
                messagebox.showwarning("Some ports could not be opened", "\n".join(errs), parent=self.app.root)
        if warnings:
            messagebox.showinfo("Note", "\n\n".join(warnings), parent=self.app.root)
