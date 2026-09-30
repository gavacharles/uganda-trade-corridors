"""Run shared pipeline scripts (../scripts) with this paper's settings (scripts/config.py).

    python run.py 01 02 05          # scripts by number, in the order given
    python run.py 00 -- 2006 2025   # arguments after -- go to the (single) script

Each script is executed as if run directly, but `import config` finds this folder's
config.py first, so data, outputs and figures go under regional-corridors/.
"""
import glob, os, runpy, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(HERE, "..", "scripts")
sys.path[:0] = [os.path.join(HERE, "scripts"), SHARED]

args = sys.argv[1:]
extra = []
if "--" in args:
    args, extra = args[:args.index("--")], args[args.index("--") + 1:]
for num in args:
    path = sorted(glob.glob(os.path.join(SHARED, f"{num}_*.py")))
    if len(path) != 1:
        raise SystemExit(f"no single script numbered {num} in {SHARED}")
    print(f"=== {os.path.basename(path[0])}", flush=True)
    sys.argv = [path[0]] + extra
    runpy.run_path(path[0], run_name="__main__")
