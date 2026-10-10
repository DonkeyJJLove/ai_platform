# LION Service Continuation Ledger — R1

Status: SOURCE CANDIDATE / NON-AUTHORIZING ARCHITECTURE RECORD until exact-head CI, formalization closure and admitted integration. This document is a v1.5 architecture surface, not a live Mission Control feed. Authority effect: NONE. Runtime effect: NONE.

## Purpose and owner

SERVICE_CONTINUATION_LEDGER_R1.json is the source-controlled service handoff register for unfinished LION work in the R11 trajectory. It preserves four operator questions across conversations and models: what remains, why, what observation or admission is missing and the first safe next action. Its semantic owner is cyber_lion/contracts/service_continuation_ledger.py, indexed as service_continuation in semantic_owners.json, with formalization records in FORMALIZATION_REGISTRY_FEDERATION_R1.json.

This ledger does not replace Mission Control mission/phase events, the GitHub Actions control ledger, the startup journal, authority provision/consumption stores, Git refs, CI observations, provider sessions or current probes. It is a versioned INTENT AND EVIDENCE-REFERENCE PLANE, not an event dispatcher, authority source, mutation engine or second scheduler. A COMPLETE label alone does not prove an effect.

The baseline preserves the operator-reported PR445 verifier rebind and separately observed service restart, five signed documents, the as-observed empty PR445 authority store, exact PR445/446 Git state, R11 policy expiry and dependent next steps. It contains no private PEMs, passwords, tokens or privileged environment values. Source checkpoints and original trusted stores remain the owners of their respective evidence.

## State and event protocol

    SOURCE-BOUND BASELINE + IMMUTABLE TASK DEFINITIONS
                           |
                  APPEND-ONLY TYPED EVENTS
                           |
                   HASH-CHAIN VALIDATION
                           |
           REPLAY TASK STATE / DEPENDENCY DAG
                           |
                  READ-ONLY NEXT PROJECTION
                           |
           FRESH TARGET CHECK / EXACT AUTHORIZATION
                           |
                    SEPARATE EFFECT
                           |
                  INDEPENDENT READBACK
                           |
                 GOVERNED NEXT REVISION

Initial tasks may be READY, WAITING or BLOCKED only. No seed task claims that work already executed. Every task records a stable task_id, owner, scope, intent, dependencies, effect_class, separate authorization_gate, source_refs, acceptance predicates and a concrete first_action. Historical achievements appear as scoped baseline evidence; they are not reintroduced as fabricated COMPLETE events.

Permitted state transitions are WAITING to READY/BLOCKED/SUPERSEDED; BLOCKED to READY/SUPERSEDED; READY to IN_PROGRESS/BLOCKED/SUPERSEDED; IN_PROGRESS to VERIFIED/BLOCKED/SUPERSEDED; and VERIFIED to COMPLETE/BLOCKED/SUPERSEDED. COMPLETE and SUPERSEDED are terminal. READY/IN_PROGRESS/VERIFIED/COMPLETE require every dependency to be COMPLETE. Completion requires independent TEST, RUNTIME, CI or GITHUB reference. Effectful completion additionally requires an OPERATOR reference. These rules check reference structure; they do not authenticate the referenced event.

The REGISTER_TASK event adds a task with a new monotonically increasing SVC-#### ID. TRANSITION advances state. Rewriting a task or erasing an event is invalid. Each event has sequence, claimed actor, timestamp, typed evidence references, previous digest and domain-separated SHA-256 digest. Revision equals one plus the event count; the chain head equals the final digest. The original task DAG must remain acyclic and timestamps must not regress. assert_append_only(previous,successor) rejects rewriting of definitions or event history. Git history and independent readback remain necessary to authenticate a published revision.

SOURCE, GITHUB, CI, TEST, RUNTIME, OPERATOR, SIGNED, CHECKPOINT and UNKNOWN are evidence-ref prefixes, not sources of granted authority. UNKNOWN is not independent success. Two concordant models or a retrieval result cannot close an execution gate.

## Continuation and evolution

At the start of operator-directed continuation, select the latest published file at a named Git ref, validate it, project the next task and independently reacquire exact Git/CI/runtime. If source or grant validity has changed, propose BLOCKED rather than silently inheriting READY. Keep both earlier and later observations. At handoff, record delta, blockers, attempted/reconciled effects, currentness and the first unfinished task. Never automatically start a new mission.

