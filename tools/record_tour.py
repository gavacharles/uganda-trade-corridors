"""Record a street-level map's fly-through as a video, frame by frame, from the map itself.

    python tools/record_tour.py <page> <out.mp4> "<title>" "<subtitle>" [--base sat] [--layer delay]

<page> is a page in web/ built from web/map_template.html (regional.html, uganda_map.html). The page
is opened in headless Chrome in its video mode (#video=1: no panels, a title band, fractional zoom);
for every frame the camera is set with window.__cam(lat, lon, zoom), which resolves once the basemap
tiles and the street detail have loaded, and the frame is captured. The camera zooms out between stops
and down to street level at each, where window.__card(i) shows the stop's card, as on the map's own
▶ Fly-through. Writes the MP4 (1280 x 720, 12 fps; --gif also writes a GIF).
"""
import argparse, base64, io, json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
import numpy as np
import imageio.v2 as imageio
import websocket
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB = os.path.join(ROOT, "web")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H, FPS = 1280, 720, 12
STREET_Z = 15.6


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.n = 0

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps(dict(id=self.n, method=method, params=params)))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"])
        return r["result"].get("value")


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def path(a, b, n):
    """Camera from view a to view b (lon, lat, width in degrees) in n frames, zooming out in between
    so the move never jumps further than the view is wide (as scripts/flylib.py)."""
    dist = np.hypot(b[0] - a[0], b[1] - a[1])
    peak = max(a[2], b[2], dist * 1.4)
    bump = np.log(peak) - max(np.log(a[2]), np.log(b[2]))
    out = []
    for i in range(n):
        u = ease((i + 1) / n)
        lw = (1 - u) * np.log(a[2]) + u * np.log(b[2]) + bump * np.sin(np.pi * u)
        if a[2] > dist * 1.4:
            v = ease(min(u / 0.45, 1))
        elif b[2] > dist * 1.4:
            v = ease(max((u - 0.55) / 0.45, 0))
        else:
            v = ease(min(max((u - 0.15) / 0.7, 0), 1))
        out.append((a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v, float(np.exp(lw))))
    return out


def zoom_of(width_deg):
    return float(np.log2(W * 360 / (256 * width_deg)))


def width_of(z):
    return W * 360 / (256 * 2 ** z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page"); ap.add_argument("out"); ap.add_argument("title"); ap.add_argument("subtitle")
    ap.add_argument("--base", default="sat"); ap.add_argument("--layer", default="delay")
    ap.add_argument("--stops", type=int, default=0); ap.add_argument("--gif", action="store_true"); ap.add_argument("--fly", type=float, default=4.0); ap.add_argument("--hold", type=float, default=4.5)
    a = ap.parse_args()

    port, dport = free_port(), free_port()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=WEB,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    prof = tempfile.mkdtemp(prefix="rec_")
    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                               f"--window-size={W},{H}", "--force-device-scale-factor=1",
                               f"--remote-debugging-port={dport}", f"--user-data-dir={prof}", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{dport}/json"))
                page = [t for t in tabs if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        q = urllib.parse.urlencode(dict(video=1, base=a.base, layer=a.layer, vt=a.title, vs=a.subtitle),
                                   quote_via=urllib.parse.quote)
        cdp.call("Page.navigate", url=f"http://127.0.0.1:{port}/{a.page}#{q}")
        for _ in range(300):
            try:
                if cdp.js("window.__ready === true"):
                    break
            except Exception:
                pass
            time.sleep(0.2)
        tour = cdp.js("D.tour")
        if a.stops:
            tour = tour[:a.stops]
        b = cdp.js("(()=>{ const b=L.latLngBounds(D.segs.flatMap(s=>s.g.flat())); return [b.getWest(),b.getSouth(),b.getEast(),b.getNorth()] })()")
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        wdeg = max(b[2] - b[0], (b[3] - b[1]) * W / H) * 1.12
        start = (cx, cy, wdeg)
        street = width_of(STREET_Z)

        mp4 = a.out
        gif_frames, n = [], 0
        t0 = time.time()
        with imageio.get_writer(mp4, fps=FPS, codec="libx264", quality=8, macro_block_size=16) as wr:
            def shot(view, rep=1):
                nonlocal n
                lon, lat, w = view
                cdp.js(f"window.__cam({lat:.6f}, {lon:.6f}, {zoom_of(w):.4f})")
                img = cdp.call("Page.captureScreenshot", format="jpeg", quality=93)["data"]
                f = np.asarray(Image.open(io.BytesIO(base64.b64decode(img))).convert("RGB"))
                for _ in range(rep):
                    wr.append_data(f)
                    if n % 2 == 0:
                        gif_frames.append(Image.fromarray(f).resize((800, 450), Image.LANCZOS)
                                          .convert("P", palette=Image.ADAPTIVE, colors=256))
                    n += 1

            view = start
            cdp.js("window.__card(-1)")
            shot(view, int(1.6 * FPS))
            for k, s in enumerate(tour):
                target = (s["lon"], s["lat"], street)
                cdp.js("window.__card(-1)")
                for v in path(view, target, int(a.fly * FPS)):
                    shot(v)
                cdp.js(f"window.__card({k})")
                shot(target, int(a.hold * FPS))
                view = target
                print(f"stop {k + 1}/{len(tour)} {s['place']} ({time.time() - t0:.0f} s)", flush=True)
            cdp.js("window.__card(-1)")
            for v in path(view, start, int(a.fly * FPS)):
                shot(v)
            shot(start, int(1.6 * FPS))
        # satellite imagery barely compresses at imageio's settings: re-encode (about 5x smaller)
        import imageio_ffmpeg
        tmp = mp4[:-4] + "_c.mp4"
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", mp4, "-c:v", "libx264",
                        "-crf", "27", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp], check=True)
        os.replace(tmp, mp4)
        if a.gif:   # GIFs of satellite video run to tens of MB; off unless asked
            gif = os.path.splitext(mp4)[0] + ".gif"
            gif_frames[0].save(gif, save_all=True, append_images=gif_frames[1:], duration=int(2000 / FPS), loop=0,
                               optimize=True)
        print(f"wrote {mp4}: {n} frames ({n / FPS:.0f} s) in {time.time() - t0:.0f} s, {os.path.getsize(mp4) / 1e6:.0f} MB")
    finally:
        chrome.kill(); srv.kill()


if __name__ == "__main__":
    main()
