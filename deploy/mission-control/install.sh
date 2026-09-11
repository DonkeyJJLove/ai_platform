#!/usr/bin/env bash
set -Eeuo pipefail
TARGET_HOST="LION-AUTH-LAB"
[[ $# -eq 3 ]] || { echo "usage: sudo bash install.sh <repo-root> <expected-head> <expected-tree>" >&2; exit 2; }
R="$(realpath "$1")"; H="$2"; T="$3"
[[ "$(id -u)" = 0 ]] || { echo "ERROR: root required" >&2; exit 1; }
[[ "$(hostname)" = "$TARGET_HOST" ]] || { echo "ERROR: wrong host" >&2; exit 1; }
[[ "$H" =~ ^[0-9a-f]{40}$ && "$T" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$(git -C "$R" rev-parse HEAD)" = "$H" ]] || { echo "ERROR: HEAD mismatch" >&2; exit 1; }
[[ "$(git -C "$R" rev-parse 'HEAD^{tree}')" = "$T" ]] || { echo "ERROR: TREE mismatch" >&2; exit 1; }
for rel in tools/lion_mission_control.py tools/lion_mission_control_event_client.py tools/lion_mission_control_read_proxy.py cyber_lion/mission_control/server.py cyber_lion/mission_control/storage.py deploy/mission-control/lion-mission-control.service deploy/mission-control/lion-mission-control-read.socket deploy/mission-control/lion-mission-control-read@.service; do
  [[ -f "$R/$rel" ]] || { echo "ERROR: missing $rel" >&2; exit 1; }
done
install -d -o sentinelx -g sentinelx -m 0700 /var/lib/sentinelx/uploads/lion-mission-control
install -o root -g root -m 0644 "$R/deploy/mission-control/lion-mission-control.service" /etc/systemd/system/lion-mission-control.service
install -o root -g root -m 0644 "$R/deploy/mission-control/lion-mission-control-read.socket" /etc/systemd/system/lion-mission-control-read.socket
install -o root -g root -m 0644 "$R/deploy/mission-control/lion-mission-control-read@.service" /etc/systemd/system/lion-mission-control-read@.service
systemctl daemon-reload
systemctl enable --now lion-mission-control-read.socket
[[ "$(systemctl is-active lion-mission-control-read.socket)" = active ]]
LEGACY_WAS_ACTIVE=NO
if systemctl is-active --quiet lion-vkt-mission-control.service; then LEGACY_WAS_ACTIVE=YES; fi
systemctl stop lion-vkt-mission-control.service 2>/dev/null || true
systemctl disable lion-vkt-mission-control.service 2>/dev/null || true
systemctl enable lion-mission-control.service
if ! systemctl restart lion-mission-control.service || [[ "$(systemctl is-active lion-mission-control.service)" != active ]]; then
  systemctl disable lion-mission-control.service 2>/dev/null || true
  if [[ "$LEGACY_WAS_ACTIVE" = YES ]]; then systemctl enable --now lion-vkt-mission-control.service; fi
  echo "ERROR: generic Mission Control failed; legacy observer restored when previously active" >&2
  exit 1
fi
if systemctl is-active --quiet lion-vkt-mission-control.service; then
  echo "ERROR: legacy Mission Control still independently active" >&2
  exit 1
fi
echo "LION_MISSION_CONTROL_INSTALLED=YES"
echo "SOURCE_HEAD=$H"
echo "SOURCE_TREE=$T"
