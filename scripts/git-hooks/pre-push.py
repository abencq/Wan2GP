#!/usr/bin/env python3
"""The offline half of this fork's pre-push reminder.

Compares the numbers printed on the front page of README.md with what git says about the commits
being pushed, and reports when the page is older than the words behind it. No network, and no
ability to stop a push: a stale page is worth a line on the terminal, not a blocked release.
Run by scripts/git-hooks/pre-push, which git calls because core.hooksPath points there.
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
live_commits = git('rev-list', '--count', '--author=%s' % author, '--no-merges', '%s...HEAD' % REF)
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
sys.exit(0)
