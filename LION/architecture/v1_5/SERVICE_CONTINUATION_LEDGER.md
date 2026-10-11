# LION Service Continuation Ledger — R1

Status: SOURCE CANDIDATE / NON-AUTHORIZING ARCHITECTURE RECORD until exact-head CI, formalization closure and admitted integration. This document is a v1.5 architecture surface, not a live Mission Control feed. Authority effect: NONE. Runtime effect: NONE.

## Purpose and owner

SERVICE_CONTINUATION_LEDGER_R1.json is the source-controlled service handoff register for unfinished LION work in the R11 trajectory. It preserves four operator questions across conversations and models: what remains, why, what observation or admission is missing and the first safe next action. Its semantic owner is cyber_lion/contracts/service_continuation_ledger.py, indexed as service_continuation in semantic_owners.json, with its twelve source-bound formalization surfaces in SERVICE_CONTINUATION_FORMALIZATION_REGISTRY_R1.json (candidate only).

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

SERVICE_CONTINUATION_FORMALIZATION_REGISTRY_R1.json contains twelve candidate surfaces. The older 36-entry FORMALIZATION_REGISTRY_FEDERATION_R1.json and its sealed historical RequiredFormalizationSets and ClosureRecords remain unchanged; they must not be retroactively extended with unverified new surfaces. A successor integrated registry and closure require an independently verified formalization of this candidate. The ledger is classified as SOURCE with MIXED currentness: it is a pinned historical proposal that references observations, not live truth. README.md, LION/README.md, this v1.5 root, Codex runbook, AGENTS and CONTRACT_MAP route readers to this owner. Documentation census/graph/reconciliation and truth/currentness carriers are generated from an exact integrated source tree and must not be manually rewritten from a candidate; their update is a separate reconciliation and publication step.

A future change may add a READ-ONLY Mission Control projection consuming a validated published ledger. That consumer is NOT implemented or deployed by this version. It must not dispatch work or mutate task states without an independent admitted effect path. SaaS and LOCAL may receive different relevance projections while retaining the same canonical evidence identity and separate projection digests.

## Actual R11 continuation

The seed contains 16 bounded tasks: 3 READY and 13 BLOCKED. Initial ready work comprises exact signed PR445 package assembly and isolated rehearsal, read-only expiry/restart observation, and source/CI formalization of this ledger. Dependent work includes distinct authority provisioning, fresh CI observation and merge for PR445, rebinding and separately authorizing PR446, deployment, and later exact Application Factory LPCL launch by the operator.

First next action SVC-0001: assemble and validate the five previously signed R11 documents, preserving their transaction digest, and execute only bounded original-contract tests against a disposable SQLite store. This is NOT permission to provision the production store. After significant source/runtime/authority changes, add new evidence-bound events and revise the published ledger through the governed source path. Do not erase history or infer a new authorization.


## R1 revision 10 — actual source-candidate delta

After the seed was published to draft PR #447, the operator's five already signed PR445 contracts were assembled into a non-authorizing signed review package. The immutable review artifact was independently read back on MOON at SHA-256 2544f26b7e47dacd0b2252e372ec12b1015c0953cdc904507f4cdbf52b560f92. The original SQLiteAuthorityProvisioningStore, exercised on an ephemeral database, produced one exact bootstrap, one lineage, two receipts and rejected a replay. The disposable database was destroyed; production provisioning remained NONE.

Nine sequential digest-chained events preserve these evidence pointers and mark SVC-0001 and SVC-0002 COMPLETE. SVC-0003 is now READY for **separate human authority-provisioning approval** (not approved), and SVC-0016 IN_PROGRESS pending this draft's CI and separately admitted merge. The dependency and evidence history is retained, not overwritten. No status creates authority or authorizes production writes.

See the [R11 operator readiness report](SERVICE_READINESS_REPORT_R11_20261010.md) and [typed snapshot](SERVICE_READINESS_SNAPSHOT_R11_20261010.json) for the observation-bound answer to whether the Panel can launch Application Factory. Fresh runtime and Git readback always supersede this snapshot.

