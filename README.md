# Microfiber filter: flow simulation

Simulations for the two-stage microfiber filter (v8 design: 110 mm Stage 1
housing screwed onto the narrower Stage 2 housing, coarse mesh, fabric
bucket, pressure sensors P1/P2, flow sensor, overflow pipe on top).

There are two parts:

| Part | What it does | Where |
|---|---|---|
| Quick model | Hand-calculation model of the whole filter: water level, P1, P2, dP, flow and overflow for any inflow and clogging level. Runs in seconds. | `model/` |
| CFD | OpenFOAM simulation of the water flow through the real geometry, with the mesh and fabric as porous zones. Runs on GitHub Actions for 5 flow rates × 3 clogging levels. | `geometry/`, `case/`, `scripts/` |

Results are written to `results/` (the Actions workflow commits them there).

## How the filter works hydraulically

The overflow pipe on top is open to air, so the housing can never hold more
pressure than the water column up to the overflow (spill level 252 mm above
the housing bottom). Any extra pump pressure simply pushes water out of the
overflow. The water inside settles at the level where gravity balances the
losses through the mesh, the fabric and the outlet:

```
water level = outlet height + (mesh + fabric + outlet losses) / (rho g)
```

If that level would be above the overflow, the extra inflow leaves through
the overflow pipe (unfiltered) and the flow sensor reads less than the inflow.

The LCD shows:

```
P1 IN :  x.xx kPa      pressure before the filter
P2 OUT:  x.xx kPa      pressure after the filter
dP    :  x.xx kPa      P1 - P2 with the 152 mm height difference removed
FLOW  : xx.x L/min     filtered flow (outlet flow sensor)
```

## Assumptions to replace with measurements

| Value | Used | Why it matters | How to measure |
|---|---|---|---|
| Fabric permeability | 2e-11 m² | Sets the fabric pressure loss | Falling-head test below |
| Flow sensor loss | K = 1 | Big share of the outlet loss | Sensor datasheet, or measure dP across it |
| Discharge | Free outlet at 13 mm height, no goose-neck | Sets the available head | Match the real installation |
| Water | 40 °C | Viscosity | - |
| Clogging | Fraction of filter area blocked (same for both stages) | Scales the media resistance | Compare with dP logged over real washes |

**Falling-head test for the fabric:** clamp a piece of the fabric over the end
of a vertical pipe (for example 50 mm PVC), fill the pipe with water and time
how long the level takes to fall from height H1 to H2. Then

```
k = mu * t * ln(H1 / H2) / (rho * g * T)
```

with `mu` = 0.00065 Pa·s (40 °C water; 0.001 at 20 °C), `t` = fabric
thickness (m), `rho g` = 9730 N/m³ and `T` = measured time (s). Put the
result in `params.py` as `FABRIC_PERMEABILITY` and rerun.

## Running on GitHub Actions (recommended)

1. Push this repo to GitHub (public repo, so Actions minutes are free).
2. The push itself starts the **CFD sweep** workflow with the `normal` mesh.
   To start it by hand: **Actions → CFD sweep → Run workflow**, pick the mesh
   size (`coarse` ≈ 10 min total, a quick test; `normal` ≈ 30–40 min, for the
   report; `fine` is much slower) and press **Run workflow**.
3. Watch the jobs: *Quick model*, *Mesh*, 15 *Q=… clog=…* jobs side by side,
   then *Collect and commit results*.
4. When it finishes:
   * pictures and readings are committed to `results/` (open
     `results/cfd/README.md` on GitHub for the table of all runs),
   * the videos are in the run's **Artifacts** section at the bottom of the run
     page: download `videos` (one `.mp4` per run). `all-results` has everything.

Each CFD run folder (`results/cfd/q15p0_c50` = 15 L/min, 50 % clogged) holds:

| File | What it is |
|---|---|
| `summary.json` | P1, P2, dP, flows, losses, convergence check |
| `lcd.png` | The 20 × 4 LCD as it would read |
| `speed_section.png` | Water speed on a vertical cut through the middle |
| `pressure_section.png` | Pressure on the same cut (water weight removed, so the losses show) |
| `streamlines_3d.png` | 3D flow paths from the inlet |
| `flow.mp4` (artifact only) | 12 s real-time animation of water particles with the LCD readings |

## Data for the web viewer

`scripts/collect.py` also writes `results/viewer/`: one JSON file per run
(the flow paths traced from the inlet, the LCD lines, the flows) and an
`index.json`. Copy that folder into the viewer repo as `public/simulation/`
to update its **Flow simulation** mode:

```bash
rm -rf ../microfiber-filter-viewer/public/simulation
cp -r results/viewer ../microfiber-filter-viewer/public/simulation
```

## Running locally

Quick model (needs Python with matplotlib):

```bash
python3 model/make_charts.py        # charts, LCD previews, lookup table
```

CFD (Ubuntu 24.04; about 8 GB RAM is enough for the coarse mesh):

```bash
sudo apt install openfoam libosmesa6
pip install pyvista matplotlib imageio imageio-ffmpeg
python3 scripts/setup_case.py --q 15 --clog 0 --mesh coarse --out runs/test
scripts/run_case.sh runs/test               # about 10 min on 2 cores
python3 scripts/postprocess.py runs/test    # writes results/cfd/q15p0_c00/
```

The fluid domain STL is built from the v8 dimensions with FreeCAD
(`freecadcmd geometry/make_fluid_domain.py`; for a 20 mm outlet run it with `OUTLET_ID=20`
and set `OUTLET_ID = 0.020` in `params.py` too). The STL is committed, so FreeCAD is not needed to run the CFD. Open any
run folder in ParaView (`case.foam`) to explore the results yourself.

## What is simplified

* Threads, wall thickness, sensors and fittings are not part of the water volume.
* The coarse mesh is a 4 mm porous disc with the loss of a 40-mesh 316 SS
  screen. The 1.2 mm fabric is a 4.5 mm porous shell with the same total
  resistance. The top 4 mm of the bucket is clamped in the plastic collar.
* Cloth straps are left out. The flow sensor is a straight pipe; its loss is
  added to the sensor readings afterwards.
* Steady flow, housing full of water, k-omega SST turbulence model.
  Gravity is added to the pressure afterwards (single-phase flow, so this is exact).
