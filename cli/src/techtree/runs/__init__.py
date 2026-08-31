"""The run event log, its state machine, and the store that owns both.

Spec section 18.

A run is a long-lived thing executed by a separate process, watched by a
command-line client that comes and goes. Nothing in that arrangement lets the
two share memory, so the run's history is the only thing they can both trust:
every fact about a run is first appended to ``events.jsonl`` and only then
projected into ``state.json``. The projection is a cache. The log is the truth.

Three modules divide the work:

:mod:`techtree.runs.events`
    Bytes. Appending one line durably, reading the log back, and refusing a log
    whose sequence numbers skip.

:mod:`techtree.runs.machine`
    Meaning. Which phase may follow which, and how a list of events becomes one
    ``RunState``.

:mod:`techtree.runs.store`
    Placement and mutual exclusion. Where each file lives under
    ``runs/<run-id>/``, and the per-run lock every writer passes through.

The narrative version, including heartbeat, PID, cancellation, and recovery
semantics, is in ``docs/run-state-machine.md``.
"""

from __future__ import annotations

__all__: list[str] = []
