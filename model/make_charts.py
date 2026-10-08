"""
Charts, LCD previews and the viewer lookup table from the Phase 1 model.

Run:  python3 model/make_charts.py        (writes results/model/)
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import FancyBboxPatch       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import params as P                                   # noqa: E402
import filter_model as M                             # noqa: E402

OUT = os.path.join(ROOT, "results", "model")
os.makedirs(OUT, exist_ok=True)

# ---------------- style ----------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]   # blue, orange, aqua
WARN = "#e34948"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2,
    "axes.titlecolor": INK,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 14,
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.frameon": False,
    "legend.fontsize": 11,
    "font.size": 11,
    "lines.linewidth": 2.2,
})

CURRENT = {"outlet_d": P.OUTLET_ID}
CLOG_LABELS = {0.0: "Clean", 0.5: "50 % clogged", 0.8: "80 % clogged"}


def frange(a, b, step):
    n = int(round((b - a) / step))
    return [a + i * step for i in range(n + 1)]


def note(fig, text):
    import textwrap
    fig.text(0.012, 0.012, "\n".join(textwrap.wrap(text, 150)), fontsize=9.5,
             color=MUTED, ha="left", va="bottom", linespacing=1.4)


ASSUMPTION_NOTE = ("Model assumptions: water at 40 °C, free discharge at the outlet, "
                   "fabric permeability 2e-11 m² and flow-sensor loss K = 1 (both assumed).")


# ------------------------------------------------------------------
# 1. Where the available pressure goes at 15 L/min
# ------------------------------------------------------------------

def chart_pressure_budget():
    q = P.lpm_to_m3s(P.Q_DESIGN_LPM)
    available = M.RHO_G * (P.OVERFLOW_SPILL_Z - P.DISCHARGE_Z) / 1000.0

    rows = []
    for label, d in [("Current design\n16 mm outlet", 0.016),
                     ("Option\n20 mm outlet", 0.020)]:
        rows.append((label,
                     M.outlet_loss(q, d) / 1000.0,
                     M.fabric_loss(q, 0.0) / 1000.0,
                     M.mesh_loss(q, 0.0) / 1000.0))

    fig, ax = plt.subplots(figsize=(10, 4.6))
    parts = [("Outlet pipe + flow sensor", SERIES[0]),
             ("Fabric bucket (clean)", SERIES[1]),
             ("Coarse mesh (clean, under 0.01 kPa)", SERIES[2])]
    for i, (label, outlet, fabric, mesh) in enumerate(rows):
        y = len(rows) - 1 - i
        left = 0.0
        for (name, color), val in zip(parts, (outlet, fabric, mesh)):
            ax.barh(y, val, left=left, height=0.5, color=color,
                    edgecolor=SURFACE, linewidth=2,
                    label=name if i == 0 else None)
            left += val
        spare = available - left
        ax.text(max(left, available) + 0.06, y, f"{left:.2f} kPa used" +
                (f"  ·  {spare:.2f} kPa left for clogging" if spare > 0
                 else "  ·  over the limit"),
                va="center", fontsize=11, color=INK)

    ax.axvline(available, color=WARN, linewidth=2, linestyle="--")
    ax.text(available - 0.04, len(rows) - 0.45, f"Overflow limit {available:.2f} kPa",
            color=INK, fontsize=11, ha="right", va="bottom")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in reversed(rows)])
    ax.set_xlim(0, available * 1.75)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlabel("Pressure loss at 15 L/min (kPa)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Where the pressure goes at 15 L/min")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=3)
    fig.subplots_adjust(left=0.17, right=0.97, top=0.86, bottom=0.33)
    note(fig, "The open overflow pipe caps the pressure at the water column "
              "height (spill level 252 mm to outlet 13 mm). " +
              "Fabric permeability and sensor loss are assumed.")
    fig.savefig(os.path.join(OUT, "01_pressure_budget_15lpm.png"), dpi=170)
    plt.close(fig)


# ------------------------------------------------------------------
# 2. Water level in the housing vs inflow
# ------------------------------------------------------------------

def chart_water_level():
    qs = frange(1.0, 25.0, 0.25)
    fig, ax = plt.subplots(figsize=(10, 6))

    refs = [
        (P.OVERFLOW_SPILL_Z * 1000, "Overflow spills (252 mm)"),
        (P.STAGE1_Z_TOP_INSIDE * 1000, "Lid (231 mm)"),
        (P.P1_Z * 1000, "P1 tap (180 mm)"),
        (P.MESH_Z * 1000, "Coarse mesh (157 mm)"),
    ]
    for z, label in refs:
        ax.axhline(z, color=MUTED, linewidth=1, linestyle=":")
        ax.text(1.2, z + 2, label, color=INK_2, fontsize=10, va="bottom")

    for color, clog in zip(SERIES, P.CLOG_SWEEP):
        levels = [M.solve(q, clog, **CURRENT)["level_mm"] for q in qs]
        ax.plot(qs, levels, color=color, label=CLOG_LABELS[clog])

    ax.axvspan(P.Q_DESIGN_LPM - 0.15, P.Q_DESIGN_LPM + 0.15, color=GRID, zorder=0)
    ax.text(P.Q_DESIGN_LPM, 12, "15 L/min", ha="center", color=INK_2, fontsize=10)
    ax.set_xlim(0, 25)
    ax.set_ylim(0, 280)
    ax.set_xlabel("Inflow from the washing machine (L/min)")
    ax.set_ylabel("Water level above housing bottom (mm)")
    ax.set_title("Water level inside the filter (current design, 16 mm outlet)")
    ax.legend(loc="lower right")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.16)
    note(fig, "Below the P1 line the P1 sensor is in air and reads zero. "
              "At the overflow line extra water leaves unfiltered. " + ASSUMPTION_NOTE)
    fig.savefig(os.path.join(OUT, "02_water_level_vs_flow.png"), dpi=170)
    plt.close(fig)


# ------------------------------------------------------------------
# 3. What the sensors see as the filter clogs (15 L/min)
# ------------------------------------------------------------------

def chart_clogging(design, tag, title_suffix):
    cs = frange(0.0, 0.9, 0.01)
    states = [M.solve(P.Q_DESIGN_LPM, c, **design) for c in cs]
    x = [c * 100 for c in cs]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8.2), sharex=True,
                                   gridspec_kw={"height_ratios": [1.15, 1]})
    for color, key, label in [(SERIES[0], "p1_kpa", "P1 (before filter)"),
                              (SERIES[1], "p2_kpa", "P2 (after filter)"),
                              (SERIES[2], "dp_kpa", "dP across filter")]:
        ax1.plot(x, [s[key] for s in states], color=color, label=label)
    ax1.set_ylabel("Sensor reading (kPa)")
    ax1.set_ylim(bottom=0)
    ax1.legend(loc="upper left", ncol=3)
    ax1.set_title(f"What the sensors read as the filter clogs ({title_suffix})")

    ax2.plot(x, [s["filtered_lpm"] for s in states], color=SERIES[0],
             label="Filtered (flow sensor)")
    ax2.plot(x, [s["overflow_lpm"] for s in states], color=SERIES[1],
             label="Overflow (unfiltered)")
    ax2.set_ylabel("Flow (L/min)")
    ax2.set_ylim(0, P.Q_DESIGN_LPM * 1.12)
    ax2.set_xlabel("Clogging: share of filter area blocked (%)")
    ax2.legend(loc="center left")

    # where P1 is above the water, its reading (and dP) is not meaningful
    dry = [xi for xi, s in zip(x, states) if not s["p1_submerged"]]
    if dry:
        ax1.axvspan(min(dry), max(dry), color=GRID, alpha=0.6, zorder=0)
        ax1.text((min(dry) + max(dry)) / 2, ax1.get_ylim()[1] * 0.62,
                 "Water below the P1 tap:\nP1 reads 0, dP is not valid",
                 ha="center", color=INK_2, fontsize=10.5)

    onset = M.overflow_onset_clog(P.Q_DESIGN_LPM, **design) * 100
    for ax in (ax1, ax2):
        ax.axvline(onset, color=WARN, linestyle="--", linewidth=1.6)
    label = ("Overflowing even when clean" if onset < 0.5
             else f"Overflow starts at {onset:.0f} %")
    right = onset > 60
    ax2.text(onset + (-1 if right else 1), P.Q_DESIGN_LPM * 1.02, label,
             color=INK, fontsize=10.5, va="bottom", ha="right" if right else "left")
    ax2.set_xlim(0, 90)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.93, bottom=0.14, hspace=0.12)
    note(fig, "Inflow 15 L/min. dP has the 1.49 kPa height difference between "
              "P1 and P2 removed. " + ASSUMPTION_NOTE)
    fig.savefig(os.path.join(OUT, f"03_clogging_15lpm_{tag}.png"), dpi=170)
    plt.close(fig)


# ------------------------------------------------------------------
# 4. Design lever: outlet bore
# ------------------------------------------------------------------

def chart_outlet_bore():
    qs = frange(5.0, 25.0, 0.25)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for color, d in zip(SERIES, (0.016, 0.020, 0.025)):
        onset = [M.overflow_onset_clog(q, outlet_d=d) * 100 for q in qs]
        ax.plot(qs, onset, color=color, label=f"{d*1000:.0f} mm outlet")
    ax.axvline(P.Q_DESIGN_LPM, color=MUTED, linestyle=":", linewidth=1)
    ax.set_xlim(5, 25)
    ax.set_ylim(0, 100)
    ax.text(15.2, 3, "15 L/min", color=INK_2, fontsize=10)
    ax.set_xlabel("Inflow from the washing machine (L/min)")
    ax.set_ylabel("Clogging when overflow starts (%)")
    ax.set_title("How much clogging the filter takes before it overflows")
    ax.legend(loc="lower left")
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.21)
    note(fig, "Higher is better: the filter keeps filtering all the water for longer. "
              + ASSUMPTION_NOTE)
    fig.savefig(os.path.join(OUT, "04_overflow_margin_vs_outlet.png"), dpi=170)
    plt.close(fig)


# ------------------------------------------------------------------
# LCD previews (20 x 4 character display)
# ------------------------------------------------------------------

def draw_lcd(lines, caption, path):
    fig = plt.figure(figsize=(6.4, 2.75))
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 43)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((2, 7), 96, 34, boxstyle="round,pad=0,rounding_size=2",
                                facecolor="#1e2a1f", edgecolor="#1e2a1f"))
    ax.add_patch(FancyBboxPatch((6, 10), 88, 28, boxstyle="round,pad=0,rounding_size=1",
                                facecolor="#2f55d4", edgecolor="#2448b8", linewidth=2))
    for i, line in enumerate(lines):
        ax.text(8.5, 33.5 - i * 6.6, line.replace(" ", " "),
                fontsize=15.5, family="DejaVu Sans Mono", color="#f2f6ff",
                va="center", ha="left")
    ax.text(50, 3, caption, ha="center", va="center", fontsize=10.5, color=INK_2)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def lcd_previews():
    states = []
    for clog in P.CLOG_SWEEP:
        s = M.solve(P.Q_DESIGN_LPM, clog, **CURRENT)
        lines = M.lcd_lines(s)
        tag = f"{int(clog*100):02d}"
        draw_lcd(lines, f"15 L/min inflow · {CLOG_LABELS[clog].lower()}",
                 os.path.join(OUT, f"lcd_15lpm_clog{tag}.png"))
        states.append({"inflow_lpm": P.Q_DESIGN_LPM, "clog": clog,
                       "lines": lines, "state": s})
    with open(os.path.join(OUT, "lcd_states.json"), "w") as fh:
        json.dump(states, fh, indent=2)
    with open(os.path.join(OUT, "lcd_states.txt"), "w") as fh:
        for st in states:
            fh.write(f"Inflow {st['inflow_lpm']} L/min, clogging {st['clog']*100:.0f} %\n")
            fh.write("+" + "-" * 20 + "+\n")
            for line in st["lines"]:
                fh.write("|" + line + "|\n")
            fh.write("+" + "-" * 20 + "+\n\n")


# ------------------------------------------------------------------
# Lookup table for the web viewer (inflow x clogging)
# ------------------------------------------------------------------

def lookup_table():
    qs = frange(0.0, 25.0, 0.5)
    cs = frange(0.0, 0.95, 0.05)
    keys = ["filtered_lpm", "overflow_lpm", "level_mm", "p1_kpa", "p2_kpa",
            "dp_kpa", "media_loss_kpa"]
    table = {k: [] for k in keys}
    for q in qs:
        rows = {k: [] for k in keys}
        for c in cs:
            s = M.solve(max(q, 1e-6), c, **CURRENT)
            for k in keys:
                rows[k].append(round(s[k], 4))
        for k in keys:
            table[k].append(rows[k])
    out = {
        "description": "Phase 1 hydraulic model of the v7 filter. "
                       "Index as table[key][inflow_index][clog_index].",
        "inflow_lpm": qs,
        "clog": [round(c, 2) for c in cs],
        "assumptions": {
            "water_temp_c": 40,
            "fabric_permeability_m2": P.FABRIC_PERMEABILITY,
            "flow_sensor_K": P.K_FLOW_SENSOR,
            "outlet_bore_mm": P.OUTLET_ID * 1000,
            "overflow_spill_mm": P.OVERFLOW_SPILL_Z * 1000,
        },
        "table": table,
    }
    with open(os.path.join(OUT, "lookup_table.json"), "w") as fh:
        json.dump(out, fh)


def summary():
    rows = []
    for q in P.Q_SWEEP_LPM:
        for c in P.CLOG_SWEEP:
            s = M.solve(q, c, **CURRENT)
            rows.append(s)
    with open(os.path.join(OUT, "summary_table.csv"), "w") as fh:
        keys = ["inflow_lpm", "clog", "filtered_lpm", "overflow_lpm", "level_mm",
                "p1_kpa", "p2_kpa", "dp_kpa", "media_loss_kpa"]
        fh.write(",".join(keys) + "\n")
        for r in rows:
            fh.write(",".join(f"{r[k]:.3f}" for k in keys) + "\n")


if __name__ == "__main__":
    chart_pressure_budget()
    chart_water_level()
    chart_clogging(CURRENT, "16mm", "current design, 16 mm outlet")
    chart_clogging({"outlet_d": 0.020}, "20mm", "option: 20 mm outlet")
    chart_outlet_bore()
    lcd_previews()
    lookup_table()
    summary()
    print("written to", OUT)
    for f in sorted(os.listdir(OUT)):
        print("  ", f)
