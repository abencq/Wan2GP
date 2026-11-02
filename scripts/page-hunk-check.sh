#!/usr/bin/env bash
# scripts/page-hunk-check.sh -- is every changed line of a page inside a generated region?
#
#   scripts/page-hunk-check.sh README.md
#
# Exit 0 when every hunk of the pending change sits between the BEGIN/END GENERATED markers, or inside
# the inline SYNCED sentence of the licence record; exit 1 when a hunk is hand-written prose.
# scripts/publish-main.sh commits a page only when this says so: what the generator wrote goes out with
# the publish, a sentence of a person's own goes in a commit of its own.
set -euo pipefail
[ $# = 1 ] || { echo 'usage: page-hunk-check.sh FILE' >&2; exit 2; }
[ -f "$1" ] || { echo "page-hunk-check: no such file: $1" >&2; exit 2; }
python3 -c '
import re, subprocess, sys
path = sys.argv[1]
cur = open(path, encoding="utf-8").read().splitlines()

def region(start_text, end_text):
    b = next((i for i, l in enumerate(cur) if l.startswith(start_text)), -1)
    e = next((i for i, l in enumerate(cur) if l.startswith(end_text)), -1)
    return (b + 1, e + 1) if b >= 0 and e > b else None

regions = [r for r in (region("<!-- BEGIN GENERATED", "<!-- END GENERATED"),
                       region("<!-- SYNCED -->", "<!-- /SYNCED -->")) if r]
hunks = subprocess.run(["git", "diff", "--unified=0", "--", path],
                       capture_output=True, text=True).stdout
ok = bool(regions)
for s, c in re.findall(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", hunks, re.M):
    s, c = int(s), int(c or 1)
    ok = ok and any(s >= lo and s + c <= hi for lo, hi in regions)
sys.exit(0 if ok else 1)
' "$1"
