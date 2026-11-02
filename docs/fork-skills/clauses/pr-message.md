## When the repository keeps its own ledger of pull requests

When the repository carries `scripts/fork-pr-notes.json`, the front page and the licence record list
every pull request on their own, from that file. The note is written in the same session as the pull
request, before the session is forgotten:

- Add the entry — `area`, `short`, `note` — on the personal branch, and add the number to `features`
  when the pull request carries a feature the front page presents.
- `note` is one sentence about what the change does for the person who runs the app, in the voice of
  a commit message. The row is read years later by someone deciding whether this fork is worth
  cloning, and by the licence record.
- Run `git fork-refresh` and commit the regenerated pages on the personal branch. A pull request
  without a note appears as a loud **TODO** row in both pages.
- A pull request that upstream closes without merging keeps its row in the ledger with its reason and
  leaves the front page: a closed request is not a feature of this fork.
