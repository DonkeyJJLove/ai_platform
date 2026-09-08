#!/usr/bin/env bash
set -Eeuo pipefail
TARGET_HOST=LION-AUTH-LAB; BRANCH=experiment/local-swarm-p0-docker-polygon; REPO_URL=https://github.com/DonkeyJJLove/ai_platform.git
RUNNER_USER=lion-maintenance-runner; RUNTIME_USER=lion-container-runtime-lab; PROVIDER_GROUP=lion-docker-p0
[[ $# -eq 2 ]] || { echo "usage: sudo bash install.sh <expected-head> <expected-tree>" >&2; exit 2; }
HEAD="$1"; TREE="$2"; [[ "$(id -u)" = 0 && "$(hostname)" = "$TARGET_HOST" && "$(uname -m)" = x86_64 ]] || exit 1; grep -qi microsoft /proc/sys/kernel/osrelease || exit 1
[[ "$HEAD" =~ ^[0-9a-f]{40}$ && "$TREE" =~ ^[0-9a-f]{40}$ ]] || exit 1
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT; git init -q "$TMP/repo"; git -C "$TMP/repo" remote add origin "$REPO_URL"; LIVE=$(git ls-remote --exit-code "$REPO_URL" "refs/heads/$BRANCH" | awk '{print $1}'); [[ "$LIVE" = "$HEAD" ]] || exit 1
git -C "$TMP/repo" fetch -q --no-tags --depth=1 origin "refs/heads/$BRANCH"; [[ "$(git -C "$TMP/repo" rev-parse FETCH_HEAD)" = "$HEAD" ]]; [[ "$(git -C "$TMP/repo" rev-parse 'FETCH_HEAD^{tree}')" = "$TREE" ]]; git -C "$TMP/repo" checkout -q --detach FETCH_HEAD; R="$TMP/repo"
python3 -m py_compile "$R/tools/lion_effect_admission_broker.py" "$R/tools/lion_runner_exec_provider.py" "$R/tools/lion_runner_exec_client.py" "$R/tools/lion_effect_admission_client.py" "$R/tools/lion_broker_update_provider.py" "$R/tools/lion_broker_update_client.py" "$R/tools/lion_scale64_controller.py"
id "$RUNNER_USER" >/dev/null; id "$RUNTIME_USER" >/dev/null; getent group "$PROVIDER_GROUP" >/dev/null || groupadd --system "$PROVIDER_GROUP"
install -o root -g root -m 0555 "$R/tools/lion_runner_exec_provider.py" /usr/local/libexec/lion-runner-exec-provider.py
install -o root -g root -m 0555 "$R/tools/lion_runner_exec_client.py" /usr/local/libexec/lion-runner-exec-client.py
install -o root -g root -m 0644 "$R/deploy/docker/lion-runner-exec/lion-runner-exec.socket" /etc/systemd/system/lion-runner-exec.socket
install -o root -g root -m 0644 "$R/deploy/docker/lion-runner-exec/lion-runner-exec@.service" /etc/systemd/system/lion-runner-exec@.service
install -d -o "$RUNNER_USER" -g "$RUNNER_USER" -m 0700 /var/lib/lion-runner-exec
install -d -o root -g root -m 0755 /opt/lion/effect-admission /opt/lion/effect-admission/workspaces
systemctl daemon-reload; systemctl enable --now lion-runner-exec.socket
/usr/bin/python3 /usr/local/libexec/lion-runner-exec-client.py identity >/tmp/lion-runner-identity.json
python3 - /tmp/lion-runner-identity.json <<'PY'
import grp,json,sys
x=json.load(open(sys.argv[1])); r=x['result']; assert x['ok'] is True; assert r['username']=='lion-maintenance-runner' and r['uid']!=0 and r['no_new_privs']==1; assert grp.getgrnam('lion-docker-p0').gr_gid in r['supplementary_groups']
PY
rm -f /tmp/lion-runner-identity.json
RESTART_RUNNER=0 bash "$R/deploy/docker/lion-p0-provider/install.sh" "$R" "$HEAD" "$TREE"
install -d -o root -g root -m 0755 /opt/lion/scale64-control/canonical; install -d -o sentinelx -g sentinelx -m 0700 /var/lib/lion-scale64-control; install -d -o sentinelx -g sentinelx -m 0750 /opt/lion/scale64-control-state
install -o root -g root -m 0444 "$R/tools/lion_effect_admission_broker.py" /opt/lion/scale64-control/canonical/lion-effect-admission-broker.py
install -o root -g root -m 0555 "$R/tools/lion_effect_admission_broker.py" /usr/local/libexec/lion-effect-admission-broker.py
install -o root -g root -m 0555 "$R/tools/lion_effect_admission_client.py" /usr/local/bin/lion-effect-admission
install -o root -g root -m 0555 "$R/tools/lion_broker_update_provider.py" /usr/local/libexec/lion-broker-update-provider.py
install -o root -g root -m 0555 "$R/tools/lion_broker_update_client.py" /usr/local/bin/lion-broker-update
install -o root -g root -m 0555 "$R/tools/lion_scale64_controller.py" /usr/local/libexec/lion-scale64-controller.py
for f in lion-effect-admission.socket 'lion-effect-admission@.service' lion-broker-update.socket 'lion-broker-update@.service' lion-scale64-control.service; do install -o root -g root -m 0644 "$R/deploy/docker/lion-scale64-control/$f" "/etc/systemd/system/$f"; done
python3 - /etc/sentinelx/config.yaml <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(); lines=s.splitlines(True)
for entry in ('/usr/local/bin/lion-effect-admission','/usr/local/bin/lion-broker-update'):
    if any(x.strip()==f'- {entry}' for x in lines): continue
    i=next(i for i,x in enumerate(lines) if x.strip()=='allowed_commands:'); lines.insert(i+1,f'  - {entry}\n')
s=''.join(lines)
if '  lion-scale64-control:\n' not in s:
    s=s.replace('services:\n','services:\n  lion-scale64-control:\n    unit: lion-scale64-control.service\n    backend: service\n    actions: [status, start, is-active, is-enabled]\n    requires_sudo: true\n    description: "Bounded LION Scale64 declarative controller"\n',1)
p.write_text(s)
PY
/opt/sentinelx-cloud-core/.venv/bin/python - <<'PY'
import yaml
from pathlib import Path
yaml.safe_load(Path('/etc/sentinelx/config.yaml').read_text())
PY
systemctl daemon-reload; systemctl enable --now lion-effect-admission.socket lion-broker-update.socket
echo LION_SCALE64_CONTROL_PLANE_INSTALLED=PASS; echo SOURCE_HEAD="$HEAD"; echo SOURCE_TREE="$TREE"; echo RUNNER_EXEC_IDENTITY_PASS=true; echo PROVIDER_ACTIVE=true; echo CONTROL_SERVICE_PRESENT=true; echo SENTINELX_RESTART_REQUIRED=YES
