"""The Simulator: engine thread, settings, start and stop. Behaviour comes from the mixins."""

from __future__ import annotations

import asyncio
import concurrent.futures
import itertools
import queue
import random
import threading
import time
from collections import deque
from datetime import datetime

from enma.core.util import list_interfaces
from enma.core.simulator.routing import RoutingMixin
from enma.core.simulator.scheduler import SchedulerMixin
from enma.core.simulator.builder import SiteBuilderMixin
from enma.core.simulator.operations import OperationsMixin
from enma.core.simulator.snapshots import SnapshotMixin
from enma.core.simulator.persistence import PersistenceMixin


class Simulator(RoutingMixin, SchedulerMixin, SiteBuilderMixin, OperationsMixin, SnapshotMixin, PersistenceMixin):
    """The simulation engine. All state lives in, and is changed from, its own asyncio thread.

    Other threads (the GUI) use query() and run_coro() to call into it.
    """

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, name="enma-engine", daemon=True)
        self.groups = []
        self.devices = {}
        self.endpoints = {}
        self.fds = {}
        self.running = False
        self.main_port = 47808
        ifs = list_interfaces()
        self.iface = ifs[0]
        self.my_ip = ifs[0][1]
        self.bcast = ifs[0][2]
        self.local_ips = {"127.0.0.1"} | {i[1] for i in ifs}
        self.iam_mode = "unicast"
        self.relay = True
        self.rx = 0
        self.tx = 0
        self.rx_ignored = 0
        self.started_at = None
        self.heap = []
        self.seq = itertools.count()
        self.next_gid = 1
        self.version = 0
        self.log_q = queue.Queue()
        self.log_traffic = False
        self._rate = deque(maxlen=12)

    def start_loop(self):
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self._ticker())
        self.loop.run_forever()

    def query(self, fn, *args, timeout=10.0):
        """Run fn in the engine thread and return its result (GUI helper)."""
        if threading.current_thread() is self.thread:
            return fn(*args)
        fut = concurrent.futures.Future()

        def run():
            try:
                fut.set_result(fn(*args))
            except BaseException as e:      # noqa: BLE001 - surfaced to the caller
                fut.set_exception(e)
        self.loop.call_soon_threadsafe(run)
        return fut.result(timeout)

    def run_coro(self, coro, timeout=30.0):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def log(self, msg, kind="info"):
        self.log_q.put((datetime.now().strftime("%H:%M:%S"), kind, msg))

    def trace(self, msg):
        if self.log_traffic:
            self.log_q.put((datetime.now().strftime("%H:%M:%S"), "traffic", msg))

    def configure(self, iface=None, main_port=None, iam_mode=None, relay=None):
        if iface is not None:
            self.iface = iface
            self.my_ip, self.bcast = iface[1], iface[2]
            self.local_ips.add(iface[1])
        if main_port is not None and main_port != self.main_port:
            if self.running:
                raise ValueError("Stop the simulation before changing the main port")
            ep = self.endpoints.get(self.main_port)
            if ep is not None and ep.empty():
                del self.endpoints[self.main_port]
            self.main_port = int(main_port)
        if iam_mode is not None:
            self.iam_mode = iam_mode
        if relay is not None:
            self.relay = bool(relay)

    async def start(self):
        self._ensure_endpoint(self.main_port)
        self.running = True
        self.started_at = time.monotonic()
        errors = await self.open_all()
        now = time.monotonic()
        for dev in self.devices.values():
            if dev.flap and dev.next_flap is None:
                dev.next_flap = now + random.uniform(dev.flap_every_min, dev.flap_every_max)
        self.log(f"Simulation started on {self.my_ip} (broadcast {self.bcast}), main port {self.main_port}: "
                 f"{len(self.devices)} devices, {sum(len(d.order) for d in self.devices.values())} objects",
                 "info")
        return errors

    async def open_all(self):
        errors = []
        for port, ep in sorted(self.endpoints.items()):
            if ep.is_open:
                continue
            try:
                await ep.open()
                what = []
                if ep.device:
                    what.append(f"device {ep.device.instance}")
                if ep.networks:
                    what.append("router to networks " + ", ".join(str(n) for n in sorted(ep.networks)))
                self.log(f"UDP port {port} open ({'; '.join(what) or 'main port: broadcasts and relay'})", "info")
                ep.announce()
            except OSError as e:
                ep.error = str(e)
                msg = f"UDP port {port}: {e}"
                if getattr(e, "errno", None) in (48, 98, 10048):
                    msg += " (another BACnet program on this computer is using it)"
                errors.append(msg)
                self.log(msg, "error")
        return errors

    def stop(self):
        self.running = False
        for ep in self.endpoints.values():
            ep.close()
        for dev in self.devices.values():
            dev.clear_subs()
            dev.seg_waits.clear()
            if dev.down_reason in ("reboot", "flap"):
                dev.online = True
                dev.down_reason = ""
                dev.back_at = None
            dev.next_flap = None
            dev.dcc = 0
            dev.dcc_until = None
        self.fds.clear()
        self.log("Simulation stopped (all ports closed, COV subscriptions cleared)", "info")
