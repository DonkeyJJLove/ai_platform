#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_HOST="LION-AUTH-LAB"
RUNNER_USER="lion-maintenance-runner"
PROVIDER_GROUP="lion-k3s-vkt-r3"
K3S_VERSION="v1.36.4+k3s1"
K3S_SHA256="835873f37245fc615f547a2fe2af9402a347875f13fa64a1f136de644955ea3f"
K3S_URL="https://github.com/k3s-io/k3s/releases/download/v1.36.4%2Bk3s1/k3s"
NETWORK_EPOCH="vkt-r3-node-cidr-mask-22-v1"
NETWORK_EPOCH_FILE="/var/lib/lion/k3s-vkt-r3/network-epoch"

[[ $# -eq 3 ]] || { echo "usage: sudo bash install.sh <repo-root> <expected-head> <expected-tree>" >&2; exit 2; }
REPO_ROOT="$(realpath "$1")"
EXPECTED_HEAD="$2"
EXPECTED_TREE="$3"

[[ "$(id -u)" = 0 ]] || { echo "ERROR: root required" >&2; exit 1; }
[[ "$(hostname)" = "$TARGET_HOST" ]] || { echo "ERROR: wrong host" >&2; exit 1; }
[[ "$EXPECTED_HEAD" =~ ^[0-9a-f]{40}$ && "$EXPECTED_TREE" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$EXPECTED_HEAD" ]] || { echo "ERROR: HEAD mismatch" >&2; exit 1; }
[[ "$(git -C "$REPO_ROOT" rev-parse 'HEAD^{tree}')" = "$EXPECTED_TREE" ]] || { echo "ERROR: TREE mismatch" >&2; exit 1; }
id "$RUNNER_USER" >/dev/null

required=(
  tools/lion_k3s_pod_provider.py
  tools/lion_k3s_pod_provider_client.py
  tools/lion_k3s_pod_materializer.py
  tools/lion_runner_exec_provider.py
  tools/lion_runner_exec_client.py
  deploy/k8s/vkt-r3/lion-k3s-vkt-r3.service
  deploy/k8s/vkt-r3/lion-k3s-pod-provider.socket
  deploy/k8s/vkt-r3/lion-k3s-pod-provider@.service
  deploy/k8s/vkt-r3/provider-policy.json
)
for rel in "${required[@]}"; do
  [[ -f "$REPO_ROOT/$rel" ]] || { echo "ERROR: missing $rel" >&2; exit 1; }
done

getent group "$PROVIDER_GROUP" >/dev/null || groupadd --system "$PROVIDER_GROUP"
usermod -aG "$PROVIDER_GROUP" "$RUNNER_USER"

install -d -o root -g root -m 0755 /opt/lion/k3s /opt/lion/k3s-vkt-r3 /etc/lion
install -d -o root -g root -m 0700 /var/lib/lion/k3s-vkt-r3 /var/lib/lion-effect-admission/vkt-r3-k3s

if [[ ! -f /opt/lion/k3s/k3s ]]; then
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  curl --fail --location --silent --show-error "$K3S_URL" -o "$tmp"
  echo "$K3S_SHA256  $tmp" | sha256sum -c -
  install -o root -g root -m 0555 "$tmp" /opt/lion/k3s/k3s
  rm -f "$tmp"
  trap - EXIT
fi
[[ "$(sha256sum /opt/lion/k3s/k3s | awk '{print $1}')" = "$K3S_SHA256" ]] || { echo "ERROR: installed k3s checksum mismatch" >&2; exit 1; }
[[ "$(/opt/lion/k3s/k3s --version | head -n1)" == *"$K3S_VERSION"* ]] || { echo "ERROR: k3s version mismatch" >&2; exit 1; }

rm -rf /opt/lion/k3s-vkt-r3/repo
cp -a "$REPO_ROOT" /opt/lion/k3s-vkt-r3/repo
rm -rf /opt/lion/k3s-vkt-r3/repo/.git
chown -R root:root /opt/lion/k3s-vkt-r3/repo
find /opt/lion/k3s-vkt-r3/repo -type d -exec chmod 0555 {} +
find /opt/lion/k3s-vkt-r3/repo -type f -exec chmod 0444 {} +

install -o root -g root -m 0555 "$REPO_ROOT/tools/lion_k3s_pod_provider.py" /opt/lion/k3s-vkt-r3/provider.py
install -o root -g root -m 0555 "$REPO_ROOT/tools/lion_k3s_pod_provider_client.py" /usr/local/libexec/lion-k3s-pod-provider-client.py
install -o root -g root -m 0555 "$REPO_ROOT/tools/lion_runner_exec_provider.py" /usr/local/libexec/lion-runner-exec-provider.py
install -o root -g root -m 0555 "$REPO_ROOT/tools/lion_runner_exec_client.py" /usr/local/libexec/lion-runner-exec-client.py
install -o root -g root -m 0444 "$REPO_ROOT/deploy/k8s/vkt-r3/provider-policy.json" /opt/lion/k3s-vkt-r3/provider-policy.json

printf '{"repository":"DonkeyJJLove/ai_platform","branch":"mission/vkt-r3-pod-materialization-r2","source_head":"%s","source_tree":"%s","trust_class":"TEST_ONLY","k3s_version":"%s","k3s_sha256":"%s"}\n' "$EXPECTED_HEAD" "$EXPECTED_TREE" "$K3S_VERSION" "$K3S_SHA256" >/opt/lion/k3s-vkt-r3/source-identity.json
chmod 0444 /opt/lion/k3s-vkt-r3/source-identity.json

install -o root -g root -m 0644 "$REPO_ROOT/deploy/k8s/vkt-r3/lion-k3s-vkt-r3.service" /etc/systemd/system/lion-k3s-vkt-r3.service
install -o root -g root -m 0644 "$REPO_ROOT/deploy/k8s/vkt-r3/lion-k3s-pod-provider.socket" /etc/systemd/system/lion-k3s-pod-provider.socket
install -o root -g root -m 0644 "$REPO_ROOT/deploy/k8s/vkt-r3/lion-k3s-pod-provider@.service" /etc/systemd/system/lion-k3s-pod-provider@.service

RUNNER_DROPIN=/etc/systemd/system/lion-runner-exec@.service.d
install -d -o root -g root -m 0755 "$RUNNER_DROPIN"
printf '[Service]\nSupplementaryGroups=%s\n' "$PROVIDER_GROUP" >"$RUNNER_DROPIN/20-lion-k3s-vkt-r3.conf"
chmod 0644 "$RUNNER_DROPIN/20-lion-k3s-vkt-r3.conf"

systemctl daemon-reload
# Node PodCIDR is persisted in the K3s datastore. A network epoch change therefore
# performs one deterministic TEST_ONLY reinitialization, confined to the VKT K3s data root.
K3S_WAS_ACTIVE=NO
if systemctl is-active --quiet lion-k3s-vkt-r3.service; then
  K3S_WAS_ACTIVE=YES
fi
CURRENT_NETWORK_EPOCH=""
if [[ -f "$NETWORK_EPOCH_FILE" ]]; then
  CURRENT_NETWORK_EPOCH="$(cat "$NETWORK_EPOCH_FILE")"
fi
NETWORK_REINITIALIZED=NO
if [[ "$CURRENT_NETWORK_EPOCH" != "$NETWORK_EPOCH" ]]; then
  if [[ "$K3S_WAS_ACTIVE" = YES ]]; then
    systemctl stop lion-k3s-vkt-r3.service
  fi
  rm -rf /var/lib/lion-effect-admission/vkt-r3-k3s/data
  rm -f /var/lib/lion-effect-admission/vkt-r3-k3s/kubeconfig.yaml
  install -d -o root -g root -m 0700 /var/lib/lion-effect-admission/vkt-r3-k3s
  printf '%s\n' "$NETWORK_EPOCH" >"$NETWORK_EPOCH_FILE"
  chmod 0600 "$NETWORK_EPOCH_FILE"
  NETWORK_REINITIALIZED=YES
fi
if [[ "$K3S_WAS_ACTIVE" = YES ]]; then
  systemctl start lion-k3s-vkt-r3.service
fi
install -d -o root -g root -m 0755 /run/lion-k3s-vkt-r3
systemctl enable lion-k3s-pod-provider.socket
systemctl restart lion-k3s-pod-provider.socket
[[ "$(systemctl is-active lion-k3s-pod-provider.socket)" = active ]]

echo "K3S_PROVIDER_INSTALLED=YES"
echo "K3S_RUNTIME_STARTED=NO"
echo "K3S_WAS_ACTIVE=$K3S_WAS_ACTIVE"
echo "NETWORK_EPOCH=$NETWORK_EPOCH"
echo "NETWORK_REINITIALIZED=$NETWORK_REINITIALIZED"
echo "PROVIDER_SOCKET=/run/lion-k3s-vkt-r3/provider.sock"
echo "SOURCE_HEAD=$EXPECTED_HEAD"
echo "SOURCE_TREE=$EXPECTED_TREE"
