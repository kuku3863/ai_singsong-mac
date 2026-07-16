#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/liubin/Desktop/ai_singsong"
BRANCH="main"

cd "$PROJECT_DIR"

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "Update macOS release"
fi

git push origin "$BRANCH"

echo "同步完成。"
