#!/usr/bin/env bash
# Commit email_dispatch_state.json immediately after send so backup runs see dedup state.
set -euo pipefail

STATE="data/email_dispatch_state.json"
if [[ ! -f "$STATE" ]]; then
  echo "No $STATE — nothing to publish (email may not have been sent)."
  exit 0
fi

git config --local user.email "action@github.com"
git config --local user.name "GitHub Action"
git checkout -B main
git add "$STATE"

if git diff --staged --quiet; then
  echo "Email dispatch state unchanged on remote."
  exit 0
fi

DATE="$(python3 -c "import json; print(json.load(open('$STATE'))['eastern_date'])")"
git commit -m "chore: record digest email dispatch for ${DATE}"

for attempt in 1 2 3 4 5; do
  if git pull --rebase origin main && git push origin main; then
    echo "Published email dedup state on attempt ${attempt}."
    exit 0
  fi
  echo "Push attempt ${attempt} failed; retrying in 5s..."
  sleep 5
done

echo "Failed to publish email dedup state after 5 attempts."
exit 1
