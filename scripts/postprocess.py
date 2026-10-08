"""
Read a finished OpenFOAM run and produce sensor values, the LCD screen and
pictures.

    python3 scripts/postprocess.py runs/<case> [--out results/cfd/<case>]

Pressure: the solver works without gravity, so the water weight is added
here:  P = rho * p + rho * g * (z_outlet - z) + flow-sensor loss.
"""

import argparse
import json
import math
import os
import sys

os.environ.setdefault("VTK_DEFAULT_OPENGL_WINDOW", "vtkOSOpenGLRenderWindow")

import numpy as np
import pyvista as pv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "model"))

import params as P                 # noqa: E402
import filter_model as M           # noqa: E402
from make_charts import draw_lcd   # noqa: E402

pv.OFF_SCREEN = True

PROBES = {
    "P1":            (-0.0480, 0.0, 0.1800),
    "P2":            (-0.0420, 0.0, 0.0280),
    "above_mesh":    (0.0, 0.0, 0.1700),
    "below_mesh":    (0.0, 0.0, 0.1450),
    "inside_bucket": (0.0, 0.0, 0.0900),
    "outside_bucket": (0.0435, 0.0, 0.0900),
}

BG = "#fcfcfb"
INK = "#0b0b0b"


def load(case, which=-1):
    foam = os.path.join(case, "case.foam")
    open(foam, "a").close()
    reader = pv.POpenFOAMReader(foam)
    times = [t for t in reader.time_values if t > 0]
    if len(times) < abs(which):
        return None, None, None
    reader.set_active_time_value(times[which])
    reader.cell_to_point_creation = True
    data = reader.read()
    return times[which], data["internalMesh"], data["boundary"]


def sample(internal, points):
    pts = pv.PolyData(np.array(points, dtype=float))
    s = pts.sample(internal)
    return s["p"], s["U"], s["vtkValidPointMask"]


def patch_flow(boundary, name, axis):
    patch = boundary[name].compute_cell_sizes(length=False, volume=False)
    u = patch.cell_data["U"][:, axis]
    return float(np.sum(u * patch.cell_data["Area"]))


def bucket_outline():
    """Outline of the porous zones on the y = 0 section (for drawing)."""
    lines = []
    r_o, r_i = 0.041, 0.0365
    z0, z1, zb = 0.040, 0.138, 0.0445
    for s in (-1, 1):
        lines.append([(s * r_o, 0, z0), (s * r_o, 0, z1)])
        lines.append([(s * r_i, 0, zb), (s * r_i, 0, z1)])
    lines.append([(-r_o, 0, z0), (r_o, 0, z0)])
    lines.append([(-r_i, 0, zb), (r_i, 0, zb)])
    lines.append([(-0.045, 0, 0.156), (0.045, 0, 0.156)])
    lines.append([(-0.045, 0, 0.160), (0.045, 0, 0.160)])
    return lines


def add_lines(pl, lines, color="#3a3a38", width=2):
    for a, b in lines:
        pl.add_mesh(pv.Line(a, b), color=color, line_width=width)


SENSOR_TAPS = {"P1": (-0.0510, 0.0, 0.1800), "P2": (-0.04525, 0.0, 0.0280)}


