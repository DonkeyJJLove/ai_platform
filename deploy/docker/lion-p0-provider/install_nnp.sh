#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -eq 3 ]] || { echo "usage: install_nnp.sh <repo-root> <head> <tree>" >&2; exit 2; }
REPO_ROOT="$(realpath "$1")"; HEAD="$2"; TREE="$3"
HELPER="$REPO_ROOT/tools/lion_nnp_runuser_compat.py"
[[ -f "$HELPER" ]] || { echo "ERROR: NNP runuser compatibility helper missing" >&2; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
ln -s "$HELPER" "$TMP/runuser"
PATH="$TMP:/usr/sbin:/usr/bin:/bin" RESTART_RUNNER="${RESTART_RUNNER:-0}" \
  /usr/bin/bash "$REPO_ROOT/deploy/docker/lion-p0-provider/install.sh" "$REPO_ROOT" "$HEAD" "$TREE"
