#!/bin/zsh
# Bring OneDrive up to date with this working copy (code, outputs, figures, deck, web, posts; not
# data/ or .git): online through rclone (the remote "onedrive:"), and into the local OneDrive
# folder through a copy that never reads OneDrive's online-only placeholders.
cd "$(dirname "$0")/.."
rclone copy . onedrive:Projects/uganda-trade-corridors --exclude ".git/**" --exclude "data/**" \
  --exclude "regional-corridors/data/**" --exclude ".env" --exclude "**/__pycache__/**" --exclude ".venv" \
  --exclude ".DS_Store" --transfers 8 && echo "online: up to date"
~/.venvs/uganda-trade-corridors/bin/python tools/push_local_onedrive.py
