"""Packet path: BVLL handling, NPDU routing to devices and networks, network layer messages."""

from __future__ import annotations

import socket
import struct
import time

from enma.bacnet.codec import Cur, DecodeError, dec_uint, decode_tags
from enma.bacnet.constants import (
    BVLC_BROADCAST,
    BVLC_DELETE_FDT,
    BVLC_DISTRIBUTE,
    BVLC_FORWARDED,
    BVLC_READ_BDT,
    BVLC_READ_FDT,
    BVLC_REGISTER_FD,
    BVLC_RESULT,
    BVLC_UNICAST,
    BVLC_WRITE_BDT,
    NL_INIT_RT,
    NL_INIT_RT_ACK,
    NL_I_AM_ROUTER,
    NL_I_COULD_BE_ROUTER,
    NL_REJECT,
    NL_ROUTER_AVAILABLE,
    NL_ROUTER_BUSY,
    NL_WHO_IS_ROUTER,
    PDU_UNCONF,
    SU_WHO_IS,
)
from enma.bacnet.framing import Addr, bvll, parse_npdu


class RoutingMixin:
    """Packet path: BVLL handling, NPDU routing to devices and networks, network layer messages."""

    def on_datagram(self, ep, data, addr):
        ip, port = addr[0], addr[1]
        if port in self.endpoints and ip in self.local_ips:
            return                                       # our own broadcast echoed back
        self.rx += 1
        if len(data) < 4 or data[0] != 0x81:
            self.rx_ignored += 1
            return
        func = data[1]
        blen = struct.unpack_from(">H", data, 2)[0]
        if blen > len(data) or blen < 4:
            self.rx_ignored += 1
            return
        data = data[:blen]
        src_ip, src_port = ip, port
        bcast = False
        if func == BVLC_UNICAST:
            npdu = data[4:]
        elif func == BVLC_BROADCAST:
            npdu = data[4:]
            bcast = True
        elif func == BVLC_FORWARDED:
            if len(data) < 10:
                return
            src_ip = socket.inet_ntoa(data[4:8])
            src_port = struct.unpack_from(">H", data, 8)[0]
            if src_port in self.endpoints and src_ip in self.local_ips:
                return
            npdu = data[10:]
            bcast = True
        elif func == BVLC_DISTRIBUTE:
            if (ip, port) not in self.fds:
                ep.sendto(bvll(BVLC_RESULT, struct.pack(">H", 0x0060)), addr)
                return
            npdu = data[4:]
            bcast = True
        elif func == BVLC_REGISTER_FD:
            ttl = struct.unpack_from(">H", data, 4)[0] if len(data) >= 6 else 60
            new = (ip, port) not in self.fds
            self.fds[(ip, port)] = time.monotonic() + ttl + 30
            ep.sendto(bvll(BVLC_RESULT, struct.pack(">H", 0x0000)), addr)
            if new:
                self.log(f"Foreign device registered: {ip}:{port} (TTL {ttl}s)", "info")
            return
        elif func in (BVLC_WRITE_BDT, BVLC_READ_BDT, BVLC_READ_FDT, BVLC_DELETE_FDT):
            nak = {BVLC_WRITE_BDT: 0x0010, BVLC_READ_BDT: 0x0020, BVLC_READ_FDT: 0x0040, BVLC_DELETE_FDT: 0x0050}
            ep.sendto(bvll(BVLC_RESULT, struct.pack(">H", nak[func])), addr)
            return
        else:
            return
        try:
            n = parse_npdu(npdu)
        except DecodeError:
            self.rx_ignored += 1
            return
        src = Addr(src_ip, src_port, n.snet, n.sadr)
        if n.msg_type is not None:
            self.on_netmsg(ep, n, src, bcast, relay_ok=True)
        else:
            self.route_apdu(ep, n, src, bcast)

    def _relay_targets(self, ep, bcast):
        if bcast and self.relay and ep.port == self.main_port:
            return [e for p, e in sorted(self.endpoints.items()) if e is not ep and e.is_open]
        return []

    def route_apdu(self, ep, n, src, bcast):
        apdu = n.payload
        if not apdu:
            return
        if n.dnet is None:                               # local: for the node on this port
            if ep.device is not None:
                self.deliver(ep.device, apdu, src, bcast)
            for other in self._relay_targets(ep, bcast):
                if other.device is not None:
                    self.deliver(other.device, apdu, src, True)
            return
        if n.dnet == 0xFFFF:                             # global broadcast
            if ep.device is not None:
                self.deliver(ep.device, apdu, src, True)
            for net in ep.networks.values():
                self.net_broadcast(net, apdu, src)
            for other in self._relay_targets(ep, True if bcast else False):
                if other.device is not None:
                    self.deliver(other.device, apdu, src, True)
                for net in other.networks.values():
                    self.net_broadcast(net, apdu, src)
            return
        net = ep.networks.get(n.dnet)
        if net is None or net.unreachable:
            if not bcast:
                body = bytes([1]) + struct.pack(">H", n.dnet)
                ep.send_netmsg(NL_REJECT, body, src)
                self.trace(f"Router :{ep.port} → {src}: Reject-Message-To-Network (network {n.dnet} unknown)")
                if net is not None:
                    net.dropped += 1
            return
        if not n.dadr:                                   # directed broadcast on that network
            self.net_broadcast(net, apdu, src)
            return
        dev = net.devices.get(n.dadr)
        if dev is None:
            return                                       # no station with that MAC: silence, like MS/TP
        self.deliver(dev, apdu, src, bcast)

    def deliver(self, dev, apdu, src, bcast):
        net = dev.network
        if net is not None:
            if net.offline or net.unreachable:
                return
            net.submit(lambda: dev.receive(apdu, src, bcast), requester=src)
        else:
            dev.receive(apdu, src, bcast)

    def net_broadcast(self, net, apdu, src):
        if net.offline or net.unreachable:
            return
        if len(apdu) >= 2 and apdu[0] >> 4 == PDU_UNCONF and apdu[1] == SU_WHO_IS:
            # one frame on the trunk; only the matching stations answer (each answer costs trunk time)
            try:
                c = Cur(decode_tags(apdu[2:]))
                lo, hi = c.opt_ctx(0), c.opt_ctx(1)
                rng = (dec_uint(lo.data), dec_uint(hi.data)) if lo is not None and hi is not None else None
            except Exception:
                rng = None
            for dev in list(net.devices.values()):
                if rng is None or rng[0] <= dev.instance <= rng[1]:
                    net.submit(lambda d=dev: d.receive(apdu, src, True), requester=src)
            return
        for dev in list(net.devices.values()):
            dev.receive(apdu, src, True)

    def on_netmsg(self, ep, n, src, bcast, relay_ok=False):
        t = n.msg_type
        body = n.payload
        if n.dnet is not None and n.dnet != 0xFFFF:
            return                                       # network messages for remote networks: ignored
        if t == NL_WHO_IS_ROUTER:
            want = struct.unpack_from(">H", body, 0)[0] if len(body) >= 2 else None
            self._answer_wirtn(ep, want, src)
            if relay_ok:
                for other in self._relay_targets(ep, bcast):
                    self._answer_wirtn(other, want, src)
        elif t == NL_INIT_RT:
            if body[:1] == b"\x00":
                nets = ep.reachable_nets()
                payload = bytes([len(nets)]) + b"".join(struct.pack(">HBB", nn, i + 1, 0)
                                                        for i, nn in enumerate(nets))
                ep.send_netmsg(NL_INIT_RT_ACK, payload, src)
        elif t in (NL_I_AM_ROUTER, NL_I_COULD_BE_ROUTER, NL_REJECT, NL_ROUTER_BUSY, NL_ROUTER_AVAILABLE,
                   NL_INIT_RT_ACK, 0x12, 0x13):
            if t == NL_I_AM_ROUTER:
                mine = set()
                for e in self.endpoints.values():
                    mine.update(e.networks)
                theirs = {struct.unpack_from(">H", body, i)[0] for i in range(0, len(body) - 1, 2)}
                clash = sorted(mine & theirs)
                if clash:
                    self.log(f"{src} also announces network(s) {clash}: duplicate network number on the LAN",
                             "warn")
        elif t < 0x80 and not bcast:
            ep.send_netmsg(NL_REJECT, bytes([3]) + struct.pack(">H", 0), src)

    def _answer_wirtn(self, ep, want, src):
        nets = ep.reachable_nets()
        if want is not None:
            if want not in nets:
                return
            nets = [want]
        if not nets:
            return
        body = b"".join(struct.pack(">H", x) for x in nets)
        if self.iam_mode in ("unicast", "both"):
            ep.send_netmsg(NL_I_AM_ROUTER, body, src)
        if self.iam_mode in ("broadcast", "both"):
            ep.send_netmsg(NL_I_AM_ROUTER, body, None)
        self.trace(f"Router :{ep.port} → {src}: I-Am-Router-To-Network {nets}")
