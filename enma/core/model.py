"""Simulated objects (points) and COV subscriptions."""

from __future__ import annotations

import time

from enma.bacnet.codec import app_bits, app_enum, app_real, app_uint
from enma.bacnet.constants import ANALOG, BINARY, COMMANDABLE


# ════════════════════════════════════════════════════════════════════════════
#  Site model
# ════════════════════════════════════════════════════════════════════════════

class Point:
    __slots__ = ("dev", "otype", "inst", "name", "desc", "units", "value", "lo", "hi", "cov_inc",
                 "texts", "chg_min", "chg_max", "frozen", "stale", "deleted", "fault", "oos",
                 "cov_ok", "prio", "next_change", "gen", "changes", "last_change", "subs", "reads")

    def __init__(self, dev, otype, inst, name):
        self.dev = dev
        self.otype = otype
        self.inst = inst
        self.name = name
        self.desc = ""
        self.units = 95
        self.value = 0
        self.lo, self.hi = 0.0, 100.0
        self.cov_inc = 0.5
        self.texts = None                 # binary: [inactive, active]; multi: state texts
        self.chg_min, self.chg_max = 10.0, 60.0
        self.frozen = False
        self.stale = False
        self.deleted = False
        self.fault = False
        self.oos = False
        self.cov_ok = True
        self.prio = [None] * 16 if otype in COMMANDABLE else None
        self.next_change = None
        self.gen = 0
        self.changes = 0
        self.last_change = None
        self.subs = []
        self.reads = 0

    @property
    def key(self):
        return (self.otype, self.inst)

    def pv(self):
        if self.prio:
            for v in self.prio:
                if v is not None:
                    return v
        return self.value

    def active_priority(self):
        if self.prio:
            for i, v in enumerate(self.prio):
                if v is not None:
                    return i + 1
        return None

    def enc_value(self, v):
        if self.otype in ANALOG:
            return app_real(v)
        if self.otype in BINARY:
            return app_enum(1 if v else 0)
        return app_uint(int(v))

    def status_flags(self):
        return app_bits([False, self.fault, False, self.oos])

    def value_text(self, v=None):
        v = self.pv() if v is None else v
        if self.otype in ANALOG:
            return f"{v:.2f}"
        if self.otype in BINARY:
            t = self.texts or ["inactive", "active"]
            return f"{t[1] if v else t[0]} ({1 if v else 0})"
        t = self.texts or []
        return f"{t[v - 1] if 0 < v <= len(t) else '?'} ({v})"

    def to_json(self):
        return [self.otype, self.inst, self.name, self.desc, self.units, self.value, self.lo, self.hi,
                self.cov_inc, self.texts, self.chg_min, self.chg_max, self.frozen, self.stale,
                self.deleted, self.fault, self.oos, self.cov_ok]

    @classmethod
    def from_json(cls, dev, a):
        p = cls(dev, a[0], a[1], a[2])
        (p.desc, p.units, p.value, p.lo, p.hi, p.cov_inc, p.texts, p.chg_min, p.chg_max, p.frozen,
         p.stale, p.deleted, p.fault, p.oos, p.cov_ok) = a[3:18]
        return p


class Sub:
    __slots__ = ("addr", "pid", "pt", "confirmed", "lifetime", "expires", "created", "last_value",
                 "count", "last_at", "fails", "renewals")

    def __init__(self, addr, pid, pt, confirmed, lifetime):
        self.addr, self.pid, self.pt = addr, pid, pt
        self.confirmed = confirmed
        self.lifetime = lifetime
        self.expires = time.monotonic() + lifetime if lifetime else None
        self.created = time.time()
        self.last_value = None
        self.count = 0
        self.last_at = None
        self.fails = 0
        self.renewals = 0


COV_MODE_LABELS = {
    "full": "Supported",
    "none": "Not supported (no SubscribeCOV)",
    "mute": "Accepts, never notifies",
}
