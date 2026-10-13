"""Ready-made scenarios that recreate field problems with standard behaviour."""

from __future__ import annotations


# ════════════════════════════════════════════════════════════════════════════
#  Scenario presets (each recreates a field problem with standard behaviour)
# ════════════════════════════════════════════════════════════════════════════

SCENARIOS = [
    dict(title="Realistic mixed site",
         problem="A typical building: controllers on MS/TP trunks behind a router, 60% support COV, "
                 "20% of points change only every 30-120 min, a few controllers are dead.",
         expect="Discover every device, poll what cannot do COV, subscribe the rest, mark dead "
                "devices offline without hammering them.",
         params=dict(name="Mixed site", prefix="AHU-", count=60, per_net=30, cov_pct=60, stale_pct=20,
                     offline_pct=5, chg_min=10, chg_max=120)),
    dict(title="Router busy under load (MS/TP trunk saturation)",
         problem="A slow MS/TP trunk (60 ms per message) behind a router with a 10-message buffer. "
                 "Subscribing or polling every point in one burst fills the buffer: the router answers "
                 "Router-Busy-To-Network and drops requests, then sends Router-Available-To-Network. "
                 "Even one global Who-Is overflows it (40 I-Am answers), so a single discovery finds only part "
                 "of the trunk.",
         expect="Pace requests per network (one or two in flight), stop sending to a network while it "
                "is busy, resume after Router-Available; no endless retries.",
         params=dict(name="Busy trunk", prefix="FCU-", count=40, per_net=40, n_ai=4, n_ao=2, n_av=3, n_bi=3,
                     n_bo=2, n_bv=1, n_msv=1, cov_pct=100, trunk_ms=60, buffer=10, chg_min=5, chg_max=20)),
    dict(title="Controllers without COV",
         problem="protocolServicesSupported does not list SubscribeCOV. Any SubscribeCOV gets "
                 "Reject: unrecognized-service.",
         expect="Read protocolServicesSupported first and poll these devices; never retry a "
                "rejected subscription in a loop.",
         params=dict(name="No-COV controllers", prefix="VAV-", count=20, cov_pct=0, chg_min=10, chg_max=60)),
    dict(title="COV subscription slots exhausted",
         problem="Each device holds only 8 COV subscriptions. The 9th answers Error "
                 "resources / no-space-to-add-list-element.",
         expect="Treat 'no space' as a capacity limit: poll the remaining points of that device and do "
                "not retry them every few seconds.",
         params=dict(name="Few COV slots", prefix="UC-", count=10, n_ai=8, n_ao=2, n_av=4, n_bi=4, n_bo=2,
                     n_bv=0, n_msv=0, cov_pct=100, max_subs=8)),
    dict(title="Some objects refuse COV",
         problem="The device supports SubscribeCOV, but half of its objects answer Error "
                 "object / optional-functionality-not-supported.",
         expect="Decide COV per object, not per device: poll the refused objects only.",
         params=dict(name="Partial COV", prefix="PLC-", count=10, cov_pct=100, refuse_pct=50)),
    dict(title="COV accepted but never notified",
         problem="SubscribeCOV is acknowledged, but no notification ever arrives (not even the initial one).",
         expect="Trust data, not the ack: a subscription with no notification is not live; keep a backup "
                "poll and flag the point.",
         params=dict(name="Mute COV", prefix="RTU-", count=10, cov_pct=100, mute_pct=100)),
    dict(title="Silent (dead) controllers",
         problem="30% of the devices never answer anything: no I-Am, no reads, no errors.",
         expect="Mark them offline after a few misses and probe slowly instead of reading every point "
                "every cycle.",
         params=dict(name="Silent controllers", prefix="DDC-", count=30, offline_pct=30)),
    dict(title="Flapping devices that forget subscriptions",
         problem="Half of the devices drop off for 30-90 s every 3-6 min, restart, send I-Am and lose all "
                 "COV subscriptions.",
         expect="Notice the restart (I-Am / no reply) and re-subscribe; values must not go stale silently.",
         params=dict(name="Flapping", prefix="CTL-", count=20, flap_pct=50, flap_every_min=3, flap_every_max=6,
                     flap_off_min=30, flap_off_max=90, flap_clear=True)),
    dict(title="Unreachable network (unknown route)",
         problem="The router does not announce this network and answers Reject-Message-To-Network "
                 "(not directly connected) to traffic for it. Who-Is-Router-To-Network gets no answer.",
         expect="Hold the whole network after the first failure with a back-off; do not retry every point.",
         params=dict(name="Unreachable net", prefix="X-", count=10, first_net=3205, unreachable=True)),
    dict(title="Slow devices and late Who-Is answers",
         problem="Half the devices answer requests after 2-6 s; half answer Who-Is after 10-15 s.",
         expect="Timeouts and retries sized for slow MS/TP devices; a late I-Am must not mark a device as "
                "removed.",
         params=dict(name="Slow devices", prefix="SLW-", count=20, slow_pct=50, slow_min=2000, slow_max=6000,
                     slowwhois_pct=50, slowwhois_min=10, slowwhois_max=15)),
    dict(title="Stale points",
         problem="Half of the points never change (frozen); the rest change every 30-120 s.",
         expect="Stale detection flags the frozen points and leaves the healthy ones alone; a device that is "
                "online with steady values is not the same as a dead one.",
         params=dict(name="Stale points", prefix="ST-", count=10, stale_pct=50, stale_frozen=True,
                     chg_min=30, chg_max=120)),
    dict(title="Packet loss",
         problem="10% of requests to every device are lost.",
         expect="Retries recover reads without duplicate writes or false 'offline' verdicts.",
         params=dict(name="Lossy", prefix="LS-", count=10, drop_pct=10)),
    dict(title="Large site (scale)",
         problem="300 routed controllers, 30 objects each (9,000 points) on 6 trunks, 70% COV.",
         expect="Discovery, polling and COV renewals stay spread out; no bursts per network.",
         params=dict(name="Large site", prefix="B-", count=300, per_net=50, n_ai=8, n_ao=4, n_av=6, n_bi=5,
                     n_bo=3, n_bv=2, n_msi=0, n_msv=2, cov_pct=70, stale_pct=15, chg_min=30, chg_max=300)),
    dict(title="Small APDU, no segmentation",
         problem="Max APDU 480, no segmentation, 200 objects. Reading the whole objectList (or a big RPM) "
                 "gets Abort: segmentation-not-supported.",
         expect="Fall back to objectList[0] and index-by-index reads; size RPM requests to fit 480 bytes.",
         params=dict(name="Big objectList", prefix="BIG-", count=3, n_ai=60, n_ao=20, n_av=40, n_bi=40, n_bo=20,
                     n_bv=10, n_msv=10, max_apdu="480", segmentation="No")),
    dict(title="Duplicate network number (two routers)",
         problem="A second router on another UDP port announces the same network number as an existing "
                 "routed group (create a routed group with network 1001 first).",
         expect="Detect two routers for one network and report it; do not flip-flop between them.",
         params=dict(name="Duplicate net", prefix="DUP-", count=5, first_net=1001, router_port=-1)),
]


