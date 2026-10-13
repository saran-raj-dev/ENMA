"""Simulated router networks (MS/TP trunks) and UDP endpoints."""

from __future__ import annotations

import asyncio
import socket
import struct
import time
import traceback
from collections import deque

from enma.bacnet.constants import (
    BVLC_BROADCAST,
    BVLC_FORWARDED,
    BVLC_UNICAST,
    NL_I_AM_ROUTER,
    NL_ROUTER_AVAILABLE,
    NL_ROUTER_BUSY,
)
from enma.bacnet.framing import build_npdu, bvll


class Network:
    """A remote network (MS/TP-style trunk) behind the simulated router on an endpoint."""

    def __init__(self, sim, ep, number, group):
        self.sim = sim
        self.ep = ep
        self.number = number
        self.group = group
        self.devices = {}
        self.trunk_ms = 0.0
        self.buffer = 0
        self.unreachable = False
        self.offline = False
        self.q = deque()
        self.worker = None
        self.busy = False
        self.forced_until = 0.0
        self.busy_events = 0
        self.dropped = 0
        self.routed = 0
        self.notified = {}
        self._last_busy_bcast = 0.0
        self.peak_q = 0

    def label(self):
        return f"Network {self.number}"

    def state_text(self):
        if self.unreachable:
            return "Unreachable"
        if self.offline:
            return "Trunk down"
        if self.busy or time.monotonic() < self.forced_until:
            return "ROUTER BUSY"
        if self.trunk_ms > 0:
            return f"Queue {len(self.q)}"
        return "OK"

    def submit(self, fn, requester=None):
        now = time.monotonic()
        if now < self.forced_until:
            self.dropped += 1
            self._busy_reply(requester, now)
            return False
        if self.trunk_ms <= 0:
            self.routed += 1
            fn()
            return True
        if self.buffer > 0 and len(self.q) >= self.buffer:
            self.dropped += 1
            if not self.busy:
                self.busy = True
                self.busy_events += 1
                self.sim.log(f"Router :{self.ep.port} → network {self.number}: buffer full "
                             f"({self.buffer} messages queued) → Router-Busy-To-Network", "router")
            self._busy_reply(requester, now)
            return False
        self.q.append(fn)
        self.routed += 1
        if len(self.q) > self.peak_q:
            self.peak_q = len(self.q)
        if self.worker is None:
            self.worker = self.sim.loop.create_task(self._work())
        return True

    def _busy_reply(self, requester, now):
        body = struct.pack(">H", self.number)
        if now - self._last_busy_bcast > 1.0:
            self._last_busy_bcast = now
            self.ep.send_netmsg(NL_ROUTER_BUSY, body, None)
        if requester is not None:
            k = requester.key()
            if now - self.notified.get(k, 0) > 1.0:
                self.notified[k] = now
                self.ep.send_netmsg(NL_ROUTER_BUSY, body, requester)
                self.sim.trace(f"Router :{self.ep.port} → {requester}: Router-Busy-To-Network {self.number}")
            self.notified.setdefault(("addr", k), requester)

    def _available(self):
        body = struct.pack(">H", self.number)
        self.ep.send_netmsg(NL_ROUTER_AVAILABLE, body, None)
        for k, v in list(self.notified.items()):
            if isinstance(k, tuple) and k and k[0] == "addr":
                self.ep.send_netmsg(NL_ROUTER_AVAILABLE, body, v)
        self.notified.clear()
        self.sim.log(f"Router :{self.ep.port} → network {self.number}: Router-Available-To-Network", "router")

    async def _work(self):
        try:
            while self.q:
                await asyncio.sleep(self.trunk_ms / 1000.0)
                if not self.q:
                    break
                fn = self.q.popleft()
                try:
                    fn()
                except Exception:
                    self.sim.log(traceback.format_exc(), "error")
                if self.busy and len(self.q) <= self.buffer // 2:
                    self.busy = False
                    self._available()
        finally:
            self.worker = None
            if self.busy:
                self.busy = False
                self._available()

    def force_busy(self, seconds):
        self.forced_until = time.monotonic() + seconds
        self.busy_events += 1
        self._last_busy_bcast = 0
        self._busy_reply(None, time.monotonic())
        self.sim.log(f"Router :{self.ep.port}: forced Router-Busy for network {self.number} ({seconds:.0f}s)",
                     "router")
        self.sim.loop.call_later(seconds, self._forced_end)

    def _forced_end(self):
        if time.monotonic() >= self.forced_until - 0.05:
            self._available()

    def reset(self):
        self.q.clear()
        self.busy = False
        self.notified.clear()
        if self.worker is not None:
            self.worker.cancel()
            self.worker = None

    def to_json(self):
        return dict(port=self.ep.port, number=self.number, trunk_ms=self.trunk_ms, buffer=self.buffer,
                    unreachable=self.unreachable, offline=self.offline)


