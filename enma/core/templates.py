"""Point templates and default parameters for generated devices."""

from __future__ import annotations

from enma.bacnet.constants import AI, AO, AV, BI, BO, BV, MSI, MSV


# ════════════════════════════════════════════════════════════════════════════
#  Point templates for generated devices
# ════════════════════════════════════════════════════════════════════════════

ANALOG_TEMPLATES = {
    AI: [("Supply Air Temp", 62, 12, 22), ("Return Air Temp", 62, 20, 28), ("Mixed Air Temp", 62, 15, 26),
         ("Outside Air Temp", 62, 18, 45), ("Zone Temp", 62, 20, 27), ("Space Humidity", 29, 35, 70),
         ("Duct Static Pressure", 53, 150, 450), ("CO2 Level", 96, 400, 1200),
         ("Chilled Water Supply Temp", 62, 5, 9), ("Chilled Water Return Temp", 62, 10, 15),
         ("Filter Differential Pressure", 53, 50, 300), ("Active Power", 48, 5, 150),
         ("Supply Air Flow", 135, 800, 6000), ("Energy Meter", 19, 1000, 90000)],
    AO: [("Cooling Valve Command", 98, 0, 100), ("Heating Valve Command", 98, 0, 100),
         ("Supply Fan Speed Command", 98, 20, 100), ("Outside Air Damper Command", 98, 0, 100),
         ("VFD Frequency Reference", 27, 20, 50)],
    AV: [("Supply Air Temp Setpoint", 62, 12, 18), ("Zone Temp Setpoint", 62, 21, 26),
         ("Static Pressure Setpoint", 53, 200, 400), ("CO2 Setpoint", 96, 800, 1000),
         ("Humidity Setpoint", 29, 45, 60), ("PID Loop Output", 98, 0, 100)],
}
BINARY_TEMPLATES = {
    BI: [("Supply Fan Status", "Off", "On"), ("Filter Alarm", "Normal", "Alarm"), ("Trip Alarm", "Normal", "Tripped"),
         ("Fire Alarm Input", "Normal", "Alarm"), ("Auto/Manual Status", "Manual", "Auto"),
         ("Smoke Detector", "Normal", "Alarm"), ("Door Status", "Closed", "Open")],
    BO: [("Supply Fan Start/Stop", "Stop", "Start"), ("Pump Enable", "Off", "On"),
         ("Alarm Reset", "Normal", "Reset"), ("Lighting Relay", "Off", "On")],
    BV: [("Occupancy Override", "Unoccupied", "Occupied"), ("Schedule Enable", "Disabled", "Enabled"),
         ("Economizer Enable", "Off", "On")],
}
MULTI_TEMPLATES = {
    MSI: [("Unit Status", ["Off", "Running", "Alarm"]), ("Compressor Stage", ["Off", "Stage 1", "Stage 2", "Stage 3"])],
    MSV: [("Operating Mode", ["Off", "Cool", "Heat", "Auto"]), ("Fan Speed Mode", ["Low", "Medium", "High"]),
          ("System State", ["Stopped", "Starting", "Running", "Stopping", "Fault"])],
}

TYPE_PARAM = {AI: "n_ai", AO: "n_ao", AV: "n_av", BI: "n_bi", BO: "n_bo", BV: "n_bv", MSI: "n_msi", MSV: "n_msv"}
UNIT_SECONDS = {"seconds": 1, "minutes": 60, "hours": 3600}

DEFAULT_PARAMS = dict(
    name="Controllers", prefix="DDC-", count=10, kind="routed",
    start_instance=0, router_port=0, first_net=1001, per_net=30, first_mac=1, first_port=0,
    n_ai=4, n_ao=2, n_av=3, n_bi=3, n_bo=2, n_bv=2, n_msi=0, n_msv=1,
    chg_min=10, chg_max=60, chg_unit="seconds",
    stale_pct=0, stale_min=30, stale_max=120, stale_unit="minutes", stale_frozen=False,
    cov_inc=0.5,
    cov_pct=100, max_subs=0, refuse_pct=0, mute_pct=0,
    offline_pct=0, flap_pct=0, flap_every_min=5, flap_every_max=15, flap_off_min=30, flap_off_max=120,
    flap_clear=True,
    slow_pct=0, slow_min=500, slow_max=3000, drop_pct=0, slowwhois_pct=0, slowwhois_min=10, slowwhois_max=15,
    trunk_ms=0, buffer=0, unreachable=False, max_apdu="Auto", segmentation="Auto",
)