## R1 revision 22 — real signed production authority and CI close

Twelve new append-only events preserve operator approval and execution evidence for PR445 production provisioning plus independent GitHub Actions readback run 38066162833 attempt 3 job 114325801039, observation digest 2ff9592fd057eeb24cf3de37cf9efc7d671c6167bbb59160fb302f043ac92488. Tasks SVC-0003, SVC-0004 and SVC-0005 are COMPLETE; SVC-0006 is READY pending consuming merge admission. The grant is CURRENT and unconsumed as of the CI readback, not merged.

Two domain-separated lineage digests must be preserved: the source/consumption key 105ddde7101bf3cdb31dddcdeed85263c6d5439704f10d0fef3ba9757cef61e5 versus the in-process admitted digest 9e579be6d140203521c644d06aae5b70a3a9677d864d71fc92046dedd90b7e8e. Reusing the second digest in the external consumption key would not fence the observer. A versioned [readiness successor](SERVICE_READINESS_REPORT_R11_20261011.md) describes the safe one-shot, non-atomic consuming admission and subsequent GitHub merge boundary. Failed or unknown state MUST be reconciled without blind retries.


## R1 revision 31 — PR445 merged, PR446 rebased

Nine new append-only transitions record successful one-shot PR445 consumption and GitHub merge receipt. GitHub readback confirms merge commit d367e47cf4f72e450cc212908b2cdfed14ceb805, tree b92133d258b6fbf2c7f1d16d992e08d2a3609a0c and both exact parents. PR446 was rebound to master with a new source-only commit and a separate carrier-only commit; final head d8141ce421952bb0b352d873b706e183684f20f9 has local tests passing, with Core CI pending at the report timestamp. SVC-0006 and SVC-0007 are COMPLETE; SVC-0008 remains IN_PROGRESS. PR446 unsigned signature payloads are source proposals, not authority. See [SERVICE_READINESS_REPORT_R11_POST_PR445_MERGE_20261011.md](SERVICE_READINESS_REPORT_R11_POST_PR445_MERGE_20261011.md) for the gate vector. Do not auto-start LPCL.


## R1 revision 46 — PR446 production authority verified

Operator-executed exact signed PR446 production provisioning passed with one bootstrap and one authority lineage; the PR445 historical records remained unchanged according to the operator receipt. An independently rerun GitHub Actions Cyber-Lion Merge Authority Observation, run 38092247411 attempt 2 job 114340312000, produced signature_valid=YES, epoch_current=YES, consumed=NO and authority_current=YES with digest 02e5ab01df879f83cf49fdb02d7e069ad3b8af6f7ef00acd47ef258683adc7f3.

Seven append-only events close SVC-0009 and SVC-0010 and mark SVC-0011 READY. A new exact PR446 consuming-merge candidate was staged on LAB-DEBIAN and tested via original installed code with disposable SQLite, including replay denial. Production consumption has not executed. The canonical source lineage digest 85244068c22b0c3304fef5a31b1f3f4ffa2117cf9a15c0ba0d739e036455d534 is distinct from the admitted lineage digest 5be926505d731815318972eb03b053c977c43132c34e3d26766f31e88eaa4a99. The durable consumption key uses the former.

Before GitHub merge, operator must execute one exact SHA-pinned preflight plus one-shot consuming admission under local root, preserve root-only receipt, then reconcile the separate GitHub operation. Do not blindly retry. LPCL remains undeployed/unregistered for Application Factory and cannot be started from this candidate source state.


## R11 local revision 68 -- bounded autonomous execution

After exact operator provisioning and one-shot consumption, PR446 remains open and unmerged because a GitHub merge connector invocation was blocked by platform safety controls. Operator signed authority consumption receipt SHA256 ddfddf17f1c1d0ac821ad90f0b18097bdad3b11ff87e0d096914882a985d053f. Do not retry consumption, switch merge transports to evade the block, or declare integration.

