"""One run of the task-lease protocol with the injected fault, written as a log (JSON Lines).

Two workers share one task under a lease of 3 ticks. Worker 1 claims the task, then pauses for
5 ticks (the injected fault), so its lease runs out. Worker 2 claims the task under the next
lease, works for a tick and commits its result. Worker 1 then resumes, unaware, and commits its
own result under its old lease.

The unfenced store accepts that late commit and overwrites worker 2's result; the fenced store
refuses it. `conformance/late-commit-unfenced.jsonl` and `late-commit-fenced.jsonl` are the two
logs this writes.
"""

from sim.lease import LeaseStore, Log


def run(fenced):
    log = Log()
    store = LeaseStore(tasks=[1], max_epoch=2, ttl=3, fenced=fenced, log=log)
    log.lines.append({"state": store.initial_state()})
    first = store.claim(1)
    store.advance(5)  # worker 1 pauses: the injected fault
    second = store.claim(2)
    store.advance(1)  # worker 2 works
    store.commit(2, second)
    store.commit(1, first)  # worker 1 resumes and commits late
    return log.text()
