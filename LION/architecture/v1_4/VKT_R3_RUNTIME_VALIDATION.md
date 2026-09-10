# VKT-R3 Runtime Validation

## Proven substrate baseline

Before the semantic-runtime rollout, the local VKT-R3 Kubernetes substrate reached 384/384 Ready real Pods, 128 TIGER + 128 SPECTRA + 128 LION, 384 unique Kubernetes `metadata.uid` values, zero restarts and zero vendor requests. The stable substrate UID-set hash was `38d5e750a210b8d7041f2ef3afbb404c999d4e2e2914cc67d246a460800aa265`.

The principal substrate counterexamples discovered during materialization were: rootless K3s delegated-cgroup failure; provider socket parent-directory traversal denial; K3s client data-root confinement mismatch; ConfigMap newline corruption; kubelet `max-pods` limit; non-root execution failure caused by K3s `UMask=0077`; and leaked host-local CNI leases. The CNI leak was empirically confirmed by 1021 IP lease files in `/var/lib/cni/networks/cbr0`. After bounded namespace cleanup, test-only K3s stop, CNI lease cleanup and restart, the fleet converged naturally to 384/384 Ready with zero restarts.

## Semantic runtime

The semantic runtime is repo-native and uses real Pod UID identity from the Kubernetes Downward API. It implements 36 local cases (`VKT-R3-CASE-01` through `VKT-R3-CASE-36`) and the ordered phases `TIGER_RELATION_ANALYSIS -> SPECTRA_FALSIFIER -> LION_LOCAL_EXECUTION -> LION_RECEIPT -> SPECTRA_PROOF_UPDATE -> TIGER_ADJACENCY`.

Messages are structured records carrying message ID, correlation ID, parent message ID, sender fleet/drone/Pod UID, target fleet, case ID, phase, message type, payload digest, evidence class and `vendor_requests=0`. Router state tracks fresh heartbeats, per-fleet freshness, ACKs, duplicate IDs, orphan parents, case state and participants per phase.

A NetworkPolicy restricts drone egress to Router TCP/8080 and DNS. No direct vendor testing is authorized.

## 600-second validation contract

A valid final run is exactly one continuous validation period. The validator defers before starting unless there are 384 materialized Pods, 384 Ready, 384 unique UIDs, zero restarts, 384 fresh semantic drones, 128 fresh drones per fleet, 36 seen/proven cases, all six phases with 128 participants, ACK rate at least 0.95, zero orphan messages, zero duplicate IDs, completed semantic mission and zero vendor requests.

During the run, any UID-set drift, restart, readiness/cardinality loss, semantic invariant loss or vendor request is a FAIL. The final elapsed duration must remain within the configured 600-second tolerance. PASS is never inferred from elapsed time alone.

## Currentness rule

When `LION-AUTH-LAB` is unreachable, ACTIVE_RUNTIME is UNKNOWN. Static tests, repository state and historical receipts remain evidence of implementation/history only and must not be promoted to current runtime truth.
