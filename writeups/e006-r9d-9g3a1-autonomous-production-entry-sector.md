# E006 R9D-9G3A1 — autonomous environment lifecycle and production-entry sector

## Why this sector exists

The completed three-node WSL laboratory proved something important and, at the same time, proved the limit of what it could prove. `MOON`, `LAB-DEBIAN`, and `LAB-UBUNTU` are distinct SentinelX routing identities with distinct logical roles. The bounded signer, independent verification, replay rejection, substitution rejection, and three-node evidence consensus all succeeded. That is valuable protocol evidence.

It is not evidence that three physical trust domains exist. All three logical nodes share the `WINDOWS-MOON` physical ancestor. The laboratory therefore gives strong bounded evidence about protocol semantics while remaining deliberately ineligible for production externality.

The architectural mistake this sector prevents is ontology collapse: treating a convenient implementation identifier such as `host_id`, hostname, process, VM, WSL distribution, quorum, or consensus result as if it were evidence of a stronger property such as physical separation, independent failure domain, hardware key custody, production readiness, or authority.

## Production is not a flag on the laboratory

LION now models two parallel tracks. The `LAB_RESEARCH_TRACK` may continue to accumulate rational evidence even when production infrastructure is incomplete. The `PRODUCTION_ENTRY_TRACK` separately collects the evidence needed to cross from experimentation into non-experimental operation.

This allows the laboratory to change shape freely: one process, several WSL distributions, role reassignment, adversarial observers, simulated failures, bounded software signers, or future multi-physical-node experiments. Every experiment must state what it supports, what it does not support, the world in which it executed, its evidence digests, currentness rule, limitations, production relevance, and its explicit `authority_effect`. Assurance claims in this sector always carry `authority_effect=NONE`.

The production-entry dossier is derived from those bounded claims and from independently described world topology. It is not a manually declared final truth. A caller cannot turn a failed physical topology into a PASS by supplying more host IDs, changing hostnames, or relabelling `TEST_ONLY` evidence.

## Five planes

The model separates an experiment plane, assurance plane, production-entry plane, authority plane, and deployment plane.

The experiment plane may generate observations and falsification results but cannot mint authority. The assurance plane interprets those observations dimension by dimension rather than collapsing them to a scalar score. The production-entry plane asks whether the candidate has enough current production-grade evidence to become eligible for independent readiness certification. The authority plane remains separate: readiness does not grant permission. The deployment plane may act only after exact currentness, bounded authority, effect mediation, rollback, and reconciliation are independently satisfied.

## Assurance vector

The sector tracks protocol correctness, role separation, identity separation, logical and physical topology, observability, provenance, cryptographic verification, private-key custody, non-exportable key storage, failure-domain independence, resilience, reconciliation, rollback readiness, currentness, governance, authority, and deployment readiness.

Each dimension is explicit: `UNTESTED`, `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE`, `STALE`, `CONFLICT`, or `BLOCKED`. A PASS in one dimension cannot hide an UNKNOWN or FAIL in another.

This is why the current three-WSL laboratory can simultaneously report protocol assurance PASS and production entry BLOCKED. Those are not contradictory statements; they answer different questions.

## The current laboratory baseline

The reference laboratory world is:

- `MOON` — consumer/observer, WSL2, physical domain `WINDOWS-MOON`;
- `LAB-DEBIAN` — bounded TEST_ONLY producer, WSL2, physical domain `WINDOWS-MOON`;
- `LAB-UBUNTU` — independent verifier, WSL2, physical domain `WINDOWS-MOON`.

The world therefore contains three logical nodes and one physical domain. Its role separation, logical routing, bounded signing, cryptographic verification and consensus may all be valid while physical topology and independent failure-domain assurance remain false and a production non-exportable hardware keystore remains blocked.

The primary production blocker is `PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED`.

## Future production transition

A future positive fixture adds one separately controlled physical signer, for example a Raspberry Pi or another Linux host with TPM 2.0 or an equivalent hardware-backed non-exportable keystore. That future world can become `PRODUCTION_ENTRY_ELIGIBLE` when the required assurance dimensions are current and PASS.

Even then the sector emits no production authority, creates no key, pins no v2 trust anchor, performs no deployment, and executes no effect. The next state is independent production-readiness certification.

The later lifecycle remains explicit:

1. environment lifecycle and production-entry sector;
2. current laboratory evidence registration and dossier baseline;
3. resilience and autonomous-role research;
4. preproduction evidence compilation;
5. physical external control-domain admission;
6. non-exportable production-key provisioning;
7. external trust-anchor rotation;
8. production-entry independent certification;
9. production-readiness certification;
10. production-authority decision;
11. production deployment canary;
12. production-effect reconciliation;
13. production active or rollback.

## Permanent invariants

`LOGICAL_HOST_COUNT != PHYSICAL_DOMAIN_COUNT`.

`WSL_INSTANCE != PHYSICAL_CONTROL_DOMAIN`.

`MULTI_NODE_CONSENSUS != PHYSICAL_INDEPENDENCE`.

`LAB_VALIDATION_PASS != PRODUCTION_ADMISSION`.

`TEST_ONLY != PRODUCTION_EXTERNAL`.

`SOFTWARE_RSA_ISOLATION != NON_EXPORTABLE_HARDWARE_KEYSTORE`.

`READINESS != AUTHORITY`.

`OBSERVATION != PERMISSION`.

`UNKNOWN != SUCCESS`.

The purpose of the sector is not to make laboratory work less flexible. It is to let laboratory work become more autonomous while making the boundary to production harder to misunderstand.
