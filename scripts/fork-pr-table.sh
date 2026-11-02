#!/usr/bin/env bash
# scripts/fork-pr-table.sh -- regenerate this fork's own pages from git and from the GitHub API.
#
#   scripts/fork-pr-table.sh          rewrite docs/FORK.md and the front page block of README.md
#   scripts/fork-pr-table.sh --check  exit 1 when either file is not up to date
#
# docs/FORK.md   the ledger: the state of my pull requests, in tables, between the markers.
# README.md      the front page: the size of the fork from git, the features of docs/fork-features.md
#                with the live state of their pull requests, and the table of the pull requests that
#                are open upstream. Between its own markers; the words live in docs/fork-features.md.
#
# The hand-written wording is scripts/fork-pr-notes.json (the rows, the features, the short titles)
# and docs/fork-features.md (the sentences of the front page). New pull requests, closures and
# upstream acceptances appear by themselves; a pull request with no note appears as a loud TODO row.
# The size of the fork is computed, never typed: git diff and git rev-list against origin/main, with
# authored commits counted by --no-merges so a sync with upstream cannot inflate the number.
# Needs an authenticated gh, and a fetched origin/main for the "behind" counts.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
MODE="${1:-write}"
case "$MODE" in
  write|check) ;;
  --check) MODE=check ;;
  -h|--help) echo "usage: $(basename "$0") [--check]"; exit 0 ;;
  *) echo "usage: $(basename "$0") [--check]" >&2; exit 2 ;;
esac
if [ "$MODE" = write ] && [ -n "${FORK_TABLE_SKIP:-}" ]; then
  exit 0                      # set by git during a merge, where rewriting is pointless
fi
export FORK_TABLE_MODE="$MODE"
exec python3 - <<'PY'
import datetime, json, os, re, subprocess, sys, textwrap

root = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                      capture_output=True, text=True).stdout.strip()
notes_file = os.path.join(root, 'scripts', 'fork-pr-notes.json')
features_file = os.path.join(root, 'docs', 'fork-features.md')
ledger = os.path.join(root, 'docs', 'FORK.md')
front = os.path.join(root, 'README.md')
mode = os.environ['FORK_TABLE_MODE']
BEGIN, END = '<!-- BEGIN GENERATED', '<!-- END GENERATED -->'
GREEN = 'https://img.shields.io/badge/merged-brightgreen'
REF = 'refs/remotes/origin/main'

def gh(path):
    r = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
    if r.returncode != 0:
        first = (r.stderr or '').strip().splitlines()
        sys.exit('fork-pr-table: gh api %s failed: %s'
                 % (path, first[0] if first else 'no output'))
    return json.loads(r.stdout)

