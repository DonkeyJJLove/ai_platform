# LION Process Contract Language (LPCL)

LPCL is the non-effectful LION process-orchestration language. Two explicitly versioned authoring surfaces coexist during the v1.1 candidate transition:

```text
LPCL 1.0 strict JSON statement surface
→ CanonicalProcessIR

LPCL 1.1 canonical RUN/PHASE authoring surface candidate
→ CanonicalRunAST
→ CanonicalProcessIR + FleetMissionIR
```

Neither surface executes directly. `CanonicalProcessIR` remains the deterministic process-state contract. `FleetMissionIR` adds only bounded execution topology and role routing; it cannot grant authority, construct RuntimeAdmission, select an EffectProvider or execute an effect.

## Unified interpretation

Consumers that accept arbitrary process-language source use one fail-closed entrypoint:

```text
interpret_process_source(source)
  ├── LPCL 1.0 strict → CanonicalProcessIR compatibility candidate
  ├── LPCL 1.1 RUN/PHASE → CanonicalProcessIR + FleetMissionIR
  └── unversioned historical RUN → data-only LegacyRun classification
```

The v1.1 conformance profile requires explicit `TERMINATION=COMPLETE_ON_DONE` and non-empty `LINEAGE`. Any declared authority/runtime/execution/effect-provider effect control must remain `NONE`.

## v1.1 architecture

```text
RUN/PHASE surface
→ interpret_process_source
→ parse_canonical_run
→ compile_canonical_run
→ CanonicalProcessIR
→ FleetMissionIR
→ internal transition OR ActionIntentCandidate
→ existing Action / PDP / RuntimeAdmission / effect chain
→ independent observation
→ reconciliation
```

Every canonical v1.1 executable process declares one fleet mission class: `LOGICAL_FLEET_MISSION`, `LOCAL_FLEET_MISSION` or `HYBRID_FLEET_MISSION`. `ACTION_REQUIRED` phases must route to a LOCAL role and may only use `EMIT_ACTION_INTENT`.

## Historical RUN

Unversioned historical RUN material remains data. `LegacyRunAdapter` stays read-only and never interprets a textual authority declaration as a grant. The v1.1 candidate creates a new explicit versioned RUN surface; it does not silently promote historical text.

## Files

- `lpcl.py` / `lpcl.ebnf` — strict LPCL 1.0 parser/renderer and grammar.
- `canonical_run.py` / `lpcl_run_1_1.ebnf` — canonical RUN/PHASE v1.1 candidate parser/compiler and grammar.
- `interpretation.py` — unified fail-closed source interpretation boundary.
- `fleet_mission.py` — non-authoritative FleetMissionIR contract.
- `canonical_run_examples.py` — positive v1.1 authoring corpus.
- `canonical_run_negative_corpus.json` — v1.1 conformance falsification corpus.
- `legacy_run.py` — read-only historical RUN adapter.
- `reference_processes.py` — shared positive ProcessIR corpus.
- `negative_corpus.json` — LPCL 1.0 architecture falsification corpus.

Normative candidate documentation is under `docs/architecture/process-language/`:

- `LPCL_LANGUAGE_CONSTITUTION.md`
- `LPCL_CROSS_THREAD_GENERATION_STANDARD.md`
- `LPCL_FLEET_MISSION_MODEL.md`
- `LPCL_MIGRATION.md`
- `LPCL_V1_1_DESIGN_FREEZE.md`

## Tests

Focused suite:

```bash
python -m unittest \
  cyber_lion.tests.test_process_ir \
  cyber_lion.tests.test_process_semantics \
  cyber_lion.tests.test_lpcl \
  cyber_lion.tests.test_lpcl_canonical_run \
  cyber_lion.tests.test_lpcl_canonical_run_negative_corpus \
  cyber_lion.tests.test_lpcl_cross_thread_conformance \
  cyber_lion.tests.test_lpcl_interpretation \
  cyber_lion.tests.test_process_reference_corpus -v
```

Repository-wide canonical suite remains:

```bash
python -m compileall cyber_lion
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```
