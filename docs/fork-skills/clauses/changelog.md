## When the repository is a fork of the app

When the repository carries `docs/FORK.md`, most of the work here is the fork's own and never reaches
the application upstream ships. `docs/CHANGELOG.md` speaks for that application:

- A fork-only change gets no entry. The front page and the licence record are where this fork says
  what it adds, and the commit message carries the reason.
- An entry belongs in the changelog only when the change is on its way upstream in a pull request,
  and only when the person asks for one.
- When an entry is written, it takes the wording of that change's commit message body, so one change
  is not described twice in two voices.
