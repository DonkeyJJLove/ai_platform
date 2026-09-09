# LPCL independent review checklist

A reviewer should reject the v1.1 candidate if any answer below is "yes":

- Can LPCL grant or mint authority?
- Can `FleetMissionIR` grant authority, carry credentials, construct RuntimeAdmission or select an EffectProvider?
- Can LPCL evaluate/replace the canonical PDP?
- Can LPCL construct RuntimeAdmission?
- Can LPCL select or execute an EffectProvider?
- Can unversioned historical RUN material become a process candidate merely because it contains `PHASE_N` blocks?
- Can an explicitly versioned invalid v1.1 source fall back to legacy and continue as executable?
- Can a canonical v1.1 source omit `TERMINATION` or `LINEAGE`?
- Can a LOGICAL-only fleet mission contain an `ACTION_REQUIRED` transition?
- Can an `ACTION_REQUIRED` transition route to a non-LOCAL role?
- Can `ACTION_REQUIRED` use any operator other than `EMIT_ACTION_INTENT`?
- Can an `ACTIONS`/`VERIFY`/`RECORD` annotation override typed transition semantics?
- Can role-separation metadata be presented as proof of physical independence?
- Can `UNKNOWN` be coerced into `PASS`?
- Can `PASS` imply `CURRENT`, `AUTHORIZED`, `OBSERVED` or `RECONCILED`?
- Can `CONTINUE` skip dependencies, ignore currentness or widen scope?
- Can non-idempotent retry occur without reconciliation-first semantics?
- Can a consequential `PASS` omit admission/effect/observation/reconciliation/currentness evidence?
- Does LPCL require a 16th architecture layer merely to exist?
- Does the process-orchestration projection alter the existing 15-layer set rather than bind existing layers?
- Does the candidate replace EvolutionaryEpochEngine, MissionSpec or SwarmSpec without separately proven equivalence?
- Are truth/currentness carriers being updated before noncarrier verification is frozen?
- Is documentation or a green receipt being treated as merge/production authority?

The candidate is suitable for integration review only when all answers are "no", the exact candidate head is bound, focused and repository-wide tests are executed on that exact identity, source-set/currentness drift is reconciled, and carrier-last readback succeeds.
