"""
Phase 1: quick hydraulic model of the two-stage microfiber filter.

The filter is fed by the washing machine pump, but the overflow pipe at the
top is open to air. The housing can therefore never hold more pressure than
the water column up to the overflow, so the water level settles where the
losses through the filter and the outlet are balanced by gravity:

    level = discharge height + (mesh + fabric + outlet losses) / (rho g)

If that level would be above the overflow spill height, the extra water
leaves through the overflow pipe (unfiltered) and only part of the inflow
passes through the filter and the flow sensor.

Clogging c is the fraction of filter area blocked by trapped fibres
(0 = clean, 0.8 = 80 % blocked). It is applied to both stages.

Run:  python3 model/filter_model.py            (writes results/model/)
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import params as P  # noqa: E402

RHO_G = P.RHO * P.G


# ------------------------------------------------------------------
# Loss terms (Pa) for a flow q (m3/s) through the filter
# ------------------------------------------------------------------

def mesh_loss(q, clog):
    v = q / P.MESH_AREA
    zeta = P.screen_loss_coeff(P.MESH_OPEN_FRACTION * (1.0 - clog))
    return zeta * 0.5 * P.RHO * v * v


def fabric_loss(q, clog, permeability=None):
    k = permeability or P.FABRIC_PERMEABILITY
    v = q / P.BUCKET_AREA
    # blocked area: the same flow squeezes through (1 - c) of the fabric
    return P.MU * (P.BUCKET_WALL / k) * v / max(1.0 - clog, 1e-3)


def friction_factor(re, d):
    if re < 2300.0:
        return 64.0 / max(re, 1e-9)
    # Haaland
    a = (P.PIPE_ROUGHNESS / d / 3.7) ** 1.11 + 6.9 / re
    return (-1.8 * math.log10(a)) ** -2


def outlet_loss(q, outlet_d=None, k_sensor=None):
    d = outlet_d or P.OUTLET_ID
    k_sensor = P.K_FLOW_SENSOR if k_sensor is None else k_sensor
    v = q / (math.pi * d * d / 4.0)
    re = v * d / P.NU
    k_total = (P.K_OUTLET_ENTRY + k_sensor + P.K_OUTLET_EXIT
               + friction_factor(re, d) * P.OUTLET_LENGTH / d)
    return k_total * 0.5 * P.RHO * v * v


def total_loss(q, clog, **kw):
    return (mesh_loss(q, clog)
            + fabric_loss(q, clog, kw.get("permeability"))
            + outlet_loss(q, kw.get("outlet_d"), kw.get("k_sensor")))


def level_for(q, clog, **kw):
    return P.DISCHARGE_Z + total_loss(q, clog, **kw) / RHO_G


# ------------------------------------------------------------------
# Operating state for an inflow and clog level
# ------------------------------------------------------------------

def solve(q_in_lpm, clog, spill_z=None, **kw):
    spill_z = spill_z or P.OVERFLOW_SPILL_Z
    q_in = P.lpm_to_m3s(q_in_lpm)

    if level_for(q_in, clog, **kw) <= spill_z:
        q_f = q_in
    else:
        lo, hi = 0.0, q_in            # bisection for level(q_f) = spill_z
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if level_for(mid, clog, **kw) > spill_z:
                hi = mid
            else:
                lo = mid
        q_f = lo

    level = min(level_for(q_f, clog, **kw), spill_z)
    media = mesh_loss(q_f, clog) + fabric_loss(q_f, clog, kw.get("permeability"))

    # Gauge pressure each tap sees (0 when the tap is above the water)
    p1 = RHO_G * (level - P.P1_Z) if level > P.P1_Z else 0.0
    # P2 sits downstream of both filter stages
    p2 = RHO_G * (level - P.P2_Z) - media
    p2 = max(p2, 0.0)
    static_offset = RHO_G * (P.P1_Z - P.P2_Z)     # zeroed at rest, housing full
    dp_display = p1 - p2 + static_offset

    q_f_lpm = q_f * 60000.0
    return {
        "inflow_lpm": q_in_lpm,
        "clog": clog,
        "filtered_lpm": q_f_lpm,
        "overflow_lpm": max(q_in_lpm - q_f_lpm, 0.0),
        "level_mm": level * 1000.0,
        "p1_kpa": p1 / 1000.0,
        "p2_kpa": p2 / 1000.0,
        "dp_kpa": dp_display / 1000.0,         # what the LCD shows
        "media_loss_kpa": media / 1000.0,      # true loss across the filter
        "mesh_loss_pa": mesh_loss(q_f, clog),
        "fabric_loss_pa": fabric_loss(q_f, clog, kw.get("permeability")),
        "outlet_loss_pa": outlet_loss(q_f, kw.get("outlet_d"), kw.get("k_sensor")),
        "p1_submerged": level > P.P1_Z,
        "overflowing": q_in_lpm - q_f_lpm > 1e-6,
    }


def overflow_onset_clog(q_in_lpm, **kw):
    """Smallest clog level at which the filter starts to overflow."""
    if solve(q_in_lpm, 0.0, **kw)["overflowing"]:
        return 0.0
    lo, hi = 0.0, 0.999
    if not solve(q_in_lpm, hi, **kw)["overflowing"]:
        return 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if solve(q_in_lpm, mid, **kw)["overflowing"]:
            hi = mid
        else:
            lo = mid
    return hi


def lcd_lines(state):
    """The four 20-character lines of the LCD for one state.

    When the water is below the P1 tap, P1 sits in air: the firmware should
    show dashes for P1 and dP instead of a misleading number.
    """
    def kpa(v):
        return f"{v:5.2f} kPa"
    wet = state.get("p1_submerged", True)
    lines = [
        f"P1 IN : {kpa(state['p1_kpa'])}" if wet else "P1 IN : --.-- (dry)",
        f"P2 OUT: {kpa(state['p2_kpa'])}",
        f"dP    : {kpa(state['dp_kpa'])}" if wet else "dP    : --.--",
        f"FLOW  : {state['filtered_lpm']:4.1f} L/min",
    ]
    return [line[:20].ljust(20) for line in lines]


if __name__ == "__main__":
    for d in (0.016, 0.020):
        print(f"\nOutlet bore {d*1000:.0f} mm")
        for q in P.Q_SWEEP_LPM:
            for c in P.CLOG_SWEEP:
                s = solve(q, c, outlet_d=d)
                print(f"Q={q:4.1f} c={c:.1f} level={s['level_mm']:6.1f} mm "
                      f"P1={s['p1_kpa']:.2f} P2={s['p2_kpa']:.2f} "
                      f"dP={s['dp_kpa']:.2f} media={s['media_loss_kpa']:.3f} "
                      f"Qf={s['filtered_lpm']:.1f} ov={s['overflow_lpm']:.1f}")
            print(f"   overflow onset clog at {q} L/min: "
                  f"{overflow_onset_clog(q, outlet_d=d):.2f}")