"""Tag encoding / decoding (ASHRAE 135 clause 20.2) and BACnet error types."""

from __future__ import annotations

import struct

from enma.bacnet.constants import (
    ERROR_CLASS_NAMES,
    ERROR_NAMES,
    REJECT_NAMES,
    R_INVALID_TAG,
    R_MISSING,
    R_TOO_MANY,
)


# ════════════════════════════════════════════════════════════════════════════
#  Encoding (ASHRAE 135 clause 20.2)
# ════════════════════════════════════════════════════════════════════════════

class DecodeError(Exception):
    pass


class BacErr(Exception):
    """Result(-): Error PDU with error class / code."""

    def __init__(self, cls, code):
        super().__init__(f"{ERROR_CLASS_NAMES.get(cls, cls)}:{ERROR_NAMES.get(code, code)}")
        self.cls = cls
        self.code = code


class WpmErr(BacErr):
    def __init__(self, cls, code, oid, pid, idx):
        super().__init__(cls, code)
        self.oid, self.pid, self.idx = oid, pid, idx


class BacReject(Exception):
    def __init__(self, reason):
        super().__init__(REJECT_NAMES.get(reason, str(reason)))
        self.reason = reason


def enc_tag(num, ctx, length):
    b0 = (num << 4) if num < 15 else 0xF0
    if ctx:
        b0 |= 0x08
    ext = b"" if num < 15 else bytes([num])
    if length < 5:
        return bytes([b0 | length]) + ext
    b0 |= 5
    if length < 254:
        return bytes([b0]) + ext + bytes([length])
    if length < 65536:
        return bytes([b0]) + ext + b"\xfe" + struct.pack(">H", length)
    return bytes([b0]) + ext + b"\xff" + struct.pack(">I", length)


