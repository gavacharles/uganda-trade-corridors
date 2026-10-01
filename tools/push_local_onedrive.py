"""Copy the working clone into the local OneDrive folder without ever reading OneDrive files
(evicted placeholders hang on read): compare size and mtime only, write to a temp name, rename."""
import os, shutil, sys
SRC = os.path.expanduser("~/Projects/uganda-trade-corridors")
DST = os.path.expanduser("~/Library/CloudStorage/OneDrive-Personal/Projects/uganda-trade-corridors")
SKIP_DIRS = {".git", "data", "__pycache__"}
n = 0
for root, dirs, files in os.walk(SRC):
    rel = os.path.relpath(root, SRC)
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (rel == "regional-corridors" and d == "data")]
    os.makedirs(os.path.join(DST, rel), exist_ok=True)
    for f in files:
        if f in (".env", ".DS_Store", ".venv"):
            continue
        s, d = os.path.join(root, f), os.path.join(DST, rel, f)
        st = os.stat(s)
        try:
            dt = os.stat(d)
            if dt.st_size == st.st_size and int(dt.st_mtime) == int(st.st_mtime):
                continue
        except FileNotFoundError:
            pass
        tmp = d + ".copying"
        shutil.copy2(s, tmp)
        os.replace(tmp, d)
        n += 1
print(f"copied {n} files")
