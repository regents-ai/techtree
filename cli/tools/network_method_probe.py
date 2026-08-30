"""Record the method, host and route of every request the product makes.

WP11g's execution contract asks for three complementary no-upload methods.
The second — an instrumented application network log — is the one WP11e could
not supply. WP11e sampled established TCP peers with ``lsof`` every five
seconds, which yields destinations and nothing else: no method, no host name,
no route. Its own report says so and defers the full capture to WP11g. This
tool is that capture.

The instrument sits inside the product's own process rather than beside it.
``sitecustomize`` is imported by ``site`` before any application code runs, so
a recorder installed there sees every request made by the CLI, by anything the
CLI imports, and by any Python child that inherits ``PYTHONPATH``. Three
layers are recorded, deepest last, so that a request cannot be seen at one
layer and missed at another:

* ``http.client.HTTPConnection.putrequest`` — the method and the route, plus
  the connection's host and port. Every stdlib HTTP client, ``urllib``
  included, funnels through it.
* ``socket.getaddrinfo`` — the host name a resolution was asked about, which
  is the only place a name survives before it becomes an address.
* ``socket.socket.connect`` and ``connect_ex`` — the raw destination. This is
  the floor: a client that bypassed ``http.client`` entirely would still have
  to connect.

The log is only worth reading if the instrument was alive, so the first step
is a deliberate loopback request to a closed port. It must appear in the
recording. A run whose self-test is missing proves nothing and fails.

Nothing here spends money. The commands driven below are the product's whole
network-reachable surface that does not require a paid comparison; the paid
path's destinations are covered by the WP11e sampler and its own resolved
engine configuration, and that division is written into the output.

Usage::

    uv run python tools/network_method_probe.py --output release/network-method-log.json
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

#: Written into the temporary directory that becomes the child's PYTHONPATH.
#: Kept defensive throughout: an instrument that can raise is an instrument
#: that changes the behaviour it is supposed to observe.
RECORDER_SOURCE = '''\
"""Record every request this process makes.

