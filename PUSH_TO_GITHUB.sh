#!/usr/bin/env bash
# One command: creates a PRIVATE repo on your GitHub and pushes everything.
# Needs the GitHub CLI logged in once: gh auth login
set -e
REPO_NAME="${1:-inventory-devops}"
[ -d .git ] || { echo "Run this inside the unzipped inventory-devops folder"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login
gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
echo "Done. Repo: $(gh repo view --json url -q .url)"
echo "Watch the pipeline: gh run watch   (or open the Actions tab)"
