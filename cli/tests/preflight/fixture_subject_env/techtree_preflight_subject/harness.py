"""A harness that completes an episode without contacting a model.

WP6a is forbidden from making real model calls, but the facts it has to prove —
that ``traces.jsonl`` grows by whole Episode records, that line order is
completion order, that a trace records ``agent.name == "subject"`` — all need a
real ``eval`` run rather than a dry run. This harness supplies one: it accepts
the interception endpoint and immediately reports success without opening it,
so the run exercises every part of the pipeline except the provider.

``TECHTREE_PREFLIGHT_STAGGER`` delays each task in reverse index order, which
makes completion order differ from task order on purpose.
"""

from __future__ import annotations

import asyncio
import os

from verifiers.v1.clients import ModelContext
from verifiers.v1.configs.harness import HarnessConfig
from verifiers.v1.harness import Harness
from verifiers.v1.runtimes import ProgramResult, Runtime
from verifiers.v1.task import TaskData
from verifiers.v1.trace import Trace

STAGGER_ENV = "TECHTREE_PREFLIGHT_STAGGER"
TASK_COUNT = 4


class StubHarnessConfig(HarnessConfig):
    pass


class StubHarness(Harness[StubHarnessConfig]):
    APPENDS_SYSTEM_PROMPT = True
    SUPPORTS_MCP = False
    SUPPORTS_RESUME = False
    EXECUTES_CODE = False
    NEEDS_CONTAINER = False

    async def setup(self, runtime: Runtime) -> None:
        return None

    async def launch(
        self,
        ctx: ModelContext,
        trace: Trace,
        runtime: Runtime,
        endpoint: str,
        secret: str,
        mcp_urls: dict[str, str],
        data: TaskData,
    ) -> ProgramResult:
        stagger = float(os.environ.get(STAGGER_ENV, "0"))
        if stagger:
            await asyncio.sleep(stagger * (TASK_COUNT - (data.idx or 0)))
        return ProgramResult(exit_code=0, stdout="", stderr="")