Installed by tools/network_method_probe.py. Never part of the wheel.
"""

import json
import os
import threading

_LOG_PATH = os.environ.get("TECHTREE_NETWORK_PROBE_LOG")

if _LOG_PATH:
    import http.client
    import socket

    _LOCK = threading.Lock()

    def _emit(record):
        record["pid"] = os.getpid()
        try:
            line = json.dumps(record, sort_keys=True, default=repr)
        except Exception:
            return
        try:
            with _LOCK, open(_LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(line + "\\n")
                handle.flush()
        except Exception:
            return

    def _address(value):
        if isinstance(value, tuple) and len(value) >= 2:
            return {"host": str(value[0]), "port": value[1]}
        return {"host": str(value), "port": None}

    _putrequest = http.client.HTTPConnection.putrequest

    def putrequest(self, method, url, *args, **kwargs):
        secure = isinstance(self, http.client.HTTPSConnection)
        _emit(
            {
                "layer": "http",
                "method": method,
                "route": url,
                "host": getattr(self, "host", None),
                "port": getattr(self, "port", None),
                "scheme": "https" if secure else "http",
            }
        )
        return _putrequest(self, method, url, *args, **kwargs)

    http.client.HTTPConnection.putrequest = putrequest

    _getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):
        _emit({"layer": "dns", "host": str(host), "port": port})
        return _getaddrinfo(host, port, *args, **kwargs)

    socket.getaddrinfo = getaddrinfo

    _connect = socket.socket.connect

    def connect(self, address):
        record = {"layer": "socket", "call": "connect", "family": int(self.family)}
        record.update(_address(address))
        _emit(record)
        return _connect(self, address)

    socket.socket.connect = connect

    _connect_ex = socket.socket.connect_ex

    def connect_ex(self, address):
        record = {"layer": "socket", "call": "connect_ex", "family": int(self.family)}
        record.update(_address(address))
        _emit(record)
        return _connect_ex(self, address)

    socket.socket.connect_ex = connect_ex
'''

#: A request the recorder must see. Port 9 is the discard port and is closed on
#: this machine, so the request fails after it has been recorded and nothing is
#: sent anywhere.
SELF_TEST_SOURCE = (
    "import urllib.request\n"
    "try:\n"
    "    urllib.request.urlopen('http://127.0.0.1:9/probe-self-test', timeout=1)\n"
    "except Exception:\n"
    "    pass\n"
)


PURPOSE = (
    "The method, host and route of every HTTP request the Techtree CLI makes "
    "across its whole network-reachable surface that does not require a paid "
    "comparison. WP11e's sampler could show destinations and nothing else; "
    "this shows what was asked for and how."
)

OBSERVATION_METHOD = {
    "kind": "in-process instrumentation, not packet or socket sampling",
    "installed_by": (
        "a sitecustomize module on the child's PYTHONPATH, so the recorder is "
        "in place before any application code imports"
    ),
    "layers": [
        "http.client.HTTPConnection.putrequest — method, route, host, port, scheme",
        "socket.getaddrinfo — the host name a resolution was asked about",
        "socket.socket.connect and connect_ex — the raw destination address",
    ],
    "self_test": (
        "the first step makes a deliberate GET to a closed loopback port. It "
        "must appear in the recording, otherwise every zero below is the "
        "silence of a dead instrument rather than of a quiet product."
    ),
    "continuous": (
        "every request is recorded as it is made. Unlike a five-second poll, "
        "nothing can happen between samples."
    ),
}

SCOPE = {
    "covers": [
        "every Python process the probe starts, and any Python child that "
        "inherits PYTHONPATH",
        "the CLI's whole command surface that is reachable without a paid "
        "comparison, including the one command that fetches",
    ],
    "does_not_cover": [
        "the paid comparison path. Running it costs money and this probe never "
        "spends any. Its destinations are covered by method 3 instead — the "
        "WP11e sampler observed the provider and the package index and nothing "
        "else — and its configuration is covered by the resolved engine config, "
        "where push is false and the client base_url is the provider.",
        "non-Python children. The Docker CLI, uv and git are separate "
        "executables, not Python, so a sitecustomize recorder cannot see "
        "inside them. What they contact is package-index and registry traffic, "
        "which method 3 enumerates as an expected destination.",
        "the evaluation engine's own process. It has its own virtual "
        "environment and its own HTTP clients, and it is launched as a "
        "subprocess by the paid path above.",
        "anything a request carried. Bodies are deliberately not recorded: the "
        "claim under test is about method and destination, and a body log "
        "would itself be a place a secret could land.",
    ],
}

LIMITATIONS = [
    (
        "This is an observation of runs that happened, not a proof about runs "
        "that did not. It is the static audit — method 1 — that establishes "
        "there is no upload code path to exercise in the first place; this "
        "shows that the product, driven through its surface, behaves the way "
        "that audit predicts."
    ),
    (
        "The recorder patches the standard library's HTTP and socket entry "
        "points. Code that reimplemented a socket below the standard library "
        "would evade the top two layers, though not the connect layer. The "
        "installed package imports no such thing: its only network import is "
        "urllib, and its dependency lock contains no HTTP client at all."
    ),
    (
        "One machine, one release, one day. It says nothing about a different "
        "build, and it is meant to be re-run rather than cited forever."
    ),
]


def _steps(executable: str) -> list[dict[str, Any]]:
    """The product commands driven under the recorder, in order."""
    return [
        {
            "id": "instrument_self_test",
            "argv": [sys.executable, "-c", SELF_TEST_SOURCE],
            "expectation": (
                "one GET to a closed loopback port, which must appear in the "
                "recording. It is the seal on every zero below."
            ),
        },
        {
            "id": "version",
            "argv": [executable, "--version"],
            "expectation": "no request",
        },
        {
            "id": "doctor",
            "argv": [executable, "--json", "doctor"],
            "expectation": (
                "no request. Readiness is answered from this machine: the "
                "Docker daemon over its local socket, uv and the engine on "
                "disk."
            ),
        },
        {
            "id": "release_info",
            "argv": [executable, "--json", "release", "info"],
            "expectation": "no request. ReleaseCore is packaged in the wheel.",
        },
        {
            "id": "release_verify",
            "argv": [executable, "--json", "release", "verify"],
            "expectation": "no request. The check is over local bytes.",
        },
        {
            "id": "climb_list",
            "argv": [executable, "--json", "climb", "list"],
            "expectation": "no request. The catalog is packaged in the wheel.",
        },
        {
            "id": "climb_show",
            "argv": [executable, "--json", "climb", "show", "hello-world-climb@1"],
            "expectation": "no request.",
        },
        {
            "id": "run_status_unknown",
            "argv": [
                executable,
                "--json",
                "run",
                "status",
                "run_00000000000000000000000000000000",
            ],
            "expectation": (
                "no request. A run this machine has never heard of is answered "
                "from local state, not by asking anyone."
            ),
        },
        {
            "id": "skill_starter",
            "argv": [executable, "--json", "skill", "starter"],
            "expectation": (
                "exactly one request: GET of the content-addressed starter "
                "object the release pins. This is the product's only outbound "
                "call site and its only contact with techtree.sh."
            ),
        },
        {
            "id": "skill_starter_again",
            "argv": [executable, "--json", "skill", "starter"],
            "expectation": (
                "no request. The verified cache entry answers without a fetch, "
                "so a second materialisation is not a second read."
            ),
        },
    ]


def _read_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _observed(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Split one step's records into the three layers, deduplicated in order."""
    http_requests: list[dict[str, Any]] = []
    dns_lookups: list[dict[str, Any]] = []
    sockets: list[dict[str, Any]] = []
    for record in records:
        layer = record.get("layer")
        if layer == "http":
            entry = {
                "method": record.get("method"),
                "scheme": record.get("scheme"),
                "host": record.get("host"),
                "port": record.get("port"),
                "route": record.get("route"),
            }
            if entry not in http_requests:
                http_requests.append(entry)
        elif layer == "dns":
            entry = {"host": record.get("host"), "port": record.get("port")}
            if entry not in dns_lookups:
                dns_lookups.append(entry)
        elif layer == "socket":
            entry = {
                "family": record.get("family"),
                "host": record.get("host"),
                "port": record.get("port"),
            }
            if entry not in sockets:
                sockets.append(entry)
    return {
        "http_requests": http_requests,
        "dns_lookups": dns_lookups,
        "socket_connections": sockets,
    }