def _uint_bytes(v):
    v = int(v)
    if v < 0:
        raise ValueError("unsigned value < 0")
    return v.to_bytes(max(1, (v.bit_length() + 7) // 8), "big")


def _sint_bytes(v):
    v = int(v)
    n = 1
    while not (-(1 << (8 * n - 1)) <= v < (1 << (8 * n - 1))):
        n += 1
    return v.to_bytes(n, "big", signed=True)


def app_null():
    return b"\x00"


def app_bool(v):
    return bytes([0x10 | (1 if v else 0)])


def app_uint(v):
    d = _uint_bytes(v)
    return enc_tag(2, False, len(d)) + d


def app_sint(v):
    d = _sint_bytes(v)
    return enc_tag(3, False, len(d)) + d


def app_real(v):
    return b"\x44" + struct.pack(">f", float(v))


def app_str(s):
    d = b"\x00" + str(s).encode("utf-8")
    return enc_tag(7, False, len(d)) + d


def app_bits(bits):
    n = len(bits)
    nbytes = (n + 7) // 8
    buf = bytearray(nbytes)
    for i, b in enumerate(bits):
        if b:
            buf[i // 8] |= 0x80 >> (i % 8)
    d = bytes([nbytes * 8 - n]) + bytes(buf)
    return enc_tag(8, False, len(d)) + d


def app_enum(v):
    d = _uint_bytes(v)
    return enc_tag(9, False, len(d)) + d


def app_date(dt):
    return b"\xa4" + bytes([dt.year - 1900, dt.month, dt.day, dt.isoweekday()])


def app_time(dt):
    return b"\xb4" + bytes([dt.hour, dt.minute, dt.second, dt.microsecond // 10000])


def app_oid(otype, inst):
    return b"\xc4" + struct.pack(">I", (otype << 22) | inst)


def ctx_uint(n, v):
    d = _uint_bytes(v)
    return enc_tag(n, True, len(d)) + d


ctx_enum = ctx_uint


def ctx_oid(n, otype, inst):
    return enc_tag(n, True, 4) + struct.pack(">I", (otype << 22) | inst)


def ctx_open(n):
    return bytes([(n << 4) | 0x0E]) if n < 15 else bytes([0xFE, n])


def ctx_close(n):
    return bytes([(n << 4) | 0x0F]) if n < 15 else bytes([0xFF, n])


class Tag:
    __slots__ = ("kind", "num", "data", "lvt")

    def __init__(self, kind, num, data, lvt):
        self.kind, self.num, self.data, self.lvt = kind, num, data, lvt

    def __repr__(self):
        return f"Tag({self.kind},{self.num},{self.data.hex()},{self.lvt})"


def decode_tags(buf):
    out = []
    pos, end = 0, len(buf)
    try:
        while pos < end:
            b0 = buf[pos]
            pos += 1
            num = b0 >> 4
            if num == 15:
                num = buf[pos]
                pos += 1
            ctx = bool(b0 & 0x08)
            lvt = b0 & 0x07
            if ctx and lvt == 6:
                out.append(Tag("open", num, b"", 0))
                continue
            if ctx and lvt == 7:
                out.append(Tag("close", num, b"", 0))
                continue
            if not ctx and num == 1:            # application boolean: value in L/V/T
                out.append(Tag("app", 1, b"", lvt))
                continue
            if lvt == 5:
                length = buf[pos]
                pos += 1
                if length == 254:
                    length = struct.unpack_from(">H", buf, pos)[0]
                    pos += 2
                elif length == 255:
                    length = struct.unpack_from(">I", buf, pos)[0]
                    pos += 4
            elif lvt > 5:
                raise DecodeError("bad application tag length")
            else:
                length = lvt
            if pos + length > end:
                raise DecodeError("tag runs past end of APDU")
            out.append(Tag("ctx" if ctx else "app", num, bytes(buf[pos:pos + length]), length))
            pos += length
    except (IndexError, struct.error):
        raise DecodeError("truncated tag")
    return out


def dec_uint(d):
    return int.from_bytes(d, "big") if d else 0


def dec_oid(d):
    if len(d) != 4:
        raise BacReject(R_INVALID_TAG)
    v = int.from_bytes(d, "big")
    return (v >> 22, v & 0x3FFFFF)


def dec_app(tag):
    """Application-tagged value -> (type_name, python value)."""
    n, d = tag.num, tag.data
    if n == 0:
        return "null", None
    if n == 1:
        return "bool", bool(tag.lvt)
    if n == 2:
        return "uint", dec_uint(d)
    if n == 3:
        return "sint", int.from_bytes(d, "big", signed=True) if d else 0
    if n == 4:
        if len(d) != 4:
            raise DecodeError("bad real")
        return "real", struct.unpack(">f", d)[0]
    if n == 5:
        if len(d) != 8:
            raise DecodeError("bad double")
        return "double", struct.unpack(">d", d)[0]
    if n == 6:
        return "octets", d
    if n == 7:
        if not d:
            return "str", ""
        cs = d[0]
        body = d[1:]
        if cs == 0:
            return "str", body.decode("utf-8", "replace")
        if cs == 4:
            return "str", body.decode("utf-16-be", "replace")
        return "str", body.decode("latin-1", "replace")
    if n == 8:
        return "bits", d
    if n == 9:
        return "enum", dec_uint(d)
    if n == 10:
        return "date", d
    if n == 11:
        return "time", d
    if n == 12:
        return "oid", dec_oid(d)
    return "unknown", d


class Cur:
    """Cursor over a decoded tag list, raising Reject on malformed requests."""

    def __init__(self, tags):
        self.tags = tags
        self.i = 0

    def peek(self):
        return self.tags[self.i] if self.i < len(self.tags) else None

    def at_end(self):
        return self.i >= len(self.tags)

    def opt_ctx(self, n):
        t = self.peek()
        if t is not None and t.kind == "ctx" and t.num == n:
            self.i += 1
            return t
        return None

    def need_ctx(self, n):
        t = self.opt_ctx(n)
        if t is None:
            raise BacReject(R_MISSING if self.at_end() else R_INVALID_TAG)
        return t

    def is_open(self, n):
        t = self.peek()
        return t is not None and t.kind == "open" and t.num == n

    def is_close(self, n):
        t = self.peek()
        return t is not None and t.kind == "close" and t.num == n

    def need_open(self, n):
        if not self.is_open(n):
            raise BacReject(R_MISSING if self.at_end() else R_INVALID_TAG)
        self.i += 1

    def need_close(self, n):
        if not self.is_close(n):
            raise BacReject(R_INVALID_TAG)
        self.i += 1

    def collect(self, n):
        """Tags up to the close tag matching an already consumed open tag n."""
        depth = 0
        out = []
        while True:
            t = self.peek()
            if t is None:
                raise BacReject(R_INVALID_TAG)
            self.i += 1
            if t.kind == "open":
                depth += 1
            elif t.kind == "close":
                if depth == 0:
                    if t.num != n:
                        raise BacReject(R_INVALID_TAG)
                    return out
                depth -= 1
            out.append(t)

    def end(self):
        if not self.at_end():
            raise BacReject(R_TOO_MANY)
