# Cooperative production R6.15 — independent bounded evidence exporter

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.15 adds the independent producer-side exporter for the R6.14 cooperative provider evidence database. The exporter does not use provider-DB records to decide what should be exported. It observes all required canonical sources first and begins provider-DB writes only after the complete snapshot is internally consistent.

For one exact cooperative write assignment the exporter requires an already-existing CooperativeRuntimeContext and independently re-observes the RuntimeAdmission source, fleet dispatch, runtime identity, provisioning binding, live authority, policy binding, observability state, context pin and context transfer binding. Admission and currentness source identities must match independent trust bindings.

Live authority is revalidated through the existing LiveAuthorityAdmission immediately before export. The context, admission, dispatch, identity and provisioning contracts must equal the independent source observations. The context pin must bind the same assignment, and the transfer binding must bind the same mission, assignment and generation.

Evidence lifetime is bounded to at most 30 seconds. A domain-separated provenance digest binds the assignment, mission, worker, observation/expiry timestamps, source trust bindings and all exported object digests. The export receipt is explicitly authority_effect=NONE and execution_performed=false.

If any independent observation is stale, substituted, ambiguous or malformed, export fails before the first provider-DB write. Provider-DB writes therefore cannot participate in their own admission decision.

R6.15 still does not create context pins, transfer bindings, RuntimeAdmission, provisioning, dispatch or authority. Those objects must already exist in their canonical owners. The source remains PRE_H5_NOT_DEPLOYED and the worker bootstrap remains UNBOUND. The next boundary is the control-plane materializer/export sequence that creates a context carrier/pin from existing admitted runtime context, exports the coherent bounded worker projection, and only then releases HELD to READY.
