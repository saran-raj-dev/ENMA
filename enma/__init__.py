"""
ENMA - Engine for Network Modeling & Automation
===============================================

BACnet site simulator.

Python 3.8+ standard library only (tkinter for the GUI).

Simulates a BACnet/IP site so BACnet client software (gateways, supervisors,
BMS front ends) can be tested against real site conditions:

  * any number of devices, created by count
  * devices directly on BACnet/IP (one UDP port each) or behind a simulated
    BACnet router on MS/TP-style networks (routed devices, DNET/DADR)
  * analog / binary / multi-state objects whose values change at a random
    interval between a low and a high limit (seconds / minutes / hours), with
    a share of "stale" points that change rarely or never
  * COV support per device (SubscribeCOV listed in protocolServicesSupported
    or not), COV slot limits, per-object COV refusal, devices that accept a
    subscription but never notify
  * faults: silent (offline) devices, flapping devices that forget their
    subscriptions, slow responders, slow Who-Is answers, packet loss
  * router faults: MS/TP trunk speed and router buffer (Router-Busy-To-Network
    when the buffer overflows), forced Router-Busy, unreachable networks
    (Reject-Message-To-Network / no route), duplicate network numbers
  * no segmentation / small max-APDU devices

Everything on the wire follows ASHRAE 135: BVLL (Annex J), NPDU (clause 6),
APDU encoding (clause 20). Services answered: Who-Is, Who-Has, ReadProperty,
ReadPropertyMultiple, WriteProperty, WritePropertyMultiple, SubscribeCOV,
DeviceCommunicationControl, ReinitializeDevice, TimeSynchronization; the
device sends I-Am, I-Have and (Un)ConfirmedCOVNotification. Network layer:
Who-Is-Router-To-Network, I-Am-Router-To-Network, Router-Busy/Available,
Reject-Message-To-Network, Initialize-Routing-Table. Foreign Device
registration is accepted.

Run:     python3 main.py            (or: python3 -m enma)
Headless (no GUI, saved site):  python3 main.py --headless site.json

Package layout
--------------
  enma/config.py              product name, version, file locations
  enma/bacnet/                protocol layer (no simulation logic)
      constants.py            enumerations and property tables
      codec.py                tag encoding / decoding, BACnet errors
      framing.py              APDU, NPDU and BVLL framing, addresses
  enma/core/                  simulation engine (no GUI code)
      model.py                objects (points) and COV subscriptions
      device/                 a simulated device
          base.py             identity, settings, life cycle (online, reboot, flapping), sending
          dispatch.py         receiving and answering APDUs, segmentation, delays, packet loss
          properties.py       object model: reading and writing properties
          services.py         confirmed services (ReadProperty, WriteProperty, SubscribeCOV, ...)
          cov.py              COV subscription table and notifications
      network.py              router networks (MS/TP trunks) and UDP endpoints
      group.py                a batch of devices created together
      templates.py            point templates and default parameters
      simulator/              the engine
          base.py             engine thread, settings, start / stop
          routing.py          BVLL / NPDU packet path, network layer messages
          scheduler.py        value changes, lifetimes, flapping
          builder.py          creating and removing groups, networks, devices, points
          operations.py       live changes requested by the user interface
          snapshots.py        read-only state for the user interface
          persistence.py      save / open a site as JSON
      scenarios.py            ready-made field problems
      util.py                 formatting and network interface helpers
  enma/gui/                   tkinter user interface
      app.py                  main window
      add_dialog.py           "Add devices" dialog
      interval_dialog.py      value change interval dialog
      views/                  detail views: welcome, device, network, group
      theme.py                colours, tooltips, shared widgets
      help_text.py            "How to use" text
  enma/headless.py            run a saved site without the GUI
  enma/app.py                 command line entry point (main)
  main.py                     boots the application
"""

from enma.config import APP_FULL_NAME, APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_FULL_NAME", "APP_VERSION"]
__version__ = APP_VERSION
