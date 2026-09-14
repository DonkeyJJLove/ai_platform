# Epoch 3 closure — architecture, federation and control plane

Generated from live evidence at `2026-09-13T11:39:17.100008Z`. This document is a **candidate projection**, not a terminal completion receipt. Epoch 3 closes only after full validation, exact GitHub publication/CI/merge, remote-ref closure and carrier-last binding.

## Mission objective

Close LION evolution epoch 3 with a truthful architecture and documentation upgrade, safely reconcile the ten-repository federation, prove GitHub collaboration through one validated publication path, close obsolete mission refs, and produce an exact handoff for the next current RAG so evolution phase 4 can begin.

## Architecture now

The target operator path is **LION CONTROL LPCL PANEL** (`127.0.0.1:8780`) → exact LPCL activation → **LION MISSION CONTROL** (`127.0.0.1:8766`). LPCL validation and registration do not create authority. At the latest Epoch 3 closure reacquisition, Mission Control is live on `8766` but the LPCL Panel on `8780` is **not listening**, therefore this target path is not yet a closure fact and remains an Epoch 3 blocker. Mission Control is a superset of the historical observer: it retains Run Registry, Fleet Observatory, Environment, events/messages/artifacts/receipts and adds mission focus, objectives, phases, typed protocol communication and bounded lifecycle control.

The local `gpt-oss-20b-MXFP4` remains proposal-only on RTX 5090/Vulkan0 at `127.0.0.1:8772`. Repository, public-web and Mission Control currentness are mediated by the 12 user-level MAT workers. For mission currentness, the path is `local model → gateway → MAT04 → MAT08/MAT10 → Mission Control`, so RAG or model memory are not used as live mission truth.

The active Epoch 3 closure mission has 12 logical roles and a separate mission-scoped Kubernetes fleet of **64/64 Ready Pods** in namespace `lion-epoch3-closure-r1`. The distribution is `6,6,6,6,5,5,5,5,5,5,5,5`; all Pods are non-root, read-only-rootfs, drop all Linux capabilities, have no service-account token and are under deny-all network policy. This proves material process instances, not 64 physical failure domains; current evidence still supports one physical/kernel failure domain.

## Repository and federation state

Live `ai_platform` master at mission entry is `849db8f5ea6434f5647ee072cd4835fd2264e078` / tree `fccec66a96e8d914dff8b835ccbbadd9dca0a608`. The ten-repository federation was reacquired and matched the LPCL-bound vector. Dirty operator work was preserved. No clean behind-only clone required fast-forward in this pass.

GitHub currently has seven branches. Five old mission refs are strict ancestors of master. `mission/master-homeostasis-publisher-r1` has one unique obsolete commit and remains **SUPERSEDED_DO_NOT_MERGE**. Publication, merge and branch deletion remain pending until exact-head validation.

## Source reconciliation

The active R10-R2 local intelligence delta has been materialized into this isolated Epoch 3 candidate. The deployed Mission Control v3 and compatibility read model are stored as complementary canonical runtime sources rather than overwriting the historical observer implementation. The exact live effect-admission broker is reconciled into the existing canonical `tools/lion_effect_admission_broker.py`. See `EPOCH3_SOURCE_PROVENANCE.json`.

## Mission database and lifecycle compatibility

Epoch 3 also closes the database/lifecycle gap exposed by imported VKT-R3 and OSS Repository Test missions. Historical mission identifiers containing `::` must resolve through the process API, and older records must be represented as `HISTORICAL_PRE_SCHEMA` rather than converted into synthetic `0.0% / no phase` modern records. The additive `lion.mission-control.lifecycle-db/v2` candidate introduces schema migration receipts, mission lineage, typed data gaps, components, design revisions, audits, rollback evidence and lifecycle action receipts. See `MISSION_CONTROL_DATABASE_LIFECYCLE_EPOCH3.md`.

The lifecycle vocabulary becomes `REFRESH`, `AUDIT`, `RESTART`, `START_COMPONENT`, `ADD_COMPONENT`, `REDESIGN` and `ROLLBACK`. Only operations backed by an exact bounded material adapter may execute effects. In particular, Epoch 3 exposes component-start as a contract but keeps it `ADAPTER_REQUIRED`; redesign/add-component/legacy replay and rollback remain revision/plan operations until compiled into a new exact LPCL. This is the control-plane scaffolding on which Epoch 4 will evolve.

## Semantic compilation frontier

The future Semantic Inference Compiler is incorporated only as target architecture. It is not promoted to AS-IS by this closure. Its role is to convert stable, evidence-bound inference into reusable semantic scaffolds and deterministic representations while preserving currentness, provenance, falsification and the existing authority/effect separation. See `SEMANTIC_INFERENCE_COMPILER_TARGET.md` and `EPOCH3_TO_EPOCH4_CONTROL_ARCHITECTURE.md`.

## Remaining closure gates

Full repository tests, Bandit 1.9.4 CI profile, Full Symbol Census, production effect inventory/taxonomy, workflow homeostasis, browser canaries, schema-aware Mission Control canaries, exact candidate publication, exact-head CI, merge, branch cleanup, restoration of the `8780` LPCL Panel and carrier-last truth are still required. The next RAG is **not built in this mission**; `RAG_HANDOFF_EPOCH3.json` is populated only with exact inputs after terminal closure.
