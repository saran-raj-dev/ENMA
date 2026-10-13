"""APDU builders, NPDU (clause 6) and BVLL (Annex J) framing, and addresses."""

from __future__ import annotations

import struct

from enma.bacnet.codec import DecodeError, app_enum


# ════════════════════════════════════════════════════════════════════════════
#  APDU / NPDU / BVLL framing
# ════════════════════════════════════════════════════════════════════════════

def apdu_simple_ack(invoke, service):
    return bytes([0x20, invoke, service])


def apdu_complex_ack(invoke, service, payload):
    return bytes([0x30, invoke, service]) + payload


def apdu_error(invoke, service, cls, code):
    return bytes([0x50, invoke, service]) + app_enum(cls) + app_enum(code)


def apdu_reject(invoke, reason):
    return bytes([0x60, invoke, reason])


def apdu_abort(invoke, reason):
    return bytes([0x71, invoke, reason])          # SRV=1: sent by the server


def apdu_unconfirmed(service, payload):
    return bytes([0x10, service]) + payload


class Addr:
    """Where a request came from / a reply goes: B/IP address plus optional SNET/SADR."""
    __slots__ = ("ip", "port", "net", "mac")

    def __init__(self, ip, port, net=None, mac=None):
        self.ip, self.port, self.net, self.mac = ip, port, net, mac

    def key(self):
        return (self.ip, self.port, self.net, self.mac)

    def __str__(self):
        base = f"{self.ip}:{self.port}"
        if self.net is not None:
            return f"{self.net}:{(self.mac or b'').hex() or '*'}@{base}"
        return base


class NPDU:
    __slots__ = ("ctrl", "dnet", "dadr", "snet", "sadr", "hop", "msg_type", "payload")


def parse_npdu(b):
    if len(b) < 2 or b[0] != 0x01:
        raise DecodeError("not a BACnet NPDU")
    n = NPDU()
    n.ctrl = ctrl = b[1]
    i = 2
    n.dnet = n.dadr = n.snet = n.sadr = n.hop = n.msg_type = None
    try:
        if ctrl & 0x20:
            n.dnet, dlen = struct.unpack_from(">HB", b, i)
            i += 3
            n.dadr = bytes(b[i:i + dlen])
            i += dlen
        if ctrl & 0x08:
            n.snet, slen = struct.unpack_from(">HB", b, i)
            i += 3
            n.sadr = bytes(b[i:i + slen])
            i += slen
            if slen == 0:
                raise DecodeError("SLEN 0")
        if ctrl & 0x20:
            n.hop = b[i]
            i += 1
        if ctrl & 0x80:
            n.msg_type = b[i]
            i += 1
            if n.msg_type >= 0x80:
                i += 2
    except (IndexError, struct.error):
        raise DecodeError("truncated NPDU")
    n.payload = bytes(b[i:])
    return n


def build_npdu(payload, *, netmsg=None, dnet=None, dadr=b"", snet=None, sadr=b"", expect_reply=False):
    ctrl = 0
    if netmsg is not None:
        ctrl |= 0x80
    if dnet is not None:
        ctrl |= 0x20
    if snet is not None:
        ctrl |= 0x08
    if expect_reply:
        ctrl |= 0x04
    out = bytearray([0x01, ctrl])
    if dnet is not None:
        out += struct.pack(">HB", dnet, len(dadr)) + dadr
    if snet is not None:
        out += struct.pack(">HB", snet, len(sadr)) + sadr
    if dnet is not None:
        out.append(255)
    if netmsg is not None:
        out.append(netmsg)
    out += payload
    return bytes(out)


def bvll(func, payload):
    return bytes([0x81, func]) + struct.pack(">H", len(payload) + 4) + payload
