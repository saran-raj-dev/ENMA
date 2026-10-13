"""Run a saved site without the GUI."""

from __future__ import annotations

import json
import queue

from enma.core.simulator import Simulator


def run_headless(path, port=None):
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
    try:
        while True:
            try:
                ts, kind, msg = sim.log_q.get(timeout=1)
                print(ts, f"[{kind}]", msg, flush=True)
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        sim.query(sim.stop)
