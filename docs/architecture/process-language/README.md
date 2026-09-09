# Process language architecture

Start with:

1. `LPCL_V1_CANDIDATE.md` — semantic/architecture model.
2. `LPCL_NEGATIVE_RULES.md` — fail-closed falsification classes.
3. `LPCL_MIGRATION.md` — additive migration and historical RUN boundary.

Machine-readable candidate decisions live under `LION/architecture/v1_4/process_language_*_candidate.json`.

Implementation lives in:

- `cyber_lion/contracts/process_ir.py`
- `cyber_lion/contracts/process_action.py`
- `cyber_lion/enterprise/process_semantics.py`
- `cyber_lion/process_language/`

The process layer is non-effectful and does not supersede the Action/PDP/RuntimeAdmission chain.
