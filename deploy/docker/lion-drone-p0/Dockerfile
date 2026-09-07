# LION Local Swarm P0 deterministic drone runtime
# Docker Hardened Images Python 3.11 / Debian 13, linux/amd64.
# Resolved 2026-09-07: index sha256:ee6f2172d994d5197755698750a815f842fe7f7df67cadfa0d32f47076a3523e
FROM dhi.io/python@sha256:ee6f2172d994d5197755698750a815f842fe7f7df67cadfa0d32f47076a3523e

WORKDIR /app
COPY cyber_lion/__init__.py /app/cyber_lion/__init__.py
COPY cyber_lion/contracts/__init__.py /app/cyber_lion/contracts/__init__.py
COPY cyber_lion/contracts/docker_fleet_polygon.py /app/cyber_lion/contracts/docker_fleet_polygon.py
COPY cyber_lion/drone_p0.py /app/cyber_lion/drone_p0.py

USER 65532:65532
ENTRYPOINT ["python3", "-m", "cyber_lion.drone_p0"]
