"""Asking a person a yes-or-no question. Spec section 12.3.

Every mutation this CLI performs on somebody's behalf is confirmed before it
happens, and there are two ways that confirmation can fail to arrive. A person
can read the question and say no. Or nobody can be there to read it: the
command was piped from ``/dev/null``, run from a cron entry, or launched by a
host agent that gave it no terminal, and the prompt reaches end of input
without ever being seen. A person can also press ``Ctrl-C`` in the middle of
reading it, which is a third way of not answering.

All three are the same outcome, and it is a usage outcome rather than a defect.
Nothing went wrong inside the product: it asked, and it was not told to go
ahead. Reported as a defect — which is what an unhandled ``Abort`` escaping to
the CLI's error boundary becomes — an unanswerable prompt tells a caller that
Techtree is broken and gives it an exit code that means so, when the true
answer is that it needs a flag.

That is the whole of what lives here. This module asks the question and says
whether it was told to go ahead; what a "no" means, which error it is, and what
the person should be told belong to the command that had something to confirm,
because only that command knows what was about to happen.

The default is always no. A prompt whose default is yes turns a stray newline
into consent, and nothing in this product is worth confirming by accident.
"""

from __future__ import annotations

import typer

__all__ = ["confirmed"]


def confirmed(question: str) -> bool:
    """Ask ``question`` and return whether the answer was an explicit yes.

    Returns ``False`` for every way of not being told to go ahead: a person who
    typed no, a prompt that reached end of input because nothing was there to
    answer it, and a person who interrupted it. A caller that must distinguish
    "nobody can be asked" from "somebody said no" checks that before it asks —
    ``CliContext.no_input`` is that check — because by the time a prompt has
    been written there is nothing left to distinguish.
    """
    try:
        return typer.confirm(question, default=False)
    except typer.Abort:
        return False