def _run_steps(executable: str, home: Path, workspace: Path) -> list[dict[str, Any]]:
    recorder_dir = workspace / "recorder"
    recorder_dir.mkdir(parents=True, exist_ok=True)
    (recorder_dir / "sitecustomize.py").write_text(RECORDER_SOURCE, encoding="utf-8")

    results: list[dict[str, Any]] = []
    for index, step in enumerate(_steps(executable)):
        log_path = workspace / f"step-{index:02d}-{step['id']}.ndjson"
        environment = dict(os.environ)
        environment["HOME"] = str(home)
        environment["PYTHONPATH"] = str(recorder_dir)
        environment["TECHTREE_NETWORK_PROBE_LOG"] = str(log_path)
        completed = subprocess.run(
            step["argv"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPOSITORY_ROOT),
        )
        records = _read_log(log_path)
        results.append(
            {
                "id": step["id"],
                "argv": [
                    "<self-test source>" if "\n" in part else part
                    for part in step["argv"]
                ],
                "expectation": step["expectation"],
                "exit_code": completed.returncode,
                "record_count": len(records),
                **_observed(records),
            }
        )
    return results


def _assertions(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {step["id"]: step for step in steps}
    every_request = [request for step in steps for request in step["http_requests"]]
    product_requests = [
        request
        for step in steps
        if step["id"] != "instrument_self_test"
        for request in step["http_requests"]
    ]
    mutating = [
        request
        for request in product_requests
        if str(request.get("method", "")).upper() not in {"GET", "HEAD", "OPTIONS"}
    ]
    techtree_requests = [
        request
        for request in product_requests
        if "techtree.sh" in str(request.get("host") or "")
    ]
    techtree_mutations = [
        request
        for request in techtree_requests
        if str(request.get("method", "")).upper() not in {"GET", "HEAD"}
    ]
    self_test = by_id.get("instrument_self_test", {})

    def result(passed: bool) -> str:
        return "pass" if passed else "FAIL"

    return [
        {
            "assertion": "the instrument was alive",
            "result": result(bool(self_test.get("http_requests"))),
            "detail": (
                "the deliberate loopback GET was recorded: "
                f"{json.dumps(self_test.get('http_requests', []))}"
            ),
        },
        {
            "assertion": "no mutating request was made by the product",
            "result": result(not mutating),
            "detail": (
                f"{len(product_requests)} product request(s) recorded, "
                f"{len(mutating)} of them with a method other than GET, HEAD "
                "or OPTIONS"
            ),
        },
        {
            "assertion": "no mutation request to techtree.sh",
            "result": result(not techtree_mutations),
            "detail": (
                f"{len(techtree_requests)} request(s) to techtree.sh, "
                f"{len(techtree_mutations)} of them mutating"
            ),
        },
        {
            "assertion": "the starter fetch is one GET and is not repeated",
            "result": result(
                len(by_id.get("skill_starter", {}).get("http_requests", [])) == 1
                and by_id.get("skill_starter_again", {}).get("http_requests") == []
            ),
            "detail": (
                f"first materialisation made "
                f"{len(by_id.get('skill_starter', {}).get('http_requests', []))} "
                "request(s); the second made "
                f"{len(by_id.get('skill_starter_again', {}).get('http_requests', []))}"
            ),
        },
        {
            "assertion": "every recorded request is accounted for",
            "result": result(len(every_request) == len(product_requests) + 1),
            "detail": (
                f"{len(every_request)} request(s) in total, of which one is the "
                "instrument's own self-test"
            ),
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--executable",
        default=str(REPOSITORY_ROOT / ".venv" / "bin" / "techtree"),
        help="the installed Techtree console script to drive",
    )
    parser.add_argument(
        "--home",
        required=True,
        help="a scratch HOME the probe may create a Techtree home under",
    )
    parser.add_argument("--output", required=True, help="where to write the log")
    arguments = parser.parse_args()

    home = Path(arguments.home).resolve()
    home.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="techtree-network-probe-") as scratch:
        steps = _run_steps(arguments.executable, home, Path(scratch))

    document = {
        "schema_version": "techtree.network-method-log.v1",
        "generated_on": datetime.now(UTC).date().isoformat(),
        "ticket": "techtree-python-ndq.3.7",
        "contract": "docs/release/contracts/wp11g.md, no-upload method 2",
        "instrument": "tools/network_method_probe.py",
        "host": f"{os.uname().sysname} {os.uname().release} {os.uname().machine}",
        "python": sys.version.split()[0],
        "executable": arguments.executable,
        "purpose": PURPOSE,
        "observation_method": OBSERVATION_METHOD,
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "steps": steps,
        "assertions": _assertions(steps),
    }
    Path(arguments.output).write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    failed = [check for check in document["assertions"] if check["result"] != "pass"]
    for check in document["assertions"]:
        print(f"{check['result']:>4}  {check['assertion']}")
    return 1 if failed else 0


if __name__ == "__main__":
    socket.setdefaulttimeout(None)
    raise SystemExit(main())
