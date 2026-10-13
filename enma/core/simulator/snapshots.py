"""Read-only snapshots of the engine state for the user interface."""

from __future__ import annotations

import time
from datetime import datetime

from enma.bacnet.constants import ANALOG, OBJ_SHORT, UNITS
from enma.core.model import COV_MODE_LABELS
from enma.core.util import fmt_dur


class SnapshotMixin:
    """Read-only snapshots of the engine state for the user interface."""

    def snapshot_tree(self):
        groups = []
        for g in self.groups:
            nets = [(n.ep.port, n.number, len(n.devices), n.state_text()) for n in g.networks]
            devs = []
            for d in g.devices:
                short = (f"{d.network.number}:{int.from_bytes(d.mac, 'big')}" if d.network
                         else f"{self.my_ip}:{d.ep.port if d.ep else '?'}")
                devs.append((d.instance, d.name, short, d.state_text(), d.cov_text(),
                             len(d.order), len(d.subs), d.st["rx"], d.net_num, d.ep.port if d.ep else None))
            groups.append((g.gid, g.name, g.kind, nets, devs))
        return dict(version=self.version, groups=groups)

    def snapshot_status(self):
        nsubs = sum(len(d.subs) for d in self.devices.values())
        online = sum(1 for d in self.devices.values() if d.online)
        return dict(running=self.running, devices=len(self.devices), online=online,
                    points=sum(len(d.order) for d in self.devices.values()), subs=nsubs, rx=self.rx, tx=self.tx,
                    rate=self.packet_rate(), fds=len(self.fds),
                    ports=sorted(p for p, e in self.endpoints.items() if e.is_open),
                    uptime=(time.monotonic() - self.started_at) if self.running and self.started_at else 0)

    def snapshot_device(self, inst):
        d = self.devices.get(inst)
        if d is None:
            return None
        now = time.monotonic()
        pts = []
        for k in d.order:
            p = d.points[k]
            if p.frozen:
                interval = "never (frozen)"
            else:
                interval = f"{fmt_dur(p.chg_min)} – {fmt_dur(p.chg_max)}"
            nxt = "-" if p.next_change is None or p.frozen or p.deleted else fmt_dur(p.next_change - now)
            flags = []
            if p.deleted:
                flags.append("DELETED")
            if p.stale:
                flags.append("stale")
            if p.fault:
                flags.append("FAULT")
            if p.oos:
                flags.append("OOS")
            ap = p.active_priority()
            if ap:
                flags.append(f"cmd@{ap}")
            cov = "no (refuses)" if not p.cov_ok else ("-" if d.cov_mode == "none" else "yes")
            unit = UNITS.get(p.units, "") if p.otype in ANALOG else ""
            last = datetime.fromtimestamp(p.last_change).strftime("%H:%M:%S") if p.last_change else "-"
            pts.append((f"{k[0]}:{k[1]}", f"{OBJ_SHORT[p.otype]}:{p.inst}", p.name, p.value_text(), unit,
                        interval, nxt, last, cov, len(p.subs), p.reads, " ".join(flags)))
        info = dict(instance=d.instance, name=d.name, address=d.address(), state=d.state_text(),
                    cov=COV_MODE_LABELS[d.cov_mode], group=d.group.name, gid=d.group.gid,
                    routed=d.network is not None, net=d.net_num, mac=int.from_bytes(d.mac, "big") if d.mac else None,
                    port=d.ep.port if d.ep else None, subs=len(d.subs), max_apdu=d.max_apdu,
                    segmentation=d.segmentation, db_rev=d.db_rev, dcc=d.dcc,
                    last_rx=datetime.fromtimestamp(d.last_rx).strftime("%H:%M:%S") if d.last_rx else "never",
                    next_flap=fmt_dur(d.next_flap - now) if d.flap and d.next_flap and d.online else "-",
                    back_in=fmt_dur(d.back_at - now) if d.back_at else "-")
        return dict(info=info, stats=dict(d.st), points=pts, settings=d.settings())

    def snapshot_network(self, port, num):
        net = self.network_of(port, num)
        if net is None:
            return None
        return dict(number=net.number, port=port, devices=len(net.devices), trunk_ms=net.trunk_ms,
                    buffer=net.buffer, unreachable=net.unreachable, offline=net.offline, queue=len(net.q),
                    peak=net.peak_q, busy=net.state_text(), busy_events=net.busy_events, dropped=net.dropped,
                    routed=net.routed, group=net.group.name)

    def snapshot_group(self, gid):
        g = next((g for g in self.groups if g.gid == gid), None)
        if g is None:
            return None
        devs = g.devices
        pts = [p for d in devs for p in d.points.values()]
        return dict(gid=g.gid, name=g.name, kind=g.kind, devices=len(devs),
                    online=sum(1 for d in devs if d.online),
                    cov_full=sum(1 for d in devs if d.cov_mode == "full"),
                    cov_none=sum(1 for d in devs if d.cov_mode == "none"),
                    cov_mute=sum(1 for d in devs if d.cov_mode == "mute"),
                    flap=sum(1 for d in devs if d.flap), slow=sum(1 for d in devs if d.delay_max > 0),
                    points=len(pts), stale=sum(1 for p in pts if p.stale), frozen=sum(1 for p in pts if p.frozen),
                    refuse=sum(1 for p in pts if not p.cov_ok), subs=sum(len(d.subs) for d in devs),
                    networks=[(n.ep.port, n.number) for n in g.networks],
                    first=devs[0].instance if devs else None, last=devs[-1].instance if devs else None,
                    reads=sum(d.st["reads"] for d in devs), notifies=sum(d.st["notifies"] for d in devs))

    def snapshot_subs(self, limit=3000):
        now = time.monotonic()
        rows = []
        total = 0
        for d in self.devices.values():
            for sub in d.subs.values():
                total += 1
                if len(rows) >= limit:
                    continue
                p = sub.pt
                rows.append((d.instance, f"{OBJ_SHORT[p.otype]}:{p.inst}", p.name, str(sub.addr), sub.pid,
                             "confirmed" if sub.confirmed else "unconfirmed",
                             "INDEFINITE" if not sub.lifetime else f"{sub.lifetime}s",
                             "∞" if sub.expires is None else fmt_dur(sub.expires - now),
                             sub.renewals, sub.count,
                             datetime.fromtimestamp(sub.last_at).strftime("%H:%M:%S") if sub.last_at else "-",
                             sub.fails, "mute" if d.cov_mode == "mute" else ""))
        return dict(rows=rows, total=total)
