"""The detached Techtree run worker. Spec section 19, PR8 §8.9-§8.10.

One process, one run, no supervisor. The worker is launched by
:class:`~techtree.runs.launcher.WorkerLauncher` in its own session so that it
outlives the command that started it, and everything it learns about the run
it is executing goes into the run's journal rather than into a terminal
somebody may already have closed.

:mod:`techtree.worker.main` is the argument parser. :mod:`techtree.worker.
execute` is the process: it announces itself, keeps a heartbeat, installs the
signal handlers that make cancellation cooperative, hands the work to a
:class:`~techtree.runs.executor.RunExecutor`, and makes sure the run ends in a
terminal state no matter how the work ended.
"""

from __future__ import annotations

__all__: list[str] = []
