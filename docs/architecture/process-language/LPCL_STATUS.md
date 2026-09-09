# LPCL candidate status

```text
LPCL_1_0_STRICT_PROCESS_IR=INTEGRATED_NON_EFFECTFUL
LPCL_1_1_RUN_PHASE_SURFACE=CANDIDATE_NOT_MERGED
FLEET_MISSION_IR=CANDIDATE_NOT_MERGED
CROSS_THREAD_GENERATION_STANDARD=CANDIDATE_NOT_MERGED
PROCESS_ORCHESTRATION_PROJECTION=CANDIDATE_NOT_MERGED
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
PRODUCTION_AUTHORITY=NONE
MERGE_AUTHORITY=NONE
```

The v1.1 work branch contains a non-effectful language/architecture candidate and associated tests. It does not make a default-branch, runtime, host, production, release or deployment claim.

The candidate is based on master `70929bb895726c0b4a552295e595e373191b0d2b` / tree `0c463f98122145a1a39287240136d1a824a8038c`. Exact candidate HEAD/TREE are live Git state and must be reacquired rather than copied from this documentation.

Current candidate implementation includes the versioned RUN/PHASE surface, unified process-source interpretation, FleetMissionIR, LOGICAL/LOCAL/HYBRID routing, source-derived process-orchestration architecture projection, positive/negative corpora and cross-thread authoring rules. Verification, truth-carrier rebind and merge remain downstream gates.
