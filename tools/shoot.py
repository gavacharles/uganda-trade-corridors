"""Screenshot a page state with headless Chrome: python tools/shoot.py <url> <out.png> [wait_ms] [w] [h]

Chrome writes the PNG and sometimes does not exit, so the process is stopped once the file exists.
"""
import os, subprocess, sys, tempfile, time

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def shoot(url, out, wait_ms=9000, w=1280, h=720):
    if os.path.exists(out):
        os.remove(out)
    prof = tempfile.mkdtemp(prefix="shoot_")
    p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                          f"--virtual-time-budget={wait_ms}", f"--user-data-dir={prof}", f"--screenshot={out}", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 120:
        if os.path.exists(out) and os.path.getsize(out) > 0:
            time.sleep(0.5)
            break
        time.sleep(0.3)
    p.kill()
    p.wait()
    return os.path.exists(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    ok = shoot(a[0], a[1], *(int(x) for x in a[2:]))
    print("ok" if ok else "failed", a[1])
