"""Command line entry point: starts the GUI, or a saved site headless with --headless."""

from __future__ import annotations

import sys

from enma.config import APP_FULL_NAME, APP_NAME, APP_VERSION


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
        run_headless(args[1], int(args[2]) if len(args) > 2 else None)
        return
    try:
        import tkinter as tk
    except ImportError:
        print("tkinter is not available. Install python3-tk, or use --headless with a saved site.")
        sys.exit(1)
    from enma.core.simulator import Simulator
    from enma.gui.app import App

    sim = Simulator()
    sim.start_loop()
    root = tk.Tk()
    App(root, sim)
    root.lift()
    root.attributes("-topmost", True)
    root.after(600, lambda: root.attributes("-topmost", False))
    sim.log(f"{APP_NAME} {APP_VERSION} ({APP_FULL_NAME}) ready. Add devices, then press Start.", "info")
    root.mainloop()
