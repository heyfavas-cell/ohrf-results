"""QCEC equivalence with the D-082 mapping: only unitary equivalence proves an output."""
from __future__ import annotations

import atexit
import hashlib
import multiprocessing as mp
from pathlib import Path

from spikes.qopt_p0.frozen import QCEC_HARD_WALL_S
from spikes.qopt_p0.normalise import NormaliseError, normalise

VERIFIED = {"equivalent", "equivalent_up_to_global_phase"}


def _write(workdir: Path, text: str) -> Path:
    path = Path(workdir) / f"{hashlib.sha256(text.encode()).hexdigest()[:16]}.qasm"
    path.write_text(text, encoding="utf-8")
    return path


def _serve(conn) -> None:
    """The worker: import QCEC once, then answer one check per message until told to stop."""
    from mqt import qcec
    conn.send("ready")
    while True:
        job = conn.recv()
        if job is None:
            return
        original, candidate, timeout_s, *rest = job
        try:
            config = dict(rest[0]) if rest else {}
            if "state_type" in config:  # the enum cannot cross the pipe by name
                from mqt.qcec.pyqcec import StateType
                config["state_type"] = StateType[config["state_type"]]
            conn.send(str(qcec.verify(original, candidate, timeout=timeout_s, **config)
                          .equivalence).rsplit(".", 1)[-1])
        except Exception:  # an input QCEC cannot read is an unverified output, not a crash
            conn.send("qcec_error")


class _Worker:
    """QCEC checks its own timeout only between steps, so a native call can run far past it. The check therefore
    runs in a child process that is killed at a hard wall and replaced."""

    def __init__(self, serve=_serve) -> None:
        self._serve = serve
        self._proc = None
        self._conn = None

    def _start(self) -> None:
        parent, child = mp.get_context("spawn").Pipe()
        self._proc = mp.get_context("spawn").Process(target=self._serve, args=(child,), daemon=True)
        self._proc.start()
        child.close()
        self._conn = parent
        if not parent.poll(300) or parent.recv() != "ready":
            self.stop()
            raise RuntimeError("the QCEC worker did not start")

    def stop(self) -> None:
        if self._proc is not None and self._proc.pid is not None:  # pid stays None until the process has started
            self._proc.kill()
            self._proc.join()
        self._proc = self._conn = None

    def check(self, original: Path, candidate: Path, timeout_s: float, hard_wall_s: float,
              config: dict | None = None) -> str:
        if self._proc is None or not self._proc.is_alive():
            self.stop()
            self._start()
        try:
            self._conn.send((str(original), str(candidate), timeout_s, config or {}))
            if self._conn.poll(hard_wall_s):
                return self._conn.recv()
        except (EOFError, BrokenPipeError, ConnectionResetError, OSError):  # the worker died without answering
            self.stop()
            return "worker_died"
        self.stop()  # the next call gets a fresh worker
        return "hard_timeout"


_WORKER = _Worker()
atexit.register(_WORKER.stop)


def outcome(original: str, candidate: str, *, workdir: Path, timeout_s: float,
            hard_wall_s: float = QCEC_HARD_WALL_S, config: dict | None = None) -> str:
    """The QCEC result name, `strict_parse` when either text could be read two ways (D-113), or `hard_timeout`
    when the call outlasted its hard wall (D-141)."""
    try:
        original, candidate = normalise(original), normalise(candidate)
    except NormaliseError:
        return "strict_parse"
    return _WORKER.check(_write(workdir, original), _write(workdir, candidate), timeout_s, hard_wall_s, config)


def verified(original: str, candidate: str, *, workdir: Path, timeout_s: float,
             hard_wall_s: float = QCEC_HARD_WALL_S) -> bool:
    return outcome(original, candidate, workdir=workdir, timeout_s=timeout_s, hard_wall_s=hard_wall_s) in VERIFIED
