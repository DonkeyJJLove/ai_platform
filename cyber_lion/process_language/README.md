# LION Process Contract Language (LPCL) — candidate

LPCL is a strict, non-effectful surface over `CanonicalProcessIR`.

```text
LPCL text
→ parse
→ CanonicalProcessIR
→ semantic validation
→ TransitionSelector
→ internal transition OR ActionIntentCandidate
```

The package contains no raw-shell operator, PDP decision, RuntimeAdmission constructor or EffectProvider selector.

## Files

- `lpcl.py` — strict parser/renderer.
- `lpcl.ebnf` — surface grammar.
- `legacy_run.py` — read-only historical RUN adapter.
- `reference_processes.py` — shared positive corpus.
- `negative_corpus.json` — architecture falsification corpus.

## Run tests

```bash
python -m unittest cyber_lion.tests.test_process_ir cyber_lion.tests.test_process_semantics cyber_lion.tests.test_lpcl cyber_lion.tests.test_process_reference_corpus -v
```

The repository-wide canonical suite remains:

```bash
python -m compileall cyber_lion
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```
