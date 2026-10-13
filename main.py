#!/usr/bin/env python3
"""ENMA - Engine for Network Modeling & Automation.

Boots the application:   python3 main.py
Headless (saved site):    python3 main.py --headless site.json [main_port]
"""

import os
import sys

if sys.version_info < (3, 8):
    sys.exit("ENMA needs Python 3.8 or newer.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enma.app import main  # noqa: E402

if __name__ == "__main__":
    main()
