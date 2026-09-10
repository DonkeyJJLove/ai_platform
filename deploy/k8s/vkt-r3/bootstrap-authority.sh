#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_HOST="LION-AUTH-LAB"
[[ $# -eq 3 ]] || { echo "usage: sudo bash bootstrap-authority.sh <repo-root> <expected-head> <expected-tree>" >&2; exit 2; }
R="$(realpath "$1")"
H="$2"
T="$3"
[[ "$(id -u)" = 0 ]] || { echo "ERROR: root required" >&2; exit 1; }
[[ "$(hostname)" = "$TARGET_HOST" ]] || { echo "ERROR: wrong host" >&2; exit 1; }
[[ "$H" =~ ^[0-9a-f]{40}$ && "$T" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$(git -C "$R" rev-parse HEAD)" = "$H" ]] || { echo "ERROR: HEAD mismatch" >&2; exit 1; }
[[ "$(git -C "$R" rev-parse 'HEAD^{tree}')" = "$T" ]] || { echo "ERROR: TREE mismatch" >&2; exit 1; }

bash "$R/deploy/k8s/vkt-r3/install.sh" "$R" "$H" "$T"
install -o root -g root -m 0555 "$R/tools/lion_vkt_effect_admission_broker.py" /usr/local/libexec/lion-vkt-effect-admission-broker.py
install -o root -g root -m 0555 "$R/tools/lion_vkt_effect_admission_client.py" /usr/local/libexec/lion-vkt-effect-admission-client.py
install -o root -g root -m 0644 "$R/deploy/k8s/vkt-r3/lion-vkt-effect-admission.socket" /etc/systemd/system/lion-vkt-effect-admission.socket
install -o root -g root -m 0644 "$R/deploy/k8s/vkt-r3/lion-vkt-effect-admission@.service" /etc/systemd/system/lion-vkt-effect-admission@.service
systemctl daemon-reload
systemctl enable --now lion-vkt-effect-admission.socket
[[ "$(systemctl is-active lion-vkt-effect-admission.socket)" = active ]]

# Mission Control is installed only after the exact VKT authority and fixed
# source tree are in place. The generic observer is read-only and owns the
# legacy listen locator as a compatibility pointer; the legacy HTTP service
# is not left independently running.
bash "$R/deploy/mission-control/install.sh" "$R" "$H" "$T"
[[ "$(systemctl is-active lion-mission-control.service)" = active ]]
if systemctl is-active --quiet lion-vkt-mission-control.service; then
  echo "ERROR: legacy Mission Control still independently active" >&2
  exit 1
fi

echo "VKT_AUTHORITY_BOOTSTRAPPED=YES"
echo "MISSION_CONTROL_GENERIC_SERVICE=ACTIVE"
echo "MISSION_CONTROL_LEGACY_PRIMARY=NO"
echo "K3S_RUNTIME_STARTED=NO"
echo "SOURCE_HEAD=$H"
echo "SOURCE_TREE=$T"
