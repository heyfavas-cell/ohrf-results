"""Audit spike parameters fixed before the run (tag `audit-prereg`). Changing one after the tag voids the run."""
import math

TOOL_PINS = {"qiskit": "2.5.2", "pytket": "2.18.4", "pyzx": "0.10.7", "mqt.qcec": "3.10.2", "mqt.bench": "2.3.0"}
TOOLS = ("qiskit", "tket-swaps", "tket-noswaps", "pyzx")
QISKIT_SEED = 1
BASE_FAMILIES = ("qft", "qpeexact", "qaoa", "vqe_two_local", "graphstate", "wstate", "dj", "qnn")
BASE_SIZES = (6, 10, 14, 18, 22)
BOUNDARY_RATE = 0.5
BOUNDARY_ANGLES = tuple(
    [1e-12, 1e-9, 9.6e-05, 1e-05, 1e-04, math.pi / 4, math.pi / 2, math.pi, 3 * math.pi / 2, 2 * math.pi]
    + [2 * math.pi / 2 ** k for k in range(3, 13)]
    + [math.pi / 2 + 1e-9, math.pi / 2 - 1e-9, math.pi + 1e-9, math.pi - 1e-9]
)
RANDOM_QUBITS = (6, 20)
RANDOM_GATES = (50, 600)
SCHEDULE_SEED = 20261014
COMPUTE_CAP_S = 30 * 3600
RUN_CAP_S = 4 * 3600
WORKERS = 3
QCEC_TIMEOUT_S = 60
QCEC_HARD_WALL_S = 120
CONFIRM_RUNS = 2
DENSE_MAX_QUBITS = 10
REDUCED_MAX_GATES = 50
REDUCE_MAX_CALLS = 300
TOLERANCE = {"qiskit": 1e-05, "tket-swaps": 1e-04, "tket-noswaps": 1e-04, "pyzx": 1e-09}
FILE_BY_DAY = 10
DECIDE_DAY = 14