# Every scenario builds a mixed site: half the devices behind a router (MS/TP style), half directly on
# BACnet/IP. Device faults apply to both halves; router faults (trunk speed, buffer, unreachable network,
# duplicate network number) only exist for the routed half.
for _sc in SCENARIOS:
    _sc["params"].setdefault("kind", "mixed")
    _sc["params"].setdefault("direct_pct", 50)


def _slug(title):
    return "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-").replace("--", "-")


for _sc in SCENARIOS:
    _sc.setdefault("id", _slug(_sc["title"]))

SCENARIO_BY_ID = {sc["id"]: sc for sc in SCENARIOS}

# Built-in combined scenario: every problem above at once, each in its own group.
EVERYTHING = dict(
    id="everything",
    title="Everything at once",
    problem="Every scenario below in one site: busy trunk, no-COV and mute-COV controllers, exhausted slots, "
            "per-object refusals, silent, flapping and slow devices, an unreachable network, stale points, packet "
            "loss, a large site, small APDUs and a duplicate network number. Each problem gets its own group.",
    expect="Stay stable and correct with every problem at once: no bursts, no endless retries, every "
           "healthy device and point still up to date.",
    parts=[dict(id=sc["id"], count=sc["params"].get("count", 10)) for sc in SCENARIOS],
)
