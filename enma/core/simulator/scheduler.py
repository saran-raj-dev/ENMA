"""Ticker: value changes, subscription lifetimes, flapping, reboots, packet rate."""

from __future__ import annotations

import asyncio
import heapq
import math
import random
import time
import traceback

from enma.bacnet.constants import ANALOG, BINARY


class SchedulerMixin:
    """Ticker: value changes, subscription lifetimes, flapping, reboots, packet rate."""

    async def _ticker(self):
        last_sec = 0.0
        while True:
            try:
                now = time.monotonic()
                if self.running:
                    self._run_changes(now)
                    if now - last_sec >= 1.0:
                        self._rate.append((now, self.rx + self.tx))
                        last_sec = now
                        self._per_second(now)
            except Exception:
                self.log("Engine tick error:\n" + traceback.format_exc(), "error")
            await asyncio.sleep(0.2)

    def schedule(self, p, now=None):
        if p.frozen or p.deleted:
            p.next_change = None
            return
        now = time.monotonic() if now is None else now
        lo, hi = sorted((max(0.5, float(p.chg_min)), max(0.5, float(p.chg_max))))
        p.gen += 1
        p.next_change = now + random.uniform(lo, hi)
        heapq.heappush(self.heap, (p.next_change, next(self.seq), p, p.gen))

    def _run_changes(self, now):
        h = self.heap
        n = 0
        while h and h[0][0] <= now and n < 50000:
            _, _, p, gen = heapq.heappop(h)
            n += 1
            if gen != p.gen or p.deleted or p.frozen or p.dev.removed:
                continue
            self.change_point(p)
            self.schedule(p, now)

    def change_point(self, p):
        before = p.pv()
        if p.otype in ANALOG:
            lo, hi = float(p.lo), float(p.hi)
            span = max(hi - lo, 1e-6)
            step = random.gauss(0, span * 0.06)
            if p.cov_inc and abs(step) < p.cov_inc and random.random() < 0.6:
                step = math.copysign(p.cov_inc * random.uniform(1.0, 2.0), step or 1)
            v = float(p.value) + step
            if v > hi:
                v = hi - (v - hi)
            if v < lo:
                v = lo + (lo - v)
            p.value = round(min(max(v, lo), hi), 2)
        elif p.otype in BINARY:
            p.value = 0 if p.value else 1
        else:
            n = len(p.texts or [])
            choices = [s for s in range(1, n + 1) if s != p.value]
            p.value = random.choice(choices) if choices else 1
        p.changes += 1
        p.last_change = time.time()
        if p.pv() != before:
            p.dev.on_value_changed(p)

    def _per_second(self, now):
        for k, exp in list(self.fds.items()):
            if now > exp:
                del self.fds[k]
                self.log(f"Foreign device {k[0]}:{k[1]} registration expired", "info")
        for dev in list(self.devices.values()):
            if dev.back_at is not None and now >= dev.back_at:
                dev.come_back()
            elif dev.flap and dev.online and dev.next_flap is not None and now >= dev.next_flap:
                dev.flap_down(now)
            if dev.subs:
                for key, sub in list(dev.subs.items()):
                    if sub.expires is not None and now >= sub.expires:
                        dev.drop_sub(key, "lifetime expired, not renewed")
            if dev.dcc_until is not None and now >= dev.dcc_until:
                dev.dcc = 0
                dev.dcc_until = None
                self.log(f"Device {dev.instance}: DeviceCommunicationControl period ended → enabled", "device")

    def packet_rate(self):
        if len(self._rate) < 2:
            return 0.0
        (t0, c0), (t1, c1) = self._rate[0], self._rate[-1]
        return (c1 - c0) / max(t1 - t0, 1e-6)
