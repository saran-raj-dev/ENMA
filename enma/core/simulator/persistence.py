"""Saving and loading a site as JSON."""

from __future__ import annotations

import time
from datetime import datetime

from enma.config import APP_NAME
from enma.core.device import Device
from enma.core.group import Group
from enma.core.model import Point
from enma.core.network import Network


class PersistenceMixin:
    """Saving and loading a site as JSON."""

    def to_json(self):
        return dict(app=APP_NAME, version=1, saved=datetime.now().isoformat(timespec="seconds"),
                    settings=dict(main_port=self.main_port, iam_mode=self.iam_mode, relay=self.relay),
                    groups=[dict(gid=g.gid, name=g.name, kind=g.kind, params=g.params,
                                 networks=[n.to_json() for n in g.networks],
                                 devices=[d.to_json() for d in g.devices]) for g in self.groups])

    def load_json(self, data):
        if self.running:
            raise ValueError("Stop the simulation before opening a site")
        self.clear_all()
        st = data.get("settings", {})
        self.main_port = int(st.get("main_port", self.main_port))
        self.iam_mode = st.get("iam_mode", self.iam_mode)
        self.relay = bool(st.get("relay", self.relay))
        now = time.monotonic()
        for gd in data.get("groups", []):
            g = Group(self.next_gid, gd["name"], gd["kind"], gd.get("params", {}))
            self.next_gid += 1
            nets = {}
            for nd in gd.get("networks", []):
                ep = self._ensure_endpoint(int(nd["port"]))
                net = Network(self, ep, int(nd["number"]), g)
                net.trunk_ms = float(nd.get("trunk_ms", 0))
                net.buffer = int(nd.get("buffer", 0))
                net.unreachable = bool(nd.get("unreachable", False))
                net.offline = bool(nd.get("offline", False))
                ep.networks[net.number] = net
                g.networks.append(net)
                nets[(ep.port, net.number)] = net
            for dd in gd.get("devices", []):
                inst = int(dd["instance"])
                if inst in self.devices:
                    continue
                dev = Device(self, g, inst, dd["name"])
                for k in Device.SETTINGS:
                    if k in dd:
                        setattr(dev, k, dd[k])
                dev.online = bool(dd.get("online", True))
                if not dev.online:
                    dev.down_reason = "manual"
                dev.vendor_id = int(dd.get("vendor_id", 999))
                dev.model = dd.get("model", dev.model)
                dev.location = dd.get("location", "")
                dev.description = dd.get("description", "")
                if dd.get("net") is not None:
                    net = nets.get((int(dd["port"]), int(dd["net"])))
                    if net is None:
                        continue
                    dev.network = net
                    dev.mac = bytes([int(dd["mac"])])
                    dev.ep = net.ep
                    net.devices[dev.mac] = dev
                else:
                    ep = self._ensure_endpoint(int(dd["port"]))
                    if ep.device is not None:
                        continue
                    ep.device = dev
                    dev.ep = ep
                for a in dd.get("points", []):
                    p = Point.from_json(dev, a)
                    dev.points[p.key] = p
                    dev.order.append(p.key)
                    self.schedule(p, now)
                self.devices[inst] = dev
                g.devices.append(dev)
            self.groups.append(g)
        self.version += 1
        self.log(f"Opened site: {len(self.groups)} groups, {len(self.devices)} devices", "info")
