#!/usr/bin/env bash
# scripts/install-fork-hooks.sh -- wire this fork's own tooling into a clone.
#
# Run it once after cloning. It sets:
#   git config core.hooksPath scripts/git-hooks     the pre-push reminder, versioned in the tree
#   git config alias.publish-main, alias.fork-refresh
#   a symlink from docs/fork-skills/<name> into the editor's skills directory
#   the fork clauses appended to the commit-message and pr-message skills
#
# The hook, the aliases and the skill texts live in the repository exactly so that a fresh clone
# keeps them; none of this is git's own state, so it has to be re-established per clone. The script
# is idempotent, and it removes the old global publish-main alias that regenerated the pages and
# then pushed the commit from before the regeneration.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

chmod +x scripts/git-hooks/pre-push scripts/git-hooks/pre-push.py \
         scripts/fork-pr-table.sh scripts/publish-main.sh 2>/dev/null || true

git config core.hooksPath scripts/git-hooks
git config alias.publish-main '!cd "$(git rev-parse --show-toplevel)" && scripts/publish-main.sh'
git config alias.fork-refresh '!cd "$(git rev-parse --show-toplevel)" && scripts/fork-pr-table.sh && git --no-pager diff --stat -- README.md docs/FORK.md'
echo 'install: hooksPath = ' "$(git config core.hooksPath)"
echo 'install: aliases   = publish-main, fork-refresh (repository only)'

# A hook left under .git/hooks is inert once core.hooksPath points into the tree, and an inert copy
# of an old reminder is worse than nothing: it reads like the ritual and never runs. Ask for the git
# dir, not for `git rev-parse --git-path hooks`, which answers with core.hooksPath and would name the
# live hook.
old_hook=$(git rev-parse --absolute-git-dir)/hooks/pre-push
if [ -e "$old_hook" ] && [ ! -L "$old_hook" ] \
   && [ "$(realpath "$old_hook")" != "$(realpath scripts/git-hooks/pre-push)" ]; then
  rm -f "$old_hook"
  echo "install: removed the superseded hook at $old_hook — scripts/git-hooks/pre-push is the one that runs"
fi

if git config --global --get-regexp '^alias\.publish-main' >/dev/null 2>&1; then
  git config --global --unset alias.publish-main
  echo 'install: removed the old global alias publish-main, which pushed the page of the previous run'
fi

skills_dir="${SKILLS_DIR:-$HOME/.config/Code/User/skills}"
[ -d "$skills_dir" ] || { echo "install: no skills directory at $skills_dir — skills left alone"; exit 0; }

for s in docs/fork-skills/*; do
  [ -f "$s/SKILL.md" ] || continue       # clauses/ holds fragments, not skills
  name=$(basename "$s")
  target="$skills_dir/$name"
  here=$(pwd)/"$s"
  if [ -L "$target" ] && [ "$(readlink -f "$target")" = "$(readlink -f "$here")" ]; then
    echo "install: skill $name already linked"
  elif [ -e "$target" ]; then
    echo "install: $target exists and is not this repository's $name — left alone"
  else
    ln -s "$here" "$target"
    echo "install: skill $name linked into $skills_dir"
  fi
done

begin='<!-- BEGIN fork clause (scripts/install-fork-hooks.sh) -->'
end='<!-- END fork clause -->'
for frag in docs/fork-skills/clauses/*.md; do
  name=$(basename "$frag" .md)
  skill="$skills_dir/$name/SKILL.md"
  [ -f "$skill" ] || { echo "install: no $name skill installed — clause skipped"; continue; }
  python3 - "$skill" "$frag" "$begin" "$end" <<'PY'
import pathlib, sys
skill, frag = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
begin, end = sys.argv[3], sys.argv[4]
if skill.is_symlink() and skill.resolve().is_relative_to(pathlib.Path('.').resolve()):
    sys.exit('install: %s is this repository\'s own skill — clause skipped' % skill)
clause = '\n'.join([begin, frag.read_text(encoding='utf-8').rstrip(), end]) + '\n'
text = skill.read_text(encoding='utf-8')
if begin in text:
    head = text.split(begin)[0]
    tail = text.split(end, 1)[1] if end in text else ''
    text = head + clause + tail.lstrip('\n')
else:
    text = text.rstrip('\n') + '\n\n' + clause
skill.write_text(text, encoding='utf-8')
print('install: fork clause in place in %s' % skill.name)
PY
done
echo 'install: done'
