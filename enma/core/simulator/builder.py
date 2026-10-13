"""Building the site: groups of devices, networks, endpoints and generated points."""

from __future__ import annotations

import random
import time

from enma.bacnet.constants import ANALOG, BINARY, OBJ_SHORT, POINT_TYPES, WILDCARD_INSTANCE
from enma.core.device import Device
from enma.core.group import Group
from enma.core.model import Point
from enma.core.network import Endpoint, Network
from enma.core.templates import (
    ANALOG_TEMPLATES,
    BINARY_TEMPLATES,
    DEFAULT_PARAMS,
    MULTI_TEMPLATES,
    TYPE_PARAM,
    UNIT_SECONDS,
)


class SiteBuilderMixin:
    """Building the site: groups of devices, networks, endpoints and generated points."""

    def _ensure_endpoint(self, port):
        ep = self.endpoints.get(port)
        if ep is None:
            ep = Endpoint(self, port)
            self.endpoints[port] = ep
        return ep

    def next_free_instance(self):
        return max(self.devices) + 1 if self.devices else 1001

    def next_free_network(self, port=None):
        port = port or self.main_port
        used = set(self.endpoints[port].networks) if port in self.endpoints else set()
        if not used:
            return 1001
        return max(used) + 1

    def next_free_port(self):
        p = self.main_port + 1
        while p in self.endpoints:
            p += 1
        return p

    def _pick(self, devices, pct):
        k = int(round(len(devices) * max(0.0, min(100.0, float(pct))) / 100.0))
        return set(random.sample(range(len(devices)), k)) if k else set()

    def add_group(self, params):
        P = dict(DEFAULT_PARAMS)
        P.update(params)
        count = int(P["count"])
        if count < 1:
            raise ValueError("Number of devices must be at least 1")
        if count > 50000:
            raise ValueError("Up to 50,000 devices per group")
        kind = P["kind"]
        if kind not in ("routed", "direct", "mixed"):
            raise ValueError(f"Unknown connection type {kind!r}")
        if kind == "mixed":
            pct = max(0.0, min(100.0, float(P.get("direct_pct", 50))))
            n_direct = int(round(count * pct / 100.0))
        else:
            n_direct = count if kind == "direct" else 0
        n_routed = count - n_direct
        start = int(P["start_instance"]) or self.next_free_instance()
        if start < 0 or start + count - 1 >= WILDCARD_INSTANCE:
            raise ValueError("Device instances must be between 0 and 4194302")
        clash = [i for i in range(start, start + count) if i in self.devices]
        if clash:
            raise ValueError(f"Device instance {clash[0]} already exists "
                             f"({len(clash)} of the requested range {start}-{start + count - 1} are taken)")
        type_counts = {t: max(0, int(P[TYPE_PARAM[t]])) for t in POINT_TYPES}
        if sum(type_counts.values()) == 0:
            raise ValueError("Each device needs at least one point")
        if sum(type_counts.values()) > 20000:
            raise ValueError("Up to 20,000 points per device")

        group = Group(self.next_gid, P["name"].strip() or f"Group {self.next_gid}", kind, P)
        warnings = []
        devices = []

        # addressing: devices 0 .. n_routed-1 are routed, the rest are direct BACnet/IP
        if n_routed:
            port = int(P["router_port"]) or self.main_port
            per_net = max(1, min(254, int(P["per_net"])))
            first_mac = max(0, min(254, int(P["first_mac"])))
            if first_mac + per_net - 1 > 254:
                raise ValueError("First MAC + devices per network must stay within 0-254")
            ep = self._ensure_endpoint(port)
            if ep.port != self.main_port and not self.relay:
                warnings.append(f"Router on port {port}: clients must send to that port "
                                f"(broadcast relay from {self.main_port} is off)")
            nets_needed = (n_routed + per_net - 1) // per_net
            net_no = int(P["first_net"]) or self.next_free_network(port)
            numbers = []
            while len(numbers) < nets_needed:
                if not 1 <= net_no <= 65534:
                    raise ValueError("Network numbers must be 1-65534")
                if net_no not in ep.networks:
                    numbers.append(net_no)
                net_no += 1
            others = {n for e in self.endpoints.values() if e is not ep for n in e.networks}
            dup = sorted(set(numbers) & others)
            if dup:
                warnings.append(f"Network(s) {dup} also exist behind another router port: duplicate "
                                f"network numbers (both routers will answer Who-Is-Router-To-Network)")
            nets = []
            for num in numbers:
                net = Network(self, ep, num, group)
                net.trunk_ms = float(P["trunk_ms"])
                net.buffer = int(P["buffer"])
                net.unreachable = bool(P["unreachable"])
                ep.networks[num] = net
                nets.append(net)
            group.networks = nets
        if n_direct:
            first_port = int(P["first_port"]) or self.next_free_port()
            cursor = first_port

        max_apdu_p = str(P["max_apdu"])
        seg_p = str(P["segmentation"])
        for i in range(count):
            inst = start + i
            dev = Device(self, group, inst, f"{P['prefix']}{i + 1:0{max(2, len(str(count)))}d}")
            routed = i < n_routed
            if routed:
                net = group.networks[i // per_net]
                mac = first_mac + (i % per_net)
                dev.network = net
                dev.mac = bytes([mac])
                dev.ep = net.ep
                net.devices[dev.mac] = dev
                dev.max_apdu = 480
                dev.segmentation = False
            else:
                # skip ports that already host a device or a router: one node per direct device
                while cursor in self.endpoints and (self.endpoints[cursor].device is not None
                                                    or self.endpoints[cursor].networks):
                    cursor += 1
                if cursor > 65535:
                    raise ValueError("Ran out of UDP ports")
                ep = self._ensure_endpoint(cursor)
                ep.device = dev
                dev.ep = ep
                cursor += 1
                dev.max_apdu = 1476
                dev.segmentation = True
            if max_apdu_p != "Auto":
                dev.max_apdu = int(max_apdu_p)
            if seg_p != "Auto":
                dev.segmentation = seg_p == "Yes"
            dev.location = group.name
            dev.description = f"Simulated {'routed (MS/TP)' if routed else 'BACnet/IP'} controller"
            devices.append(dev)

        # behaviour mix (exact percentages, random devices)
        cov_set = self._pick(devices, P["cov_pct"])
        cov_devs = [devices[i] for i in sorted(cov_set)]
        mute_set = {id(cov_devs[i]) for i in self._pick(cov_devs, P["mute_pct"])}
        off_set = self._pick(devices, P["offline_pct"])
        flap_set = self._pick(devices, P["flap_pct"])
        slow_set = self._pick(devices, P["slow_pct"])
        whois_set = self._pick(devices, P["slowwhois_pct"])
        nmul = UNIT_SECONDS.get(P["chg_unit"], 1)
        smul = UNIT_SECONDS.get(P["stale_unit"], 60)
        for i, dev in enumerate(devices):
            if i in cov_set:
                dev.cov_mode = "mute" if id(dev) in mute_set else "full"
                dev.max_subs = int(P["max_subs"])
            else:
                dev.cov_mode = "none"
            if i in off_set:
                dev.online = False
                dev.down_reason = "manual"
            if i in flap_set:
                dev.flap = True
                dev.flap_every_min = float(P["flap_every_min"]) * 60
                dev.flap_every_max = float(P["flap_every_max"]) * 60
                dev.flap_off_min = float(P["flap_off_min"])
                dev.flap_off_max = float(P["flap_off_max"])
                dev.flap_clear = bool(P["flap_clear"])
            if i in slow_set:
                dev.delay_min, dev.delay_max = float(P["slow_min"]), float(P["slow_max"])
            if i in whois_set:
                dev.iam_delay_min, dev.iam_delay_max = float(P["slowwhois_min"]), float(P["slowwhois_max"])
            dev.drop_pct = float(P["drop_pct"])
            self._make_points(dev, type_counts, P, nmul, smul)
            self.devices[dev.instance] = dev
            group.devices.append(dev)

        now = time.monotonic()
        for dev in devices:
            for p in dev.points.values():
                self.schedule(p, now)
            if self.running and dev.flap:
                dev.next_flap = now + random.uniform(dev.flap_every_min, dev.flap_every_max)
        self.groups.append(group)
        self.next_gid += 1
        self.version += 1
        npts = sum(len(d.order) for d in devices)
        where = []
        if n_routed:
            where.append(f"{n_routed} routed on networks {group.networks[0].number}-{group.networks[-1].number} "
                         f"behind router port {group.networks[0].ep.port}")
        if n_direct:
            where.append(f"{n_direct} direct on UDP ports {devices[n_routed].ep.port}-{devices[-1].ep.port}")
        where = "; ".join(where)
        self.log(f"Created '{group.name}': {count} devices ({start}-{start + count - 1}), {npts} objects, {where}",
                 "info")
        for w in warnings:
            self.log(w, "warn")
        return group.gid, warnings

    def add_composite(self, name, parts, direct_pct=50):
        """Create several scenarios as one: one group per part, named '<name>: <part>'.

        parts: [{"id": scenario id, "count": devices}]. All parts share the routed / direct split. If any
        part cannot be created, the parts already created are removed again.
        """
        from enma.core.scenarios import SCENARIO_BY_ID
        if not parts:
            raise ValueError("Choose at least one scenario")
        name = (name or "").strip() or "Custom"
        created, warnings = [], []
        try:
            for part in parts:
                sc = SCENARIO_BY_ID.get(part.get("id"))
                if sc is None:
                    raise ValueError(f"Unknown scenario {part.get('id')!r}")
                P = dict(sc["params"])
                P["count"] = int(part.get("count", P.get("count", 10)))
                P["kind"] = "mixed"
                P["direct_pct"] = float(direct_pct)
                P["name"] = f"{name}: {P.get('name', sc['title'])}"
                if P.get("router_port") == -1:
                    P["router_port"] = self.next_free_port()
                if P["count"] < 1:
                    continue
                gid, w = self.add_group(P)
                created.append(gid)
                warnings += w
        except Exception:
            for gid in created:
                self.remove_group(gid)
            raise
        if not created:
            raise ValueError("Every chosen scenario has 0 devices")
        self.log(f"Scenario '{name}': {len(created)} groups created", "info")
        return created, warnings

    def _make_points(self, dev, type_counts, P, nmul, smul):
        all_pts = []
        for t in POINT_TYPES:
            n = type_counts[t]
            for k in range(n):
                inst = k + 1
                if t in ANALOG:
                    tpl = ANALOG_TEMPLATES[t]
                    name, units, lo, hi = tpl[k % len(tpl)]
                    p = Point(dev, t, inst, name if k < len(tpl) else f"{name} {k // len(tpl) + 1}")
                    p.units, p.lo, p.hi = units, float(lo), float(hi)
                    p.value = round(random.uniform(lo, hi), 2)
                    p.cov_inc = float(P["cov_inc"])
                elif t in BINARY:
                    tpl = BINARY_TEMPLATES[t]
                    name, off, on = tpl[k % len(tpl)]
                    p = Point(dev, t, inst, name if k < len(tpl) else f"{name} {k // len(tpl) + 1}")
                    p.texts = [off, on]
                    p.value = random.randint(0, 1)
                else:
                    tpl = MULTI_TEMPLATES[t]
                    name, states = tpl[k % len(tpl)]
                    p = Point(dev, t, inst, name if k < len(tpl) else f"{name} {k // len(tpl) + 1}")
                    p.texts = list(states)
                    p.value = random.randint(1, len(states))
                p.name = f"{dev.name} {p.name}"
                p.desc = f"{OBJ_SHORT[t]} {inst} of {dev.name}"
                p.chg_min = float(P["chg_min"]) * nmul
                p.chg_max = float(P["chg_max"]) * nmul
                dev.points[p.key] = p
                dev.order.append(p.key)
                all_pts.append(p)
        for i in self._pick(all_pts, P["stale_pct"]):
            p = all_pts[i]
            p.stale = True
            if P["stale_frozen"]:
                p.frozen = True
            else:
                p.chg_min = float(P["stale_min"]) * smul
                p.chg_max = float(P["stale_max"]) * smul
        if dev.cov_mode != "none":
            for i in self._pick(all_pts, P["refuse_pct"]):
                all_pts[i].cov_ok = False

    def remove_group(self, gid):
        g = next((g for g in self.groups if g.gid == gid), None)
        if g is None:
            return
        for dev in list(g.devices):
            self._remove_device(dev)
        for net in g.networks:
            net.reset()
            net.ep.networks.pop(net.number, None)
            if net.ep.empty() and net.ep.port != self.main_port:
                net.ep.close()
                self.endpoints.pop(net.ep.port, None)
        self.groups.remove(g)
        self.version += 1
        self.log(f"Removed group '{g.name}'", "info")

    def _remove_device(self, dev):
        dev.removed = True
        dev.clear_subs()
        self.devices.pop(dev.instance, None)
        if dev.network is not None:
            dev.network.devices.pop(dev.mac, None)
        elif dev.ep is not None:
            dev.ep.device = None
            if dev.ep.empty() and dev.ep.port != self.main_port:
                dev.ep.close()
                self.endpoints.pop(dev.ep.port, None)
        if dev in dev.group.devices:
            dev.group.devices.remove(dev)

    def remove_device(self, inst):
        dev = self.devices.get(inst)
        if dev is None:
            return
        g = dev.group
        self._remove_device(dev)
        self.version += 1
        self.log(f"Removed device {inst}", "info")
        if not g.devices:
            self.remove_group(g.gid)

    def clear_all(self):
        for g in list(self.groups):
            self.remove_group(g.gid)
        self.next_gid = 1
        self.heap.clear()
        self.version += 1
