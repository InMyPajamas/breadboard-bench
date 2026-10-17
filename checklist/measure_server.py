"""Serve the bench's result sheets and keep what they record.

    python checklist/measure_server.py
        http://<this-mac>:8765/bench-hub.html  the whole site, Checks tab included
        http://<this-mac>:8765/fit02.html      plate 02, tap-through fit test
        http://<this-mac>:8765/cleat.html      plates 02e-02h, the cleat gauges
        http://127.0.0.1:8765/measure.html     plate 01, voice caliper sheet

This one port now serves the site as well as the sheets, so bench-hub.html's
Checks tab can read each sheet's progress and link straight into it. Serving
the hub from a second port instead would make every sheet cross-origin and
its Save would fail.

Two reasons this is a server and not a file:// page. The browser's speech
recognition wants a secure context, and localhost counts where file:// asks
for the microphone again on every load. And a page cannot write to disk, so
each sheet POSTs its readings here and they land next to the plate they
answer: /save?sheet=plate1 -> out/plate1_tpu/measurements.json, and
/save?sheet=plate2 -> out/plate2_pla/fit_results.json.

It listens on the whole LAN so the tap sheet works from the iPad at the
printer. The voice sheet still has to be opened on this machine, as
127.0.0.1: a LAN address is not a secure context, so the mic stays off there.
"""
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(HERE, "..", "out")
# The only files this server will ever write, by name -- never a path from
# the request.
SHEETS = {
    "plate1": os.path.join(OUT, "plate1_tpu", "measurements.json"),
    "plate2": os.path.join(OUT, "plate2_pla", "fit_results.json"),
    "cleat": os.path.join(OUT, "plate2_pla", "cleat_results.json"),
    "ledge": os.path.join(OUT, "plate2_pla", "ledge_results.json"),
    "plate3": os.path.join(OUT, "plate3_petg", "fit_results.json"),
    # the boards themselves, punched in by hand -- the CAD reads this rather
    # than carrying my measurements as literals
    "board": os.path.join(OUT, "board_dims.json"),
}
# 8765 is where this has always lived and every bookmark points; 80 is what a
# bare http://bench/ means. Listen on both, so neither breaks. In the bench-hub
# container the service binds 80 without root via CAP_NET_BIND_SERVICE; on a
# Mac 80 needs root, so BENCH_PORTS=8765 keeps it to the one.
PORTS = [int(x) for x in os.environ.get("BENCH_PORTS", "8765,80").split(",")]
MAX_BODY = 1 << 20


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def translate_path(self, path):
        """Serve checklist/ first, then fall back to the project root.

        This is what lets ONE port carry the whole site: the sheets keep their
        short URLs (/cleat.html), and bench-hub.html plus its renders/ and
        out/ assets resolve from the root. Same origin is the point, not
        tidiness -- a sheet opened from the hub can only POST its answers back
        if the hub is not on a different port.

        The base implementation has already stripped any traversal and joined
        the request to HERE, so `local` is always inside HERE and the relative
        path below cannot escape ROOT.
        """
        local = super().translate_path(path)
        if os.path.exists(local):
            return local
        rel = os.path.relpath(local, HERE)
        if rel.startswith(os.pardir):
            return local
        return os.path.join(ROOT, rel)

    def _json(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _sheet(self):
        name = parse_qs(urlparse(self.path).query).get("sheet", ["plate1"])[0]
        return SHEETS.get(name)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            # the site's front door: http://bench/ lands on the hub
            self.send_response(302)
            self.send_header("Location", "/bench-hub.html")
            self.end_headers()
            return
        if path == "/data":
            data = self._sheet()
            if data is None:
                return self._json(404, {"error": "unknown sheet"})
            if os.path.exists(data):
                return self._json(200, json.load(open(data, encoding="utf-8")))
            return self._json(200, {})
        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/save":
            return self._json(404, {"error": "unknown path"})
        data = self._sheet()
        if data is None:
            return self._json(404, {"error": "unknown sheet"})
        try:
            size = int(self.headers["Content-Length"])
            if size > MAX_BODY:
                return self._json(413, {"error": "too large"})
            body = json.loads(self.rfile.read(size))
        except (ValueError, KeyError, TypeError):
            return self._json(400, {"error": "bad json"})
        os.makedirs(os.path.dirname(data), exist_ok=True)
        # Write beside, then swap: a reader never sees half a file.
        tmp = data + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(body, f, indent=2)
        os.replace(tmp, data)
        self._json(200, {"ok": True})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 1))
        lan = s.getsockname()[0]
        s.close()
    except OSError:
        lan = "<this-mac>"
    import threading
    servers = []
    for port in PORTS:
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        except OSError as e:
            print(f"port {port}: not bound ({e.strerror}); carrying on")
            continue
        servers.append(srv)
        print(f"http://{lan}{'' if port == 80 else ':' + str(port)}/   -> the hub")
    if not servers:
        raise SystemExit("no port could be bound")
    print(f"http://127.0.0.1:{PORTS[0]}/measure.html   voice sheet, this machine only")
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
