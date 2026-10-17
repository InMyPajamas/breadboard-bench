"""One live frame from the H2S camera, through OBS.

    python cad/printer_cam.py [out.jpg] [width]     ->  default out/printer_cam.jpg, 1600 wide

The camera reaches this Mac through Bambu Studio's Go Live tool, which relays
it to rtp://127.0.0.1:1234. OBS holds that port as the "Media" source in its
"Bambu" scene, and only one listener can have it, so this script never opens
the stream itself: it asks OBS for a screenshot over obs-websocket (v5, port
4455, enabled by the user 2026-10-04). The password is read from OBS's own
config file and never printed.

A source that is not in the active scene shows a FROZEN last frame (it showed
an empty bed while the printer was on layer 198). So the script restarts that
one media source and waits for a frame that differs from the frozen one. The
program scene is never changed. Needs `websocket-client`.
"""
import base64, hashlib, json, os, sys, time

import websocket

CFG = os.path.expanduser("~/Library/Application Support/obs-studio/plugin_config/obs-websocket/config.json")
SOURCE = "Media"


def connect():
    c = json.load(open(CFG))
    ws = websocket.create_connection(f"ws://127.0.0.1:{c.get('server_port', 4455)}", timeout=10)
    hello = json.loads(ws.recv())["d"]
    ident = {"rpcVersion": 1}
    if "authentication" in hello:
        a, pw = hello["authentication"], c.get("server_password", "")
        secret = base64.b64encode(hashlib.sha256((pw + a["salt"]).encode()).digest()).decode()
        ident["authentication"] = base64.b64encode(
            hashlib.sha256((secret + a["challenge"]).encode()).digest()).decode()
    ws.send(json.dumps({"op": 1, "d": ident}))
    assert json.loads(ws.recv())["op"] == 2, "OBS refused the login"
    return ws


def req(ws, typ, data=None):
    rid = f"{typ}-{time.time()}"
    ws.send(json.dumps({"op": 6, "d": {"requestType": typ, "requestId": rid, "requestData": data or {}}}))
    while True:
        m = json.loads(ws.recv())
        if m["op"] == 7 and m["d"]["requestId"] == rid:
            st = m["d"]["requestStatus"]
            if not st["result"]:
                raise RuntimeError(f"{typ}: {st.get('code')} {st.get('comment', '')}")
            return m["d"].get("responseData", {})


def shot(ws, width):
    d = req(ws, "GetSourceScreenshot", {"sourceName": SOURCE, "imageFormat": "jpg",
                                        "imageWidth": width, "imageCompressionQuality": 85})
    return base64.b64decode(d["imageData"].split(",", 1)[1])


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "out", "printer_cam.jpg")
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1600
    ws = connect()
    try:
        frozen = hashlib.md5(shot(ws, width)).hexdigest()
    except RuntimeError:
        frozen = None
    req(ws, "TriggerMediaInputAction",
        {"inputName": SOURCE, "mediaAction": "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"})
    for i in range(20):                      # an RTP stream needs a keyframe first: ~25 s
        time.sleep(3)
        try:
            b = shot(ws, width)
        except RuntimeError:
            continue
        if hashlib.md5(b).hexdigest() != frozen:
            with open(out, "wb") as f:
                f.write(b)
            print(f"live frame after {3 * (i + 1)} s -> {os.path.abspath(out)}")
            break
    else:
        raise SystemExit("no live frame in 60 s: is Go Live still running in Bambu Studio?")
    ws.close()
