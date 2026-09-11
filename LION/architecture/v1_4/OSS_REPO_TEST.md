# Bounded OSS Repository Test

This capability runs one fixed public open-source test target inside the local LION K3s laboratory. It is not a generic Kubernetes execution API.

Target: `pallets/itsdangerous` at immutable commit `672971d66a2ef9f85151e53283113f33d642dabd`. The provider exposes only `START_OSS_REPO_TEST`, `READ_OSS_REPO_TEST_EVIDENCE`, and `STOP_OSS_REPO_TEST`. Caller-supplied repository URLs, commits, shell commands, images, manifests, namespaces, host mounts, and privileged execution are not accepted.

The workload runs in namespace `oss-test-itsdangerous`. Source is cloned from GitHub by a digest-pinned `alpine/git` init container. Tests run in the existing digest-pinned Python runtime using the upstream project's own pytest suite with its declared test dependencies (`pytest` and `freezegun`). The Pod has no service-account token, no hostPath, no privileged containers, drops all capabilities, disables privilege escalation, uses a read-only root filesystem, and runs as UID/GID 1000.

Ingress is denied. Egress is restricted to cluster DNS on port 53 and outbound TCP/443 required to clone from GitHub and resolve Python test dependencies. This is public-source laboratory traffic, not production-target testing.
