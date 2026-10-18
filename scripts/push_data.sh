#!/usr/bin/env bash
# push_data.sh "<commit message>" <path>...
# Commits the given data paths and pushes to the current branch with rebase-and-retry.
#
# Several workflows regenerate the shared ETF analytics files (etf_extras / etf_holdings / etf_smart / etf_audit) from
# their own inputs. When two runs race, a rebase can conflict on those derived files: the conflict is resolved by taking
# main's version and rebuilding them on top of the latest data (then re-auditing), so a race never loses a run's own
# data. If the rebuilt files fail the audit, main's version is kept.
set -u
export PYTHONDONTWRITEBYTECODE=1
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
MSG="$1"; shift
DERIVED="data/etf_extras.json data/etf_holdings.json data/etf_smart.json data/etf_smart_state.json data/etf_audit.json"

[ -n "${GITHUB_ACTIONS:-}" ] && git config --global user.name "github-actions[bot]" && git config --global user.email "github-actions[bot]@users.noreply.github.com"
for p in "$@"; do [ -e "$p" ] || git ls-files --error-unmatch "$p" >/dev/null 2>&1 && git add -A "$p"; done   # one at a time: a missing path must not block the rest
if git diff --staged --quiet; then
  echo "No changes."
  exit 0
fi
git commit -q -m "$MSG"

rebuild_derived() {
  if python scripts/build_etf_extras.py && python scripts/build_etf_smart.py && python scripts/audit_etf_data.py; then
    git add $DERIVED 2>/dev/null || true
  else
    echo "Rebuilt ETF analytics failed the audit — keeping main's version."
    git checkout origin/"$BRANCH" -- $DERIVED 2>/dev/null || true
  fi
}

for attempt in 1 2 3 4 5; do
  if git push -q origin HEAD:"$BRANCH"; then
    echo "Pushed."
    exit 0
  fi
  echo "Push rejected (attempt $attempt). Rebasing..."
  git fetch -q origin "$BRANCH"
  if ! git rebase -q origin/"$BRANCH"; then
    conflicted=$(git diff --name-only --diff-filter=U)
    other=$(echo "$conflicted" | grep -v -x -F -f <(echo "$DERIVED" | tr ' ' '\n') || true)
    if [ -n "$other" ]; then
      echo "Conflict outside the derived ETF files: $other — aborting this attempt."
      git rebase --abort
    else
      echo "Derived ETF files conflict — taking main's version and rebuilding on the latest data."
      git checkout origin/"$BRANCH" -- $conflicted
      rebuild_derived
      git checkout -- . 2>/dev/null || true          # drop stray unstaged changes (caches) so the rebase can continue
      GIT_EDITOR=true git rebase --continue || { git rebase --abort; }
    fi
  fi
  sleep $((attempt * 5))
done
echo "All push attempts failed."
exit 1
