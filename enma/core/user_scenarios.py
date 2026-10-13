"""Combined scenarios saved by the user (CONFIG_DIR/scenarios.json)."""

from __future__ import annotations

import json
import os

from enma.config import CONFIG_DIR, USER_SCENARIOS
from enma.core.scenarios import SCENARIO_BY_ID


def load():
    """Saved scenarios: [{"name", "direct_pct", "parts": [{"id", "count"}]}]. Unknown parts are dropped."""
    try:
        with open(USER_SCENARIOS) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        parts = [p for p in item.get("parts", []) if p.get("id") in SCENARIO_BY_ID]
        if item.get("name") and parts:
            out.append(dict(name=item["name"], direct_pct=float(item.get("direct_pct", 50)), parts=parts))
    return out


def _write(items):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = USER_SCENARIOS + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(items, fh, indent=2)
    os.replace(tmp, USER_SCENARIOS)


def save(name, parts, direct_pct):
    """Save (or replace, by name) a combined scenario."""
    items = [i for i in load() if i["name"].lower() != name.lower()]
    items.append(dict(name=name, direct_pct=float(direct_pct), parts=[dict(id=p["id"], count=int(p["count"])) for p in parts]))
    _write(items)


def delete(name):
    _write([i for i in load() if i["name"] != name])
