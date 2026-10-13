"""Single instance: only one ENMA process may run on a computer.

The first ENMA listens on a localhost-only TCP port (INSTANCE_PORT). A second start finds the port taken,
asks the running ENMA to come to the front and exits, so two simulators never fight over the BACnet ports.
"""

from __future__ import annotations

import os
import queue
import socket
import sys
import threading

from enma.config import APP_NAME, INSTANCE_PORT

_HELLO = APP_NAME.encode()


class SingleInstance:
    def __init__(self, mode):
        self.mode = mode                      # "gui" or "headless"
        self.sock = None
        self.requests = queue.Queue()         # one item per "show" request from a second start

    def acquire(self):
        """True if this is the only ENMA running; the lock is held until the process ends."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name == "nt":
                s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR), 1)
            else:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # ignore TIME_WAIT, not a live owner
            s.bind(("127.0.0.1", INSTANCE_PORT))
            s.listen(5)
        except OSError:
            s.close()
            return False
        self.sock = s
        threading.Thread(target=self._serve, name="enma-instance", daemon=True).start()
        return True

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(2)
                    if conn.recv(64).strip() == b"show":
                        conn.sendall(_HELLO + f" {self.mode} {os.getpid()}\n".encode())
                        self.requests.put("show")
                except OSError:
                    pass

    @staticmethod
    def contact_running():
        """Ask the running ENMA to come to the front. Returns (mode, pid), or None if no ENMA answered."""
        try:
            with socket.create_connection(("127.0.0.1", INSTANCE_PORT), timeout=2) as c:
                c.sendall(b"show\n")
                reply = c.recv(128).decode(errors="replace").split()
        except OSError:
            return None
        if len(reply) == 3 and reply[0].encode() == _HELLO:
            return reply[1], reply[2]
        return None

    def release(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


def ensure_single_instance(mode):
    """Take the instance lock, or bring the running ENMA forward and exit this process."""
    inst = SingleInstance(mode)
    if inst.acquire():
        return inst
    running = SingleInstance.contact_running()
    if running is not None:
        r_mode, pid = running
        if r_mode == "gui":
            print(f"{APP_NAME} is already running (process {pid}); its window has been brought to the front.")
        else:
            print(f"{APP_NAME} is already running headless (process {pid}). Stop it first (Ctrl+C in its terminal).")
        sys.exit(0)
    # The port belongs to some other program: run anyway rather than refuse to start.
    print(f"Note: localhost TCP port {INSTANCE_PORT} is used by another program; "
          f"{APP_NAME} cannot check for a second copy of itself.", file=sys.stderr)
    return inst
