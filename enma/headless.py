"""Run a saved site without the GUI."""

from __future__ import annotations

import json
import queue
import signal

from enma.core.simulator import Simulator


def run_headless(path, port=None, instance=None):
    sim = Simulator()
    sim.start_loop()
    with open(path) as fh:
        sim.query(sim.load_json, json.load(fh))
    if port:
        sim.configure(main_port=port)
    errors = sim.run_coro(sim.start())
    for e in errors:
        print("ERROR", e, flush=True)
    print(f"Running {len(sim.devices)} devices on {sim.my_ip}, main port {sim.main_port}. Ctrl+C to stop.", flush=True)
    def stop_from_signal(signum, frame):             # Ctrl+C, kill, terminal closed
        raise KeyboardInterrupt

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop_from_signal)
    try:
        while True:
            try:
                ts, kind, msg = sim.log_q.get(timeout=1)
                print(ts, f"[{kind}]", msg, flush=True)
            except queue.Empty:
                pass
            while instance is not None and not instance.requests.empty():
                instance.requests.get_nowait()
                print("Another start of ENMA was refused: this headless instance is already running.", flush=True)
    except KeyboardInterrupt:
        print("Stopping...", flush=True)
    finally:
        sim.shutdown()                                   # closes every UDP port
        if instance is not None:
            instance.release()
        print("ENMA stopped.", flush=True)
