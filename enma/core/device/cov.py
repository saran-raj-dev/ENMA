"""COV subscription table and (un)confirmed COV notifications."""

from __future__ import annotations

import time

from enma.bacnet.codec import ctx_close, ctx_enum, ctx_oid, ctx_open, ctx_uint
from enma.bacnet.constants import (
    ANALOG,
    DEVICE,
    OBJ_SHORT,
    P_PRESENT_VALUE,
    P_STATUS_FLAGS,
    SC_COV_NOTIFY,
    SU_COV_NOTIFY,
    max_apdu_to_code,
)
from enma.bacnet.framing import apdu_unconfirmed


class CovMixin:
    """COV subscription table and (un)confirmed COV notifications."""

    def drop_sub(self, key, reason=""):
        sub = self.subs.pop(key, None)
        if sub is not None:
            try:
                sub.pt.subs.remove(sub)
            except ValueError:
                pass
            if reason:
                self.sim.log(f"Device {self.instance}: COV subscription on {OBJ_SHORT[sub.pt.otype]}:"
                             f"{sub.pt.inst} from {sub.addr} removed ({reason})", "cov")

    def clear_subs(self, reason=""):
        n = len(self.subs)
        for sub in self.subs.values():
            sub.pt.subs = []
        self.subs.clear()
        for p in self.pending.values():
            if p[3] is not None:
                p[3].cancel()
        self.pending.clear()
        if n and reason:
            self.sim.log(f"Device {self.instance}: {n} COV subscription(s) cleared ({reason})", "cov")

    def on_value_changed(self, p, flags_changed=False):
        if not p.subs or self.cov_mode != "full":
            return
        pv = p.pv()
        for sub in list(p.subs):
            if flags_changed or sub.last_value is None:
                self.notify(sub)
            elif p.otype in ANALOG:
                if pv != sub.last_value and abs(pv - sub.last_value) >= p.cov_inc:
                    self.notify(sub)
            elif pv != sub.last_value:
                self.notify(sub)

    def notify(self, sub):
        p = sub.pt
        if not self.is_up() or self.dcc or self.cov_mode != "full":
            return
        if self.subs.get((sub.addr.key(), sub.pid, p.otype, p.inst)) is not sub:
            return
        remaining = max(0, int(sub.expires - time.monotonic())) if sub.expires else 0
        values = (ctx_open(4) +
                  ctx_enum(0, P_PRESENT_VALUE) + ctx_open(2) + p.enc_value(p.pv()) + ctx_close(2) +
                  ctx_enum(0, P_STATUS_FLAGS) + ctx_open(2) + p.status_flags() + ctx_close(2) +
                  ctx_close(4))
        payload = (ctx_uint(0, sub.pid) + ctx_oid(1, DEVICE, self.instance) + ctx_oid(2, p.otype, p.inst) +
                   ctx_uint(3, remaining) + values)
        sub.last_value = p.pv()
        sub.count += 1
        sub.last_at = time.time()
        self.st["notifies"] += 1
        if sub.confirmed:
            inv = self.next_invoke()
            old = self.pending.pop(inv, None)
            if old is not None and old[3] is not None:
                old[3].cancel()
            apdu = bytes([0x00, max_apdu_to_code(self.max_apdu), inv, SC_COV_NOTIFY]) + payload
            self.pending[inv] = [sub, apdu, 0, None]
            self._send_pending(inv)
        else:
            self._out(apdu_unconfirmed(SU_COV_NOTIFY, payload), sub.addr, via_trunk=True)

    def _send_pending(self, inv):
        p = self.pending.get(inv)
        if p is None:
            return
        self._out(p[1], p[0].addr, expect_reply=True, via_trunk=True)
        p[3] = self.sim.loop.call_later(3.0, self._pending_timeout, inv)

    def _pending_timeout(self, inv):
        p = self.pending.get(inv)
        if p is None:
            return
        p[2] += 1
        if p[2] > 3 or not self.is_up():
            self.pending.pop(inv, None)
            p[0].fails += 1
            self.st["notify_fail"] += 1
            self.sim.log(f"Device {self.instance}: ConfirmedCOVNotification to {p[0].addr} not acknowledged "
                         f"after 4 tries", "cov")
            return
        self._send_pending(inv)