On LION-AUTH-LAB, original 93-file canonical staging and original installer with rollback were tested in isolated directories, including byte-exact restoration and SQLite preservation. Exact HTTP LPCL registration accepted an initial registration (201), idempotent repeat (201), and rejected wrong digest (400). The original broker VALIDATE_UPDATE passed with candidate source bytes; no production update occurred. The source-bound R11 external adapter was also tested using real existing R6.21/R6.15/R6.16/R6.17 classes and disposable synthetic authority input; MD001 qualified without artifact write, while source, worker, and SHA substitution were denied. Genuine production R6.21/R6.17 owners remain unbound.

Correction: the Application Factory first CONTROL_PLANE_RECONNAISSANCE phase does not require an already completed SaaS or LOCAL session before explicit operator START. Those separate independent cognition results and a responded SaaS advisory are needed to complete the first phase. The canonical contract maps earlier cognitive readiness only for directly declared LOCAL_MODEL_INFERENCE or SAAS_DELEGATION classes; existing source tests confirm the behavior. First launch remains separately operator authorized and requires exact current deployed source.

A dedicated read-only R11 readiness diagnostic was created on LION-AUTH-LAB at /var/lib/sentinelx/uploads/lion-r11-pr446-autonomous-readiness/lion_r11_pr446_readiness_probe.py with SHA256 2d2a6ab8f392f1e6c8bc252f2c047347f88bf80046470a809a077479b4003461. It checks current GitHub, live Mission Control source/broker identity, registration, capability binding, true 32-worker qualification and candidate archive; correct run returned seven blockers and zero UNKNOWN. The 13-member target-host source/test archive SHA256 is 44532408775e18c1e8d8d1baddde929832163e02f396af68af989d5484679610.

Local append-only ledger: revision 68, 67 events, 16 of 21 tasks COMPLETE, three BLOCKED. Tests: 54 ledger/formalization PASS; LION-AUTH-LAB source tests: 71 R11/wiring/resolver and 53 ApplicationFactory/cognitive/packaging PASS. Some of the first 71 showed SQLite ResourceWarnings; do not infer resource hygiene from functional PASS. Production Mission Control 8766 is healthy but still old source; factory mission/drivers absent; live 32 workers not qualified; no production LPCL activation.

Exact next step: resolve the blocked GitHub merge via originally approved governance, without evasive retry. If newly permitted, independently confirm the merge commit and parent chain, then use separately admitted broker update and canonical master-bound staging/install; verify deployed HEAD/TREE, recompile source-bound registration and present exact LPCL to operator for separate explicit START. Full fleet material BUILD and VERIFY remain later gates. The local source ledger is not on master; PR447 remains draft and stale based.

## R1 revision 85 — scope supersession and new bounded successor

Nine append-only source events supersede SVC-0012, SVC-0013 and SVC-0014, whose immutable PR446 identities have become stale. Their original records are retained. Six successor tasks SVC-0024 through SVC-0029 explicitly separate read-only currentness, new authority admission, exact PR merge, broker deployment, 93-file Mission Control installation and exact human LPCL START.

PR446 base d367e47cf4f72e450cc212908b2cdfed14ceb805 and head d8141ce421952bb0b352d873b706e183684f20f9 were independently read at source-candidate time; they are not future authority. Only SVC-0024 is READY for observation; all five effectful successors remain BLOCKED. Neither an expired/consumed grant nor a denied merge tool permits another transport or automatic mission activation. Runtime readiness is not implied by this ledger.

## R1 revision 88 — read-only SVC-0024 observation closed without new authority

Three append-only transitions advance only SVC-0024 through IN_PROGRESS, VERIFIED and COMPLETE. The cited MOON evidence records exact PR446 Git/CI identity, historical consumed-grant receipt, and fresh broker state UNBOUND/EXPIRED. Live production authority-store currentness remains explicitly UNKNOWN. This completion proves a scoped classification and negative effect boundary, not a new authorization.

SVC-0025 through SVC-0029 remain BLOCKED. They require a separately admitted current authority grant, an admitted GitHub merge, independently authorized broker/Mission Control deployment and exact operator LPCL launch. Old consumed authority is not reusable. The original 84 historical events are byte-preserved in the new event-array prefix.
