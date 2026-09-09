# Process language architecture

The process-language documentation now separates the integrated LPCL 1.0 machine-oriented surface from the LPCL 1.1 canonical RUN/PHASE authoring candidate.

Start with:

1. `LPCL_LANGUAGE_CONSTITUTION.md` — normative v1.1 candidate language interpretation.
2. `LPCL_CROSS_THREAD_GENERATION_STANDARD.md` — one authoring profile for all LION threads.
3. `LPCL_FLEET_MISSION_MODEL.md` — LOGICAL/LOCAL/HYBRID execution-topology semantics.
4. `LPCL_V1_CANDIDATE.md` — ProcessIR and architecture boundary, including v1.0 compatibility.
5. `LPCL_NEGATIVE_RULES.md` — fail-closed falsification classes for both surfaces.
6. `LPCL_MIGRATION.md` — explicit v1.0/v1.1/legacy migration model.
7. `LPCL_V1_1_DESIGN_FREEZE.md` — candidate design-freeze receipt.

Machine-readable historical/current architecture decisions under `LION/architecture/v1_4/` remain subject to carrier-last reconciliation. They are not manually promoted merely because the candidate implementation exists.

Implementation lives in:

- `cyber_lion/contracts/process_ir.py` — canonical deterministic process semantics;
- `cyber_lion/contracts/process_action.py` — existing Process→Action boundary;
- `cyber_lion/enterprise/process_semantics.py` — transition semantics;
- `cyber_lion/process_language/lpcl.py` — strict LPCL 1.0 compatibility parser;
- `cyber_lion/process_language/canonical_run.py` — v1.1 RUN/PHASE parser/compiler;
- `cyber_lion/process_language/interpretation.py` — unified fail-closed source interpretation;
- `cyber_lion/process_language/fleet_mission.py` — non-authoritative FleetMissionIR;
- `cyber_lion/architecture_projection/process_orchestration.py` — cross-layer process-orchestration projection.

Canonical candidate path:

```text
process source
→ interpret_process_source
→ CanonicalProcessIR
→ FleetMissionIR when v1.1
→ bounded role routing
→ ActionIntent only for ACTION_REQUIRED
→ existing PDP / RuntimeAdmission / effect path
→ observation
→ reconciliation
```

The process and fleet-mission layers are non-effectful and do not supersede the Action/PDP/RuntimeAdmission chain.
