"""Receiving APDUs: confirmed / unconfirmed dispatch, replies, segmentation, delays and packet loss."""

from __future__ import annotations

import asyncio
import random
import time
import traceback

from enma.bacnet.codec import (
    BacErr,
    BacReject,
    Cur,
    DecodeError,
    Tag,
    WpmErr,
    app_enum,
    app_oid,
    app_str,
    ctx_close,
    ctx_enum,
    ctx_oid,
    ctx_open,
    ctx_uint,
    dec_app,
    dec_oid,
    dec_uint,
    decode_tags,
)
from enma.bacnet.constants import (
    A_APDU_TOO_LONG,
    A_SEG_NOT_SUPPORTED,
    CONF_SERVICE_NAMES,
    DEVICE,
    MAX_SEGS,
    PDU_ABORT,
    PDU_CACK,
    PDU_CONF,
    PDU_ERROR,
    PDU_REJECT,
    PDU_SACK,
    PDU_SEGACK,
    PDU_UNCONF,
    R_INVALID_TAG,
    R_UNRECOGNIZED,
    SC_DCC,
    SC_READ_PROP,
    SC_READ_PROP_MULTI,
    SC_REINIT,
    SC_SUBSCRIBE_COV,
    SC_WRITE_PROP,
    SC_WRITE_PROP_MULTI,
    SU_I_HAVE,
    SU_TIME_SYNC,
    SU_UTC_TIME_SYNC,
    SU_WHO_HAS,
    SU_WHO_IS,
    max_apdu_from_code,
)
from enma.bacnet.framing import (
    apdu_abort,
    apdu_complex_ack,
    apdu_error,
    apdu_reject,
    apdu_simple_ack,
    apdu_unconfirmed,
)


