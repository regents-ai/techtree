"""The gate between Muse Code and the machine's translator (Sean, 1 October 2026: 4 a), on 127.0.0.1:4001 inside the
runner while a Muse Code turn runs. Three changes, nothing else:

1. Muse Code asks for GET /muse-code/models before every run; the gate answers with the one benchmark model.
2. Muse Code declares its tools as one namespace ("muse") but replays earlier tool calls with the joined name
   "muse.bash". Those replayed calls are sent as name "bash" with namespace "muse", the form of its own declarations.
3. Muse Code refuses a Responses stream event without its `sequence_number`, which the translator leaves out of most
   events when it turns Anthropic's stream into the Responses format. The gate numbers the events in order.

Every other byte goes unchanged, streamed, to the translator on 127.0.0.1:4000.
"""
import http.client
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GATE = "http://127.0.0.1:4001/v1"
UPSTREAM = ("127.0.0.1", 4000)
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "host", "content-length"}


def split_namespaced_calls(body: bytes) -> bytes:
    request = json.loads(body)
    for item in request.get("input", []):
        if isinstance(item, dict) and item.get("type") == "function_call" and "." in item["name"]:
            item["namespace"], item["name"] = item["name"].split(".", 1)
    return json.dumps(request).encode()


class Gate(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/muse-code/models"):
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(self.server.catalog)))
            self.end_headers()
            self.wfile.write(self.server.catalog)
            return
        self.forward(None)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["content-length"]))
        self.forward(split_namespaced_calls(body) if self.path.rstrip("/").endswith("/responses") else body)

    def forward(self, body):
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        upstream = http.client.HTTPConnection(*UPSTREAM, timeout=900)
        upstream.request(self.command, self.path, body=body, headers=headers)
        reply = upstream.getresponse()
        self.send_response(reply.status)
        for k, v in reply.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        sequence = 0
        for line in reply:
            if line.startswith(b"data: {"):
                event = json.loads(line[6:])
                event.setdefault("sequence_number", sequence)
                sequence += 1
                line = b"data: " + json.dumps(event).encode() + b"\n"
            self.wfile.write(b"%x\r\n%s\r\n" % (len(line), line))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        upstream.close()

    def log_message(self, format, *args):
        """The translator logs every call; the gate adds nothing to the turn's output."""


@contextmanager
def serving(model: str):
    """The gate, answering the catalog with `model`, for the length of the `with` block."""
    server = ThreadingHTTPServer(("127.0.0.1", 4001), Gate)
    server.catalog = json.dumps({"data": [{"id": model}]}).encode()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
