"""Product identity and file locations."""

from __future__ import annotations

import os


APP_NAME = "ENMA"
APP_FULL_NAME = "Engine for Network Modeling & Automation"
APP_VERSION = "1.0"
AUTHOR_NAME = "Saran Raj"
AUTHOR_URL = "https://github.com/saran-raj-dev"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".enma")
LAST_SITE = os.path.join(CONFIG_DIR, "last_site.json")
