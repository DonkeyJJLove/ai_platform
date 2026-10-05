# Cooperative production R6.13 — private per-worker storage topology

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.13 prepares the existing R24 32-worker Docker topology for the R6.12 bounded bootstrap without installing any trusted dependency provider or activating cooperative effects.

Each material worker now receives one exclusive bind mount: ./private/MDxxx:/cooperative:rw.

The common worker environment declares LION_COOPERATIVE_BOOTSTRAP_MODE=UNBOUND, bootstrap version 1.0.0, repository root /src and private root /cooperative.

The source therefore remains fail-closed: even after rematerialization the worker cannot publish the cooperative runtime provider marker because bootstrap mode is explicitly UNBOUND.

materialize.py creates exactly 32 persistent private roots and the artifacts, contexts, verifiers, and state subdirectories required by R6.10–R6.12. Unlike volatile status and gate, the private tree is preserved across source rematerialization. Existing replay, admission-consumption, budget, materialization and artifact bytes are never deleted by the materializer.

Ownership is temporarily reclaimed only while the fleet is stopped, then restored to material worker uid 65532 and the observer group. Directories are validated at mode 2750; existing files are normalized to 0640. Each container sees only its own worker root and cannot address another worker's private bind through the compose topology.

The materialization receipt now records the private root, exact worker-root count, state-preservation flag and UNBOUND bootstrap mode. The current source-package manifest also covers compose.yaml, materialize.py and fleet-currentness.py so deployment topology is part of the exact source package.

No running container was modified by this source increment. No private volume was mounted into the live fleet, no Mission Control database was exposed to a worker, no external dependency module was installed and no cooperative assignment was executed.
