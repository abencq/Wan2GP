#!/usr/bin/env python3
"""The offline half of this fork's pre-push reminder.

Four checks, all of them read from git and the two generated pages, none of them from the network:

  1. the numbers printed on the front page against what git says of the commits being pushed;
  2. the date of the front page and of the ledger, and the words behind the page, for staleness;
  3. the upstream sha written in the licence statement of docs/FORK.md against origin/main;
  4. nothing at all when the push carries no ref to push.

There is no way to stop a push from here: a stale page is worth a line on the terminal, not a
blocked release. Run by scripts/git-hooks/pre-push, which git calls because core.hooksPath points
there, and installed by scripts/install-fork-hooks.sh.
"""
import datetime
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
REF = 'refs/remotes/origin/main'
WORDS = ['docs/fork-features.md', 'scripts/fork-pr-notes.json', 'scripts/fork-pr-table.sh']

# git hands the refs to push on stdin; an empty stdin means the push carries nothing to do.
if not sys.stdin.read().strip():
    sys.exit(0)


def git(*args):
    r = subprocess.run(('git', '-C', str(root)) + args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def warn(msg):
    print('pre-push: %s' % msg, file=sys.stderr)


author = 'abencq'
notes = root / 'scripts' / 'fork-pr-notes.json'
if notes.exists():
    try:
        author = json.loads(notes.read_text(encoding='utf-8')).get('author', author)
    except Exception:
        pass

front = root / 'README.md'
text = front.read_text(encoding='utf-8') if front.exists() else ''
stamp = re.search(r'<!-- front page: regenerated (\d{4}-\d\d-\d\d) · (\d+) files \+(\d+) lines'
                  r' · (\d+) authored commits', text)
if not stamp:
    warn('the front page carries no machine stamp: run scripts/fork-pr-table.sh before publishing')
    sys.exit(0)
if not git('rev-parse', '--verify', '--quiet', REF):
    sys.exit(0)                     # no upstream ref in this clone: nothing to compare against

stamp, files, adds, commits = stamp.group(1), int(stamp.group(2)), int(stamp.group(3)), int(stamp.group(4))
names = [l for l in git('diff', '--name-only', '%s...HEAD' % REF).splitlines() if l.strip()]
live_adds = 0
for line in git('diff', '--numstat', '%s...HEAD' % REF).splitlines():
    parts = line.split('\t')
    if len(parts) > 1 and parts[0].isdigit():
        live_adds += int(parts[0])
live_commits = git('rev-list', '--count', '--author=%s' % author, '--no-merges', '%s...HEAD' % REF,
                   '--', '.', ':(exclude)README.md', ':(exclude)docs/FORK.md')
live = (len(names), live_adds, int(live_commits) if live_commits.isdigit() else None)

if live != (files, adds, commits):
    warn('the front page says %s files, +%s lines, %s authored commits; git says'
         ' %s files, +%s lines, %s' % (files, adds, commits, live[0], live[1], live[2]))
    warn('run git fork-refresh, then git publish-main, so the page goes out with these commits')

age = (datetime.date.today() - datetime.date.fromisoformat(stamp)).days
if age > 7:
    warn('the front page was generated on %s, %s days ago: the pull requests moved since' % (stamp, age))

last = git('log', '-1', '--format=%as', '--', *WORDS)
if last and last > stamp:
    warn('the words of the front page (%s) changed on %s, after the page was generated on %s'
         % (', '.join(WORDS), last, stamp))

# the ledger is the licence record: its own stamp is read the same way
ledger = root / 'docs' / 'FORK.md'
ltext = ledger.read_text(encoding='utf-8') if ledger.exists() else ''
lstamp = re.search(r'^\*current as of (\d{4}-\d\d-\d\d)\b', ltext, re.M)
if not lstamp:
    warn('docs/FORK.md carries no "current as of" stamp: run scripts/fork-pr-table.sh')
else:
    ldate = lstamp.group(1)
    lage = (datetime.date.today() - datetime.date.fromisoformat(ldate)).days
    if lage > 7:
        warn('docs/FORK.md says "current as of %s", %s days ago: the pull requests moved since'
             % (ldate, lage))
    if ldate != stamp:
        warn('docs/FORK.md says "current as of %s" and the front page was generated on %s:'
             ' one of the two pages is stale' % (ldate, stamp))

# the licence statement names the upstream commit this fork sits on; it is hand-written, so it drifts
synced = re.search(r'synced with upstream `([0-9a-f]{7,40})`', ltext)
tip = git('rev-parse', '--short', REF)
if synced and tip and not synced.group(1).startswith(tip):
    warn('docs/FORK.md says this branch is synced with upstream %s, origin/main is %s:'
         ' the licence statement is behind the last sync' % (synced.group(1), tip))
sys.exit(0)