def section_plot(internal, boundary, field, title, cmap, clim, unit, path, scale=1.0):
    sl = internal.slice(normal="y", origin=(0, 0, 0.1))
    sl[field + "_plot"] = sl.point_data[field] * scale
    pl = pv.Plotter(off_screen=True, window_size=(1500, 1450))
    pl.set_background(BG)
    pl.add_mesh(sl, scalars=field + "_plot", cmap=cmap, clim=clim, lighting=False,
                show_scalar_bar=True,
                scalar_bar_args={"title": unit, "color": INK, "vertical": True,
                                 "position_x": 0.86, "position_y": 0.22,
                                 "height": 0.55, "width": 0.05,
                                 "title_font_size": 22, "label_font_size": 20,
                                 "fmt": "%.2f"})
    walls = boundary["walls"].slice(normal="y", origin=(0, 0, 0.1))
    pl.add_mesh(walls, color="#3a3a38", line_width=3)
    add_lines(pl, bucket_outline(), color="#6b6a66", width=2)

    taps = pv.PolyData(np.array(list(SENSOR_TAPS.values())))
    pl.add_mesh(taps, color="#e34948", point_size=18, render_points_as_spheres=True)

    labels = {
        "Inlet": (-0.100, 0, 0.226),
        "Overflow": (0.040, 0, 0.250),
        "Outlet": (0.125, 0, 0.028),
        "P1": (-0.068, 0, 0.180),
        "P2": (-0.062, 0, 0.028),
        "Coarse mesh": (0.058, 0, 0.158),
        "Fabric bucket": (0.050, 0, 0.090),
    }
    pl.add_point_labels(np.array(list(labels.values())), list(labels.keys()),
                        font_size=22, text_color=INK, shape=None,
                        show_points=False, always_visible=True)
    pl.add_text(title, position="upper_left", font_size=15, color=INK)
    pl.enable_parallel_projection()
    pl.camera.focal_point = (0.020, 0.0, 0.122)
    pl.camera.position = (0.020, -1.0, 0.122)
    pl.camera.up = (0, 0, 1)
    pl.camera.parallel_scale = 0.150
    pl.screenshot(path)
    pl.close()


def compute_streamlines(internal, boundary):
    """Flow paths of water entering through the inlet."""
    c = np.array(boundary["inlet"].center)
    seeds = pv.Disc(center=c, inner=0.0, outer=0.0095, normal=(1, 0, 0),
                    r_res=4, c_res=16)
    lines = internal.streamlines_from_source(
        seeds, vectors="U", integration_direction="forward",
        max_length=3.0, initial_step_length=0.2, max_steps=40000,
        terminal_speed=1e-6)
    lines["speed"] = np.linalg.norm(lines["U"], axis=1)
    return lines


SPEED_BAR = {"title": "Speed (m/s)", "color": INK, "title_font_size": 22,
             "label_font_size": 20, "fmt": "%.2f", "position_x": 0.25,
             "position_y": 0.04, "width": 0.5}
CAMERA_3D = [(-0.42, -0.52, 0.36), (0.02, 0.0, 0.125), (0, 0, 1)]


def streamline_plot(boundary, lines, title, path):
    pl = pv.Plotter(off_screen=True, window_size=(1600, 1350))
    pl.set_background(BG)
    pl.add_mesh(boundary["walls"], color="#c9d3df", opacity=0.13,
                smooth_shading=True)
    if lines.n_points:
        pl.add_mesh(lines.tube(radius=0.0006), scalars="speed", cmap="Blues",
                    clim=(0.0, 0.3), show_scalar_bar=True,
                    scalar_bar_args=SPEED_BAR)
    pl.add_text(title, position="upper_left", font_size=16, color=INK)
    pl.camera_position = CAMERA_3D
    pl.screenshot(path)
    pl.close()


def split_lines(lines):
    """Each streamline as (times, points, speeds), ordered along the path."""
    out = []
    conn = lines.lines
    t_all = lines["IntegrationTime"]
    i = 0
    while i < len(conn):
        n = conn[i]
        ids = conn[i + 1:i + 1 + n]
        i += n + 1
        t = t_all[ids]
        if n < 2 or t[-1] - t[0] <= 0:
            continue
        order = np.argsort(t)
        ids = ids[order]
        out.append((t_all[ids] - t_all[ids][0], lines.points[ids], lines["speed"][ids]))
    return out