def git(*args):
    r = subprocess.run(('git',) + args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''

notes = json.load(open(notes_file, encoding='utf-8'))
up, author = notes['upstream_repo'], notes['author']
areas, prs = notes['areas'], notes['prs']
closed_reason, fork_only = notes.get('closed_reason', {}), notes.get('fork_only', [])
features = notes.get('features', [])

q = 'repo:%s+is:pr+author:%s' % (up, author)
open_nums = [i['number'] for i in gh('search/issues?q=%s+state:open&per_page=200' % q)['items']]
merged_nums = [i['number'] for i in gh('search/issues?q=%s+is:merged&per_page=200' % q)['items']]
dead_nums = [i['number'] for i in gh('search/issues?q=%s+is:closed+is:unmerged&per_page=200' % q)['items']]

info, supersedes = {}, {}
for n in sorted(set(open_nums) | set(merged_nums) | set(dead_nums)):
    d = gh('repos/%s/pulls/%d' % (up, n))
    base_behind = git('rev-list', '--count', '%s..%s' % (d['base']['sha'], REF))
    shipped = ''
    if d.get('merged_at') and d.get('merge_commit_sha'):
        tags = git('tag', '--contains', d['merge_commit_sha']).split()
        tags = [t for t in tags if not t.startswith('backup-')]
        shipped = ' shipped in ' + ', '.join(sorted(tags)[-2:]) if tags else ''
    info[n] = {
        'title': d['title'], 'url': d['html_url'],
        'state': 'merged' if d.get('merged_at') else ('open' if d['state'] == 'open' else 'closed'),
        'commits': d['commits'], 'files': d['changed_files'],
        'add': d['additions'], 'del': d['deletions'],
        'mergeable': d.get('mergeable_state') or '?',
        'behind': base_behind if base_behind.isdigit() else '?',
        'created': d['created_at'][:10],
        'closed': (d.get('closed_at') or '')[:10],
        'merged': (d.get('merged_at') or '')[:10],
        'shipped': shipped,
    }
    for m in re.finditer(r'supersedes and closes #(\d+)|supersedes #(\d+)', d.get('body') or '', re.I):
        supersedes[int(m.group(1) or m.group(2))] = n

unknown = sorted(int(k) for k in prs if int(k) not in info)
for f in features:
    missing = [n for n in f['prs'] if n not in info]
    if missing:
        sys.exit('fork-pr-table: feature %s names pull request(s) %s, which are not mine upstream'
                 % (f['id'], ', '.join(map(str, missing))))
    if not os.path.exists(os.path.join(root, f.get('image', '.'))):
        f.pop('image', None)          # never publish a link to a picture that is not there

def label(n):
    e = info[n]
    if e['state'] == 'open':
        return 'open · %s · %s behind' % (e['mergeable'], e['behind'])
    if e['state'] == 'merged':
        return 'accepted %s%s' % (e['merged'], e['shipped'])
    return 'closed %s' % e['closed']

def sup(n):
    return ' (supersedes #%d)' % supersedes[n] if n in supersedes else ''

def row(area, text, n):
    e = info[n]
    return '| %s | %s | [#%d](%s) | %s |' % (area, text, n, e['url'], label(n))

order = list(areas)
def rank(n):
    a = prs.get(str(n), {}).get('area', '')
    return (order.index(a) if a in order else len(order), -n)

today = datetime.date.today().isoformat()
tip = git('rev-parse', '--short', REF) or '?'
L = ['<!-- BEGIN GENERATED by scripts/fork-pr-table.sh -- do not edit between the markers;',
     '     the hand-written wording is in scripts/fork-pr-notes.json -->',
     '*current as of %s · upstream `%s` · %d open · %d merged · %d closed without merge*'
     % (today, tip, len(open_nums), len(merged_nums), len(dead_nums)), '',
     '### In this fork, submitted upstream',
     '| Area | What it does | PR | State |', '|---|---|---|---|']
for n in sorted(open_nums, key=rank):
    note = prs.get(str(n))
    area = areas.get(note['area'], note['area']) if note else '**TODO**'
    text = note['note'] if note else '**add a note for this PR in scripts/fork-pr-notes.json** (%s)' % info[n]['title']
    L.append(row(area, text + sup(n), n))
L.append('')

L += ['### Only in this fork, not submitted', '| Area | What it does |', '|---|---|']
for e in fork_only:
    L.append('| %s | %s |' % (areas.get(e['area'], e['area']), e['note']))
L.append('')

L += ['### Merged upstream — removed from this fork', '| Area | What it does | PR | State |', '|---|---|---|---|']
if merged_nums:
    for n in sorted(merged_nums, key=rank):
        note = prs.get(str(n))
        L.append(row(areas.get(note['area'], note['area']) if note else info[n]['title'],
                     note['note'] if note else info[n]['title'], n))
else:
    del L[-2:]            # keep the heading, drop the empty table
    L.append('*(none yet — nothing of mine has been accepted upstream as of %s. When a pull request'
             ' is merged, its row moves here by itself and leaves the list above.)*' % today)
L.append('')

L += ['### Closed without merge', '| PR | Why |', '|---|---|']
for n in sorted(dead_nums, reverse=True):
    why = closed_reason.get(str(n)) or 'not picked up'
    for other, who in supersedes.items():
        if other == n:
            w = info.get(who, {})
            when = w.get('closed') or w.get('merged') or ''
            why = 'superseded by #%d (%s%s)' % (who, w.get('state', 'open'),
                                                ' on ' + when if when else '')
    L.append('| [#%d](%s) | %s — %s |' % (n, info[n]['url'], info[n]['title'], why))
L.append('<!-- END GENERATED -->')
block = '\n'.join(L)

# ---- the front page block of README.md ---------------------------------------------------
def num(n):
    return format(int(n), ',').replace(',', ' ')

def fork_size():
    """The size of this fork against upstream, from git alone: a file count is never typed again."""
    names = [l for l in git('diff', '--name-only', '%s...HEAD' % REF).splitlines() if l.strip()]
    adds = dels = 0
    for line in git('diff', '--numstat', '%s...HEAD' % REF).splitlines():
        p = line.split('\t')
        if len(p) > 1:
            adds += int(p[0]) if p[0].isdigit() else 0
            dels += int(p[1]) if p[1].isdigit() else 0
    commits = git('rev-list', '--count', '--author=%s' % author, '--no-merges', '%s...HEAD' % REF)
    return len(names), adds, dels, (commits or '?')

def wrap(text, width=100):
    """A generated sentence, wrapped like the prose around it; a bullet keeps its indent."""
    bullet = text.startswith('- ')
    return textwrap.fill(text, width=width, subsequent_indent='  ' if bullet else '')

def sections():
    """docs/fork-features.md, split on its own directives: intro, each feature, closing."""
    out, key, buf = {}, None, []
    for line in open(features_file, encoding='utf-8').read().splitlines():
        s = line.strip()
        if s == '<!-- end -->':
            if key:
                out[key] = '\n'.join(buf).strip('\n')
            key, buf = None, []
        elif key is None and s.startswith('<!--') and s.endswith('-->'):
            key, buf = s[5:-3].strip(), []
        elif key:
            buf.append(line)
    if key:
        out[key] = '\n'.join(buf).strip('\n')
    return out

def state_phrase(n):
    e = info[n]
    if e['state'] == 'merged':
        return '**Merged** ![merged](%s) on %s%s' % (GREEN, e['merged'], e['shipped'])
    if e['state'] == 'closed':
        return 'closed without merge on %s' % e['closed']
    return 'open, not accepted'

def feature_bullets(f):
    """The bullets the front page writes for itself: the size of the change, the doc, the state."""
    out = []
    if f.get('stat'):
        files = sum(info[n]['files'] for n in f['prs'])
        adds = sum(info[n]['add'] for n in f['prs'])
        which = ' · '.join('PR #%d' % n for n in f['prs'])
        out.append(wrap('- %s files, +%s lines%s (%s)'
                        % (num(files), num(adds), f.get('stat_extra', ''), which)))
    if f.get('doc_note'):
        out.append(wrap('- ' + f['doc_note']))
    links = []
    for n in f['prs']:
        short = prs.get(str(n), {}).get('short', '')
        links.append('**[PR #%d](%s)**%s' % (n, info[n]['url'],
                                             (' (%s)' % short) if short else sup(n)))
    states = {info[n]['state'] for n in f['prs']}
    if len(states) == 1:
        st = states.pop()
        tail = '' if st == 'merged' else (', so today this needs the fork' if st == 'open'
                                          else ' — the feature lives in this fork')
        out.append(wrap('- upstream: %s — %s%s'
                        % (' and '.join(links), state_phrase(f['prs'][0]), tail)))
    else:
        for n, link in zip(f['prs'], links):
            out.append(wrap('- upstream: %s — %s' % (link, state_phrase(n))))
    return out

sec = sections()
files_n, adds_n, dels_n, commits_n = fork_size()
claim = notes.get('front_claim_sentence',
                  'Everything general enough is submitted upstream, which means the')
synced = 'synced with upstream `%s`' % tip
SHIELDS_OPEN = ('![upstream PRs open](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2F'
                'api.github.com%2Fsearch%2Fissues%3Fq%3Drepo%3Adeepbeepmeep%2FWanGP%2Bis%3Apr%2B'
                'author%3Aabencq%2Bis%3Aopen&query=%24.total_count&label=upstream%20PRs%20open&color=blue)')
SHIELDS_MERGED = ('![upstream PRs merged](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2F'
                  'api.github.com%2Fsearch%2Fissues%3Fq%3Drepo%3Adeepbeepmeep%2FWanGP%2Bis%3Apr%2B'
                  'author%3Aabencq%2Bis%3Amerged&query=%24.total_count&label=upstream%20PRs%20merged&color=blue)')

F = ['<!-- BEGIN GENERATED (front page) by scripts/fork-pr-table.sh -- do not edit between the markers;',
     '     the words are docs/fork-features.md, the size comes from git, the states from the API -->',
     '# Wan2GP — unofficial fork of WanGP', '',
     '[![fork of WanGP](https://img.shields.io/badge/fork_of-WanGP-blue)](https://github.com/deepbeepmeep/WanGP)',
     '![synced with upstream](https://img.shields.io/badge/synced_with_upstream-%s-orange)' % tip,
     SHIELDS_OPEN, SHIELDS_MERGED, '', sec['intro'], '',
     wrap('The `main` branch here is an integration branch: current upstream, plus my own work — '
          '**%s files, +%s lines**, %s authored commits, %s. %s %d features below are '
          '**not in an official WanGP release today**.'
          % (num(files_n), num(adds_n), commits_n, synced, claim, len(features))), '']
for f in features:
    F += ['## ' + f['title'], '']
    for ln in sec.get('feature: ' + f['id'], '').splitlines():
        s = ln.strip()
        if s == '<!-- image -->':
            if 'image' in f:
                F.append('![%s](%s)' % (f.get('alt', f['title']), f['image']))
        elif s == '<!-- bullets -->':
            bullets = feature_bullets(f)
            if bullets and F and F[-1] == '' and len(F) > 1 and F[-2].startswith('- '):
                F.pop()           # keep a bullet list tight
            F += bullets
        else:
            F.append(ln)
    F.append('')

claimed = {n for f in features for n in f['prs']}
F += ['## Also in this fork', '', '| Feature | What it does | Upstream |', '|---|---|---|']
for n in [x for x in sorted(open_nums, key=rank) if x not in claimed] \
        + [x for x in sorted(merged_nums, key=rank) if x not in claimed]:
    note = prs.get(str(n)) or {}
    title = note.get('short') or '**add a short title in scripts/fork-pr-notes.json** (%s)' % info[n]['title']
    what = note.get('note') or info[n]['title']
    link = '[#%d](%s)' % (n, info[n]['url'])
    state = link + (' **Merged** ![merged](%s) %s' % (GREEN, info[n]['merged'])
                    if info[n]['state'] == 'merged' else ' open')
    F.append('| %s | %s | %s |' % (title, what, state))
F += ['', wrap('The table lists what is **open upstream** and what upstream has **accepted**, the latter '
               'as **Merged** ![merged](%s). A pull request closed without merging is not a feature of this '
               'fork, so it is not listed here; [docs/FORK.md](docs/FORK.md) keeps those with their reason, '
               'as the licence record asks, and it is regenerated from the GitHub API on every publish.'
               % GREEN), '',
      sec['closing'], '',
      '<!-- front page: regenerated %s · %s files +%s lines · %s authored commits · %d open, %d merged upstream -->'
      % (today, files_n, adds_n, commits_n, len(open_nums), len(merged_nums)),
      '<!-- END GENERATED -->']
front_block = '\n'.join(F)

def rewrite(path, new_block):
    cur = open(path, encoding='utf-8').read()
    i, j = cur.find(BEGIN), cur.find(END)
    if i < 0 or j < 0:
        sys.exit('fork-pr-table: the BEGIN/END GENERATED markers are missing from %s'
                 % os.path.relpath(path, root))
    if path == front and cur[:i].strip():
        sys.exit('fork-pr-table: the front page block must start at the top of README.md')
    tail = cur[j + len(END):].lstrip('\n')
    while tail.startswith(END):
        tail = tail[len(END):].lstrip('\n')     # the block brings its own END
    return cur, cur[:i] + new_block + '\n\n' + tail

stale = []
wrote = []
for path, new_block in ((ledger, block), (front, front_block)):
    cur, new = rewrite(path, new_block)
    if new == cur:
        continue
    if mode == 'check':
        stale.append(os.path.relpath(path, root))
    else:
        open(path, 'w', encoding='utf-8').write(new)
        wrote.append(os.path.relpath(path, root))
        print('fork-pr-table: %s rewritten' % wrote[-1])
if mode == 'check':
    if stale:
        sys.exit('fork-pr-table: out of date: %s — run scripts/fork-pr-table.sh' % ', '.join(stale))
    print('fork-pr-table: docs/FORK.md and README.md are up to date')
elif not wrote:
    print('fork-pr-table: docs/FORK.md and README.md already up to date')
PY
