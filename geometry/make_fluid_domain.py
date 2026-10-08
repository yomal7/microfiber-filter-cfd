"""
Build the water volume (fluid domain) of the v7 filter for OpenFOAM.

Run with FreeCAD's command-line Python:
    freecadcmd geometry/make_fluid_domain.py

Writes case/constant/triSurface/fluid.stl with four named regions
(walls, inlet, outlet, overflow), in metres.

What is simplified compared with the CAD model:
  * threads, wall thickness, sensors and fittings are not part of the water
  * the coarse mesh and the fabric bucket are NOT cut out here; they are
    porous zones selected later by topoSet (see case/system/topoSetDict)
  * cloth straps are left out; the top 4 mm of the bucket is clamped in the
    plastic collar, so water cannot slip past the fabric there
  * the flow sensor is a straight 16 mm pipe (its loss is in the model)
All dimensions follow microfiber_filter_v7.py (mm).
"""

import os
import sys
import math

import FreeCAD as App
import Part
import MeshPart

V = App.Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "case", "constant", "triSurface")

# Allow a different outlet bore for design studies: OUTLET_ID=20 freecadcmd ...
OUTLET_ID = float(os.environ.get("OUTLET_ID", "16"))

# ---------------- dimensions from v7 (mm) ----------------
STAGE2_R = 90.5 / 2.0
FLOOR_Z = 5.0
DOME_H = 15.0
DOME_GUTTER = 3.0
COLLAR_Z0 = 138.0            # top 4 mm of the bucket is clamped in the collar
COLLAR_R = 36.5               # inner face of the 4.5 mm fabric zone
RING_Z0 = 150.0
RING_R = 84.0 / 2.0            # plastic flange + rubber ring bore
MESH_Z0 = 156.0
MESH_R = 90.0 / 2.0
MESH_TOP = 160.0               # mesh zone 156-160 (4 mm equivalent)
STAGE1_R = 102.0 / 2.0
LID_Z = 231.0

INLET_Z = 210.0
INLET_R = 21.0 / 2.0
INLET_END_X = -111.0           # 60 mm of straight pipe outside the wall

OVERFLOW_X = 30.0
OVERFLOW_R = 16.0 / 2.0
OVERFLOW_TOP = 252.0           # spill level

OUTLET_Z = FLOOR_Z + 16.0 / 2.0  # axis stays where v7 puts it (13 mm)
OUTLET_R = OUTLET_ID / 2.0
OUTLET_END_X = 160.0


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def cyl_x(r, x0, x1, z):
    return Part.makeCylinder(r, x1 - x0, V(x0, 0, z), V(1, 0, 0))


pieces = [
    cyl_z(STAGE2_R, FLOOR_Z, COLLAR_Z0),
    cyl_z(COLLAR_R, COLLAR_Z0 - 0.5, RING_Z0),
    cyl_z(RING_R, RING_Z0 - 0.5, MESH_Z0),
    cyl_z(MESH_R, MESH_Z0 - 0.5, MESH_TOP),
    cyl_z(STAGE1_R, MESH_TOP - 0.5, LID_Z),
    cyl_x(INLET_R, INLET_END_X, -STAGE1_R + 5.0, INLET_Z),
    cyl_z(OVERFLOW_R, LID_Z - 5.0, OVERFLOW_TOP, x=OVERFLOW_X),
    cyl_x(OUTLET_R, STAGE2_R - 5.0, OUTLET_END_X, OUTLET_Z),
]

fluid = pieces[0]
for p in pieces[1:]:
    fluid = fluid.fuse(p)
fluid = fluid.removeSplitter()

# Domed floor (same construction as v7): solid cap removed from the water
dome_a = STAGE2_R - DOME_GUTTER
dome_R = (dome_a ** 2 + DOME_H ** 2) / (2.0 * DOME_H)
sphere = Part.makeSphere(dome_R, V(0, 0, FLOOR_Z + DOME_H - dome_R))
dome = sphere.common(cyl_z(dome_a, FLOOR_Z - 1.0, FLOOR_Z + DOME_H + 1.0))
fluid = fluid.cut(dome).removeSplitter()

if not fluid.isValid() or len(fluid.Solids) != 1:
    sys.exit("fluid domain is not a single valid solid")

print(f"fluid volume: {fluid.Volume/1e6:.3f} L, faces: {len(fluid.Faces)}")


def classify(face):
    c = face.CenterOfMass
    if face.Surface.__class__.__name__ == "Plane":
        if abs(c.x - INLET_END_X) < 1e-3:
            return "inlet"
        if abs(c.x - OUTLET_END_X) < 1e-3:
            return "outlet"
        if abs(c.z - OVERFLOW_TOP) < 1e-3:
            return "overflow"
    return "walls"


groups = {"walls": [], "inlet": [], "outlet": [], "overflow": []}
for f in fluid.Faces:
    groups[classify(f)].append(f)

for name in ("inlet", "outlet", "overflow"):
    if len(groups[name]) != 1:
        sys.exit(f"expected exactly one {name} face, found {len(groups[name])}")

os.makedirs(OUT_DIR, exist_ok=True)
path = os.path.join(OUT_DIR, "fluid.stl")

with open(path, "w") as fh:
    for name, faces in groups.items():
        shell = Part.makeCompound(faces)
        mesh = MeshPart.meshFromShape(Shape=shell, LinearDeflection=0.05,
                                      AngularDeflection=math.radians(8),
                                      Relative=False)
        fh.write(f"solid {name}\n")
        for facet in mesh.Facets:
            n = facet.Normal
            fh.write(f"  facet normal {n.x:.6e} {n.y:.6e} {n.z:.6e}\n    outer loop\n")
            for p in facet.Points:
                fh.write(f"      vertex {p[0]/1000:.7e} {p[1]/1000:.7e} {p[2]/1000:.7e}\n")
            fh.write("    endloop\n  endfacet\n")
        fh.write(f"endsolid {name}\n")
        print(f"  {name}: {len(faces)} faces, {mesh.CountFacets} triangles")

print("written", path)
