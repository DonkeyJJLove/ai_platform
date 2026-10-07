# Artifact-first build method R1

```text
DOCUMENT_ID=LION-ARTIFACT-FIRST-BUILD-METHOD-R1
STATUS=SOURCE_CANDIDATE
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
```

## Problem

A long interactive response stream is not a durable execution record. A UI failure such as
`Resume stream unavailable` or `Stream cache expired` may hide progress even when a worker,
GitHub workflow, local build, or candidate artifact continues independently.

Therefore:

```text
STREAM_AVAILABLE != WORK_RUNNING
STREAM_LOST      != WORK_FAILED
STREAM_EXPIRED   != CANDIDATE_MISSING
HTTP_HEALTH_OK   != FUNCTIONALLY_READY
```

The build process must not hold one interactive stream open while waiting for a long operation.

## Canonical method

Use an artifact-first, bounded observe/reconcile loop:

```text
FREEZE EXACT INPUTS
→ START ONE BOUNDED GENERATION
→ RETURN CONTROL IMMEDIATELY
→ WRITE/OBSERVE DURABLE STATE
→ PERIODICALLY POLL DURABLE STATE
→ CANDIDATE BYTES APPEAR?
    NO  → continue bounded polling
    YES → read bytes + digest + verify
→ VERIFIED?
    YES → terminal PASS
    NO  → preserve rejected generation + falsifier
          → bounded next generation
→ UNKNOWN?
    reconcile process/artifact/receipt first
    never blind retry
```

One generation still produces one primary artifact or one coherent contract change, consistent
with the Generation Evolution Protocol.

## What is durable

Prefer already-owned durable state, in this order:

1. Mission Control assignment/model-call/receipt/artifact records.
2. Exact repository candidate commit/tree and CI result.
3. Assignment-scoped local workspace artifact plus digest/readback.
4. A small status/checkpoint artifact owned by the bounded local job when no canonical mission store is available.

The interactive assistant/tool stream is never canonical state.

## Poll policy

Polling is observation, not execution. Recommended default profile for long authoring/build work:

```text
initial_interval=2s
backoff=2x
max_interval=30s
max_polls=120
max_elapsed=1800s
max_generations=4
```

The exact profile is task-specific and must remain bounded.

When the poll or UI stream itself fails, a later turn/session resumes by exact
`run_id`, mission/task/generation and reads durable state again.

## Generation rule

A new generation is legal only when the prior generation has a terminal verified disposition:

```text
VERIFIED           → COMPLETE
REJECTED           → NEXT_GENERATION if budget remains
UNKNOWN            → RECONCILE
RUNNING            → OBSERVE_LATER
CANDIDATE_AVAILABLE→ VERIFY_ARTIFACT
SUPERSEDED         → lineage only
```

Do not create a successor merely because an observation stream disappeared.

Every rejected generation remains in lineage with:
- exact input/source digest,
- candidate digest,
- verifier/falsifier receipt,
- terminal reason,
- successor generation identity.

## Local artifact verification

For generated files prefer local readback before waiting for remote presentation:

```text
producer writes bytes
→ close/finalize
→ consumer reads bytes independently
→ SHA-256 / size
→ parser/schema/compiler
→ targeted tests
→ verifier receipt
→ only then publish/push
```

A remote UI rendering, streamed log, or upload preview is secondary evidence.

## GitHub CI

GitHub workflow streams are also non-canonical.

After push/PR:
- capture exact candidate head,
- discover exact workflow run IDs,
- poll run/job status by ID,
- read terminal conclusion,
- fetch failed job logs only after terminal or when diagnosis is needed,
- never wait on one streaming log connection as the only progress mechanism.

A new commit invalidates prior exact-head CI.

## Chat/SaaS work

For SaaS model work:
- request/turn identity is durable before send,
- stream output is convenience only,
- result becomes usable only after durable response/receipt reconciliation,
- stream loss is UNKNOWN until readback,
- do not resend blindly.

## Relation to LION owners

This method adds no scheduler, event bus, conversation store, artifact registry, authority source,
or runtime effect provider.

It composes:
- Mission Control durable state,
- model-call state,
- existing artifact transfer/readback,
- repository candidate/CI identity,
- conversation/SaaS delivery reconciliation,
- Generation Evolution Protocol.

The pure contract in
`cyber_lion/contracts/artifact_candidate_iteration.py`
encodes the bounded observation decision. It does not start processes, execute external effects,
write repositories, or grant authority.

## Completion criterion

A long build is complete because a durable exact artifact was independently read back and
verified, not because an interactive stream stayed alive until the end.
