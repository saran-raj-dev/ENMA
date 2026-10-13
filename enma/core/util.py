"""Formatting and network interface helpers."""

from __future__ import annotations

import os
import re
import socket
import struct
import subprocess
import sys


# ════════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════════

def fmt_dur(sec):
    if sec is None:
        return "-"
    sec = float(sec)
    if sec < 0:
        sec = 0
    if sec < 120:
        return f"{sec:.0f}s"
    if sec < 7200:
        return f"{sec / 60:.0f}m" if sec % 60 < 1 or sec >= 600 else f"{sec / 60:.1f}m"
    if sec < 172800:
        return f"{sec / 3600:.1f}h".replace(".0h", "h")
    return f"{sec / 86400:.1f}d".replace(".0d", "d")


def _primary_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _mask_to_bcast(ip, mask_int):
    ipi = struct.unpack(">I", socket.inet_aton(ip))[0]
    return socket.inet_ntoa(struct.pack(">I", (ipi & mask_int) | (~mask_int & 0xFFFFFFFF)))


def list_interfaces():
    """[(name, ip, broadcast)] for IPv4 interfaces, primary first."""
    found = []
    try:
        if sys.platform.startswith("linux"):
            txt = subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True,
                                 text=True, timeout=3).stdout
            for line in txt.splitlines():
                m = re.search(r"^\d+:\s+(\S+)\s+inet (\d+\.\d+\.\d+\.\d+)/(\d+)(?: brd (\S+))?", line)
                if m and not m.group(2).startswith("127."):
                    bits = int(m.group(3))
                    mask = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
                    found.append((m.group(1), m.group(2), m.group(4) or _mask_to_bcast(m.group(2), mask)))
        elif os.name != "nt":
            txt = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=3).stdout
            name = None
            for line in txt.splitlines():
                h = re.match(r"^(\S+?):? flags=", line)
                if h:
                    name = h.group(1)
                    continue
                m = re.search(r"inet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-fA-F]+|\d+\.\d+\.\d+\.\d+)"
                              r"(?: broadcast (\d+\.\d+\.\d+\.\d+))?", line)
                if m and name and not m.group(1).startswith("127."):
                    mk = m.group(2)
                    mask = int(mk, 16) if mk.startswith("0x") else struct.unpack(">I", socket.inet_aton(mk))[0]
                    found.append((name, m.group(1), m.group(3) or _mask_to_bcast(m.group(1), mask)))
    except Exception:
        pass
    primary = _primary_ip()
    if not any(f[1] == primary for f in found) and not primary.startswith("127."):
        found.append(("default", primary, "255.255.255.255"))
    found.sort(key=lambda f: (f[1] != primary, f[0]))
    if not found:
        found.append(("loopback", "127.0.0.1", "127.255.255.255"))
    return found
