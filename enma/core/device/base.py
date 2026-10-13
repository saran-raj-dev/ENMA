"""The Device: identity, behaviour settings, life cycle (online, reboot, flapping), sending and persistence."""

from __future__ import annotations

import random
import time

from enma.bacnet.codec import app_enum, app_oid, app_uint
from enma.bacnet.constants import DEVICE, SU_I_AM
from enma.bacnet.framing import apdu_unconfirmed
from enma.core.device.dispatch import DispatchMixin
from enma.core.device.properties import PropertiesMixin
from enma.core.device.services import ServicesMixin
from enma.core.device.cov import CovMixin


class Device(DispatchMixin, PropertiesMixin, ServicesMixin, CovMixin):
    """One simulated BACnet device.

    The behaviour is split into mixins: DispatchMixin (receiving and answering APDUs), PropertiesMixin
    (object model), ServicesMixin (confirmed services) and CovMixin (subscriptions and notifications).
    """

    SETTINGS = ("cov_mode", "max_subs", "delay_min", "delay_max", "drop_pct", "iam_delay_min",
                "iam_delay_max", "flap", "flap_every_min", "flap_every_max", "flap_off_min",
                "flap_off_max", "flap_clear", "max_apdu", "segmentation")

    def __init__(self, sim, group, instance, name):
        self.sim = sim
        self.group = group
        self.instance = instance
        self.name = name
        self.ep = None
        self.network = None
        self.mac = b""
        self.points = {}
        self.order = []
        self.vendor_id = 999
        self.vendor_name = "ENMA (Engine for Network Modeling & Automation)"
        self.model = "ENMA Simulated Controller"
        self.firmware = "1.0.0"
        self.location = ""
        self.description = ""
        self.max_apdu = 1476
        self.segmentation = True
        self.online = True
        self.back_at = None
        self.down_reason = ""
        self.cov_mode = "full"
        self.max_subs = 0
        self.delay_min = self.delay_max = 0
        self.drop_pct = 0.0
        self.iam_delay_min = self.iam_delay_max = 0.0
        self.flap = False
        self.flap_every_min, self.flap_every_max = 300.0, 900.0
        self.flap_off_min, self.flap_off_max = 30.0, 120.0
        self.flap_clear = True
        self.next_flap = None
        self.dcc = 0
        self.dcc_until = None
        self.subs = {}
        self.pending = {}
        self.seg_waits = {}
        self.db_rev = 1
        self._invoke = random.randint(0, 255)
        self.st = dict(rx=0, tx=0, reads=0, writes=0, subscribes=0, renewals=0, cancels=0, refused=0,
                       notifies=0, notify_fail=0, errors=0, dropped=0, ignored=0, iams=0)
        self.last_rx = None
        self.removed = False

    @property
    def net_num(self):
        return self.network.number if self.network else None

    def address(self):
        ip = self.sim.my_ip
        port = self.ep.port if self.ep else "?"
        if self.network:
            return f"{self.network.number}:{int.from_bytes(self.mac, 'big')}@{ip}:{port}"
        return f"{ip}:{port}"

    def is_up(self):
        return self.online and self.sim.running and not self.removed

    def state_text(self):
        if not self.online:
            if self.down_reason == "reboot":
                return "Rebooting"
            if self.down_reason == "flap":
                return "Down (flap)"
            return "OFFLINE"
        if self.network and self.network.offline:
            return "Net down"
        if self.dcc:
            return "DCC off"
        if self.flap:
            return "Flapping"
        if self.delay_max > 0 or self.iam_delay_max > 0:
            return "Slow"
        return "Online"

    def cov_text(self):
        if self.cov_mode == "none":
            return "No COV"
        if self.cov_mode == "mute":
            return "Mute COV"
        return f"COV {len(self.subs)}/{self.max_subs}" if self.max_subs else "COV"

    def live_points(self):
        return [self.points[k] for k in self.order if not self.points[k].deleted]

    def settings(self):
        d = {k: getattr(self, k) for k in self.SETTINGS}
        d["online"] = self.online
        return d

    def apply(self, s):
        old_mode = self.cov_mode
        for k in self.SETTINGS:
            if k in s:
                setattr(self, k, s[k])
        if self.cov_mode != old_mode:
            self.db_rev += 1
            if self.cov_mode == "none":
                self.clear_subs("COV support turned off")
        if self.flap and self.next_flap is None:
            self.next_flap = time.monotonic() + random.uniform(self.flap_every_min, self.flap_every_max)
        if not self.flap:
            self.next_flap = None
            if self.down_reason == "flap":
                self.come_back()
        if "online" in s:
            self.set_online(s["online"])

    def set_online(self, on):
        if on and not self.online:
            self.online = True
            self.back_at = None
            self.down_reason = ""
            self.sim.log(f"Device {self.instance} back online", "device")
        elif not on and self.online:
            self.online = False
            self.back_at = None
            self.down_reason = "manual"
            self.sim.log(f"Device {self.instance} taken offline (silent: no replies)", "device")

    def reboot(self, down_s=5.0, why="reboot"):
        self.clear_subs(why)
        self.online = False
        self.down_reason = "reboot"
        self.back_at = time.monotonic() + down_s
        self.dcc = 0
        self.dcc_until = None
        self.sim.log(f"Device {self.instance} rebooting ({why}); back in {down_s:.0f}s, COV subscriptions lost",
                     "device")

    def flap_down(self, now):
        off = random.uniform(self.flap_off_min, self.flap_off_max)
        self.online = False
        self.down_reason = "flap"
        self.back_at = now + off
        if self.flap_clear:
            self.clear_subs("flap reboot")
        self.sim.log(f"Device {self.instance} dropped off the network (flapping) for {off:.0f}s", "device")

    def come_back(self):
        was = self.down_reason
        self.online = True
        self.back_at = None
        self.down_reason = ""
        if self.flap:
            self.next_flap = time.monotonic() + random.uniform(self.flap_every_min, self.flap_every_max)
        if was == "reboot" or (was == "flap" and self.flap_clear):
            self.send_iam(None)                       # devices announce themselves after a restart
        self.sim.log(f"Device {self.instance} is back "
                     f"({'restarted' if was == 'reboot' or (was == 'flap' and self.flap_clear) else 'answering again'})",
                     "device")

    def _out(self, apdu, dest, expect_reply=False, via_trunk=False):
        def go():
            if self.ep is not None and not self.removed:
                self.ep.send_apdu_from(self, apdu, dest, expect_reply)
                self.st["tx"] += 1
        if via_trunk and self.network is not None:
            self.network.submit(go, requester=None)
        else:
            go()

    def next_invoke(self):
        self._invoke = (self._invoke + 1) & 0xFF
        return self._invoke

    def send_iam(self, requester):
        if self.dcc == 1:
            return
        payload = (app_oid(DEVICE, self.instance) + app_uint(self.max_apdu) +
                   app_enum(1 if self.segmentation else 3) + app_uint(self.vendor_id))
        self.st["iams"] += 1
        self._answer(apdu_unconfirmed(SU_I_AM, payload), requester)

    def _answer(self, apdu, requester):
        """Answer to a broadcast query (I-Am, I-Have): unicast and/or broadcast per the site setting."""
        mode = self.sim.iam_mode
        if requester is None:
            self._out(apdu, None)
            return
        if mode in ("unicast", "both"):
            self._out(apdu, requester)
        if mode in ("broadcast", "both"):
            self._out(apdu, None)

    def to_json(self):
        d = {k: getattr(self, k) for k in self.SETTINGS}
        d.update(instance=self.instance, name=self.name, online=self.online if self.down_reason in ("", "manual") else True,
                 vendor_id=self.vendor_id, model=self.model, location=self.location,
                 description=self.description, mac=int.from_bytes(self.mac, "big") if self.mac else None,
                 net=self.net_num, port=self.ep.port if self.ep else None,
                 points=[self.points[k].to_json() for k in self.order])
        return d
