# ENMA: Engine for Network Modeling & Automation

ENMA simulates a BACnet/IP site so you can test BACnet clients (gateways, supervisors, YABE) against
real site conditions. It needs Python 3.8+ and uses only the standard library plus tkinter.

```
python3 main.py                          # GUI
python3 main.py --headless site.json     # no GUI, runs a saved site
python3 -m enma                          # same as main.py
```

Only one ENMA runs per computer: starting it again brings the running window to the front. Closing
the window (or Cmd+Q / Ctrl+C / kill) stops the simulation, frees every port, saves the site and ends
the process.

The full user manual is in [`docs/user-manual.html`](docs/user-manual.html).

## Project layout

```
main.py                 boots the application
enma/
  config.py             product name, version, file locations
  app.py                command line entry point
  headless.py           run a saved site without the GUI
  bacnet/               protocol layer: constants, encoding, APDU/NPDU/BVLL framing
  core/                 simulation engine (no GUI code)
    device/             a simulated device: dispatch, properties, services, COV
    simulator/          the engine: routing, scheduler, builder, operations, snapshots, persistence
    network.py          router networks (MS/TP trunks) and UDP endpoints
    model.py            objects (points) and COV subscriptions
    group.py, templates.py, scenarios.py, util.py
  gui/                  tkinter user interface: main window, dialogs, detail views, theme
```

The engine runs in its own asyncio thread and has no GUI dependency, so it can be driven by other
front ends or by test scripts (`from enma.core.simulator import Simulator`).

## What it simulates

- **Devices by count**, either:
  - behind a simulated BACnet router on MS/TP-style networks (`network:MAC`), or
  - directly on BACnet/IP, one UDP port each, or
  - mixed: a percentage direct and the rest routed. Every scenario is half routed, half direct.
- **Objects**: AI, AO, AV, BI, BO, BV, MSI and MSV, with priority arrays on the commandable ones.
- **Value changes** at a random interval between a low and a high limit (seconds, minutes or hours).
  A chosen share of points can be stale (change rarely) or frozen (never change).
- **COV**, set per device:
  - supported, or not supported (SubscribeCOV is missing from protocolServicesSupported);
  - a slot limit per device;
  - per-object refusal;
  - "accepts but never notifies".
- **Device faults**: silent (offline), flapping (optionally a reboot that forgets subscriptions),
  reply delay, late I-Am, packet loss, deleted objects. Clients can also use
  DeviceCommunicationControl and ReinitializeDevice.
- **Router faults**:
  - MS/TP trunk time and router buffer. When the buffer overflows the router sends
    Router-Busy-To-Network.
  - Forced Router-Busy.
  - Unreachable network (Reject-Message-To-Network).
  - Trunk down.
  - Duplicate network numbers.
- **Limits**: no segmentation and small max APDU.

The **Scenarios** tab has "Everything at once" (all problems in one site), a **Custom scenario** builder
(tick problems, set device counts, save the combination for reuse), and single problems in one click: Router-Busy from a burst, no-COV
controllers, exhausted COV slots, mute COV, silent controllers, flapping, unknown route, slow
devices, stale points, packet loss, large site, small APDU and duplicate network.

Everything on the wire follows ASHRAE 135, so if a client misbehaves against ENMA, the fault is in
the client.

## Tips

- Only one program can own UDP 47808 on a computer. If the client runs on this same computer, give
  the client another port (e.g. 47900) and keep **I-Am replies = Unicast**.
- Direct devices use the ports after 47808. With **Relay broadcasts** on, a global Who-Is sent to 47808
  finds every device.
- Routers only pass **global** broadcasts (DNET 65535) to remote networks, as real routers do.
- Sites are saved as JSON (**Save site / Open site**). The last site is kept in `~/.enma/` and can be
  reloaded with **Restore last**.
