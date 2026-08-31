# 0004 — Engine installs build in place, not via temp-dir rename

Status: binding. Deviates deliberately from spec §20.3 step 9 (build in a
temporary directory, atomically rename to the final digest path).

Why: a Python virtual environment records its own absolute location
(script shebangs, editable-install paths). An environment built elsewhere
and renamed into place is broken — the managed `validate` executable does
not launch and the reference package no longer imports. This was verified
empirically during PR9, not assumed.

Replacement protocol, preserving the original invariant ("a partial
directory must never count as installed"):

1. Installs are serialized by a global engine-install lock.
2. The engine is built directly at its final digest path.
3. `installed.json` (the completion marker) is written last.
4. Nothing is treated as installed unless the marker exists and the
   live-environment verification query matched the descriptor.
5. A failed or interrupted install removes the directory; a test kills an
   install mid-flight and asserts the directory is gone.

Consequence for readers of spec §20.3: steps 5 and 9 of the install
algorithm are replaced by the protocol above; every other step stands.
