"""Text of the 'How to use' tab."""

from __future__ import annotations


HELP_TEXT = """\
WHAT THIS IS
ENMA (Engine for Network Modeling & Automation) simulates a BACnet/IP site on one computer. Every device, router and network message follows ASHRAE 135, so
any BACnet client (a gateway, YABE, a supervisor) can discover, read, write and subscribe to it. Use it
to reproduce field problems on your desk and to check that a client handles them correctly.

QUICK START
1. Add devices (left panel, "＋ Add devices") or pick a ready-made problem in the Scenarios tab.
2. Choose the network interface at the top and press Start.
3. On the client, discover with a global Who-Is (broadcast) to port 47808 of this network.
4. Change things live: select a device, network or group in the tree.

HOW DEVICES ARE ADDRESSED
• Routed devices sit on remote networks (MS/TP style) behind a simulated BACnet router on UDP port
  47808 (or the port you choose). They answer as network:MAC, e.g. 1001:5, through the router.
  The router answers Who-Is-Router-To-Network and Initialize-Routing-Table, and announces
  I-Am-Router-To-Network when it starts.
• Direct devices each have their own UDP port on this computer's IP (47809, 47810, ...). Their
  address is IP:port. Because one IP can have only one device on 47808, the main port relays
  broadcasts (Who-Is, Who-Is-Router-To-Network) to the other ports ("Relay" switch at the top).
• Routers only forward GLOBAL broadcasts (DNET 65535) to remote networks, as real routers do. A
  local-broadcast Who-Is reaches only the direct devices.

RUNNING THE CLIENT ON THE SAME COMPUTER
Two programs cannot both own UDP 47808. Run the client on another port (e.g. 47809 is taken by
direct devices, so use 47900) and set "I-Am replies" to Unicast (default): answers then go straight
back to the client's port. Or run the client on another machine / VM on the same LAN.

STALE POINTS
Every object changes after a random wait between a low and a high limit. Mark a share of the
objects as stale (they change every e.g. 30-120 min) or frozen (never). Select objects to change
their interval, or freeze them, at any time.

COV
• Supported: SubscribeCOV listed in protocolServicesSupported; initial notification after the ack,
  then a notification when presentValue moves by covIncrement (analog) or changes (binary,
  multi-state), or statusFlags change. Lifetime 0 means indefinite (shown as INDEFINITE).
• Not supported: SubscribeCOV is not listed and is rejected (unrecognized-service).
• Never notifies: the ack is sent but no notification ever follows.
• Slot limit: Error resources / no-space-to-add-list-element when the table is full.
• Objects can refuse COV one by one: Error object / optional-functionality-not-supported.
The COV tab lists every live subscription with its remaining lifetime and notification count.

FAULTS YOU CAN SWITCH ON
Offline (silent), flapping (with or without losing subscriptions), reboot, reply delay, late I-Am,
packet loss, DeviceCommunicationControl / ReinitializeDevice from the client, deleted objects
(unknown-object), fault and out-of-service flags, priority-array commands.
Per network: MS/TP trunk time per message and router buffer (Router-Busy-To-Network when it
overflows), forced Router-Busy, unreachable network (Reject-Message-To-Network), trunk down.
Duplicate network numbers: create two routed groups on different router ports with the same
network number.

SAVING
"Save site" writes everything (devices, objects, faults) to a JSON file; "Open site" loads it.
The last site is kept automatically and can be restored with "Restore last".
"""