class DispatchMixin:
    """Receiving APDUs: confirmed / unconfirmed dispatch, replies, segmentation, delays and packet loss."""

    def receive(self, apdu, src, bcast):
        if not apdu or self.removed:
            return
        t = apdu[0] >> 4
        if t in (PDU_SACK, PDU_CACK, PDU_ERROR, PDU_REJECT, PDU_ABORT, PDU_SEGACK):
            if self.is_up():
                self._on_reply(t, apdu, src)
            return
        if not self.is_up():
            self.st["ignored"] += 1
            return
        if t == PDU_CONF and bcast:
            return                                    # confirmed requests are never broadcast
        if self.drop_pct and random.random() * 100.0 < self.drop_pct:
            self.st["dropped"] += 1
            self.sim.trace(f"{src} → dev {self.instance}: request dropped (packet loss)")
            return
        delay = 0.0
        if self.delay_max > 0:
            delay = random.uniform(self.delay_min, self.delay_max) / 1000.0
        if t == PDU_UNCONF and len(apdu) > 1 and apdu[1] == SU_WHO_IS and self.iam_delay_max > 0:
            delay += random.uniform(self.iam_delay_min, self.iam_delay_max)
        if delay > 0:
            self.sim.loop.call_later(delay, self._process, t, apdu, src, bcast)
        else:
            self._process(t, apdu, src, bcast)

    def _process(self, t, apdu, src, bcast):
        if not self.is_up():
            return
        try:
            if t == PDU_CONF:
                self._confirmed(apdu, src)
            elif t == PDU_UNCONF:
                self._unconfirmed(apdu, src)
        except Exception:
            self.sim.log(f"Device {self.instance}: internal error\n{traceback.format_exc()}", "error")

    def _reply(self, src, apdu):
        self._out(apdu, src)

    def _confirmed(self, apdu, src):
        if len(apdu) < 4:
            return
        b0, b1, invoke = apdu[0], apdu[1], apdu[2]
        if b0 & 0x08:
            self._reply(src, apdu_abort(invoke, A_SEG_NOT_SUPPORTED))
            return
        service = apdu[3]
        body = apdu[4:]
        client_max = max_apdu_from_code(b1 & 0x0F)
        client_segs = MAX_SEGS[(b1 >> 4) & 0x07]
        seg_ok = bool(b0 & 0x02)
        self.st["rx"] += 1
        self.last_rx = time.time()
        sname = CONF_SERVICE_NAMES.get(service, f"service {service}")
        if self.dcc == 1 and service not in (SC_DCC, SC_REINIT):
            self.st["ignored"] += 1
            return
        handler = {
            SC_READ_PROP: self.svc_read,
            SC_READ_PROP_MULTI: self.svc_rpm,
            SC_WRITE_PROP: self.svc_write,
            SC_WRITE_PROP_MULTI: self.svc_wpm,
            SC_SUBSCRIBE_COV: self.svc_subscribe if self.cov_mode != "none" else None,
            SC_DCC: self.svc_dcc,
            SC_REINIT: self.svc_reinit,
        }.get(service)
        if handler is None:
            self.st["errors"] += 1
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → Reject unrecognized-service")
            self._reply(src, apdu_reject(invoke, R_UNRECOGNIZED))
            return
        try:
            result = handler(decode_tags(body), src)
        except WpmErr as e:
            self.st["errors"] += 1
            payload = (ctx_open(0) + app_enum(e.cls) + app_enum(e.code) + ctx_close(0) + ctx_open(1) +
                       ctx_oid(0, *e.oid) + ctx_enum(1, e.pid) +
                       (ctx_uint(2, e.idx) if e.idx is not None else b"") + ctx_close(1))
            self._reply(src, bytes([0x50, invoke, service]) + payload)
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → Error {e}")
            return
        except BacErr as e:
            self.st["errors"] += 1
            self._reply(src, apdu_error(invoke, service, e.cls, e.code))
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → Error {e}")
            return
        except BacReject as r:
            self.st["errors"] += 1
            self._reply(src, apdu_reject(invoke, r.reason))
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → Reject {r}")
            return
        except DecodeError:
            self.st["errors"] += 1
            self._reply(src, apdu_reject(invoke, R_INVALID_TAG))
            return
        if result is None:
            self._reply(src, apdu_simple_ack(invoke, service))
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → SimpleACK")
            return
        full = apdu_complex_ack(invoke, service, result)
        limit = min(self.max_apdu, client_max)
        if len(full) <= limit:
            self._reply(src, full)
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → ComplexACK ({len(full)} bytes)")
        elif self.segmentation and seg_ok:
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → segmented ComplexACK ({len(full)} bytes)")
            self.sim.loop.create_task(self._send_segmented(src, invoke, service, result, limit, client_segs))
        else:
            self.st["errors"] += 1
            self._reply(src, apdu_abort(invoke, A_SEG_NOT_SUPPORTED))
            self.sim.trace(f"{src} → dev {self.instance}: {sname} → Abort segmentation-not-supported "
                           f"(answer {len(full)} bytes > max APDU {limit})")

    async def _send_segmented(self, src, invoke, service, payload, limit, client_segs):
        seg_size = limit - 5
        segs = [payload[i:i + seg_size] for i in range(0, len(payload), seg_size)]
        total = len(segs)
        if client_segs and total > client_segs:
            self._reply(src, apdu_abort(invoke, A_APDU_TOO_LONG))
            return
        key = (src.key(), invoke)

        def seg_apdu(n):
            more = 0x04 if n < total - 1 else 0
            return bytes([0x38 | more, invoke, n & 0xFF, 16, service]) + segs[n]

        window, base, retries = 1, 0, 0
        while base < total:
            end = min(total, base + window)
            for n in range(base, end):
                self._reply(src, seg_apdu(n))
            fut = self.sim.loop.create_future()
            self.seg_waits[key] = fut
            try:
                res = await asyncio.wait_for(fut, 3.0)
            except asyncio.TimeoutError:
                retries += 1
                if retries > 3:
                    self.sim.log(f"Device {self.instance}: segmented reply to {src} timed out", "warn")
                    return
                continue
            finally:
                self.seg_waits.pop(key, None)
            if res is None:
                return                                 # client aborted
            retries = 0
            _nak, seq, win = res
            acked = base - 1 + ((seq - (base - 1)) & 0xFF)
            if acked > end - 1 or acked < base - 1:
                acked = base - 1
            base = acked + 1
            window = max(1, min(win or 1, 127))

    def _on_reply(self, t, apdu, src):
        if len(apdu) < 2:
            return
        invoke = apdu[1]
        if t == PDU_SEGACK:
            if len(apdu) >= 4:
                fut = self.seg_waits.get((src.key(), invoke))
                if fut is not None and not fut.done():
                    fut.set_result((bool(apdu[0] & 0x02), apdu[2], apdu[3]))
            return
        if t == PDU_ABORT:
            fut = self.seg_waits.get((src.key(), invoke))
            if fut is not None and not fut.done():
                fut.set_result(None)
        p = self.pending.pop(invoke, None)
        if p is None:
            return
        if p[3] is not None:
            p[3].cancel()
        sub = p[0]
        if t == PDU_SACK:
            sub.fails = 0
        else:
            sub.fails += 1
            self.st["notify_fail"] += 1
            self.sim.log(f"Device {self.instance}: subscriber {sub.addr} answered ConfirmedCOVNotification "
                         f"with {['', '', '', '', '', 'Error', 'Reject', 'Abort'][t]}", "cov")

    def _unconfirmed(self, apdu, src):
        if len(apdu) < 2:
            return
        service = apdu[1]
        try:
            tags = decode_tags(apdu[2:])
        except DecodeError:
            return
        if service == SU_WHO_IS:
            c = Cur(tags)
            lo, hi = c.opt_ctx(0), c.opt_ctx(1)
            if (lo is None) != (hi is None):
                return
            if lo is not None and not (dec_uint(lo.data) <= self.instance <= dec_uint(hi.data)):
                return
            if self.dcc == 1:
                return
            self.sim.trace(f"{src} → dev {self.instance}: Who-Is → I-Am")
            self.send_iam(src)
        elif service == SU_WHO_HAS:
            c = Cur(tags)
            lo, hi = c.opt_ctx(0), c.opt_ctx(1)
            if lo is not None and hi is not None and not (dec_uint(lo.data) <= self.instance <= dec_uint(hi.data)):
                return
            oid_t, name_t = c.opt_ctx(2), c.opt_ctx(3)
            target = None
            if oid_t is not None:
                k = dec_oid(oid_t.data)
                target = self if k == (DEVICE, self.instance) else self.points.get(k)
            elif name_t is not None:
                name = dec_app(Tag("app", 7, name_t.data, len(name_t.data)))[1]
                if name == self.name:
                    target = self
                else:
                    target = next((p for p in self.points.values() if p.name == name), None)
            if target is None or getattr(target, "deleted", False) or self.dcc:
                return
            if target is self:
                oid, oname = (DEVICE, self.instance), self.name
            else:
                oid, oname = target.key, target.name
            payload = app_oid(DEVICE, self.instance) + app_oid(*oid) + app_str(oname)
            self._answer(apdu_unconfirmed(SU_I_HAVE, payload), src)
        elif service in (SU_TIME_SYNC, SU_UTC_TIME_SYNC):
            self.sim.trace(f"{src} → dev {self.instance}: TimeSynchronization")
