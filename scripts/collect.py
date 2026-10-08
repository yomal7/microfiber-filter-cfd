"""
Combine all CFD runs into one table, compare them with the quick model and
write the data file the web viewer uses.

    python3 scripts/collect.py          (reads results/cfd/*/summary.json)
"""

import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "model"))

import params as P                                 # noqa: E402
import filter_model as M                           # noqa: E402
from make_charts import SERIES, INK_2, note        # noqa: E402  (also sets style)

CFD = os.path.join(ROOT, "results", "cfd")


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(CFD, "*", "summary.json"))):
        s = json.load(open(path))
        rows.append(s)
    if not rows:
        sys.exit("no CFD results found")

    rows.sort(key=lambda r: (r["clog"], r["inflow_lpm"]))
    keys = ["inflow_lpm", "clog", "converged", "cells", "outlet_lpm", "overflow_lpm",
            "P1_kpa", "P2_kpa", "dP_kpa", "mesh_loss_pa", "fabric_loss_pa",
            "model_dP_kpa", "model_fabric_loss_pa"]
    with open(os.path.join(CFD, "sweep.csv"), "w") as fh:
        fh.write(",".join(keys) + "\n")
        for r in rows:
            vals = [r["inflow_lpm"], r["clog"], r["converged"], r["cells"],
                    r["flows_lpm"]["outlet"], r["flows_lpm"]["overflow"],
                    r["sensors_kpa"]["P1"], r["sensors_kpa"]["P2"], r["sensors_kpa"]["dP"],
                    r["losses_pa"]["coarse_mesh"], r["losses_pa"]["fabric_bucket"],
                    r["model_prediction"]["dp_kpa"], r["model_prediction"]["fabric_loss_pa"]]
            fh.write(",".join(f"{v:.4f}" if isinstance(v, float) else str(v)
                              for v in vals) + "\n")

    # CFD vs quick model: pressure loss across the filter media
    fig, ax = plt.subplots(figsize=(10, 6))
    for color, clog in zip(SERIES, P.CLOG_SWEEP):
        pts = [r for r in rows if abs(r["clog"] - clog) < 1e-6]
        if not pts:
            continue
        q = [r["flows_lpm"]["outlet"] for r in pts]
        loss = [(r["losses_pa"]["coarse_mesh"] + r["losses_pa"]["fabric_bucket"]) / 1000
                for r in pts]
        ax.plot(q, loss, "o", color=color, markersize=9,
                label=f"CFD, {int(clog*100)} % clogged")
        qs = [0.5 * i for i in range(1, 51)]
        model = [(M.mesh_loss(P.lpm_to_m3s(x), clog) + M.fabric_loss(P.lpm_to_m3s(x), clog))
                 / 1000 for x in qs]
        ax.plot(qs, model, color=color, linewidth=1.6, alpha=0.8)
    ax.set_xlim(0, 26)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Flow through the filter (L/min)")
    ax.set_ylabel("Pressure loss across mesh + fabric (kPa)")
    ax.set_title("CFD check of the quick model")
    ax.legend(loc="upper left")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.16)
    note(fig, "Dots: OpenFOAM runs. Lines: quick model. Same assumed fabric "
              "permeability in both, so this checks the flow paths, not the fabric value.")
    fig.savefig(os.path.join(CFD, "cfd_vs_model.png"), dpi=170)
    plt.close(fig)

    viewer = {
        "description": "OpenFOAM sweep of the v7 filter (sensor values in kPa, flows in L/min).",
        "runs": [{"inflow_lpm": r["inflow_lpm"], "clog": r["clog"],
                  "outlet_lpm": round(r["flows_lpm"]["outlet"], 3),
                  "overflow_lpm": round(r["flows_lpm"]["overflow"], 3),
                  "P1": round(r["sensors_kpa"]["P1"], 3),
                  "P2": round(r["sensors_kpa"]["P2"], 3),
                  "dP": round(r["sensors_kpa"]["dP"], 3),
                  "lcd": r["lcd"]} for r in rows],
    }
    with open(os.path.join(CFD, "viewer_data.json"), "w") as fh:
        json.dump(viewer, fh, indent=2)
    # Readable summary for GitHub
    md = ["# CFD results", "",
          "Each row is one OpenFOAM run. Sensor values are what the LCD would show; "
          "flows are what leaves through the outlet (filtered) and the overflow (unfiltered). "
          "Pictures and summary.json for each run are in the folder of the same name; "
          "videos are in the `videos` artifact of the Actions run.", "",
          "| Inflow (L/min) | Clogging | P1 (kPa) | P2 (kPa) | dP (kPa) | Filtered (L/min) "
          "| Overflow (L/min) | Fabric loss (Pa) | Converged* | Folder |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(rows, key=lambda r: (r["inflow_lpm"], r["clog"])):
        chk = r.get("convergence_check") or {}
        drift = max(abs(chk.get("P1_change_pa", 0)), abs(chk.get("P2_change_pa", 0))) \
            if chk else None
        conv = "yes" if r["converged"] else (f"drift {drift:.0f} Pa" if drift is not None else "no")
        md.append(f"| {r['inflow_lpm']:g} | {r['clog']*100:.0f} % | {r['sensors_kpa']['P1']:.2f} "
                  f"| {r['sensors_kpa']['P2']:.2f} | {r['sensors_kpa']['dP']:.2f} "
                  f"| {r['flows_lpm']['outlet']:.1f} | {r['flows_lpm']['overflow']:.1f} "
                  f"| {r['losses_pa']['fabric_bucket']:.0f} | {conv} | [{r['case']}]({r['case']}/) |")
    md += ["", "*Converged: the solver met its residual targets, or else how much P1/P2 still "
           "changed over the last quarter of the iterations.", "",
           "![CFD check of the quick model](cfd_vs_model.png)"]
    with open(os.path.join(CFD, "README.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")

    print(f"collected {len(rows)} runs")
    print(open(os.path.join(CFD, "sweep.csv")).read())


if __name__ == "__main__":
    main()
