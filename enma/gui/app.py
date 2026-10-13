"""Main window."""

from __future__ import annotations

import gc
import json
import os
import queue
import sys
import traceback
import webbrowser
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont

from enma.config import APP_FULL_NAME, APP_NAME, AUTHOR_NAME, AUTHOR_URL, CONFIG_DIR, LAST_SITE
from enma.core.scenarios import SCENARIOS
from enma.core.util import list_interfaces
from enma.gui.add_dialog import AddDialog
from enma.gui.help_text import HELP_TEXT
from enma.gui.theme import (
    ACCENT,
    ACCENT_DARK,
    BG,
    DANGER,
    HEADER,
    LOG_COLORS,
    MUTED,
    OK,
    PANEL,
    ScrollFrame,
    TEXT,
    WARN,
    parse_num,
    tip,
)
from enma.gui.views.device import DeviceView
from enma.gui.views.group import GroupView
from enma.gui.views.network import NetworkView
from enma.gui.views.welcome import WelcomeView


class App:
    def __init__(self, root, sim):
        self.root = root
        self.sim = sim
        # Tk objects must only be finalised on the Tk thread. Cyclic garbage collection could otherwise
        # run in the engine thread, finalise a tkinter Variable there and deadlock against this thread.
        # So automatic GC is off and collections run from the Tk timer (see _tick).
        gc.disable()
        self._gc_ticks = 0
        self.font = tkfont.nametofont("TkDefaultFont").actual()["family"]
        root.title(f"{APP_NAME} — {APP_FULL_NAME}")
        root.configure(background=BG)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(1500, sw - 60)}x{min(920, sh - 80)}+20+20")
        root.minsize(1100, 640)
        self._styles()
        self.tree_version = -1
        self.tree_cache = {}
        self.detail = None
        self.detail_key = None
        self.filter_after = None
        self.log_lines = deque(maxlen=20000)
        self.ifaces = list_interfaces()

        self._build_header()
        self._build_body()
        self._build_statusbar()
        self.show_welcome()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(300, self._drain_log)
        root.after(800, self._tick)
        if os.path.exists(LAST_SITE):
            self.restore_btn.configure(state="normal")

    # ── look ────────────────────────────────────────────────────────────────
    def _styles(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        f = self.font
        st.configure(".", background=BG, foreground=TEXT, font=(f, 12))
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("Sub.TLabel", background=BG, foreground=MUTED)
        st.configure("Head.TFrame", background=HEADER)
        st.configure("Head.TLabel", background=HEADER, foreground="white", font=(f, 17, "bold"))
        st.configure("HeadSub.TLabel", background=HEADER, foreground="#9ca3af", font=(f, 11))
        st.configure("Bar.TFrame", background="#e5e7eb")
        st.configure("Bar.TLabel", background="#e5e7eb", foreground=TEXT)
        st.configure("Bar.TCheckbutton", background="#e5e7eb")
        st.configure("TLabelframe", background=BG, bordercolor="#d1d5db")
        st.configure("TLabelframe.Label", background=BG, foreground=TEXT, font=(f, 12, "bold"))
        st.configure("TButton", padding=(8, 3), width=0)
        st.configure("Accent.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT_DARK,
                     font=(f, 12, "bold"), padding=(12, 4), width=0)
        st.map("Accent.TButton", background=[("disabled", "#93c5fd"), ("active", ACCENT_DARK)],
               foreground=[("disabled", "#eff6ff")])
        st.configure("Start.TButton", background=OK, foreground="white", font=(f, 12, "bold"), padding=(14, 4), width=0)
        st.map("Start.TButton", background=[("disabled", "#86efac"), ("active", "#166534")])
        st.configure("Danger.TButton", background=DANGER, foreground="white", font=(f, 12, "bold"), padding=(12, 4), width=0)
        st.map("Danger.TButton", background=[("disabled", "#fca5a5"), ("active", "#991b1b")])
        st.configure("Treeview", background=PANEL, fieldbackground=PANEL, rowheight=22, font=(f, 12))
        st.configure("Treeview.Heading", font=(f, 11, "bold"), background="#e5e7eb")
        st.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", TEXT)])
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", padding=(14, 6), font=(f, 12))
        st.map("TNotebook.Tab", background=[("selected", PANEL)])

    def _build_header(self):
        head = ttk.Frame(self.root, style="Head.TFrame", padding=(16, 10))
        head.pack(fill="x")
        ttk.Label(head, text=APP_NAME, style="Head.TLabel").pack(side="left")
        ttk.Label(head, text=f"  {APP_FULL_NAME}  ·  BACnet site simulator",
                  style="HeadSub.TLabel").pack(side="left", pady=(5, 0))
        self.run_pill = tk.Label(head, text="  STOPPED  ", background="#4b5563", foreground="white",
                                 font=(self.font, 11, "bold"), padx=6, pady=2)
        self.run_pill.pack(side="right")
        ttk.Button(head, text="Save site…", command=self.save).pack(side="right", padx=(4, 14))
        ttk.Button(head, text="Open site…", command=self.open).pack(side="right", padx=4)
        self.restore_btn = ttk.Button(head, text="Restore last", command=self.restore_last, state="disabled")
        self.restore_btn.pack(side="right", padx=4)
        ttk.Button(head, text="New site", command=self.new_site).pack(side="right", padx=4)

        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(12, 8))
        bar.pack(fill="x")
        self.start_btn = ttk.Button(bar, text="▶  Start", style="Start.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="■  Stop", style="Danger.TButton", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(6, 14))
        ttk.Label(bar, text="Interface", style="Bar.TLabel").pack(side="left")
        self.iface_var = tk.StringVar(value=self._iface_label(self.ifaces[0]))
        self.iface_cb = ttk.Combobox(bar, state="readonly", width=30, textvariable=self.iface_var,
                                     values=[self._iface_label(i) for i in self.ifaces])
        self.iface_cb.pack(side="left", padx=(4, 12))
        tip(self.iface_cb, "The network the simulator broadcasts on (I-Am, I-Am-Router-To-Network).")
        ttk.Label(bar, text="Main UDP port", style="Bar.TLabel").pack(side="left")
        self.port_var = tk.StringVar(value=str(self.sim.main_port))
        self.port_entry = tip(ttk.Entry(bar, width=7, textvariable=self.port_var),
                              "Standard BACnet/IP port is 47808. The router and broadcast relay live here.")
        self.port_entry.pack(side="left", padx=(4, 12))
        ttk.Label(bar, text="I-Am replies", style="Bar.TLabel").pack(side="left")
        self.iam_var = tk.StringVar(value="Unicast")
        cb = ttk.Combobox(bar, state="readonly", width=10, textvariable=self.iam_var,
                          values=["Unicast", "Broadcast", "Both"])
        cb.pack(side="left", padx=(4, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self.sim.query(self.sim.configure, None, None,
                                                                   self.iam_var.get().lower(), None))
        tip(cb, "How devices answer Who-Is (and routers answer Who-Is-Router-To-Network).\nUnicast: straight back to "
                "the asker (works across subnets and with a client on this computer).\nBroadcast: to the whole "
                "subnet on the main port (classic behaviour).")
        self.relay_var = tk.BooleanVar(value=True)
        tip(ttk.Checkbutton(bar, text="Relay broadcasts to other ports", style="Bar.TCheckbutton",
                            variable=self.relay_var,
                            command=lambda: self.sim.query(self.sim.configure, None, None, None, self.relay_var.get())),
            "Who-Is and Who-Is-Router-To-Network arriving on the main port also reach the direct devices and "
            "routers on other ports, so one global Who-Is finds the whole site.").pack(side="left")


    @staticmethod
    def _iface_label(i):
        return f"{i[1]}  ({i[0]}, broadcast {i[2]})"

    def _build_body(self):
        pw = ttk.Panedwindow(self.root, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        left = ttk.Frame(pw)
        right = ttk.Frame(pw)
        pw.add(left, weight=1)
        pw.add(right, weight=1)
        self.pw = pw
        self.root.after(200, lambda: pw.sashpos(0, min(700, int(self.root.winfo_width() * 0.45))))

        top = ttk.Frame(left)
        top.pack(fill="x")
        ttk.Label(top, text="Site", font=(self.font, 15, "bold")).pack(side="left")
        ttk.Button(top, text="＋ Add devices", style="Accent.TButton", command=self.add_devices).pack(side="right")
        ttk.Button(top, text="Scenarios", command=lambda: self.nb.select(self.tab_scen)).pack(side="right", padx=6)
        fr = ttk.Frame(left)
        fr.pack(fill="x", pady=(8, 4))
        ttk.Label(fr, text="Filter", style="Sub.TLabel").pack(side="left")
        self.filter_var = tk.StringVar()
        e = ttk.Entry(fr, textvariable=self.filter_var)
        e.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tip(e, "Show only devices whose name, instance, address or state contains this text.")
        self.filter_var.trace_add("write", lambda *a: self._filter_changed())

        tf = ttk.Frame(left)
        tf.pack(fill="both", expand=True)
        cols = ("inst", "addr", "state", "cov", "pts", "subs", "rx")
        self.tree = ttk.Treeview(tf, columns=cols, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Name")
        self.tree.column("#0", width=150, minwidth=100)
        for c, h, w in zip(cols, ("Instance", "Address", "State", "COV", "Objects", "Subs", "Requests"),
                           (62, 135, 82, 66, 56, 42, 64)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, minwidth=40, anchor="center" if c != "addr" else "w", stretch=c == "addr")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("group", font=(self.font, 12, "bold"))
        self.tree.tag_configure("net", foreground="#1e40af")
        self.tree.tag_configure("down", foreground=DANGER)
        self.tree.tag_configure("warn", foreground=WARN)
        self.tree.tag_configure("netbad", foreground=DANGER)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Button-2>" if sys.platform == "darwin" else "<Button-3>", self._context_menu)
        if sys.platform == "darwin":
            self.tree.bind("<Control-Button-1>", self._context_menu)

        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Label(bar, text="Selected:", style="Sub.TLabel").pack(side="left")
        for text, op, h in [("Online", "online", "Bring the selected devices back."),
                            ("Offline", "offline", "Selected devices stop answering (silent)."),
                            ("Reboot", "reboot", "Restart: COV subscriptions are lost, I-Am after 5 s."),
                            ("I-Am", "iam", "Broadcast I-Am from the selected devices.")]:
            tip(ttk.Button(bar, text=text, command=lambda o=op: self.selected_op(o)), h).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Remove", command=self.remove_selected).pack(side="right")

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True, padx=(8, 0))
        self.tab_detail = ttk.Frame(self.nb)
        self.tab_subs = ttk.Frame(self.nb)
        self.tab_scen = ttk.Frame(self.nb)
        self.tab_log = ttk.Frame(self.nb)
        self.tab_help = ttk.Frame(self.nb)
        self.nb.add(self.tab_detail, text="Details")
        self.nb.add(self.tab_subs, text="COV subscriptions")
        self.nb.add(self.tab_scen, text="Scenarios")
        self.nb.add(self.tab_log, text="Activity log")
        self.nb.add(self.tab_help, text="How to use")
        self._build_subs_tab()
        self._build_scen_tab()
        self._build_log_tab()
        self._build_help_tab()

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(12, 4))
        bar.pack(fill="x", side="bottom", pady=(8, 0))
        credit = tk.Label(bar, text=f"  © {AUTHOR_NAME}  ", background="#dbeafe", foreground=ACCENT_DARK,
                          cursor="pointinghand" if sys.platform == "darwin" else "hand2",
                          font=(self.font, 11, "bold"), padx=4, pady=1)
        credit.pack(side="right", padx=(14, 0))
        credit.bind("<Button-1>", lambda e: webbrowser.open(AUTHOR_URL))
        credit.bind("<Enter>", lambda e: credit.configure(background=ACCENT, foreground="white"))
        credit.bind("<Leave>", lambda e: credit.configure(background="#dbeafe", foreground=ACCENT_DARK))
        tip(credit, f"{AUTHOR_NAME} - open GitHub profile")
        self.status_left = ttk.Label(bar, text="", style="Bar.TLabel")
        self.status_left.pack(side="left")
        self.status_right = ttk.Label(bar, text="", style="Bar.TLabel")
        self.status_right.pack(side="right")

    def _build_subs_tab(self):
        f = ttk.Frame(self.tab_subs, padding=10)
        f.pack(fill="both", expand=True)
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        self.subs_lbl = ttk.Label(top, text="No active COV subscriptions", font=(self.font, 13, "bold"))
        self.subs_lbl.pack(side="left")
        tip(ttk.Button(top, text="Clear all", command=self.clear_subs),
            "Every device forgets its subscriptions (like a site-wide power cut). Subscribers are not told.").pack(side="right")
        cols = ("dev", "obj", "name", "subscriber", "pid", "type", "lifetime", "left", "renew", "count", "last", "fails")
        heads = ("Device", "Object", "Name", "Subscriber", "Process", "Notifications", "Lifetime", "Expires in",
                 "Renewals", "Sent", "Last sent", "Failures")
        widths = (70, 70, 200, 170, 60, 95, 85, 75, 65, 50, 75, 60)
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        self.subs_tree = ttk.Treeview(tf, columns=cols, show="headings")
        for c, h, w in zip(cols, heads, widths):
            self.subs_tree.heading(c, text=h)
            self.subs_tree.column(c, width=w, minwidth=40, anchor="w" if c in ("name", "subscriber") else "center",
                                  stretch=c in ("name", "subscriber"))
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.subs_tree.yview)
        self.subs_tree.configure(yscrollcommand=vsb.set)
        self.subs_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.subs_tree.tag_configure("indef", foreground=DANGER)
        self.subs_tree.tag_configure("mute", foreground=WARN)
        ttk.Label(f, text="Red = indefinite subscription (lifetime 0): it never expires on its own. "
                          "Orange = device accepts but never notifies.", style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

    def _build_scen_tab(self):
        sf = ScrollFrame(self.tab_scen)
        sf.pack(fill="both", expand=True)
        body = sf.body
        ttk.Label(body, text="Recreate a field problem", font=(self.font, 16, "bold")).pack(anchor="w", padx=14, pady=(12, 0))
        intro = ttk.Label(body, text="Each scenario opens the Add devices form already filled in. Change the count "
                                     "or anything else, then create. Several scenarios can run side by side.",
                          style="Sub.TLabel", wraplength=760)
        intro.pack(anchor="w", fill="x", padx=14, pady=(2, 8))
        body.bind("<Configure>", lambda e: intro.configure(wraplength=max(200, e.width - 40)), add="+")
        for sc in SCENARIOS:
            card = tk.Frame(body, background=PANEL, highlightbackground="#e5e7eb", highlightthickness=1)
            texts = []
            card.pack(fill="x", padx=14, pady=5)
            row = tk.Frame(card, background=PANEL)
            row.pack(fill="x", padx=12, pady=(10, 2))
            tk.Label(row, text=sc["title"], background=PANEL, foreground=TEXT,
                     font=(self.font, 13, "bold")).pack(side="left")
            ttk.Button(row, text="Set up…", style="Accent.TButton",
                       command=lambda s=sc: self.add_devices(s)).pack(side="right")
            texts.append(tk.Label(card, text=sc["problem"], background=PANEL, foreground=TEXT, wraplength=720,
                                  justify="left", anchor="w"))
            texts[-1].pack(fill="x", padx=12)
            texts.append(tk.Label(card, text="Client should: " + sc["expect"], background=PANEL, foreground=MUTED,
                                  wraplength=720, justify="left", anchor="w"))
            texts[-1].pack(fill="x", padx=12, pady=(2, 10))
            card.bind("<Configure>", lambda e, ls=texts: [l.configure(wraplength=max(200, e.width - 30)) for l in ls])

    def _build_log_tab(self):
        f = ttk.Frame(self.tab_log, padding=10)
        f.pack(fill="both", expand=True)
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Show").pack(side="left")
        self.log_kind = tk.StringVar(value="Everything")
        cb = ttk.Combobox(top, state="readonly", width=16, textvariable=self.log_kind,
                          values=["Everything", "COV", "Router", "Devices", "Writes", "Warnings & errors", "Traffic"])
        cb.pack(side="left", padx=(4, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self._rerender_log())
        ttk.Label(top, text="Search").pack(side="left")
        self.log_search = tk.StringVar()
        e = ttk.Entry(top, width=20, textvariable=self.log_search)
        e.pack(side="left", padx=(4, 10))
        e.bind("<Return>", lambda ev: self._rerender_log())
        self.traffic_var = tk.BooleanVar(value=False)
        tip(ttk.Checkbutton(top, text="Log traffic", variable=self.traffic_var,
                            command=lambda: setattr(self.sim, "log_traffic", self.traffic_var.get())),
            "One line per request and answer. Busy sites produce a lot of lines.").pack(side="left")
        self.autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Auto-scroll", variable=self.autoscroll).pack(side="left", padx=8)
        ttk.Button(top, text="Save…", command=self.save_log).pack(side="right")
        ttk.Button(top, text="Clear", command=self.clear_log).pack(side="right", padx=4)
        tf = ttk.Frame(f)
        tf.pack(fill="both", expand=True)
        self.log_text = tk.Text(tf, wrap="word", background=PANEL, foreground=TEXT, relief="flat",
                                font=("Menlo" if sys.platform == "darwin" else "Consolas", 11), padx=8, pady=6)
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb.set, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for k, c in LOG_COLORS.items():
            self.log_text.tag_configure(k, foreground=c)
        self.log_text.tag_configure("ts", foreground="#9ca3af")

    def _build_help_tab(self):
        t = tk.Text(self.tab_help, wrap="word", background=PANEL, foreground=TEXT, relief="flat", padx=16, pady=12,
                    font=(self.font, 12))
        vsb = ttk.Scrollbar(self.tab_help, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=vsb.set)
        t.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        t.tag_configure("h", font=(self.font, 13, "bold"), spacing1=10, spacing3=4)
        for line in HELP_TEXT.splitlines():
            if line and line.isupper():
                t.insert("end", line + "\n", "h")
            else:
                t.insert("end", line + "\n")
        t.configure(state="disabled")

    # ── actions ─────────────────────────────────────────────────────────────
    def add_devices(self, preset=None):
        AddDialog(self, preset)

    def _selected_iface(self):
        label = self.iface_var.get()
        for i in self.ifaces:
            if self._iface_label(i) == label:
                return i
        return self.ifaces[0]

    def start(self):
        try:
            port = parse_num(self.port_var, "Main UDP port", 1, 65535, True)
        except ValueError as e:
            messagebox.showerror("Main port", str(e))
            return
        try:
            self.sim.query(self.sim.configure, self._selected_iface(), port, self.iam_var.get().lower(),
                           self.relay_var.get())
        except ValueError as e:
            messagebox.showerror("Cannot start", str(e))
            return
        if not self.sim.query(lambda: len(self.sim.devices)):
            if not messagebox.askyesno("No devices yet", "There are no devices yet. Start anyway (only the main "
                                                         "port opens)?"):
                return
        errors = self.sim.run_coro(self.sim.start())
        if errors:
            main_failed = any(e.startswith(f"UDP port {port}:") for e in errors)
            messagebox.showwarning("Some ports could not be opened",
                                   "\n".join(errors[:15]) + (f"\n… and {len(errors) - 15} more" if len(errors) > 15 else "") +
                                   ("\n\nThe main port is taken: close the other BACnet program or choose another main "
                                    "port." if main_failed else ""))
        self._set_running(True)
        self.refresh_now()

    def stop(self):
        self.sim.query(self.sim.stop)
        self._set_running(False)
        self.refresh_now()

    def _set_running(self, on):
        self.start_btn.configure(state="disabled" if on else "normal")
        self.stop_btn.configure(state="normal" if on else "disabled")
        self.port_entry.configure(state="disabled" if on else "normal")
        self.iface_cb.configure(state="disabled" if on else "readonly")
        self.run_pill.configure(text="  RUNNING  " if on else "  STOPPED  ", background=OK if on else "#4b5563")

    def selected_insts(self):
        insts = []
        for iid in self.tree.selection():
            if iid.startswith("d"):
                insts.append(int(iid[1:]))
            elif iid.startswith("g"):
                insts += self.sim.query(self.sim.group_devices, int(iid[1:]))
            elif iid.startswith("n"):
                for child in self.tree.get_children(iid):
                    if child.startswith("d"):
                        insts.append(int(child[1:]))
        return sorted(set(insts))

    def selected_op(self, op):
        insts = self.selected_insts()
        if not insts:
            messagebox.showinfo("Select devices", "Select devices (or a group / network) in the tree first.")
            return
        if op in ("reboot", "iam") and not self.sim.running:
            messagebox.showinfo("Not running", "Start the simulation first.")
            return
        self.sim.query(self.sim.device_op, insts, op)
        self.refresh_now()

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        groups = [int(i[1:]) for i in sel if i.startswith("g")]
        devs = [int(i[1:]) for i in sel if i.startswith("d")]
        if not groups and not devs:
            messagebox.showinfo("Remove", "Select devices or a group. Networks are removed with their group.")
            return
        what = (f"{len(groups)} group(s)" if groups else "") + (" and " if groups and devs else "") + \
               (f"{len(devs)} device(s)" if devs else "")
        if not messagebox.askyesno("Remove", f"Remove {what}?"):
            return
        for g in groups:
            self.sim.query(self.sim.remove_group, g)
        for d in devs:
            self.sim.query(self.sim.remove_device, d)
        self.after_structure_change()

    def _context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Online", command=lambda: self.selected_op("online"))
        m.add_command(label="Offline (silent)", command=lambda: self.selected_op("offline"))
        m.add_command(label="Reboot", command=lambda: self.selected_op("reboot"))
        m.add_command(label="Send I-Am", command=lambda: self.selected_op("iam"))
        m.add_command(label="Clear COV subscriptions", command=lambda: self.selected_op("clear_subs"))
        m.add_separator()
        m.add_command(label="Remove…", command=self.remove_selected)
        m.tk_popup(event.x_root, event.y_root)

    def clear_subs(self):
        if messagebox.askyesno("Clear subscriptions", "Make every device forget its COV subscriptions?"):
            self.sim.query(self.sim.clear_all_subs)

    def new_site(self):
        if self.sim.running:
            messagebox.showinfo("Running", "Stop the simulation first.")
            return
        if self.sim.query(lambda: len(self.sim.groups)) and not messagebox.askyesno("New site", "Remove all devices?"):
            return
        self.sim.query(self.sim.clear_all)
        self.after_structure_change()

    def save(self):
        path = filedialog.asksaveasfilename(title="Save site", defaultextension=".json",
                                            filetypes=[("ENMA site", "*.json")],
                                            initialfile="enma-site.json")
        if not path:
            return
        data = self.sim.query(self.sim.to_json, timeout=60)
        with open(path, "w") as fh:
            json.dump(data, fh)
        self.sim.log(f"Site saved to {path}", "info")

    def _load(self, path):
        if self.sim.running:
            messagebox.showinfo("Running", "Stop the simulation before opening a site.")
            return
        try:
            with open(path) as fh:
                data = json.load(fh)
            self.sim.query(self.sim.load_json, data, timeout=120)
        except Exception as e:
            messagebox.showerror("Cannot open site", f"{path}\n\n{e}")
            return
        self.port_var.set(str(self.sim.main_port))
        self.iam_var.set(self.sim.iam_mode.capitalize())
        self.relay_var.set(self.sim.relay)
        self.after_structure_change()

    def open(self):
        path = filedialog.askopenfilename(title="Open site", filetypes=[("ENMA site", "*.json"),
                                                                          ("All files", "*")])
        if path:
            self._load(path)

    def restore_last(self):
        if os.path.exists(LAST_SITE):
            self._load(LAST_SITE)

    def save_log(self):
        path = filedialog.asksaveasfilename(title="Save activity log", defaultextension=".txt",
                                            initialfile="enma-log.txt")
        if path:
            with open(path, "w") as fh:
                for ts, kind, msg in self.log_lines:
                    fh.write(f"{ts} [{kind}] {msg}\n")

    def clear_log(self):
        self.log_lines.clear()
        self._rerender_log()

    def on_close(self):
        try:
            if self.sim.query(lambda: len(self.sim.groups)):
                os.makedirs(CONFIG_DIR, exist_ok=True)
                data = self.sim.query(self.sim.to_json, timeout=60)
                with open(LAST_SITE, "w") as fh:
                    json.dump(data, fh)
            if self.sim.running:
                self.sim.query(self.sim.stop)
        except Exception:
            pass
        self.root.destroy()

    # ── tree ────────────────────────────────────────────────────────────────
    def after_structure_change(self, select=None):
        self.tree_version = -1
        self.refresh_now()
        if select and self.tree.exists(select):
            self.tree.selection_set(select)
            self.tree.see(select)
        elif self.detail_key and self.detail_key[0] != "welcome":
            self._on_select(force=True)

    def _filter_changed(self):
        if self.filter_after:
            self.root.after_cancel(self.filter_after)
        self.filter_after = self.root.after(300, lambda: (setattr(self, "tree_version", -1), self.refresh_now()))

    def _device_row(self, d):
        inst, name, addr, state, cov, npts, nsubs, rx, net, port = d
        tags = ()
        if state in ("OFFLINE", "Rebooting", "Down (flap)", "Net down"):
            tags = ("down",)
        elif state in ("Flapping", "Slow", "DCC off"):
            tags = ("warn",)
        return name, (inst, addr, state, cov, npts, nsubs, rx), tags

    def _rebuild_tree(self, snap):
        flt = self.filter_var.get().strip().lower()
        sel = self.tree.selection()
        old = set(self.tree_cache)
        opened = {iid for iid in old if iid[0] in "gn" and self.tree.exists(iid) and self.tree.item(iid, "open")}
        self.tree.delete(*self.tree.get_children())
        self.tree_cache = {}
        for gid, gname, kind, nets, devs in snap["groups"]:
            if flt:
                devs = [d for d in devs if flt in " ".join(str(x) for x in d[:5]).lower()]
                if not devs and flt not in gname.lower():
                    continue
            giid = f"g{gid}"
            label = f"{gname}"
            vals = ("", "routed" if kind == "routed" else "BACnet/IP", f"{len(devs)} devices", "", "", "", "")
            self.tree.insert("", "end", iid=giid, text=label, values=vals, tags=("group",),
                             open=giid not in old or giid in opened)
            self.tree_cache[giid] = vals
            parents = {}
            for port, num, ndev, state in nets:
                niid = f"n{port}_{num}"
                nvals = ("", f"router :{port}", state, "", ndev, "", "")
                self.tree.insert(giid, "end", iid=niid, text=f"Network {num}", values=nvals,
                                 tags=("netbad",) if state not in ("OK",) and not state.startswith("Queue") else ("net",),
                                 open=bool(flt) or niid in opened or (niid not in old and ndev <= 40))
                self.tree_cache[niid] = nvals
                parents[(port, num)] = niid
            for d in devs:
                name, vals, tags = self._device_row(d)
                parent = parents.get((d[9], d[8]), giid) if d[8] is not None else giid
                diid = f"d{d[0]}"
                self.tree.insert(parent, "end", iid=diid, text=name, values=vals, tags=tags)
                self.tree_cache[diid] = vals
        keep = [i for i in sel if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        self.tree_version = snap["version"]

    def _update_tree(self, snap):
        for gid, gname, kind, nets, devs in snap["groups"]:
            for port, num, ndev, state in nets:
                niid = f"n{port}_{num}"
                nvals = ("", f"router :{port}", state, "", ndev, "", "")
                if self.tree_cache.get(niid) != nvals and self.tree.exists(niid):
                    self.tree.item(niid, values=nvals,
                                   tags=("netbad",) if state != "OK" and not state.startswith("Queue") else ("net",))
                    self.tree_cache[niid] = nvals
            for d in devs:
                diid = f"d{d[0]}"
                if diid not in self.tree_cache:
                    continue
                name, vals, tags = self._device_row(d)
                if self.tree_cache[diid] != vals:
                    self.tree.item(diid, values=vals, tags=tags)
                    self.tree_cache[diid] = vals

    def _on_select(self, force=False):
        sel = self.tree.selection()
        if not sel:
            return
        iid = self.tree.focus() if self.tree.focus() in sel else sel[0]
        if iid.startswith("d"):
            key = ("device", int(iid[1:]))
        elif iid.startswith("n"):
            port, num = iid[1:].split("_")
            key = ("network", int(port), int(num))
        else:
            key = ("group", int(iid[1:]))
        if key == self.detail_key and not force:
            return
        self._show(key)
        self.nb.select(self.tab_detail)

    def _show(self, key):
        if self.detail is not None:
            self.detail.destroy()
        self.detail_key = key
        if key[0] == "device":
            self.detail = DeviceView(self, self.tab_detail, key[1])
        elif key[0] == "network":
            self.detail = NetworkView(self, self.tab_detail, key[1], key[2])
        elif key[0] == "group":
            self.detail = GroupView(self, self.tab_detail, key[1])
        else:
            self.detail = WelcomeView(self, self.tab_detail)
        self.detail.pack(fill="both", expand=True)

    def show_welcome(self):
        if self.detail_key != ("welcome",):
            self.root.after_idle(lambda: self._show(("welcome",)))
            self.detail_key = ("welcome",)

    # ── periodic refresh ────────────────────────────────────────────────────
    def refresh_now(self):
        try:
            self._refresh()
        except Exception:
            traceback.print_exc()

    def _tick(self):
        self.refresh_now()
        self._gc_ticks += 1
        gc.collect(2 if self._gc_ticks % 120 == 0 else (1 if self._gc_ticks % 10 == 0 else 0))
        self.root.after(1000, self._tick)

    def _refresh(self):
        snap = self.sim.query(self.sim.snapshot_tree, timeout=20)
        if snap["version"] != self.tree_version:
            self._rebuild_tree(snap)
        else:
            self._update_tree(snap)
        s = self.sim.query(self.sim.snapshot_status)
        if s["running"]:
            up = int(s["uptime"])
            self.status_left.configure(
                text=f"Running {up // 3600:d}:{up % 3600 // 60:02d}:{up % 60:02d} on {self.sim.my_ip} · "
                     f"ports {self._ports_text(s['ports'])}" + (f" · {s['fds']} foreign device(s)" if s["fds"] else ""))
        else:
            self.status_left.configure(text="Stopped · add devices and press Start")
        self.status_right.configure(text=f"{s['devices']:,} devices ({s['online']:,} online) · {s['points']:,} objects · "
                                         f"{s['subs']:,} COV subs · RX {s['rx']:,} · TX {s['tx']:,} · "
                                         f"{s['rate']:.0f} pkt/s")
        if self.detail is not None and self.detail_key and self.detail_key[0] != "welcome":
            try:
                self.detail.refresh()
            except tk.TclError:
                pass
        if self.nb.select() == str(self.tab_subs):
            self._refresh_subs()

    @staticmethod
    def _ports_text(ports):
        if not ports:
            return "none"
        if len(ports) <= 4:
            return ", ".join(map(str, ports))
        return f"{ports[0]}…{ports[-1]} ({len(ports)})"

    def _refresh_subs(self):
        snap = self.sim.query(self.sim.snapshot_subs)
        rows = snap["rows"]
        t = self.subs_tree
        t.delete(*t.get_children())
        for r in rows:
            tags = ("indef",) if r[6] == "INDEFINITE" else (("mute",) if r[12] else ())
            t.insert("", "end", values=r[:12], tags=tags)
        n = snap["total"]
        self.subs_lbl.configure(text=f"{n:,} active COV subscription{'s' if n != 1 else ''}" +
                                     (f" (showing {len(rows):,})" if n > len(rows) else ""))

    # ── log ─────────────────────────────────────────────────────────────────
    KIND_FILTER = {"COV": {"cov"}, "Router": {"router"}, "Devices": {"device"}, "Writes": {"write"},
                   "Warnings & errors": {"warn", "error"}, "Traffic": {"traffic"}}

    def _log_visible(self, kind, msg):
        allowed = self.KIND_FILTER.get(self.log_kind.get())
        if allowed is not None and kind not in allowed:
            return False
        q = self.log_search.get().strip().lower()
        return not q or q in msg.lower()

    def _drain_log(self):
        new = []
        try:
            for _ in range(3000):
                new.append(self.sim.log_q.get_nowait())
        except queue.Empty:
            pass
        if new:
            self.log_lines.extend(new)
            t = self.log_text
            t.configure(state="normal")
            for ts, kind, msg in new:
                if self._log_visible(kind, msg):
                    t.insert("end", ts + "  ", "ts")
                    t.insert("end", msg + "\n", kind)
            lines = int(t.index("end-1c").split(".")[0])
            if lines > 8000:
                t.delete("1.0", f"{lines - 6000}.0")
            t.configure(state="disabled")
            if self.autoscroll.get():
                t.see("end")
        self.root.after(250 if len(new) < 3000 else 50, self._drain_log)

    def _rerender_log(self):
        t = self.log_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        shown = [x for x in self.log_lines if self._log_visible(x[1], x[2])][-6000:]
        for ts, kind, msg in shown:
            t.insert("end", ts + "  ", "ts")
            t.insert("end", msg + "\n", kind)
        t.configure(state="disabled")
        t.see("end")