Commands from repository root:

    python tools/lion_service_continuation_ledger.py validate
    python tools/lion_service_continuation_ledger.py next
    python tools/lion_service_continuation_ledger.py propose-transition \
      --task SVC-0001 --to IN_PROGRESS --actor operator \
      --at 2026-10-11T09:00:00Z --evidence-ref SOURCE:exact-observation \
      > /tmp/lion-service-ledger-proposed.json
    python tools/lion_service_continuation_ledger.py \
      --ledger /tmp/lion-service-ledger-proposed.json \
      validate-append --previous LION/architecture/v1_5/SERVICE_CONTINUATION_LEDGER_R1.json

The CLI validates and prints proposals to stdout only; it never updates the tracked journal. All proposed next revisions require ordinary source review, exact-head CI, dependency revalidation, appropriate formalization and repository publication gates. New tasks must be appended as REGISTER_TASK events, not inserted into immutable baseline tasks. No worker fleet is needed for an administrative ledger update.

TRUST CHANGE, AUTHORITY PROVISIONING, GIT MERGE, DEPLOYMENT and LPCL LAUNCH are five separate effects. The R11 verifier rebind was explicitly approved and observed, but it did not authorize PR445 production provisioning. That grant depends on exact transaction, mission, epoch, resource, head/base and validity window. Signed PR445 policy/grant inputs expire on 2026-10-12T20:23:44Z; new authorized issuance is necessary after expiry. PR446 must be rebound to post-PR445 master and requires distinct signing/admission.

## Formalization, consumers and future integration

The non-effectful owner is cyber_lion/contracts/service_continuation_ledger.py; the source instance is SERVICE_CONTINUATION_LEDGER_R1.json; SERVICE_CONTINUATION_LEDGER.schema.json supplies JSON Schema structure; tools/lion_service_continuation_ledger.py is the read-only/proposal consumer; cyber_lion/tests/test_service_continuation_ledger.py tests mutations, DAG, authority boundaries and replay.

FORMALIZATION_REGISTRY_FEDERATION_R1.json includes all six surfaces. The ledger is classified as SOURCE with MIXED currentness: it is a pinned historical proposal that references observations, not live truth. README.md, LION/README.md, this v1.5 root, Codex runbook, AGENTS and CONTRACT_MAP route readers to this owner. Documentation census/graph/reconciliation and truth/currentness carriers are generated from an exact integrated source tree and must not be manually rewritten from a candidate; their update is a separate reconciliation and publication step.

A future change may add a READ-ONLY Mission Control projection consuming a validated published ledger. That consumer is NOT implemented or deployed by this version. It must not dispatch work or mutate task states without an independent admitted effect path. SaaS and LOCAL may receive different relevance projections while retaining the same canonical evidence identity and separate projection digests.

## Actual R11 continuation

The seed contains 16 bounded tasks: 3 READY and 13 BLOCKED. Initial ready work comprises exact signed PR445 package assembly and isolated rehearsal, read-only expiry/restart observation, and source/CI formalization of this ledger. Dependent work includes distinct authority provisioning, fresh CI observation and merge for PR445, rebinding and separately authorizing PR446, deployment, and later exact Application Factory LPCL launch by the operator.

First next action SVC-0001: assemble and validate the five previously signed R11 documents, preserving their transaction digest, and execute only bounded original-contract tests against a disposable SQLite store. This is NOT permission to provision the production store. After significant source/runtime/authority changes, add new evidence-bound events and revise the published ledger through the governed source path. Do not erase history or infer a new authorization.


## R1 revision 10 — actual source-candidate delta

After the seed was published to draft PR #447, the operator's five already signed PR445 contracts were assembled into a non-authorizing signed review package. The immutable review artifact was independently read back on MOON at SHA-256 2544f26b7e47dacd0b2252e372ec12b1015c0953cdc904507f4cdbf52b560f92. The original SQLiteAuthorityProvisioningStore, exercised on an ephemeral database, produced one exact bootstrap, one lineage, two receipts and rejected a replay. The disposable database was destroyed; production provisioning remained NONE.

Nine sequential digest-chained events preserve these evidence pointers and mark SVC-0001 and SVC-0002 COMPLETE. SVC-0003 is now READY for **separate human authority-provisioning approval** (not approved), and SVC-0016 IN_PROGRESS pending this draft's CI and separately admitted merge. The dependency and evidence history is retained, not overwritten. No status creates authority or authorizes production writes.

See the [R11 operator readiness report](SERVICE_READINESS_REPORT_R11_20261010.md) and [typed snapshot](SERVICE_READINESS_SNAPSHOT_R11_20261010.json) for the observation-bound answer to whether the Panel can launch Application Factory. Fresh runtime and Git readback always supersede this snapshot.