def flow_video(boundary, lines, lcd, title, path, seconds=12, fps=24):
    """Water particles moving along the CFD flow paths, in real time."""
    paths = split_lines(lines)
    if not paths:
        return False
    total_time = sum(p[0][-1] for p in paths)
    spacing = max(0.25, total_time / 12000.0)       # keep about 12k particles

    particles = []                                   # (path index, phase)
    for j, (t, _, _) in enumerate(paths):
        for k in range(int(np.ceil(t[-1] / spacing))):
            particles.append((j, k * spacing))
    path_idx = np.array([p[0] for p in particles])
    phase = np.array([p[1] for p in particles])

    def positions(time_s):
        pts = np.empty((len(particles), 3))
        spd = np.empty(len(particles))
        for j, (t, xyz, sp) in enumerate(paths):
            sel = path_idx == j
            tau = (time_s + phase[sel]) % t[-1]
            for a in range(3):
                pts[sel, a] = np.interp(tau, t, xyz[:, a])
            spd[sel] = np.interp(tau, t, sp)
        return pts, spd

    pts, spd = positions(0.0)
    cloud = pv.PolyData(pts)
    cloud["speed"] = spd

    pl = pv.Plotter(off_screen=True, window_size=(1280, 960))
    pl.set_background(BG)
    pl.add_mesh(boundary["walls"], color="#c9d3df", opacity=0.13, smooth_shading=True)
    pl.add_mesh(lines, color="#9fb4cc", opacity=0.18, line_width=1)
    pl.add_mesh(cloud, scalars="speed", cmap="Blues", clim=(0.0, 0.3),
                point_size=6, render_points_as_spheres=True,
                show_scalar_bar=True, scalar_bar_args=SPEED_BAR)
    pl.add_text(title, position="upper_left", font_size=15, color=INK)
    pl.add_text("\n".join(lcd), position="upper_right", font="courier",
                font_size=13, color="#1f3fbf")
    clock = pl.add_text("t = 0.0 s (real time)", position="lower_left",
                        font_size=12, color=INK)
    pl.camera_position = CAMERA_3D
    pl.open_movie(path, framerate=fps, quality=5)
    frames = seconds * fps
    for f in range(frames):
        t_now = f / fps
        pts, spd = positions(t_now)
        cloud.points = pts
        cloud["speed"] = spd
        clock.SetText(0, f"t = {t_now:4.1f} s (real time)")
        pl.camera.azimuth = 25.0 * f / frames - 12.5
        pl.write_frame()
    pl.close()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--out")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()

    case = os.path.abspath(args.case)
    meta = json.load(open(os.path.join(case, "case.json")))
    out = args.out or os.path.join(ROOT, "results", "cfd", meta["name"])
    os.makedirs(out, exist_ok=True)

    time, internal, boundary = load(case)
    names = list(PROBES)
    p_kin, U, valid = sample(internal, [PROBES[n] for n in names])
    probe = {n: {"p_kin": float(p_kin[i]), "speed": float(np.linalg.norm(U[i])),
                 "valid": bool(valid[i])} for i, n in enumerate(names)}

    q_out = patch_flow(boundary, "outlet", 0)
    q_in = abs(patch_flow(boundary, "inlet", 0))
    q_ov = patch_flow(boundary, "overflow", 2)
    v_out = q_out / P.OUTLET_AREA
    sensor_loss = P.K_FLOW_SENSOR * 0.5 * P.RHO * v_out ** 2

    def gauge(n):
        z = PROBES[n][2]
        return P.RHO * probe[n]["p_kin"] + P.RHO * P.G * (P.OUTLET_Z - z) + sensor_loss

    p1, p2 = max(gauge("P1"), 0.0), max(gauge("P2"), 0.0)
    dp = P.RHO * (probe["P1"]["p_kin"] - probe["P2"]["p_kin"])
    mesh_loss = P.RHO * (probe["above_mesh"]["p_kin"] - probe["below_mesh"]["p_kin"])
    fabric_loss = P.RHO * (probe["inside_bucket"]["p_kin"] - probe["outside_bucket"]["p_kin"])

    state = {
        "p1_kpa": p1 / 1000, "p2_kpa": p2 / 1000, "dp_kpa": dp / 1000,
        "filtered_lpm": q_out * 60000,
    }
    lines = M.lcd_lines(state)

    log = open(os.path.join(case, "log.simpleFoam")).read()
    converged = "SIMPLE solution converged" in log

    # Convergence check: compare the sensor pressures with the previous save
    change = None
    prev_time, prev_internal, _ = load(case, -2)
    if prev_internal is not None:
        pp, _, _ = sample(prev_internal, [PROBES["P1"], PROBES["P2"],
                                          PROBES["inside_bucket"], PROBES["outside_bucket"]])
        now = [probe[n]["p_kin"] for n in ("P1", "P2", "inside_bucket", "outside_bucket")]
        change = {
            "compared_iterations": [float(prev_time), float(time)],
            "P1_change_pa": float(P.RHO * (now[0] - pp[0])),
            "P2_change_pa": float(P.RHO * (now[1] - pp[1])),
            "fabric_loss_change_pa": float(P.RHO * ((now[2] - now[3]) - (pp[2] - pp[3]))),
        }

    summary = {
        "case": meta["name"], "inflow_lpm": meta["inflow_lpm"], "clog": meta["clog"],
        "mesh": meta["mesh"], "iterations": float(time), "converged": converged,
        "convergence_check": change,
        "cells": int(internal.n_cells),
        "flows_lpm": {"inlet": q_in * 60000, "outlet": q_out * 60000,
                      "overflow": q_ov * 60000},
        "sensors_kpa": {"P1": p1 / 1000, "P2": p2 / 1000, "dP": dp / 1000},
        "losses_pa": {"coarse_mesh": mesh_loss, "fabric_bucket": fabric_loss,
                      "flow_sensor_added": sensor_loss},
        "probes": probe,
        "lcd": lines,
        "model_prediction": {k: meta["model_prediction"][k] for k in
                             ("p1_kpa", "p2_kpa", "dp_kpa", "filtered_lpm",
                              "overflow_lpm", "mesh_loss_pa", "fabric_loss_pa")},
    }
    with open(os.path.join(out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    clog_txt = "clean filter" if meta["clog"] == 0 else f"{meta['clog']*100:.0f} % clogged"
    tag = f"{meta['inflow_lpm']:g} L/min, {clog_txt}"
    draw_lcd(lines, f"CFD · {tag}", os.path.join(out, "lcd.png"))

    if not args.no_images:
        section_plot(internal, boundary, "U", f"Water speed, centre section ({tag})",
                     "Blues", (0.0, 0.2), "Speed (m/s)",
                     os.path.join(out, "speed_section.png"))
        internal.point_data["Umag"] = np.linalg.norm(internal.point_data["U"], axis=1)
        internal.point_data["p_pa"] = internal.point_data["p"] * P.RHO / 1000.0
        section_plot(internal, boundary, "p_pa",
                     f"Pressure loss, centre section ({tag})",
                     "Oranges", (0.0, float(internal.point_data["p_pa"].max())),
                     "kPa\n(water weight\nremoved)",
                     os.path.join(out, "pressure_section.png"))
        lines3d = compute_streamlines(internal, boundary)
        streamline_plot(boundary, lines3d, f"Flow paths from the inlet ({tag})",
                        os.path.join(out, "streamlines_3d.png"))
        if not args.no_video:
            flow_video(boundary, lines3d, lines, f"Water flow ({tag})",
                       os.path.join(out, "flow.mp4"))

    print(json.dumps({k: summary[k] for k in
                      ("case", "converged", "convergence_check", "iterations",
                       "cells", "flows_lpm",
                       "sensors_kpa", "losses_pa", "lcd")}, indent=2))


if __name__ == "__main__":
    main()
