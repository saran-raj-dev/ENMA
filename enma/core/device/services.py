"""Confirmed service handlers: ReadProperty(Multiple), WriteProperty(Multiple), SubscribeCOV, DCC, ReinitializeDevice."""

from __future__ import annotations

import time

from enma.bacnet.codec import (
    BacErr,
    BacReject,
    Cur,
    WpmErr,
    app_enum,
    ctx_close,
    ctx_enum,
    ctx_oid,
    ctx_open,
    ctx_uint,
    dec_oid,
    dec_uint,
)
from enma.bacnet.constants import (
    EC_OBJECT,
    EC_RESOURCES,
    EC_SERVICES,
    E_INCONSISTENT_PARAMS,
    E_NO_SPACE_LIST,
    E_OPTIONAL_NOT_SUPPORTED,
    OBJ_SHORT,
    P_ALL,
    P_OPTIONAL,
    P_REQUIRED,
    R_MISSING,
    R_RANGE,
)
from enma.core.model import Sub


class ServicesMixin:
    """Confirmed service handlers: ReadProperty(Multiple), WriteProperty(Multiple), SubscribeCOV, DCC, ReinitializeDevice."""

    def svc_read(self, tags, src):
        c = Cur(tags)
        oid = dec_oid(c.need_ctx(0).data)
        pid = dec_uint(c.need_ctx(1).data)
        it = c.opt_ctx(2)
        idx = dec_uint(it.data) if it else None
        c.end()
        obj = self.resolve(oid)
        if pid in (P_ALL, P_REQUIRED, P_OPTIONAL):
            raise BacErr(EC_SERVICES, E_INCONSISTENT_PARAMS)
        val = self.read_value(obj, pid, idx)
        self.st["reads"] += 1
        return (ctx_oid(0, *self.obj_id(obj)) + ctx_enum(1, pid) +
                (ctx_uint(2, idx) if idx is not None else b"") + ctx_open(3) + val + ctx_close(3))

    def svc_rpm(self, tags, src):
        c = Cur(tags)
        out = bytearray()
        specs = 0
        while not c.at_end():
            oid = dec_oid(c.need_ctx(0).data)
            c.need_open(1)
            props = []
            while not c.is_close(1):
                pid = dec_uint(c.need_ctx(0).data)
                it = c.opt_ctx(1)
                props.append((pid, dec_uint(it.data) if it else None))
            c.need_close(1)
            if not props:
                raise BacReject(R_MISSING)
            specs += 1
            try:
                obj = self.resolve(oid)
                err = None
            except BacErr as e:
                obj, err = None, e
            out += ctx_oid(0, *(self.obj_id(obj) if obj is not None else oid))
            out += ctx_open(1)
            for pid, idx in props:
                if obj is None:
                    out += ctx_enum(2, pid) + (ctx_uint(3, idx) if idx is not None else b"")
                    out += ctx_open(5) + app_enum(err.cls) + app_enum(err.code) + ctx_close(5)
                    continue
                expanded = self.expand(obj, pid) if pid in (P_ALL, P_REQUIRED, P_OPTIONAL) else [pid]
                for p in expanded:
                    use_idx = idx if p == pid else None
                    out += ctx_enum(2, p) + (ctx_uint(3, use_idx) if use_idx is not None else b"")
                    try:
                        v = self.read_value(obj, p, use_idx)
                        out += ctx_open(4) + v + ctx_close(4)
                    except BacErr as e:
                        out += ctx_open(5) + app_enum(e.cls) + app_enum(e.code) + ctx_close(5)
            out += ctx_close(1)
        if not specs:
            raise BacReject(R_MISSING)
        self.st["reads"] += 1
        return bytes(out)

    def svc_write(self, tags, src):
        c = Cur(tags)
        oid = dec_oid(c.need_ctx(0).data)
        pid = dec_uint(c.need_ctx(1).data)
        it = c.opt_ctx(2)
        idx = dec_uint(it.data) if it else None
        c.need_open(3)
        vals = c.collect(3)
        pt = c.opt_ctx(4)
        c.end()
        prio = dec_uint(pt.data) if pt else 16
        if not 1 <= prio <= 16:
            raise BacReject(R_RANGE)
        obj = self.resolve(oid)
        self.write_value(obj, pid, idx, vals, prio)
        self.st["writes"] += 1
        return None

    def svc_wpm(self, tags, src):
        c = Cur(tags)
        writes = []
        while not c.at_end():
            oid = dec_oid(c.need_ctx(0).data)
            c.need_open(1)
            while not c.is_close(1):
                pid = dec_uint(c.need_ctx(0).data)
                it = c.opt_ctx(1)
                c.need_open(2)
                vals = c.collect(2)
                pt = c.opt_ctx(3)
                prio = dec_uint(pt.data) if pt else 16
                if not 1 <= prio <= 16:
                    raise BacReject(R_RANGE)
                writes.append((oid, pid, dec_uint(it.data) if it else None, vals, prio))
            c.need_close(1)
        if not writes:
            raise BacReject(R_MISSING)
        for oid, pid, idx, vals, prio in writes:
            try:
                self.write_value(self.resolve(oid), pid, idx, vals, prio)
            except BacErr as e:
                raise WpmErr(e.cls, e.code, oid, pid, idx)
        self.st["writes"] += 1
        return None

    def svc_subscribe(self, tags, src):
        c = Cur(tags)
        pid = dec_uint(c.need_ctx(0).data)
        oid = dec_oid(c.need_ctx(1).data)
        conf_t = c.opt_ctx(2)
        life_t = c.opt_ctx(3)
        c.end()
        obj = self.resolve(oid)
        if obj is self:
            raise BacErr(EC_OBJECT, E_OPTIONAL_NOT_SUPPORTED)
        p = obj
        key = (src.key(), pid, p.otype, p.inst)
        if conf_t is None and life_t is None:            # cancellation
            if key in self.subs:
                self.drop_sub(key)
                self.st["cancels"] += 1
                self.sim.log(f"Device {self.instance}: COV subscription cancelled on {OBJ_SHORT[p.otype]}:"
                             f"{p.inst} by {src}", "cov")
            return None
        if conf_t is None:
            raise BacReject(R_MISSING)
        if not p.cov_ok:
            self.st["refused"] += 1
            raise BacErr(EC_OBJECT, E_OPTIONAL_NOT_SUPPORTED)
        confirmed = bool(conf_t.data and conf_t.data[0])
        lifetime = dec_uint(life_t.data) if life_t is not None else 0
        sub = self.subs.get(key)
        if sub is None:
            if self.max_subs and len(self.subs) >= self.max_subs:
                self.st["refused"] += 1
                self.sim.log(f"Device {self.instance}: COV subscription refused on {OBJ_SHORT[p.otype]}:{p.inst} "
                             f"(all {self.max_subs} slots used)", "cov")
                raise BacErr(EC_RESOURCES, E_NO_SPACE_LIST)
            sub = Sub(src, pid, p, confirmed, lifetime)
            self.subs[key] = sub
            p.subs.append(sub)
            self.st["subscribes"] += 1
            self.sim.log(f"Device {self.instance}: COV subscribed {OBJ_SHORT[p.otype]}:{p.inst} by {src} "
                         f"(pid {pid}, {'confirmed' if confirmed else 'unconfirmed'}, "
                         f"lifetime {'INDEFINITE' if not lifetime else str(lifetime) + 's'})", "cov")
        else:
            sub.confirmed = confirmed
            sub.lifetime = lifetime
            sub.expires = time.monotonic() + lifetime if lifetime else None
            sub.renewals += 1
            self.st["renewals"] += 1
        if self.cov_mode == "full":
            self.sim.loop.call_soon(self.notify, sub)    # initial notification after the ack
        return None

    def svc_dcc(self, tags, src):
        c = Cur(tags)
        dur_t = c.opt_ctx(0)
        state = dec_uint(c.need_ctx(1).data)
        c.opt_ctx(2)
        c.end()
        if state > 2:
            raise BacReject(R_RANGE)
        self.dcc = state
        mins = dec_uint(dur_t.data) if dur_t else 0
        self.dcc_until = time.monotonic() + mins * 60 if (state and mins) else None
        self.sim.log(f"Device {self.instance}: DeviceCommunicationControl → "
                     f"{['enable', 'disable', 'disable-initiation'][state]}"
                     f"{f' for {mins} min' if mins and state else ''} (from {src})", "device")
        return None

    def svc_reinit(self, tags, src):
        c = Cur(tags)
        state = dec_uint(c.need_ctx(0).data)
        c.opt_ctx(1)
        c.end()
        if state not in (0, 1):
            raise BacErr(EC_SERVICES, E_OPTIONAL_NOT_SUPPORTED)
        self.sim.loop.call_later(0.2, self.reboot, 5.0, f"ReinitializeDevice {'coldstart' if state == 0 else 'warmstart'} from {src}")
        return None
