"""The runner's commands, run as root on the machine by the machine scripts.

  python -m awb_runner setup <harness_id>
      Installs the agent for the baseline (Harbor's setup) and prints its version.
  python -m awb_runner version <harness_id>
      Prints the installed agent's version, asked as the tested account.
  python -m awb_runner turn <harness_id> <turn_dir> <wall_cap_seconds> <resume_session_id | ->
      Hands <turn_dir>/prompt.txt to the agent: a new conversation with "-", otherwise the attempt's conversation
      continued. Copies the agent's output to stream.jsonl and its trajectory to trajectory.json, and exits with the
      exit code of the first command Harbor reported as failed (124 when the wall cap ran out), 1 when the adapter
      itself failed, or 0.
  python -m awb_runner transcript <turn_dir>
      Writes transcript.md, turn-summary.json and tool-calls.json from the turn's trajectory.
"""
import asyncio
import shutil
import sys
import traceback
from pathlib import Path

from harbor.agents.installed.base import NonZeroAgentExitCodeError
from harbor.models.agent.context import AgentContext

from . import transcript
from .machine import Machine
from .roster import LOGS, ROSTER, agent


async def setup(harness_id: str) -> None:
    tested = agent(harness_id)
    await tested.setup(Machine())
    print(await version_of(harness_id))


async def version_of(harness_id: str) -> str:
    tested = agent(harness_id)
    result = await Machine().exec(tested.get_version_command(), timeout_sec=60)
    if result.return_code != 0:
        raise RuntimeError(f"the version command failed: {result.stdout}{result.stderr}")
    return tested.parse_version(result.stdout)


async def turn(harness_id: str, turn_dir: Path, wall_cap: int, resume: str) -> int:
    tested = agent(harness_id)
    output = LOGS / ROSTER[harness_id].output
    for stale in (output, LOGS / "trajectory.json"):
        stale.unlink(missing_ok=True)

    machine = Machine(wall_cap=wall_cap)
    # Harbor raises on a failed command without its return code, and the adapter's clean-up runs after it, so the
    # failing command's code is kept as it is raised.
    failed: list[int] = []
    harbor_exec = tested._exec

    async def recorded_exec(*args, **kwargs):
        try:
            return await harbor_exec(*args, **kwargs)
        except NonZeroAgentExitCodeError:
            failed.append(machine.last_return_code)
            raise

    tested._exec = recorded_exec
    instruction = (turn_dir / "prompt.txt").read_text()
    context = AgentContext()
    try:
        if resume == "-":
            await tested.run(instruction, machine, context)
        else:
            tested.resume_session_id = resume
            await tested.resume(instruction, machine, context)
        code = 0
    except Exception:
        traceback.print_exc()
        code = failed[0] if failed else 1

    tested.populate_context_post_run(context)
    for source, target in ((output, "stream.jsonl"), (LOGS / "trajectory.json", "trajectory.json")):
        if source.exists():
            shutil.copy(source, turn_dir / target)
    return code


def main(argv: list[str]) -> int:
    match argv:
        case ["setup", harness_id]:
            asyncio.run(setup(harness_id))
        case ["version", harness_id]:
            print(asyncio.run(version_of(harness_id)))
        case ["turn", harness_id, turn_dir, wall_cap, resume]:
            return asyncio.run(turn(harness_id, Path(turn_dir), int(wall_cap), resume))
        case ["transcript", turn_dir]:
            transcript.write(Path(turn_dir))
        case _:
            print(__doc__, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
