"""
Create one OpenFOAM run from the case template.

    python3 scripts/setup_case.py --q 15 --clog 0.5 --mesh coarse
    python3 scripts/setup_case.py --q 15 --clog 0.5 --mesh-from runs/mesh_normal

Fills in the flow rate, clogging (porous resistances), overflow split and
mesh size. The overflow split comes from the Phase 1 model: if the filter
cannot pass all the inflow, the excess leaves through the overflow pipe.
"""

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "model"))

import params as P            # noqa: E402
import filter_model as M      # noqa: E402

TEMPLATE = os.path.join(ROOT, "case")

MESH_ZONE_L = 0.0040          # coarse mesh zone thickness (m)
FABRIC_ZONE_L = 0.0045        # fabric zone thickness (m)

# name: (background cell size m, surface level, porous zone level, iterations)
MESHES = {
    "coarse": (0.0040, 1, 1, 800),
    "normal": (0.0030, 1, 1, 1500),
    "fine":   (0.0025, 2, 2, 2000),
}

BOX = (0.280, 0.110, 0.254)   # blockMesh box size (m)


def case_name(q, clog):
    return f"q{q:04.1f}_c{int(round(clog * 100)):02d}".replace(".", "p")


def porous_coeffs(clog):
    open_f = P.MESH_OPEN_FRACTION * (1.0 - clog)
    mesh_f = P.screen_loss_coeff(open_f) / MESH_ZONE_L
    fab_d = P.BUCKET_WALL / (P.FABRIC_PERMEABILITY * FABRIC_ZONE_L) / max(1.0 - clog, 1e-3)
    return 0.0, mesh_f, fab_d


def fill(text, values):
    for key, val in values.items():
        text = text.replace(f"@@{key}@@", str(val))
    if "@@" in text:
        start = text.index("@@")
        raise ValueError(f"unfilled placeholder near: {text[start:start+30]}")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", type=float, default=P.Q_DESIGN_LPM, help="inflow, L/min")
    ap.add_argument("--clog", type=float, default=0.0, help="0 = clean, 0.8 = 80%% blocked")
    ap.add_argument("--mesh", choices=MESHES, default="normal")
    ap.add_argument("--mesh-from", help="reuse constant/polyMesh from this case")
    ap.add_argument("--nprocs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", help="run directory (default runs/<name>)")
    args = ap.parse_args()

    name = case_name(args.q, args.clog)
    out = args.out or os.path.join(ROOT, "runs", name)
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(TEMPLATE, out)

    h, surf_level, zone_level, iters = MESHES[args.mesh]
    state = M.solve(args.q, args.clog)
    q_in = P.lpm_to_m3s(args.q)
    q_ov = P.lpm_to_m3s(state["overflow_lpm"])

    if q_ov > 1e-9:
        overflow_u = (
            "        type            flowRateInletVelocity;   // negative = outflow\n"
            f"        volumetricFlowRate constant {-q_ov:.6e};\n"
            "        extrapolateProfile no;\n"
            "        value           uniform (0 0 0);")
    else:
        overflow_u = "        type            noSlip;   // standing water column, no flow"

    mesh_d, mesh_f, fab_d = porous_coeffs(args.clog)
    values = {
        "END_ITER": iters, "WRITE_INT": iters // 4,
        "NX": round(BOX[0] / h), "NY": round(BOX[1] / h), "NZ": round(BOX[2] / h),
        "SURF_LEVEL": surf_level, "ZONE_LEVEL": zone_level,
        "NPROCS": args.nprocs,
        "MESH_D": f"{mesh_d:.6e}", "MESH_F": f"{mesh_f:.6e}", "FAB_D": f"{fab_d:.6e}",
        "NU": f"{P.NU:.6e}",
        "Q_IN": f"{q_in:.6e}",
        "OVERFLOW_U": overflow_u,
    }

    for dirpath, _, files in os.walk(out):
        for fname in files:
            if fname.endswith(".stl") or fname.endswith(".eMesh"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path) as fh:
                text = fh.read()
            if "@@" in text:
                with open(path, "w") as fh:
                    fh.write(fill(text, values))

    if args.mesh_from:
        src = os.path.join(args.mesh_from, "constant", "polyMesh")
        shutil.copytree(src, os.path.join(out, "constant", "polyMesh"))

    meta = {
        "name": name,
        "inflow_lpm": args.q,
        "clog": args.clog,
        "mesh": args.mesh,
        "model_prediction": state,
        "porous": {"mesh_f": mesh_f, "fabric_d": fab_d},
        "assumptions": {
            "fabric_permeability_m2": P.FABRIC_PERMEABILITY,
            "fabric_thickness_m": P.BUCKET_WALL,
            "flow_sensor_K": P.K_FLOW_SENSOR,
            "water_nu": P.NU, "water_rho": P.RHO,
        },
    }
    with open(os.path.join(out, "case.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print(out)


if __name__ == "__main__":
    main()
