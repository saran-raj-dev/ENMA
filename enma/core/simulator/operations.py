"""Live operations requested by the user interface on devices, networks, groups and points."""

from __future__ import annotations

import time

from enma.bacnet.constants import ANALOG, BINARY, OBJ_SHORT


class OperationsMixin:
    """Live operations requested by the user interface on devices, networks, groups and points."""

    def device_settings(self, inst):
        dev = self.devices.get(inst)
        return dev.settings() if dev else None

    def apply_device(self, inst, s, whole_group=False):
        dev = self.devices.get(inst)
        if dev is None:
            return 0
        targets = list(dev.group.devices) if whole_group else [dev]
        for d in targets:
            s2 = dict(s)
            if whole_group:
                s2.pop("online", None)
            d.apply(s2)
        self.log(f"Applied settings to {len(targets)} device(s)" +
                 (f" in '{dev.group.name}'" if whole_group else f" ({inst})"), "info")
        return len(targets)

    def device_op(self, insts, op, arg=None):
        n = 0
        for inst in insts:
            d = self.devices.get(inst)
            if d is None:
                continue
            n += 1
            if op == "online":
                d.set_online(True)
                if d.down_reason in ("reboot", "flap"):
                    d.come_back()
            elif op == "offline":
                d.set_online(False)
            elif op == "reboot":
                if self.running:
                    d.reboot(float(arg or 5), "manual reboot")
            elif op == "iam":
                if self.running and d.online:
                    if d.network is not None:
                        d.network.submit(lambda dd=d: dd.send_iam(None))
                    else:
                        d.send_iam(None)
            elif op == "clear_subs":
                d.clear_subs("cleared by user")
        return n

    def group_devices(self, gid):
        g = next((g for g in self.groups if g.gid == gid), None)
        return [d.instance for d in g.devices] if g else []

    def network_of(self, port, num):
        ep = self.endpoints.get(port)
        return ep.networks.get(num) if ep else None

    def apply_network(self, port, num, s):
        net = self.network_of(port, num)
        if net is None:
            return
        was_unreachable = net.unreachable
        net.trunk_ms = float(s["trunk_ms"])
        net.buffer = int(s["buffer"])
        net.unreachable = bool(s["unreachable"])
        net.offline = bool(s["offline"])
        if net.trunk_ms <= 0 and net.q:
            pending = list(net.q)
            net.q.clear()
            for fn in pending:
                fn()
        if was_unreachable and not net.unreachable and self.running:
            net.ep.announce()
        self.log(f"Network {num}: trunk {net.trunk_ms:.0f} ms/message, buffer {net.buffer or 'unlimited'}, "
                 f"{'UNREACHABLE' if net.unreachable else 'reachable'}, {'trunk DOWN' if net.offline else 'trunk up'}",
                 "router")

    def network_op(self, port, num, op, arg=None):
        net = self.network_of(port, num)
        if net is None or not self.running:
            return
        if op == "busy":
            net.force_busy(float(arg or 30))
        elif op == "announce":
            net.ep.announce()
            self.log(f"Router :{port} announced I-Am-Router-To-Network {net.ep.reachable_nets()}", "router")
        elif op == "storm":
            for d in list(net.devices.values()):
                if d.online:
                    net.submit(lambda dd=d: dd.send_iam(None))
            self.log(f"Network {num}: every device broadcasting I-Am (storm)", "router")

    def point_op(self, inst, keys, op, arg=None):
        dev = self.devices.get(inst)
        if dev is None:
            return "Device not found"
        msgs = []
        for key in keys:
            p = dev.points.get(tuple(key))
            if p is None:
                continue
            if op == "set":
                try:
                    v = self._parse_value(p, arg)
                except ValueError as e:
                    return str(e)
                before = p.pv()
                p.value = v
                p.changes += 1
                p.last_change = time.time()
                if p.pv() != before:
                    dev.on_value_changed(p)
                elif p.active_priority():
                    msgs.append(f"{OBJ_SHORT[p.otype]}:{p.inst} is commanded at priority {p.active_priority()}; "
                                f"the new value is its relinquish default")
            elif op == "freeze":
                p.frozen = not p.frozen if arg is None else bool(arg)
                if p.frozen:
                    p.gen += 1
                    p.next_change = None
                else:
                    self.schedule(p)
            elif op == "interval":
                lo, hi, frozen = arg
                p.chg_min, p.chg_max = float(lo), float(hi)
                p.frozen = bool(frozen)
                p.gen += 1
                self.schedule(p)
            elif op == "fault":
                p.fault = not p.fault
                dev.on_value_changed(p, flags_changed=True)
            elif op == "oos":
                p.oos = not p.oos
                dev.on_value_changed(p, flags_changed=True)
            elif op == "cov":
                p.cov_ok = not p.cov_ok
                if not p.cov_ok:
                    for sub in list(p.subs):
                        dev.drop_sub((sub.addr.key(), sub.pid, p.otype, p.inst), "object no longer supports COV")
            elif op == "relinquish":
                if p.prio:
                    before = p.pv()
                    p.prio = [None] * 16
                    if p.pv() != before:
                        dev.on_value_changed(p)
            elif op == "delete":
                if not p.deleted:
                    p.deleted = True
                    for sub in list(p.subs):
                        dev.drop_sub((sub.addr.key(), sub.pid, p.otype, p.inst), "object deleted")
                    dev.db_rev += 1
                    self.log(f"Device {inst}: {OBJ_SHORT[p.otype]}:{p.inst} deleted (now unknown-object)", "device")
            elif op == "restore":
                if p.deleted:
                    p.deleted = False
                    dev.db_rev += 1
                    self.schedule(p)
                    self.log(f"Device {inst}: {OBJ_SHORT[p.otype]}:{p.inst} restored", "device")
        return "\n".join(msgs) or None

    def group_points_interval(self, gid, lo, hi, frozen, only_stale=None):
        g = next((g for g in self.groups if g.gid == gid), None)
        if g is None:
            return 0
        n = 0
        for d in g.devices:
            for p in d.points.values():
                if only_stale is not None and p.stale != only_stale:
                    continue
                p.chg_min, p.chg_max, p.frozen = float(lo), float(hi), bool(frozen)
                p.gen += 1
                self.schedule(p)
                n += 1
        self.log(f"'{g.name}': value change interval set on {n} points", "info")
        return n

    @staticmethod
    def _parse_value(p, text):
        text = str(text).strip()
        if p.otype in ANALOG:
            try:
                return round(float(text), 4)
            except ValueError:
                raise ValueError(f"'{text}' is not a number")
        if p.otype in BINARY:
            t = text.lower()
            texts = [x.lower() for x in (p.texts or ["inactive", "active"])]
            if t in ("1", "on", "true", "active", texts[1]):
                return 1
            if t in ("0", "off", "false", "inactive", texts[0]):
                return 0
            raise ValueError(f"Use 0/1 or {p.texts[0]}/{p.texts[1]}")
        texts = [x.lower() for x in (p.texts or [])]
        if text.lower() in texts:
            return texts.index(text.lower()) + 1
        try:
            v = int(text)
        except ValueError:
            raise ValueError(f"Use 1-{len(texts)} or a state name")
        if not 1 <= v <= len(texts):
            raise ValueError(f"State must be 1-{len(texts)}")
        return v

    def clear_all_subs(self):
        n = 0
        for d in self.devices.values():
            n += len(d.subs)
            d.clear_subs()
        self.log(f"Cleared {n} COV subscriptions on all devices", "cov")
        return n
