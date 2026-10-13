"""Detail view of one device."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from enma.core.model import COV_MODE_LABELS
from enma.gui.interval_dialog import IntervalDialog
from enma.gui.theme import DANGER, OK, WARN, parse_num, tip


class DeviceView(ttk.Frame):
    def __init__(self, app, parent, inst):
        super().__init__(parent, padding=(14, 10))
        self.app, self.sim, self.inst = app, app.sim, inst
        snap = self.sim.query(self.sim.snapshot_device, inst)
        if snap is None:
            ttk.Label(self, text="Device not found").pack()
            return
        info = snap["info"]
        head = ttk.Frame(self)
        head.pack(fill="x")
        self.title = ttk.Label(head, text=f"{info['name']}", font=(app.font, 17, "bold"))
        self.title.pack(side="left")
        self.state_lbl = tk.Label(head, text="", font=(app.font, 11, "bold"), padx=8, pady=2, foreground="white")
        self.state_lbl.pack(side="left", padx=10)
        tip(ttk.Button(head, text="Clear COV subs", command=lambda: self.op("clear_subs")),
            "Forget every COV subscription without telling the subscribers.").pack(side="right")
        tip(ttk.Button(head, text="Send I-Am", command=lambda: self.op("iam")), "Broadcast an I-Am now.").pack(side="right", padx=4)
        tip(ttk.Button(head, text="Reboot", command=lambda: self.op("reboot")),
            "Offline for 5 s, loses all COV subscriptions, then sends I-Am.").pack(side="right")
        self.sub = ttk.Label(self, text="", style="Sub.TLabel", wraplength=900)
        self.sub.pack(anchor="w", pady=(2, 8))

        top = ttk.Frame(self)
        top.pack(fill="x")
        form = ttk.LabelFrame(top, text="Behaviour", padding=(10, 6))
        form.pack(side="left", fill="both", expand=True)
        stats = ttk.LabelFrame(self, text="Live", padding=(10, 6))
        stats.pack(fill="x", pady=(10, 0))

        s = snap["settings"]
        self.v = {
            "online": tk.BooleanVar(value=s["online"]),
            "cov_mode": tk.StringVar(value=COV_MODE_LABELS[s["cov_mode"]]),
            "max_subs": tk.StringVar(value=str(s["max_subs"])),
            "delay_min": tk.StringVar(value=f"{s['delay_min']:g}"), "delay_max": tk.StringVar(value=f"{s['delay_max']:g}"),
            "drop_pct": tk.StringVar(value=f"{s['drop_pct']:g}"),
            "iam_delay_min": tk.StringVar(value=f"{s['iam_delay_min']:g}"),
            "iam_delay_max": tk.StringVar(value=f"{s['iam_delay_max']:g}"),
            "flap": tk.BooleanVar(value=s["flap"]),
            "flap_every_min": tk.StringVar(value=f"{s['flap_every_min'] / 60:g}"),
            "flap_every_max": tk.StringVar(value=f"{s['flap_every_max'] / 60:g}"),
            "flap_off_min": tk.StringVar(value=f"{s['flap_off_min']:g}"),
            "flap_off_max": tk.StringVar(value=f"{s['flap_off_max']:g}"),
            "flap_clear": tk.BooleanVar(value=s["flap_clear"]),
            "max_apdu": tk.StringVar(value=str(s["max_apdu"])),
            "segmentation": tk.BooleanVar(value=s["segmentation"]),
        }
        r = 0
        tip(ttk.Checkbutton(form, text="Online (answers on the network)", variable=self.v["online"]),
            "Off = silent device: no I-Am, no answers, no errors.").grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1
        ttk.Label(form, text="COV").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Combobox(form, state="readonly", width=28, textvariable=self.v["cov_mode"],
                     values=list(COV_MODE_LABELS.values())).grid(row=r, column=1, columnspan=3, sticky="w")
        r += 1
        ttk.Label(form, text="Max COV subscriptions").grid(row=r, column=0, sticky="w", pady=2)
        tip(ttk.Entry(form, width=7, textvariable=self.v["max_subs"]), "0 = unlimited").grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(form, text="Reply delay (ms)").grid(row=r, column=0, sticky="w", pady=2)
        self._pair(form, r, "delay_min", "delay_max", "ms")
        r += 1
        ttk.Label(form, text="I-Am delay (s)").grid(row=r, column=0, sticky="w", pady=2)
        self._pair(form, r, "iam_delay_min", "iam_delay_max", "s")
        r += 1
        ttk.Label(form, text="Packet loss (%)").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(form, width=7, textvariable=self.v["drop_pct"]).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Checkbutton(form, text="Flapping: every", variable=self.v["flap"]).grid(row=r, column=0, sticky="w", pady=2)
        fr = self._pair(form, r, "flap_every_min", "flap_every_max", "min, down")
        ttk.Entry(fr, width=5, textvariable=self.v["flap_off_min"]).pack(side="left", padx=2)
        ttk.Label(fr, text="–").pack(side="left")
        ttk.Entry(fr, width=5, textvariable=self.v["flap_off_max"]).pack(side="left", padx=2)
        ttk.Label(fr, text="s").pack(side="left")
        r += 1
        ttk.Checkbutton(form, text="Flap = reboot (forget COV subscriptions)",
                        variable=self.v["flap_clear"]).grid(row=r, column=1, columnspan=3, sticky="w")
        r += 1
        ttk.Label(form, text="Max APDU").grid(row=r, column=0, sticky="w", pady=2)
        fr = ttk.Frame(form)
        fr.grid(row=r, column=1, columnspan=3, sticky="w")
        ttk.Combobox(fr, width=6, state="readonly", textvariable=self.v["max_apdu"],
                     values=["50", "128", "206", "480", "1024", "1476"]).pack(side="left")
        ttk.Checkbutton(fr, text="Segmentation (transmit)", variable=self.v["segmentation"]).pack(side="left", padx=10)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(bar, text="Apply", style="Accent.TButton", command=lambda: self.apply(False)).pack(side="left")
        tip(ttk.Button(bar, text="Apply to whole group", command=lambda: self.apply(True)),
            "Same behaviour for every device in this group (the Online switch is left as it is).").pack(side="left", padx=6)

        self.stat_lbls = {}
        grid = ttk.Frame(stats)
        grid.pack(fill="x")
        names = [("rx", "Requests"), ("reads", "Reads"), ("writes", "Writes"), ("subscribes", "Subscribes"),
                 ("renewals", "Renewals"), ("cancels", "Cancels"), ("refused", "COV refused"),
                 ("notifies", "Notifies"), ("notify_fail", "Notify fail"), ("errors", "Errors"),
                 ("dropped", "Lost"), ("ignored", "Ignored"), ("iams", "I-Am sent"),
                 ("subs_now", "Subs now"), ("last_rx", "Last req"), ("db_rev", "DB rev"),
                 ("next_flap", "Next flap"), ("back_in", "Back in")]
        for i, (k, lbl) in enumerate(names):
            rr, cc = divmod(i, 6)
            ttk.Label(grid, text=lbl + ":", style="Sub.TLabel").grid(row=rr, column=cc * 2, sticky="w", padx=(0, 4))
            l = ttk.Label(grid, text="-", width=7)
            l.grid(row=rr, column=cc * 2 + 1, sticky="w", padx=(0, 6))
            self.stat_lbls[k] = l

        pts = ttk.LabelFrame(self, text="Objects (select one or more, then use the buttons; double-click to set a value)",
                             padding=(8, 6))
        pts.pack(fill="both", expand=True, pady=(10, 0))
        bars = [ttk.Frame(pts), ttk.Frame(pts)]
        bars[0].pack(fill="x", pady=(0, 4))
        bars[1].pack(fill="x", pady=(0, 6))
        for n, (text, cmd, h) in enumerate([
            ("Set value…", self.set_value, "Set the value (inputs) or the relinquish default (commandable objects)."),
            ("Change interval…", self.set_interval, "How often the selected objects change value, or freeze them."),
            ("Freeze / unfreeze", lambda: self.pop("freeze"), "Frozen objects never change: a stale point."),
            ("Relinquish all", lambda: self.pop("relinquish"), "Clear the priority array."),
            ("Fault", lambda: self.pop("fault"), "Toggle statusFlags FAULT and reliability."),
            ("Out of service", lambda: self.pop("oos"), "Toggle outOfService (inputs then accept writes)."),
            ("COV on/off", lambda: self.pop("cov"), "Toggle whether this object accepts SubscribeCOV."),
            ("Delete", lambda: self.pop("delete"), "Remove from objectList; reads get unknown-object (dead point)."),
            ("Restore", lambda: self.pop("restore"), "Bring a deleted object back."),
        ]):
            tip(ttk.Button(bars[0 if n < 4 else 1], text=text, command=cmd), h).pack(side="left", padx=(0, 4))
        cols = ("obj", "name", "value", "units", "interval", "next", "last", "cov", "subs", "reads", "flags")
        heads = ("Object", "Name", "Value", "Units", "Changes every", "Next", "Last change", "COV", "Subs",
                 "Reads", "Flags")
        widths = (62, 210, 115, 45, 105, 50, 72, 70, 40, 50, 100)
        tf = ttk.Frame(pts)
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="extended", height=12)
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, minwidth=40, stretch=c in ("name", "flags"),
                             anchor="w" if c in ("name", "flags", "value", "interval") else "center")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("deleted", foreground="#9ca3af")
        self.tree.tag_configure("fault", foreground=DANGER)
        self.tree.tag_configure("frozen", foreground=WARN)
        self.tree.bind("<Double-1>", lambda e: self.set_value())
        self.rows = {}
        self.refresh(snap)

    def _pair(self, form, r, k1, k2, unit):
        fr = ttk.Frame(form)
        fr.grid(row=r, column=1, columnspan=3, sticky="w")
        ttk.Entry(fr, width=6, textvariable=self.v[k1]).pack(side="left")
        ttk.Label(fr, text="–").pack(side="left", padx=2)
        ttk.Entry(fr, width=6, textvariable=self.v[k2]).pack(side="left")
        ttk.Label(fr, text=unit).pack(side="left", padx=(4, 4))
        return fr

    def collect(self):
        v = self.v
        rev = {lbl: k for k, lbl in COV_MODE_LABELS.items()}
        s = dict(online=v["online"].get(), cov_mode=rev[v["cov_mode"].get()],
                 max_subs=parse_num(v["max_subs"], "Max COV subscriptions", 0, 100000, True),
                 delay_min=parse_num(v["delay_min"], "Reply delay", 0), delay_max=parse_num(v["delay_max"], "Reply delay", 0),
                 drop_pct=parse_num(v["drop_pct"], "Packet loss", 0, 100),
                 iam_delay_min=parse_num(v["iam_delay_min"], "I-Am delay", 0),
                 iam_delay_max=parse_num(v["iam_delay_max"], "I-Am delay", 0),
                 flap=v["flap"].get(),
                 flap_every_min=parse_num(v["flap_every_min"], "Flap interval", 0.05) * 60,
                 flap_every_max=parse_num(v["flap_every_max"], "Flap interval", 0.05) * 60,
                 flap_off_min=parse_num(v["flap_off_min"], "Flap down time", 1),
                 flap_off_max=parse_num(v["flap_off_max"], "Flap down time", 1),
                 flap_clear=v["flap_clear"].get(), max_apdu=int(v["max_apdu"].get()),
                 segmentation=v["segmentation"].get())
        for a, b in (("delay_min", "delay_max"), ("iam_delay_min", "iam_delay_max"),
                     ("flap_every_min", "flap_every_max"), ("flap_off_min", "flap_off_max")):
            if s[b] < s[a]:
                s[a], s[b] = s[b], s[a]
        return s

    def apply(self, whole):
        try:
            s = self.collect()
        except ValueError as e:
            messagebox.showerror("Check the values", str(e), parent=self.app.root)
            return
        self.sim.query(self.sim.apply_device, self.inst, s, whole)
        self.app.refresh_now()

    def op(self, op):
        if op in ("reboot", "iam") and not self.sim.running:
            messagebox.showinfo("Not running", "Start the simulation first.", parent=self.app.root)
            return
        self.sim.query(self.sim.device_op, [self.inst], op)
        self.app.refresh_now()

    def selected_keys(self):
        return [tuple(int(x) for x in iid.split(":")) for iid in self.tree.selection()]

    def pop(self, op, arg=None):
        keys = self.selected_keys()
        if not keys:
            messagebox.showinfo("Select objects", "Select one or more objects in the table first.", parent=self.app.root)
            return
        msg = self.sim.query(self.sim.point_op, self.inst, keys, op, arg)
        if msg:
            messagebox.showinfo("Note", msg, parent=self.app.root)
        self.refresh()

    def set_value(self):
        keys = self.selected_keys()
        if not keys:
            messagebox.showinfo("Select objects", "Select an object in the table first.", parent=self.app.root)
            return
        row = self.tree.item(self.tree.selection()[0], "values")
        val = simpledialog.askstring("Set value", f"New value for {row[0]} {row[1]}\n"
                                                  f"(number; 0/1 or the text for binary; state number or text for "
                                                  f"multi-state)", initialvalue=row[2].split(" (")[0],
                                     parent=self.app.root)
        if val is not None:
            self.pop("set", val)

    def set_interval(self):
        keys = self.selected_keys()
        if not keys:
            messagebox.showinfo("Select objects", "Select one or more objects first.", parent=self.app.root)
            return
        res = IntervalDialog(self.app.root, f"Value change interval for {len(keys)} object(s)").result
        if res:
            self.pop("interval", res)

    def refresh(self, snap=None):
        snap = snap or self.sim.query(self.sim.snapshot_device, self.inst)
        if snap is None:
            self.app.show_welcome()
            return
        info, st = snap["info"], snap["stats"]
        state = info["state"]
        color = OK if state == "Online" else (DANGER if state in ("OFFLINE", "Rebooting", "Down (flap)", "Net down")
                                              else WARN)
        self.state_lbl.configure(text=state, background=color)
        where = (f"network {info['net']}, MAC {info['mac']} behind router port {info['port']}" if info["routed"]
                 else f"BACnet/IP on UDP port {info['port']}")
        self.sub.configure(text=f"Device {info['instance']} · {info['address']} · {where} · group "
                                f"'{info['group']}' · COV: {info['cov']} · max APDU {info['max_apdu']}"
                                f"{', segmentation' if info['segmentation'] else ', no segmentation'}")
        st = dict(st)
        st.update(subs_now=info["subs"], last_rx=info["last_rx"], db_rev=info["db_rev"],
                  next_flap=info["next_flap"], back_in=info["back_in"])
        for k, l in self.stat_lbls.items():
            l.configure(text=str(st.get(k, "-")))
        rows = snap["points"]
        ids = [r[0] for r in rows]
        if list(self.rows) != ids:
            sel = set(self.tree.selection())
            self.tree.delete(*self.tree.get_children())
            self.rows = {}
            for r in rows:
                self.tree.insert("", "end", iid=r[0], values=r[1:], tags=self._tags(r))
                self.rows[r[0]] = r
            keep = [i for i in sel if i in self.rows]
            if keep:
                self.tree.selection_set(keep)
        else:
            for r in rows:
                if self.rows.get(r[0]) != r:
                    self.tree.item(r[0], values=r[1:], tags=self._tags(r))
                    self.rows[r[0]] = r

    @staticmethod
    def _tags(r):
        flags = r[-1]
        if "DELETED" in flags:
            return ("deleted",)
        if "FAULT" in flags:
            return ("fault",)
        if r[5].startswith("never"):
            return ("frozen",)
        return ()
