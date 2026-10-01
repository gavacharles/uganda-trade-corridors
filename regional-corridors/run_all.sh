#!/bin/zsh
# The whole regional pipeline after discovery, one step at a time, each under a memory cap so the
# laptop never runs short. Steps already finished are recorded in data/run_all.done and skipped
# on a re-run. Usage (from regional-corridors/):  nohup ./run_all.sh > <log> 2>&1 &
cd "$(dirname "$0")"
PY=~/.venvs/uganda-trade-corridors/bin/python
CAP=${CAP_GB:-6}
DONE=data/run_all.done
touch $DONE
step() {   # step <name> <command...>
  local name=$1; shift
  if grep -qx "$name" $DONE; then echo "== $name already done"; return 0; fi
  echo "== $name  $(date '+%H:%M')"
  if scripts/capped.sh $CAP "$@"; then echo "$name" >> $DONE; echo "== $name ok  $(date '+%H:%M')"
  else echo "== $name FAILED  $(date '+%H:%M')"; exit 1; fi
}
step 02 $PY -W ignore run.py 02
step 03 $PY -W ignore run.py 03
step 04 $PY -W ignore run.py 04
step 05 $PY -W ignore run.py 05
step 00 $PY -W ignore run.py 00 -- 2006 2025
for s in 06 08 09 10 16 17 18 19 20; do step $s $PY -W ignore run.py $s; done
step compare $PY -W ignore scripts/compare.py
echo "== all done  $(date '+%H:%M')"
