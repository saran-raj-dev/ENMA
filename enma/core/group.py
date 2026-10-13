"""A batch of devices created together."""

from __future__ import annotations


class Group:
    def __init__(self, gid, name, kind, params):
        self.gid = gid
        self.name = name
        self.kind = kind
        self.params = params
        self.devices = []
        self.networks = []
