#!/usr/bin/env bash
# scripts/publish-main.sh -- publish this fork's main branch with its pages up to date.
#
#   scripts/publish-main.sh            regenerate the pages, commit them, push
#   scripts/publish-main.sh --dry-run  regenerate, show what would be committed, push nothing
#
# The order is the whole point. scripts/fork-pr-table.sh rewrites README.md and docs/FORK.md in the
# working tree, so a page that has just been refreshed is an uncommitted change: pushing first
# publishes the page of the previous run. So the sequence is generate, commit what the generator
# touched, push.
#
# Only the fork is ever pushed: the script refuses a remote whose URL names the upstream owner,
# because in this clone `origin` is upstream (deepbeepmeep) and `fork` is mine (abencq).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

FORK_REMOTE="${FORK_REMOTE:-fork}"
FORK_BRANCH="${FORK_BRANCH:-main}"
UPSTREAM_OWNER="${UPSTREAM_OWNER:-deepbeepmeep}"
notes='scripts/fork-pr-notes.json'
[ -f "$notes" ] && UPSTREAM_OWNER=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['upstream_repo'].split('/')[0])" "$notes")

DRY=0
case "${1:-}" in
  '') ;;
  --dry-run) DRY=1 ;;
  -h|--help) echo "usage: $(basename "$0") [--dry-run]"; exit 0 ;;
  *) echo "usage: $(basename "$0") [--dry-run]" >&2; exit 2 ;;
esac

url=$(git remote get-url "$FORK_REMOTE" 2>/dev/null || echo '')
if [ -z "$url" ]; then
  echo "publish-main: remote '$FORK_REMOTE' does not exist — see git remote -v" >&2
  exit 1
fi
case "$url" in
  *"$UPSTREAM_OWNER"*)
    echo "publish-main: '$FORK_REMOTE' points at $url, which is upstream. Nothing is pushed there." >&2
    exit 1 ;;
esac
LOCAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "publish-main: regenerating README.md and docs/FORK.md"
scripts/fork-pr-table.sh

# generated_only FILE — true when every changed line of FILE sits between the generated markers.
# A hunk outside them is a hand-written sentence, and that belongs in a commit of its own.
generated_only() {
  python3 -c '
import re, subprocess, sys
path = sys.argv[1]
cur = open(path, encoding="utf-8").read().splitlines()
begin = next((i for i, l in enumerate(cur) if l.startswith("<!-- BEGIN GENERATED")), -1)
end = next((i for i, l in enumerate(cur) if l.startswith("<!-- END GENERATED")), -1)
hunks = subprocess.run(["git", "diff", "--unified=0", "--", path],
                       capture_output=True, text=True).stdout
ok = begin >= 0 and end >= 0
for s, c in re.findall(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", hunks, re.M):
    s, c = int(s), int(c or 1)
    ok = ok and s >= begin + 1 and s + c <= end + 1
sys.exit(0 if ok else 1)
' "$1"
}

dirty=()
for f in README.md docs/FORK.md; do
  git diff --quiet -- "$f" && continue
  if ! generated_only "$f"; then
    echo "publish-main: $f holds edits outside the generated block." >&2
    echo "publish-main: commit those words yourself — publish-main commits only what the generator wrote." >&2
    exit 1
  fi
  dirty+=("$f")
done
if [ ${#dirty[@]} -gt 0 ]; then
  echo "publish-main: the generator changed ${dirty[*]}"
  if [ "$DRY" = 1 ]; then
    git --no-pager diff --stat -- "${dirty[@]}"
  else
    git add -- "${dirty[@]}"
    git commit -q -F - <<'MSG'
Refresh the front page and the pull-request ledger

The generator counted this fork against upstream and read the state of every pull
request from the GitHub API, so the front page and the licence record say what is
true today. The words of the front page come from docs/fork-features.md and the
rows from scripts/fork-pr-notes.json; nothing here was typed by hand.
MSG
    echo "publish-main: committed the regenerated pages"
  fi
else
  echo "publish-main: the pages were already up to date"
fi

if [ "$DRY" = 1 ]; then
  echo "publish-main: --dry-run, nothing pushed. Would push $LOCAL_BRANCH to $FORK_REMOTE/$FORK_BRANCH"
  git --no-pager log --oneline -3
  exit 0
fi

if ! git diff --quiet; then
  echo "publish-main: note: the working tree still has changes of its own; they stay uncommitted" >&2
fi
echo "publish-main: pushing $LOCAL_BRANCH to $FORK_REMOTE/$FORK_BRANCH"
git push "$FORK_REMOTE" "$LOCAL_BRANCH:$FORK_BRANCH"
