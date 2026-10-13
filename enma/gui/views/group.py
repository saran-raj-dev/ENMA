"""Detail view of one group of devices."""

from __future__ import annotations

from tkinter import messagebox, ttk

from enma.gui.interval_dialog import IntervalDialog
from enma.gui.theme import tip


class GroupView(ttk.Frame):
    def __init__(self, app, parent, gid):
        super().__init__(parent, padding=(14, 10))
        self.app, self.sim, self.gid = app, app.sim, gid
        snap = self.sim.query(self.sim.snapshot_group, gid)
        if snap is None:
            return
        ttk.Label(self, text=snap["name"], font=(app.font, 17, "bold")).pack(anchor="w")
        n_routed, n_direct = snap["routed"], snap["devices"] - snap["routed"]
        if n_routed and n_direct:
            kind = f"Mixed: {n_routed} routed (behind a BACnet router), {n_direct} direct BACnet/IP"
        elif n_routed:
            kind = "Routed devices (behind a BACnet router)"
        else:
            kind = "Direct BACnet/IP devices"
        nets = ", ".join(f"{n} (port {p})" for p, n in snap["networks"])
        ttk.Label(self, text=f"{kind} · instances {snap['first']}–{snap['last']}" + (f" · networks {nets}" if nets else ""),
                  style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(2, 8))
        st = ttk.LabelFrame(self, text="Summary", padding=(10, 6))
        st.pack(fill="x")
        self.lbls = {}
        items = [("devices", "Devices"), ("online", "Online"), ("cov_full", "COV supported"),
                 ("cov_none", "No COV"), ("cov_mute", "COV never notifies"), ("flap", "Flapping"),
                 ("slow", "Slow"), ("points", "Objects"), ("stale", "Stale objects"), ("frozen", "Frozen objects"),
                 ("refuse", "Objects refusing COV"), ("subs", "Active COV subs"), ("reads", "Read requests"),
                 ("notifies", "Notifications sent")]
        for i, (k, lbl) in enumerate(items):
            r, c = divmod(i, 3)
            ttk.Label(st, text=lbl + ":", style="Sub.TLabel").grid(row=r, column=c * 2, sticky="w", padx=(0, 4))
            l = ttk.Label(st, text="-", width=9)
            l.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 16))
            self.lbls[k] = l
        acts = ttk.LabelFrame(self, text="Whole group", padding=(10, 6))
        acts.pack(fill="x", pady=(10, 0))
        fr = ttk.Frame(acts)
        fr.pack(anchor="w")
        ttk.Button(fr, text="All online", command=lambda: self.op("online")).pack(side="left")
        ttk.Button(fr, text="All offline", command=lambda: self.op("offline")).pack(side="left", padx=4)
        tip(ttk.Button(fr, text="Reboot all", command=lambda: self.op("reboot")),
            "Every device restarts at once: all COV subscriptions are lost, then I-Am from all.").pack(side="left")
        ttk.Button(fr, text="I-Am from all", command=lambda: self.op("iam")).pack(side="left", padx=4)
        ttk.Button(fr, text="Clear COV subs", command=lambda: self.op("clear_subs")).pack(side="left")
        fr = ttk.Frame(acts)
        fr.pack(anchor="w", pady=(8, 0))
        ttk.Button(fr, text="Change interval of all objects…", command=lambda: self.interval(None)).pack(side="left")
        ttk.Button(fr, text="…of stale objects only", command=lambda: self.interval(True)).pack(side="left", padx=4)
        ttk.Button(fr, text="…of normal objects only", command=lambda: self.interval(False)).pack(side="left")
        ttk.Label(acts, text="Tip: to change COV mode, delays or flapping for the whole group, open any device of "
                             "the group and press 'Apply to whole group'.", style="Sub.TLabel",
                  wraplength=700).pack(anchor="w", pady=(8, 0))
        fr = ttk.Frame(self)
        fr.pack(anchor="w", pady=(12, 0))
        ttk.Button(fr, text="Remove this group", style="Danger.TButton", command=self.remove).pack(side="left")
        self.refresh(snap)

    def op(self, op):
        if op in ("reboot", "iam") and not self.sim.running:
            messagebox.showinfo("Not running", "Start the simulation first.", parent=self.app.root)
            return
        insts = self.sim.query(self.sim.group_devices, self.gid)
        self.sim.query(self.sim.device_op, insts, op)
        self.app.refresh_now()

    def interval(self, only_stale):
        res = IntervalDialog(self.app.root, "Value change interval").result
        if res:
            self.sim.query(self.sim.group_points_interval, self.gid, res[0], res[1], res[2], only_stale)
            self.app.refresh_now()

    def remove(self):
        if messagebox.askyesno("Remove group", "Remove this group and all its devices?", parent=self.app.root):
            self.sim.query(self.sim.remove_group, self.gid)
            self.app.after_structure_change()

    def refresh(self, snap=None):
        snap = snap or self.sim.query(self.sim.snapshot_group, self.gid)
        if snap is None:
            self.app.show_welcome()
            return
        for k, l in self.lbls.items():
            l.configure(text=f"{snap[k]:,}" if isinstance(snap[k], int) else str(snap[k]))
