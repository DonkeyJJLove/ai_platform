# LPCL independent review checklist

A reviewer should reject the candidate if any answer below is "yes":

- Can LPCL grant or mint authority?
- Can LPCL evaluate/replace the canonical PDP?
- Can LPCL construct RuntimeAdmission?
- Can LPCL select or execute an EffectProvider?
- Can a historical RUN reach execution without canonicalization?
- Can `UNKNOWN` be coerced into `PASS`?
- Can `PASS` imply `CURRENT`, `AUTHORIZED`, `OBSERVED` or `RECONCILED`?
- Can `CONTINUE` skip dependencies, ignore currentness or widen scope?
- Can non-idempotent retry occur without reconciliation-first semantics?
- Can a consequential `PASS` omit admission/effect/observation/reconciliation/currentness evidence?
- Does LPCL require a 16th architecture layer merely to exist?
- Does it replace EvolutionaryEpochEngine rather than coexist with it?

The candidate is suitable for integration review only when all answers are "no" and exact-head CI is successful.
