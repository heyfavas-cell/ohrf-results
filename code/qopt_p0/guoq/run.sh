#!/usr/bin/env bash
# Run GUOQ (wisq 0.2.7, built from the Dockerfile beside this file) on every rebased circuit, N at a time.
# usage: spikes/qopt_p0/guoq/run.sh <inputs-folder> <outputs-folder> [parallel]
# The budget is the frozen GUOQ_BUDGET_S. A circuit GUOQ fails on has no output file and is reported missing.
set -euo pipefail
abs() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }  # Docker Desktop wants C:/... from Git Bash
mkdir -p "$2"; in="$(abs "$1")"; out="$(abs "$2")"; jobs="${3:-8}"
export GUOQ_BUDGET_S="${GUOQ_BUDGET_S:-300}"
export in out
docker build -q -t ohrf-wisq:97c12a5 "$(dirname "$0")" >/dev/null
ls "$in" | sed 's/\.qasm$//' | xargs -P "$jobs" -I{} sh -c '
  MSYS_NO_PATHCONV=1 docker run --rm -v "$in:/in:ro" -v "$out:/out" ohrf-wisq:97c12a5 sh -c "
    cd /tmp && wisq /in/{}.qasm --mode opt --target_gateset IBMN --optimization_objective TWO_Q \
      --opt_timeout $GUOQ_BUDGET_S --output_path /out/{}.qasm" >"$out/{}.log" 2>&1 || echo "failed: {}"'
