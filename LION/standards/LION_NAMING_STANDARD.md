# LION naming standard

Status: CURRENT_STANDARD. Authority effect: NONE.

## Canonical forms

- Directories: `lower_snake_case`.
- Python modules: `lower_snake_case.py`.
- Python functions and methods: `lower_snake_case`.
- Python classes and semantic contracts: `PascalCase`.
- JSON/YAML keys: `lower_snake_case`.
- Environment variables: `LION_UPPER_SNAKE_CASE`.
- Workflow filenames: `lower-kebab-case.yml`.
- Current README filename: `README.md`.
- Machine artifact IDs: `lower-kebab-case`.
- Schema IDs: `lion.<domain>.<artifact>/vN`.
- Task IDs: `LION-UPPER-KEBAB-RN`.
- Working branches: `<class>/<semantic-scope>-rN`, where class is one of `mission`, `fix`, `docs`, `ci`, `test`, `research`, `maintenance`.

## Historical names

Immutable evidence is not renamed to satisfy current spelling. Every migration must classify a name as one of:

```text
CURRENT_CANONICAL_NAME
HISTORICAL_NAME
COMPATIBILITY_ALIAS
DEPRECATED_ALIAS
```

A current rename requires a migration map, consumer update, documentation update, tests, compatibility policy and rollback.

## Repository names

Existing repository names are stable identities unless a separately formalized repository migration proves that a rename is necessary. In particular, `mosaic_lab_pro.py`, `SymulacjaKaskadySieciowej` and `hipotezy_nadawcze_LLM` are not renamed by this standard alone.
