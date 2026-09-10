#!/bin/sh
set -eu
R=${1:-/opt/lion/k3s-vkt-r3/repo}
install -d -o sentinelx -g sentinelx -m 0700 /var/lib/sentinelx/uploads/lion-mission-control
install -m 0644 "$R/deploy/mission-control/lion-mission-control.service" /etc/systemd/system/lion-mission-control.service
systemctl daemon-reload
systemctl disable --now lion-vkt-mission-control.service 2>/dev/null || true
systemctl enable --now lion-mission-control.service
install -d -o sentinelx -g sentinelx -m 0755 /run/lion-vkt-mission-control
ln -sf /run/lion-mission-control/listen.json /run/lion-vkt-mission-control/listen.json
