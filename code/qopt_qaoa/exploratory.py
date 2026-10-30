"""Exploratory passes, tried alone on the development set only. They are not in the pool and are never counted.

The pool is fixed (plan, "The pass pool and the search") and frozen with `search_config.json`; nothing here can enter the
search, `S*`, or any outcome. Results go to their own run folder and are reported as exploratory.
"""
from __future__ import annotations

from spikes.qopt_qaoa.passes import Pass, _tket


def pool() -> dict[str, Pass]:
    def greedy(**kw):
        import pytket.passes as P
        return lambda: P.GreedyPauliSimp(**kw)

    def pauli(strat: str, cx: str):
        def make():
            import pytket.passes as P
            from pytket._tket.transform import PauliSynthStrat
            from pytket.circuit import CXConfigType
            return P.PauliSimp(getattr(PauliSynthStrat, strat), getattr(CXConfigType, cx))
        return make

    return {
        "x-greedy-reduce": _tket(greedy(only_reduce=True, depth_weight=0.0, trials=8, thread_timeout=20),
                                 accepts=("CX", "Rz", "H")),
        "x-pauli-individual-star": _tket(pauli("Individual", "Star")),
        "x-pauli-pairwise-tree": _tket(pauli("Pairwise", "Tree")),
    }
