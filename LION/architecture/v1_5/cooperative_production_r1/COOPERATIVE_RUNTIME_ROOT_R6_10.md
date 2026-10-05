# Cooperative production R6.10 — trusted runtime composition root

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.10 connects the previously separate R5 resolver, R6.7 private materialization, R6.8 process-local materializer registry and R6.9 durable runtime state into one explicit trusted composition root. It still does not issue RuntimeAdmission, run PDP, schedule work, start a worker or grant authority.

The Mission Control-side materializer re-reads the canonical HELD assignment and exact input from the Mission Control SQLite source. It then requires an already-provisioned CooperativeRuntimeContext from a trusted source and independently re-observes the upstream RuntimeAdmission source, provisioning binding, runtime identity, fleet dispatch, live authority, policy binding and observability state before publishing any worker-visible carrier.

The upstream RuntimeAdmission is copied into the R6.9 durable admission source only after exact source/trust equality and currentness checks. The copy provenance binds the upstream source identity, admission digest, provisioning digest, runtime identity and fleet-dispatch digest. The context transfer contains the admission digest but never the RuntimeAdmission object.

Private context and verifier transfers are indexed by SQLiteCooperativeMaterializationStore. The store is non-authorizing, append-only per assignment and revalidates database identity, private parent identity, transfer bytes and context pins on every read. Verifier transfer is now bound to the actual verifier/consumer assignment rather than reusing the producer assignment as the transfer identity.

A reconstructed worker-side root can resolve the stored context, use the durable RuntimeAdmission source, durable admission consumption, sandbox replay and budget state, build the PinnedCooperativeContextResolver and CooperativeRuntimeWriterProvider, and re-observe provisioning before both context resolutions surrounding the filesystem effect.

The root exposes an exact CooperativeMaterializationProvider for the R6.8 Mission Control registry and the existing worker provider-status marker. Neither object is an authority grant. Missing materialization, source substitution, stale admission, changed authority/policy/observability, changed dispatch/runtime/provisioning, replaced state databases or substituted transfer bindings fail closed.

This increment is source composition only. The existing R24 worker process has not been changed to instantiate this root, no private volumes were mounted, no Mission Control package was deployed, no container was restarted and no successor LPCL was launched. The next boundary is worker-process injection and deployment qualification using the existing 2-logical / 32-material topology.