class Endpoint(asyncio.DatagramProtocol):
    """One UDP port: a BACnet/IP node that may host one device and/or route to networks."""

    def __init__(self, sim, port):
        self.sim = sim
        self.port = port
        self.device = None
        self.networks = {}
        self.transport = None
        self.error = None

    # asyncio protocol
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            self.sim.on_datagram(self, data, addr)
        except Exception:
            self.sim.log(f"Port {self.port}: error handling packet from {addr}\n{traceback.format_exc()}", "error")

    def error_received(self, exc):
        pass

    def connection_lost(self, exc):
        self.transport = None

    @property
    def is_open(self):
        return self.transport is not None

    async def open(self):
        if self.transport is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for opt in (socket.SO_RCVBUF, socket.SO_SNDBUF):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, opt, 1 << 20)
                except OSError:
                    pass
            sock.bind(("", self.port))
            sock.setblocking(False)
        except OSError:
            sock.close()
            raise
        await self.sim.loop.create_datagram_endpoint(lambda: self, sock=sock)
        self.error = None

    def close(self):
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        for n in self.networks.values():
            n.reset()

    def empty(self):
        return self.device is None and not self.networks

    # sending
    def sendto(self, data, addr):
        if self.transport is None:
            return
        try:
            self.transport.sendto(data, addr)
            self.sim.tx += 1
        except OSError as e:
            self.sim.log(f"Port {self.port}: send to {addr} failed: {e}", "warn")

    def send_npdu(self, npdu, dest):
        if dest is None:
            self.sendto(bvll(BVLC_BROADCAST, npdu), (self.sim.bcast, self.sim.main_port))
            if self.sim.fds:
                fwd = bvll(BVLC_FORWARDED, socket.inet_aton(self.sim.my_ip) + struct.pack(">H", self.port) + npdu)
                for fd in list(self.sim.fds):
                    self.sendto(fwd, fd)
        else:
            self.sendto(bvll(BVLC_UNICAST, npdu), (dest.ip, dest.port))

    def send_apdu_from(self, dev, apdu, dest, expect_reply=False):
        snet = dev.net_num
        sadr = dev.mac if snet is not None else b""
        if dest is None:
            npdu = build_npdu(apdu, dnet=0xFFFF if snet is not None else None, snet=snet, sadr=sadr)
        else:
            npdu = build_npdu(apdu, dnet=dest.net, dadr=dest.mac or b"", snet=snet, sadr=sadr,
                              expect_reply=expect_reply)
        self.send_npdu(npdu, dest)

    def send_netmsg(self, mtype, body, dest):
        if dest is None:
            npdu = build_npdu(body, netmsg=mtype)
        else:
            npdu = build_npdu(body, netmsg=mtype, dnet=dest.net, dadr=dest.mac or b"")
        self.send_npdu(npdu, dest)

    def reachable_nets(self):
        return [n for n, net in sorted(self.networks.items()) if not net.unreachable]

    def announce(self, dest=None):
        nets = self.reachable_nets()
        if nets:
            self.send_netmsg(NL_I_AM_ROUTER, b"".join(struct.pack(">H", n) for n in nets), dest)
