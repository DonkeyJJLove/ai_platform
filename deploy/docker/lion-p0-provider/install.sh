#!/usr/bin/env bash
set -Eeuo pipefail
TARGET_HOST="LION-AUTH-LAB"; RUNTIME_USER="lion-container-runtime-lab"; RUNNER_USER="lion-maintenance-runner"; PROVIDER_GROUP="lion-docker-p0"
RUNNER_UNIT="actions.runner.DonkeyJJLove-ai_platform.lion-moon-r9d8-test.service"; PROVIDER_UNIT="lion-p0-rootless-docker-provider.service"
[[ $# -eq 3 ]] || { echo "usage: sudo bash install.sh <repo-root> <expected-head> <expected-tree>" >&2; exit 2; }
REPO_ROOT="$(realpath "$1")"; EXPECTED_HEAD="$2"; EXPECTED_TREE="$3"
[[ "$(id -u)" = 0 && "$(hostname)" = "$TARGET_HOST" && "$(uname -m)" = x86_64 ]] || exit 1; grep -qi microsoft /proc/sys/kernel/osrelease || exit 1
[[ "$EXPECTED_HEAD" =~ ^[0-9a-f]{40}$ && "$EXPECTED_TREE" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$EXPECTED_HEAD" && "$(git -C "$REPO_ROOT" rev-parse 'HEAD^{tree}')" = "$EXPECTED_TREE" ]] || exit 1
for path in "$REPO_ROOT/tools/p0_rootless_docker_provider.py" "$REPO_ROOT/tools/p0_docker_fleet_contract.py" "$REPO_ROOT/tools/p0_docker_drone_runtime.py" "$REPO_ROOT/deploy/docker/lion-drone-p0/Dockerfile" "$REPO_ROOT/deploy/docker/lion-p0-provider/lion-p0-rootless-docker-provider.service" /usr/local/libexec/lion-runner-exec-client.py; do [[ -f "$path" ]] || { echo "ERROR: required source missing: $path" >&2; exit 1; }; done
id "$RUNTIME_USER" >/dev/null; id "$RUNNER_USER" >/dev/null
RUNTIME_UID="$(id -u "$RUNTIME_USER")"; RUNNER_UID="$(id -u "$RUNNER_USER")"; ROOTLESS_RUNTIME_DIR="/run/user/$RUNTIME_UID"; ROOTLESS_SOCKET="$ROOTLESS_RUNTIME_DIR/docker.sock"
[[ -d "$ROOTLESS_RUNTIME_DIR" && "$(stat -c %U "$ROOTLESS_RUNTIME_DIR")" = "$RUNTIME_USER" && -S "$ROOTLESS_SOCKET" ]] || { echo "ERROR: rootless runtime prerequisite failed" >&2; exit 1; }
[[ "$(systemctl show -p User --value "$RUNNER_UNIT")" = "$RUNNER_USER" ]] || { echo "ERROR: runner identity mismatch" >&2; exit 1; }
getent group "$PROVIDER_GROUP" >/dev/null || groupadd --system "$PROVIDER_GROUP"
usermod -aG "$PROVIDER_GROUP" "$RUNTIME_USER"; usermod -aG "$PROVIDER_GROUP" "$RUNNER_USER"
install -d -o root -g root -m 0755 /opt/lion/docker-p0-provider /opt/lion/docker-p0-provider/build-context /opt/lion/docker-p0-provider/build-context/tools /etc/lion
install -d -o "$RUNTIME_USER" -g "$RUNTIME_USER" -m 0700 /var/lib/lion/docker-p0-provider
install -o root -g root -m 0555 "$REPO_ROOT/tools/p0_rootless_docker_provider.py" /opt/lion/docker-p0-provider/provider.py
install -o root -g root -m 0444 "$REPO_ROOT/deploy/docker/lion-drone-p0/Dockerfile" /opt/lion/docker-p0-provider/build-context/Dockerfile
install -o root -g root -m 0444 "$REPO_ROOT/tools/p0_docker_fleet_contract.py" /opt/lion/docker-p0-provider/build-context/tools/p0_docker_fleet_contract.py
install -o root -g root -m 0444 "$REPO_ROOT/tools/p0_docker_drone_runtime.py" /opt/lion/docker-p0-provider/build-context/tools/p0_docker_drone_runtime.py
printf '{"repository":"DonkeyJJLove/ai_platform","source_head":"%s","source_tree":"%s","trust_class":"TEST_ONLY"}\n' "$EXPECTED_HEAD" "$EXPECTED_TREE" >/opt/lion/docker-p0-provider/build-context/source-identity.json
chmod 0444 /opt/lion/docker-p0-provider/build-context/source-identity.json
cat >/etc/lion/docker-p0-provider.env <<EOF
LION_P0_PROVIDER_SOCKET=/run/lion-docker-p0/provider.sock
LION_P0_STATE_DIR=/var/lib/lion/docker-p0-provider
LION_P0_BUILD_CONTEXT=/opt/lion/docker-p0-provider/build-context
LION_P0_DOCKER_HOST=unix://$ROOTLESS_SOCKET
LION_P0_ALLOWED_CALLER_UID=$RUNNER_UID
LION_P0_PROVIDER_GROUP=$PROVIDER_GROUP
EOF
chmod 0640 /etc/lion/docker-p0-provider.env; chown root:"$PROVIDER_GROUP" /etc/lion/docker-p0-provider.env
printf 'd /run/lion-docker-p0 0770 root %s - -\n' "$PROVIDER_GROUP" >/etc/tmpfiles.d/lion-docker-p0.conf
systemd-tmpfiles --create /etc/tmpfiles.d/lion-docker-p0.conf
install -o root -g root -m 0644 "$REPO_ROOT/deploy/docker/lion-p0-provider/lion-p0-rootless-docker-provider.service" "/etc/systemd/system/$PROVIDER_UNIT"
RUNNER_DROPIN_DIR="/etc/systemd/system/${RUNNER_UNIT}.d"; install -d -o root -g root -m 0755 "$RUNNER_DROPIN_DIR"; printf '[Service]\nSupplementaryGroups=%s\n' "$PROVIDER_GROUP" >"$RUNNER_DROPIN_DIR/10-lion-docker-p0.conf"; chmod 0644 "$RUNNER_DROPIN_DIR/10-lion-docker-p0.conf"
systemctl daemon-reload; systemctl enable "$PROVIDER_UNIT"; systemctl restart "$PROVIDER_UNIT"; [[ "$(systemctl is-active "$PROVIDER_UNIT")" = active ]]
/usr/bin/python3 /usr/local/libexec/lion-runner-exec-client.py provider-call --provider-operation PING --source-head "$EXPECTED_HEAD" --source-tree "$EXPECTED_TREE" >/tmp/lion-provider-ping.json
python3 - /tmp/lion-provider-ping.json <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); assert x['ok'] is True and x['result'].get('docker_server_version')
PY
rm -f /tmp/lion-provider-ping.json
if [[ "${RESTART_RUNNER:-0}" == "1" ]]; then
  systemctl restart "$RUNNER_UNIT"
  [[ "$(systemctl is-active "$RUNNER_UNIT")" == "active" ]]
fi
echo PROVIDER_INSTALLED=YES; echo PROVIDER_SERVICE="$PROVIDER_UNIT"; echo PROVIDER_SOCKET=/run/lion-docker-p0/provider.sock; echo ROOTLESS_DOCKER_SOCKET="$ROOTLESS_SOCKET"
