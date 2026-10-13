"""Product identity and file locations."""

from __future__ import annotations

import os


APP_NAME = "ENMA"
APP_FULL_NAME = "Engine for Network Modeling & Automation"
APP_VERSION = "1.0"
AUTHOR_NAME = "Saran Raj"
AUTHOR_URL = "https://github.com/saran-raj-dev"
# localhost-only TCP port used to make sure a single ENMA runs per computer (not BACnet)
INSTANCE_PORT = 47790
# ENMA_HOME overrides the settings folder (used by tests so they never touch the real one)
CONFIG_DIR = os.environ.get("ENMA_HOME") or os.path.join(os.path.expanduser("~"), ".enma")
LAST_SITE = os.path.join(CONFIG_DIR, "last_site.json")
USER_SCENARIOS = os.path.join(CONFIG_DIR, "scenarios.json")
