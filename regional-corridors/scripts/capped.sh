#!/bin/zsh
# Run a command, stopping it if its memory (resident set) passes a cap, so a long run cannot
# push the laptop into swap. Usage: scripts/capped.sh <cap_GB> <command...>
cap_kb=$(( $1 * 1024 * 1024 )); shift
"$@" &
pid=$!
while kill -0 $pid 2>/dev/null; do
  rss=$(ps -o rss= -p $pid 2>/dev/null | tr -d ' ')
  if [[ -n "$rss" && "$rss" -gt "$cap_kb" ]]; then
    echo "capped.sh: stopped $* at $(( rss / 1024 )) MB (cap $(( cap_kb / 1024 )) MB)" >&2
    kill $pid; wait $pid; exit 137
  fi
  sleep 3
done
wait $pid
