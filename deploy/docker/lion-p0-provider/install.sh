#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="LION-AUTH-LAB"
RUNTIME_USER="lion-container-runtime-lab"
RUNNER_USER="lion-maintenance-runner"
PROVIDER_GROUP="lion-docker-p0"
RUNNER_UNIT="actions.runner.DonkeyJJLove-ai_platform.lion-moon-r9d8-test.service"
PROVIDER_UNIT="lion-p0-rootless-docker-provider.service"

usage() {
  cat <<'EOF'
Usage:
  sudo bash install.sh <repo-root> <expected-head-sha40> <expected-tree-sha40>

Optional:
  RESTART_RUNNER=1 sudo -E bash install.sh ...
EOF
}

if [[ $# -ne 3 ]]; then
  usage >&2
  exit 2
fi

REPO_ROOT="$(realpath "$1")"
EXPECTED_HEAD="$2"
EXPECTED_TREE="$3"

if [[ "$(id -u)" != "0" ]]; then
  echo "ERROR: run as root" >&2
  exit 1
fi

if [[ "$(hostname)" != "$TARGET_HOST" ]]; then
  echo "ERROR: wrong host: $(hostname), expected $TARGET_HOST" >&2
  exit 1
fi

if ! grep -qi microsoft /proc/sys/kernel/osrelease; then
  echo "ERROR: target is not WSL2" >&2
  exit 1
fi

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: expected linux/amd64 host" >&2
  exit 1
fi

if [[ ! "$EXPECTED_HEAD" =~ ^[0-9a-f]{40}$ || ! "$EXPECTED_TREE" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: expected Git identities must be full lowercase SHA-1" >&2
  exit 1
fi

ACTUAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD)"
ACTUAL_TREE="$(git -C "$REPO_ROOT" rev-parse 'HEAD^{tree}')"
if [[ "$ACTUAL_HEAD" != "$EXPECTED_HEAD" || "$ACTUAL_TREE" != "$EXPECTED_TREE" ]]; then
  echo "ERROR: checkout currentness mismatch" >&2
  echo "actual_head=$ACTUAL_HEAD expected_head=$EXPECTED_HEAD" >&2
  echo "actual_tree=$ACTUAL_TREE expected_tree=$EXPECTED_TREE" >&2
  exit 1
fi

for path in \
  "$REPO_ROOT/tools/p0_rootless_docker_provider.py" \
  "$REPO_ROOT/tools/p0_rootless_docker_provider_client.py" \
  "$REPO_ROOT/tools/p0_docker_fleet_contract.py" \
  "$REPO_ROOT/tools/p0_docker_drone_runtime.py" \
  "$REPO_ROOT/deploy/docker/lion-drone-p0/Dockerfile" \
  "$REPO_ROOT/deploy/docker/lion-p0-provider/lion-p0-rootless-docker-provider.service"
do
  [[ -f "$path" ]] || { echo "ERROR: required source missing: $path" >&2; exit 1; }
done

id "$RUNTIME_USER" >/dev/null
id "$RUNNER_USER" >/dev/null

RUNTIME_UID="$(id -u "$RUNTIME_USER")"
RUNNER_UID="$(id -u "$RUNNER_USER")"
ROOTLESS_RUNTIME_DIR="/run/user/$RUNTIME_UID"
ROOTLESS_SOCKET="$ROOTLESS_RUNTIME_DIR/docker.sock"

if [[ ! -d "$ROOTLESS_RUNTIME_DIR" ]]; then
  echo "ERROR: rootless runtime dir missing: $ROOTLESS_RUNTIME_DIR" >&2
  exit 1
fi

if [[ "$(stat -c %U "$ROOTLESS_RUNTIME_DIR")" != "$RUNTIME_USER" ]]; then
  echo "ERROR: rootless runtime dir owner mismatch" >&2
  exit 1
fi

if [[ ! -S "$ROOTLESS_SOCKET" ]]; then
  echo "ERROR: rootless Docker socket missing: $ROOTLESS_SOCKET" >&2
  exit 1
fi

if [[ "$(systemctl show -p User --value "$RUNNER_UNIT")" != "$RUNNER_USER" ]]; then
  echo "ERROR: runner unit/user mismatch: $RUNNER_UNIT" >&2
  exit 1
fi

runuser -u "$RUNTIME_USER" -- env \
  HOME="/home/$RUNTIME_USER" \
  XDG_RUNTIME_DIR="$ROOTLESS_RUNTIME_DIR" \
  DOCKER_HOST="unix://$ROOTLESS_SOCKET" \
  /usr/bin/docker version --format '{{.Server.Version}}' >/dev/null

if ! getent group "$PROVIDER_GROUP" >/dev/null; then
  groupadd --system "$PROVIDER_GROUP"
fi

# Dedicated provider-access group only. Never grant access to the rootful `docker` group.
usermod -aG "$PROVIDER_GROUP" "$RUNTIME_USER"
usermod -aG "$PROVIDER_GROUP" "$RUNNER_USER"

install -d -o root -g root -m 0755 /opt/lion/docker-p0-provider
install -d -o root -g root -m 0755 /opt/lion/docker-p0-provider/build-context
install -d -o root -g root -m 0755 /opt/lion/docker-p0-provider/build-context/tools
install -d -o "$RUNTIME_USER" -g "$RUNTIME_USER" -m 0700 /var/lib/lion/docker-p0-provider
install -d -o root -g root -m 0755 /etc/lion

install -o root -g root -m 0555 \
  "$REPO_ROOT/tools/p0_rootless_docker_provider.py" \
  /opt/lion/docker-p0-provider/provider.py

install -o root -g root -m 0444 \
  "$REPO_ROOT/deploy/docker/lion-drone-p0/Dockerfile" \
  /opt/lion/docker-p0-provider/build-context/Dockerfile

install -o root -g root -m 0444 \
  "$REPO_ROOT/tools/p0_docker_fleet_contract.py" \
  /opt/lion/docker-p0-provider/build-context/tools/p0_docker_fleet_contract.py

install -o root -g root -m 0444 \
  "$REPO_ROOT/tools/p0_docker_drone_runtime.py" \
  /opt/lion/docker-p0-provider/build-context/tools/p0_docker_drone_runtime.py

cat >/opt/lion/docker-p0-provider/build-context/source-identity.json <<EOF
{"repository":"DonkeyJJLove/ai_platform","source_head":"$EXPECTED_HEAD","source_tree":"$EXPECTED_TREE","trust_class":"TEST_ONLY"}
EOF
chmod 0444 /opt/lion/docker-p0-provider/build-context/source-identity.json

cat >/etc/lion/docker-p0-provider.env <<EOF
LION_P0_PROVIDER_SOCKET=/run/lion-docker-p0/provider.sock
LION_P0_STATE_DIR=/var/lib/lion/docker-p0-provider
LION_P0_BUILD_CONTEXT=/opt/lion/docker-p0-provider/build-context
LION_P0_DOCKER_HOST=unix://$ROOTLESS_SOCKET
LION_P0_ALLOWED_CALLER_UID=$RUNNER_UID
LION_P0_PROVIDER_GROUP=$PROVIDER_GROUP
EOF
chmod 0640 /etc/lion/docker-p0-provider.env
chown root:"$PROVIDER_GROUP" /etc/lion/docker-p0-provider.env

cat >/etc/tmpfiles.d/lion-docker-p0.conf <<EOF
d /run/lion-docker-p0 0770 root $PROVIDER_GROUP - -
EOF
systemd-tmpfiles --create /etc/tmpfiles.d/lion-docker-p0.conf

install -o root -g root -m 0644 \
  "$REPO_ROOT/deploy/docker/lion-p0-provider/lion-p0-rootless-docker-provider.service" \
  "/etc/systemd/system/$PROVIDER_UNIT"

RUNNER_DROPIN_DIR="/etc/systemd/system/${RUNNER_UNIT}.d"
install -d -o root -g root -m 0755 "$RUNNER_DROPIN_DIR"
cat >"$RUNNER_DROPIN_DIR/10-lion-docker-p0.conf" <<EOF
[Service]
SupplementaryGroups=$PROVIDER_GROUP
EOF
chmod 0644 "$RUNNER_DROPIN_DIR/10-lion-docker-p0.conf"

systemctl daemon-reload
systemctl enable --now "$PROVIDER_UNIT"

if [[ "$(systemctl is-active "$PROVIDER_UNIT")" != "active" ]]; then
  systemctl status "$PROVIDER_UNIT" --no-pager >&2 || true
  exit 1
fi

PING_REQUEST="$(mktemp)"
trap 'rm -f "$PING_REQUEST"' EXIT
python3 - "$PING_REQUEST" "$EXPECTED_HEAD" "$EXPECTED_TREE" <<'PY'
import hashlib
import json
import sys
path, head, tree = sys.argv[1:]
req = {
    "schema_version": "1.0.0",
    "request_id": "0" * 64,
    "operation": "PING",
    "mission_id": "bootstrap-probe",
    "fleet_id": "lion-local-swarm-p0",
    "run_id": "bootstrap-probe",
    "source_head": head,
    "source_tree": tree,
    "plan_digest": hashlib.sha256(b"bootstrap-probe").hexdigest(),
    "payload": {},
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(req, handle, sort_keys=True, separators=(",", ":"))
PY

chown root:"$PROVIDER_GROUP" "$PING_REQUEST"
chmod 0640 "$PING_REQUEST"

runuser \
  -u "$RUNNER_USER" \
  -g "$RUNNER_USER" \
  -G "$PROVIDER_GROUP" -- \
  /usr/bin/python3 "$REPO_ROOT/tools/p0_rootless_docker_provider_client.py" \
  --request "$PING_REQUEST" \
  --socket /run/lion-docker-p0/provider.sock

if [[ "${RESTART_RUNNER:-0}" == "1" ]]; then
  systemctl restart "$RUNNER_UNIT"
  [[ "$(systemctl is-active "$RUNNER_UNIT")" == "active" ]]
else
  cat <<EOF

PROVIDER_INSTALLED=YES
PROVIDER_SERVICE=$PROVIDER_UNIT
PROVIDER_SOCKET=/run/lion-docker-p0/provider.sock
ROOTLESS_DOCKER_SOCKET=$ROOTLESS_SOCKET
RUNTIME_USER=$RUNTIME_USER
RUNNER_USER=$RUNNER_USER
PROVIDER_GROUP=$PROVIDER_GROUP

The already-running GitHub runner process has not been restarted.
Its systemd drop-in is installed. Activate it when no job is running:

  sudo systemctl restart $RUNNER_UNIT

Or rerun this installer with:
  RESTART_RUNNER=1 sudo -E bash install.sh ...
EOF
fi
