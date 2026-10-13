"""Command line entry point: starts the GUI, or a saved site headless with --headless."""

from __future__ import annotations

import os
import queue
import signal
import sys

from enma.config import APP_FULL_NAME, APP_NAME, APP_VERSION
from enma.instance import ensure_single_instance


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if args and args[0] in ("-h", "--help"):
        print(f"{APP_NAME} {APP_VERSION} - {APP_FULL_NAME}\n\n"
              "usage: python3 main.py                              start the GUI\n"
              "       python3 main.py --headless site.json [port]  run a saved site without the GUI")
        return
    if args and args[0] == "--headless":
        if len(args) < 2:
            print("usage: python3 main.py --headless site.json [main_port]")
            sys.exit(2)
        from enma.headless import run_headless
        instance = ensure_single_instance("headless")
        run_headless(args[1], int(args[2]) if len(args) > 2 else None, instance)
        return
    try:
        import tkinter as tk
    except ImportError:
        print("tkinter is not available. Install python3-tk, or use --headless with a saved site.")
        sys.exit(1)
    instance = ensure_single_instance("gui")           # exits here if ENMA is already running
    from enma.core.simulator import Simulator
    from enma.gui.app import App

    sim = Simulator()
    sim.start_loop()
    root = tk.Tk()
    app = App(root, sim)

    def close_from_signal(signum, frame):            # Ctrl+C, kill, terminal closed
        root.after(0, app.on_close)

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), close_from_signal)
    def poll_instance():                              # another start of ENMA asked us to show ourselves
        try:
            while True:
                instance.requests.get_nowait()
                app.bring_to_front()
        except queue.Empty:
            pass
        root.after(300, poll_instance)

    poll_instance()
    app.bring_to_front(log=False)
    sim.log(f"{APP_NAME} {APP_VERSION} ({APP_FULL_NAME}) ready. Add devices, then press Start.", "info")
    try:
        root.mainloop()
    finally:
        # Window closed: make sure no port stays open and no thread keeps the process alive.
        sim.shutdown()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
