## In a fork that publishes its own pages

When the repository carries `scripts/publish-main.sh`, its README front page and its `docs/FORK.md`
ledger write themselves from git and from the GitHub API. Two consequences for the message:

- A diff that touches those pages inside their `BEGIN GENERATED` markers is a generated diff. The
  message says the pages were refreshed and names what moved — a count, a merged pull request — and
  it never presents a sentence of them as hand-written work. When a commit carries a real change and
  a regeneration, name the change first and the regeneration last.
- A commit that changes the words behind the pages — `docs/fork-features.md`,
  `scripts/fork-pr-notes.json`, `scripts/fork-pr-table.sh` — changes what the fork says about
  itself. Say which sentence a reader now reads differently, not which file was edited.

Run `git fork-refresh` before committing such a change, so the committed pages match the committed
words. `git publish-main` keeps the order that the pages demand: generate, commit, push.
