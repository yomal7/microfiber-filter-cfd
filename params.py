"""
Shared design and physics parameters for the microfiber filter simulations.

Geometry comes from the FreeCAD model (microfiber_filter_v7.py, mm there,
metres here). Physics values marked ASSUMED are estimates; replace them
with measured values when the team has them.
"""

import math

# ------------------------------------------------------------------
# Water (washing machine drain water, about 40 degC)
# Research brief: 30-60 degC, 985-995 kg/m3, 0.5-0.8 mPa.s
# ------------------------------------------------------------------
RHO = 992.2          # kg/m3
MU = 0.653e-3        # Pa.s
NU = MU / RHO        # m2/s
G = 9.81             # m/s2

# ------------------------------------------------------------------
# Operating point and sweep
# ------------------------------------------------------------------
Q_DESIGN_LPM = 15.0
Q_SWEEP_LPM = [5.0, 10.0, 15.0, 20.0, 25.0]
CLOG_SWEEP = [0.0, 0.5, 0.8]          # fraction of filter area blocked


def lpm_to_m3s(q_lpm):
    return q_lpm / 60000.0


# ------------------------------------------------------------------
# Geometry from v7 (all heights measured from the bottom of Stage 2)
# ------------------------------------------------------------------
STAGE1_ID = 0.102
STAGE1_Z_TOP_INSIDE = 0.231          # underside of the lid
STAGE2_ID = 0.0905
FLOOR_RIM_Z = 0.005                  # lowest point inside (gutter)
RING_ID = 0.084                      # rubber ring / plastic flange bore

INLET_ID = 0.021
INLET_Z = 0.210

MESH_OPEN_D = 0.090                  # coarse mesh open diameter
MESH_Z = 0.157

BUCKET_OD = 0.082                    # fabric bucket
BUCKET_BOTTOM_Z = 0.040
BUCKET_TOP_Z = 0.142
BUCKET_WALL = 0.0012                 # fabric thickness

OUTLET_ID = 0.016
OUTLET_Z = 0.013                     # outlet axis
OUTLET_LENGTH = 0.115                # housing wall to pipe end

OVERFLOW_ID = 0.016
OVERFLOW_X = 0.030
OVERFLOW_ELBOW_Z = 0.260             # centre of the bend above the lid
# Water starts to spill once it reaches the floor of the sideways run
OVERFLOW_SPILL_Z = OVERFLOW_ELBOW_Z - OVERFLOW_ID / 2.0      # 0.252

P1_Z = 0.180
P2_Z = 0.028


def circle_area(d):
    return math.pi * d * d / 4.0


MESH_AREA = circle_area(MESH_OPEN_D)
BUCKET_AREA = (circle_area(BUCKET_OD)
               + math.pi * BUCKET_OD * (BUCKET_TOP_Z - BUCKET_BOTTOM_Z))
OUTLET_AREA = circle_area(OUTLET_ID)

# ------------------------------------------------------------------
# Coarse mesh: 316 SS woven, 40 mesh (380 um aperture, 254 um wire)
# ------------------------------------------------------------------
MESH_APERTURE = 380e-6
MESH_WIRE = 254e-6
MESH_OPEN_FRACTION = (MESH_APERTURE / (MESH_APERTURE + MESH_WIRE)) ** 2   # 0.36


def screen_loss_coeff(open_fraction):
    """Idelchik loss coefficient for a woven wire screen (high Re)."""
    f = max(open_fraction, 1e-4)
    return 1.3 * (1.0 - f) + (1.0 / f - 1.0) ** 2


# ------------------------------------------------------------------
# Fine fabric bucket: Darcy permeability. ASSUMED.
# 2e-11 m2 sits between a needle felt (~5e-12) and an open woven
# filter cloth (~1e-10). Replace with the falling-head test result.
# ------------------------------------------------------------------
FABRIC_PERMEABILITY = 2.0e-11        # m2, ASSUMED

# ------------------------------------------------------------------
# Outlet path losses (based on velocity in the 16 mm outlet)
# ------------------------------------------------------------------
K_OUTLET_ENTRY = 0.5                 # sharp-edged pipe entry
K_FLOW_SENSOR = 1.0                  # ASSUMED, full-bore turbine sensor
K_OUTLET_EXIT = 1.0                  # free discharge (velocity head lost)
PIPE_ROUGHNESS = 1.5e-6              # smooth plastic

# Filtered water is assumed to discharge freely at the outlet level
# (to a floor drain). No goose-neck.
DISCHARGE_Z = OUTLET_Z
