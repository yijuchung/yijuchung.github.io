#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: scripts/release.sh <tag>" >&2
}

fail() {
  echo "Release failed: $*" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

tag="$1"
remote="origin"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ "$tag" == -* ]] ||
  ! git check-ref-format "refs/tags/$tag" >/dev/null 2>&1; then
  fail "'$tag' is not a valid Git tag."
fi

for command in git gh python3 docker; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required."
done

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
  fail "Run this script from a Git worktree."
git remote get-url "$remote" >/dev/null 2>&1 ||
  fail "Git remote '$remote' is not configured."
gh auth status --hostname github.com >/dev/null 2>&1 ||
  fail "Authenticate GitHub CLI with 'gh auth login --hostname github.com'."

branch="$(git symbolic-ref --quiet --short HEAD)" ||
  fail "Releases must be created from a branch, not a detached HEAD."

default_branch="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')" ||
  fail "Could not determine the repository's default branch."
[[ -n "$default_branch" ]] ||
  fail "Could not determine the repository's default branch."

if [[ "$branch" != "$default_branch" ]]; then
  fail "Check out the default branch '$default_branch' before releasing."
fi

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  fail "Commit or stash all working-tree changes before releasing."
fi

echo "Fetching $remote/$branch and tags..."
git fetch --quiet "$remote" --tags

if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null; then
  fail "Tag '$tag' already exists."
fi

remote_tip="$(git rev-parse --verify "refs/remotes/$remote/$branch")" ||
  fail "Could not resolve $remote/$branch."
if ! git merge-base --is-ancestor "$remote_tip" HEAD; then
  fail "Local '$branch' is behind or has diverged from $remote/$branch."
fi

echo "Syncing aggregate contribution metrics..."
python3 scripts/sync_contributions.py

echo "Generating the private-contribution isocalendar..."
metrics_token="$(
  env -u GH_TOKEN -u GITHUB_TOKEN gh auth token --hostname github.com
)" || fail "Could not read the local GitHub CLI token."
METRICS_TOKEN="$metrics_token" scripts/sync_isocalendar.sh
unset metrics_token

unexpected_changes="$(
  git status --porcelain --untracked-files=all -- \
    . \
    ':(exclude)_data/metrics.json' \
    ':(exclude)assets/metrics/isocalendar.svg'
)"
if [[ -n "$unexpected_changes" ]]; then
  printf 'Release failed: contribution sync changed unexpected files:\n%s\n' \
    "$unexpected_changes" >&2
  exit 1
fi

git add -- _data/metrics.json assets/metrics/isocalendar.svg
if git diff --cached --quiet; then
  echo "Contribution artifacts are unchanged; tagging the current commit."
else
  git commit -m "Sync contribution metrics for $tag"
fi

git tag --annotate --message "Release $tag" -- "$tag"

echo "Pushing $branch and $tag atomically..."
git push --atomic "$remote" \
  "HEAD:refs/heads/$branch" \
  "refs/tags/$tag"

echo "Creating GitHub release $tag..."
gh release create "$tag" \
  --verify-tag \
  --generate-notes \
  --title "$tag"
