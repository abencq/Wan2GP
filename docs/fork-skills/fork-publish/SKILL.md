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

`scripts/install-fork-hooks.sh` wires those two aliases, the `pre-push` reminder and the skills in
this repository into a clone. Run it once after every fresh clone: hooks, aliases and skills live in
the repository precisely so that they survive a clone, and none of them is active before it runs.

## Who owns which sentence

| file | owns |
|---|---|
| `docs/fork-features.md` | every sentence a reader reads about the features, plus the intro and the install text |
| `scripts/fork-pr-notes.json` | the features, the short titles, the one-line descriptions of each pull request, the closed reasons |
| `scripts/fork-pr-table.sh` | the numbers, the states, the tables, the wrapping, the order |
| `README.md` between the markers | the assembled front page; written by the generator, not by hand |
| `docs/FORK.md` between the markers | the ledger; same |

Edit the first two, never the last two. Between the markers a hand edit is lost at the next
regeneration, and the licence record in `docs/FORK.md` is a generated file.

## Rules

1. **Numbers are counted, never typed.** The size of the fork is `git diff --numstat` against
   `origin/main`, and the commits are `git rev-list --count --author=… --no-merges`, so a sync with
   upstream cannot inflate them; the commits that only refresh the two pages are left out of that
   count, so publishing the page is not counted as work and the headline number does not move when
   the page is published. A typed number in the front page block is a bug: the hand-typed
   `88 files / +13 219 / 75 commits` was already false when it was published.
2. **Look at the remote, generate, commit, read back, push.** The generator rewrites the working
   tree. A refreshed page is an uncommitted change, so pushing first publishes the page of the
   previous run — that was the `publish-main` bug. Publishing also refuses a `fork/main` holding a
   commit the local branch does not contain, and reads the committed pages back from git and the API:
   a generator that cannot reproduce its own output stops the publish, rather than publishing a page
   nobody checked.
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
   licence statement of `docs/FORK.md` with `origin/main`. Silence means the pages match the commits;
   a warning means run `git fork-refresh`. In a clone where the installer has not run, the generator
   says so.
7. **Keep the merge with upstream cheap.** The fork block ends before the `-----` rule that opens
   upstream's README text, and everything below that rule is left byte-identical. Upstream rewrites
   its README about fifty times a year; a fork block that spans their text turns every one of those
   into a conflict.

## Before publishing, check

- `scripts/fork-pr-table.sh --check` says both pages are up to date.
- `scripts/install-fork-hooks.sh` has run in this clone: the generator says when it has not.
- The diff of the generated block changes only numbers, dates and states — a changed *sentence* means
  `docs/fork-features.md` changed, and that is a change worth naming in the commit message.
- Nothing outside the markers moved: `git diff --stat` shows `README.md` and `docs/FORK.md` only.
- The push target is `fork`, not `origin`.
