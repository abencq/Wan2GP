#!/usr/bin/env python3
"""scripts/fork-api-fixture.py — one scenario of the GitHub API, written down.

The page generator reads the state of every pull request of the upstream repository from the API, so
anything that runs the generator needs an answer. FORK_TABLE_FIXTURES points it at a JSON map of API
path to response, and this builds such a map from the real scripts/fork-pr-notes.json and the commit
shas of a scratch repository: which pull requests are open, which are merged and into which merge
commit, which were closed unmerged. Nothing is fetched, nothing is pushed.

It is called with the environment, and writes API/api.json:

  NOTES=scripts/fork-pr-notes.json FIX_MERGED='{"2441": "<sha>"}' FIX_CLOSED='[2286]' \\
      UP_TIP=<the upstream commit the scratch fork sits on> API=<a directory> \\
      scripts/fork-api-fixture.py

scripts/fork-table-fixture-test.sh drives it through the scenarios that matter on the day upstream
accepts a pull request; the suites under scripts/fork-checks/ use it so a scratch clone never has to
ask the network what a scratch clone can be told.
"""
import json, os

notes = json.load(open(os.environ['NOTES'], encoding='utf-8'))
up, author = notes['upstream_repo'], notes['author']
merged = {int(k): v for k, v in json.loads(os.environ['FIX_MERGED']).items()}
closed = set(int(n) for n in json.loads(os.environ['FIX_CLOSED']))
base = os.environ['UP_TIP']
nums = sorted(set(int(k) for k in notes['prs']) | {n for f in notes['features'] for n in f['prs']})


def at(n, when):
    return {'number': n, 'total_count': 1, 'items': [{'number': n} for n in when]}


def detail(n):
    url = 'https://github.com/%s/pull/%d' % (up, n)
    body = {'title': 'pull request #%d' % n, 'html_url': url, 'base': {'sha': base}, 'body': '',
            'commits': 3, 'changed_files': 12, 'additions': 900, 'deletions': 30,
            'mergeable_state': 'clean', 'created_at': '2026-01-01T10:00:00Z'}
    if n in merged:
        body.update(state='closed', merged_at='2026-11-10T10:00:00Z', merge_commit_sha=merged[n],
                    closed_at='2026-11-10T10:00:00Z')
    elif n in closed:
        body.update(state='closed', merged_at=None, merge_commit_sha='',
                    closed_at='2026-09-01T10:00:00Z')
    else:
        body.update(state='open', merged_at=None, merge_commit_sha='')
    return body


q = 'repo:%s+is:pr+author:%s' % (up, author)
open_list = [n for n in nums if n not in merged and n not in closed]
api = {'search/issues?q=%s+state:open&per_page=200' % q: at(0, open_list),
       'search/issues?q=%s+is:merged&per_page=200' % q: at(0, sorted(merged)),
       'search/issues?q=%s+is:closed+is:unmerged&per_page=200' % q: at(0, sorted(closed))}
for n in nums:
    api['repos/%s/pulls/%d' % (up, n)] = detail(n)
json.dump(api, open(os.path.join(os.environ['API'], 'api.json'), 'w'), indent=1)
