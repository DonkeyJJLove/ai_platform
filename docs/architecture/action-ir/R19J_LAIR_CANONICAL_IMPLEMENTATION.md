# R19J Canonical LAIR Implementation

```text
ActionSpec = schema/type contract
CanonicalActionIR = validated deterministic instance
CanonicalActionIR != ExecutionPlan
CanonicalActionIR != ActionProposal
ActionProposal != authority grant
ActionProposal != effect
```

The implementation is deliberately pre-authority and non-effectful. It validates the exact live
`cyberlion://schemas/action-spec/v1` shape, emits one compact UTF-8 JSON representation and binds it
with a raw lowercase SHA-256 digest suitable for the existing `ActionProposal.payload_digest`
comparison path. It does not create an ActionProposal, select a provider, map authority vocabularies,
create a PDP request, issue a permit, execute a process, perform transport, or reconcile an effect.

The current lowering direction is therefore:

```text
ActionIntent / future LCMS producer
→ CanonicalActionIR
→ future static effect projection
→ ActionProposal
→ PDP / authority / runtime identity
→ PEP / executor
```

The old C1 LCMS candidate is historical evidence only. Its `sha256:<hex>` output format and stricter
source-language restrictions are not copied into the LAIR contract implementation where they would
silently diverge from the current live ActionSpec/runtime contracts.
