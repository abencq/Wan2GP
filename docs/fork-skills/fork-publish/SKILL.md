---
name: fork-publish
description: "Use when working in this fork of Wan2GP and its own pages are involved: publishing main to the fork remote, refreshing README.md's front page or the docs/FORK.md ledger, running git publish-main or git fork-refresh, after opening a pull request upstream, after a pull request is merged or closed, after adding a feature to the fork, and after a fresh clone. Covers which file owns which sentence, why the numbers are never typed, why the pages are committed before the push, and what must never be pushed."
---

# Fork Publish

This fork keeps two pages that write themselves: the front page block of `README.md` and the ledger
tables of `docs/FORK.md`. Both come from `scripts/fork-pr-table.sh`, which reads git for the size of
the fork and the GitHub API for the state of every pull request. The ritual below keeps them true.

## The three commands

| command | what it does |
|---|---|
| `git fork-refresh` | regenerate both pages and show the diff; commits nothing, pushes nothing |
| `git publish-main` | look at `fork/main`, regenerate, commit the regenerated pages, read them back, push `local` to `fork/main` |
| `git publish-main --fast` | the same, without the read-back (one API pass less, for when the page is known good) |
| `scripts/fork-pr-table.sh --check` | exit 1 when a page is not what the data says today |
| `scripts/fork-table-fixture-test.sh` | run the generator in a scratch repository against written-down answers of the API: the accepted, shipped and closed paths, offline |

`scripts/install-fork-hooks.sh` wires those two aliases, the `pre-push` reminder and the skills in
this repository into a clone. Run it once after every fresh clone: hooks, aliases and skills live in
the repository precisely so that they survive a clone, and none of them is active before it runs.

## Who owns which sentence

| file | owns |
|---|---|
| `docs/fork-features.md` | every sentence a reader reads about the features, plus the intro and the install text |
| `docs/fork-unreleased.md` | the Unreleased entries of the front page: the section the changelog used to carry under Unreleased |
| `scripts/fork-pr-notes.json` | the features, the short titles, the one-line descriptions of each pull request, the closed reasons |
| `scripts/fork-pr-table.sh` | the numbers, the states, the tables, the wrapping, the order, the claim of the headline |
| `README.md` between the markers | the assembled front page; written by the generator, not by hand |
| `docs/FORK.md` between the markers | the ledger; same |
| `docs/FORK.md` between the `<!-- SYNCED -->` markers | the sentence of the licence record naming the upstream commit and release this fork sits on |

Edit the first two, never the last two. Between the markers a hand edit is lost at the next
regeneration. The statement of modifications in `docs/FORK.md` is hand-written prose around one
generated sentence: the sentence that names the commit is written by the generator, because it is only
true of the commit it names, and a hand-typed one drifts on the first sync.

## Rules

1. **Numbers are counted, never typed.** The size of the fork is `git diff --numstat` against the
   merge base with `origin/main`, and the commits are `git rev-list --count --author=… --no-merges`.
   Neither moves when upstream is merged, so a sync cannot inflate them; the commits that only refresh
   the two pages are left out of that count, so publishing the page is not counted as work and the
   headline number does not move when the page is published. A typed number in the front page block is
   a bug: the hand-typed `88 files / +13 219 / 75 commits` was already false when it was published.
2. **Look at the remote, generate, commit, read back, push.** The generator rewrites the working
   tree. A refreshed page is an uncommitted change, so pushing first publishes the page of the
   previous run — that was the `publish-main` bug. Publishing commits only hunks that sit in a
   generated region: the block, and the licence sentence between the inline `<!-- SYNCED -->` markers;
   `scripts/page-hunk-check.sh` answers that, and a hand-written sentence in a page is refused its
   place in the publish. Publishing also refuses a `fork/main` holding a commit the local branch does
   not contain, and reads the committed pages back from git and the API: a generator that cannot
   reproduce its own output stops the publish, rather than publishing a page nobody checked.
3. **A pull request closed without merging is not a feature.** It stays out of the front page table
   and out of the feature sections; `docs/FORK.md` keeps it with its reason, as the licence record asks.
4. **A new pull request needs a note in the same session it is opened.** Add its `area`, `short` and
   `note` to `scripts/fork-pr-notes.json` (and to `features` when it carries a front-page feature).
   Without a note, the row appears as a loud **TODO** in both pages at the next regeneration.
5. **Never push to upstream.** In this clone `origin` is `deepbeepmeep/WanGP` and `fork` is
   `abencq/Wan2GP`. `git publish-main` refuses a remote whose URL names the upstream owner; a manual
   push is `git push fork local:main`.
6. **The pre-push hook is a reminder, not a gate.** It never touches the network and never stops a
   push. It compares the numbers on the front page with git, the dates of the two pages with today and
   with each other, the words behind the page with the page, and the upstream commit named in the
   licence statement of `docs/FORK.md` with the newest upstream commit the branch carries. It also says
   when `origin/main` has moved past that commit: that is a sync to do, not a page to fix, and the
   licence statement must not move before the merge does. Silence means the pages match the commits;
   a warning means run `git fork-refresh`. In a clone where the installer has not run, the generator
   says so.
7. **Keep the merge with upstream cheap.** The fork block ends before the `-----` rule that opens
   upstream's README text, and everything below that rule is left byte-identical. Upstream rewrites
   its README about fifty times a year; a fork block that spans their text turns every one of those
   into a conflict.
8. **The claim about releases is counted, feature by feature.** Upstream puts no release tag on the
   application — its only tags are the manager's — so the release an acceptance went into is the
   `WanGP_version` in `wgp.py` at the merge commit. That is where the row `accepted 2026-11-10 in
   v19.02`, the bullet "in v19.02, so this fork is not needed for it", and the headline "2 of the 3
   features below are in an official WanGP release" come from. A merge commit that is not in the
   fetched history says `not in a release yet`: the page never guesses a release, and a feature counts
   as released only when every pull request behind it is accepted into one.

## Before publishing, check

- `scripts/fork-pr-table.sh --check` says both pages are up to date.
- `scripts/install-fork-hooks.sh` has run in this clone: the generator says when it has not.
- The diff of the generated block changes only numbers, dates and states — a changed *sentence* means
  a word file changed, `docs/fork-features.md` or `docs/fork-unreleased.md`, and that is a change worth
  naming in the commit message.
- Nothing outside the markers moved: `git diff --stat` shows `README.md` and `docs/FORK.md` only.
- After a change to the generator, `scripts/fork-table-fixture-test.sh` passes. It is the only place
  where an accepted pull request, a shipped release and a closure are exercised, because nothing of
  mine is merged upstream today.
- The push target is `fork`, not `origin`.
