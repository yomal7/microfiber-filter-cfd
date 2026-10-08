#!/usr/bin/env bash
# Mesh (if needed) and solve one case.   Usage: scripts/run_case.sh runs/<case>
# NPROCS=n sets the core count; MESH_ONLY=1 stops after meshing.
set -euo pipefail

CASE="$1"

# Ubuntu's openfoam package works once it knows its install folder
if [ -z "${WM_PROJECT_DIR:-}" ] && [ -d /usr/share/openfoam/etc ]; then
    export WM_PROJECT_DIR=/usr/share/openfoam
fi
NPROCS="${NPROCS:-$(nproc)}"
cd "$CASE"

log() { echo "[$(date +%H:%M:%S)] $*"; }

if [ ! -f constant/polyMesh/owner ] || [ ! -d constant/polyMesh/sets ]; then
    log "background mesh"
    blockMesh > log.blockMesh 2>&1
    log "feature edges"
    surfaceFeatureExtract > log.surfaceFeatureExtract 2>&1
    log "snappyHexMesh"
    snappyHexMesh -overwrite > log.snappyHexMesh 2>&1
    log "porous zones"
    topoSet > log.topoSet 2>&1
    checkMesh > log.checkMesh 2>&1 || true
    grep -E "cells:|Mesh OK|Failed" log.checkMesh || true
else
    log "reusing mesh"
fi

if [ "${MESH_ONLY:-0}" = "1" ]; then
    log "mesh only, stopping here"
    exit 0
fi

# clear any old decomposition
rm -rf processor*
log "simpleFoam on $NPROCS cores"
if [ "$NPROCS" -gt 1 ]; then
    decomposePar -force > log.decomposePar 2>&1
    mpirun --allow-run-as-root --oversubscribe -np "$NPROCS" \
        simpleFoam -parallel > log.simpleFoam 2>&1
    reconstructPar -latestTime > log.reconstructPar 2>&1
    rm -rf processor*
else
    simpleFoam > log.simpleFoam 2>&1
fi
grep -E "SIMPLE solution converged|^End" log.simpleFoam | tail -2 || true
log "done"
