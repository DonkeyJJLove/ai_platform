# Cooperative production R6.16 — control-plane export and release sequence

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.16 binds the R6.15 independent bounded evidence exporter to the existing R6.7 HELD→READY release fence without creating a second scheduler, PDP or authority source.

The new CooperativeControlPlaneMaterializer is a non-authorizing write-materializer callback for cooperative_production._materialize_and_release. It never calls release_held_assignment itself. The existing scheduler remains the only owner of HELD→READY and executes that transition only after this callback returns a complete exact evidence digest.

The callback re-reads the canonical HELD assignment, Mission Control driver, operator-control coordinates and LPCL binding from the exact Mission Control SQLite source. Presented assignment bytes are compared to that canonical snapshot before any provider-state write.

It then serializes an already-existing CooperativeRuntimeContext with exact assignment/driver/control coordinates into a pending context carrier. The final context filename is deterministic from a domain-separated assignment digest. The final CooperativeContextPin is independent of the assignment payload and binds the exact context bytes.

Before publishing the final carrier, R6.16 creates a pin-specialized R6.15 exporter. The exporter independently re-observes RuntimeAdmission, dispatch, runtime identity, provisioning, live authority, policy currentness, observability and the exact CONTEXT transfer binding. Provider evidence is bounded by the existing maximum 30-second TTL and has authority_effect=NONE.

All provider evidence is exported while the assignment is still HELD. Only after the bounded export succeeds is the pending carrier atomically renamed to its final name. The materializer then re-opens the provider DB through the R6.14 read-only sources and verifies admission, pin, dispatch, provisioning, runtime identity, live authority/currentness and transfer binding, plus a direct carrier digest readback.

If any source is stale, substituted, ambiguous, replaced or malformed, the callback fails and the existing release fence never executes. Export failure removes the pending carrier. A pre-existing final carrier, Mission Control DB replacement or provider-context-root replacement also fails closed.

The returned materialization object contains exactly the four fields required by the R6.7 scheduler bridge: materialization_kind, provider_id, evidence_digest and authority_effect=NONE. execution_performed remains false in the bound evidence basis.

R6.16 is source-only. It does not deploy provider state, switch worker bootstrap from UNBOUND, rematerialize a container, install a runtime root or execute a live cooperative artifact write. The next boundary is worker-private import/materialization of the released provider projection and bounded qualification of one existing material worker before any fleet activation.
