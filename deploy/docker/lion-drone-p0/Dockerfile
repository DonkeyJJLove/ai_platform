# LION Local Swarm P0 deterministic drone runtime
# Docker Hardened Images Python 3.11 / Debian 13, linux/amd64.
# Resolved 2026-09-07: index sha256:ee6f2172d994d5197755698750a815f842fe7f7df67cadfa0d32f47076a3523e
FROM dhi.io/python@sha256:ee6f2172d994d5197755698750a815f842fe7f7df67cadfa0d32f47076a3523e

WORKDIR /app
COPY tools/p0_docker_fleet_contract.py /app/tools/p0_docker_fleet_contract.py
COPY tools/p0_docker_drone_runtime.py /app/tools/p0_docker_drone_runtime.py

USER 65532:65532
ENTRYPOINT ["python3", "-m", "tools.p0_docker_drone_runtime"]
