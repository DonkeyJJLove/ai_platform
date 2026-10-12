# R11 — original R6.21/R6.16/R6.17 owner construction

Status: SOURCE_CANDIDATE_ONLY, not a production provider deployment.
Parent source is exact PR #455 head 3218f451f5f759329f12bdd2f4788fefed053708.

cyber_lion/mission_control/cooperative_current_owner_wiring.py
provides CurrentOwnerSources and assemble_original_owners(sources).
This is a concrete constructor over the original three R6.21, R6.16, R6.17
classes. It reuses the R6.15 exporter, R6.14 evidence publisher/readers,
canonical Mission Control SQLite, currentness and authority revalidator.
It does NOT mint RuntimeAdmission, PDP decisions, identity, authority,
operator activation, or real evidence.

The separately SHA-256 pinned build_current_owners() external owner module
must retrieve existing, independently current CurrentOwnerSources from
the original governance-authorized Mission Control producer interfaces,
then call assemble_original_owners(sources). There is no default or
silent substitution from worker fixtures or synthetic test records.

Exact conditions before production use: PR #446's consumed one-shot grant and
prior platform-security merge denial resolved by original governance;
code source legally merged and installed; MD001 real preactivation
evidence, independent runtime admission, current authority/currentness,
policy, dispatch, provisioned executor, identity and transfer binding;
private root and publisher DB backed up; exact installer release SHA;
one non-executing canary observed and rolled back safely before MD001 START.
The constructor initializes private SQLite tables; it is not safe to call
from read-only live preflight and is never automatically invoked there.

The isolated test uses real original classes and disposable SQLite only;
its synthetic upstream evidence is explicitly not a live authority or
material-workload pass. Unavailable independent upstream sources must block
the external build_current_owners() before any live installation or effect.

Producer -> consumer:
- preparation evidence + original RuntimeAdmissionEngine -> R6.21
- R6.21 -> R6.15 evidence exporter / R6.16 carrier-publisher
- R6.16 released evidence -> R6.14 readers / R6.17 qualification
- original R11 factory -> original Mission Control preactivation registry
- original scheduler -> MD001 qualification only; material effect requires
  separate admission and original LPCL operator START.

AUTHORITY_EFFECT=NONE; SOURCE_ONLY_NOT_DEPLOYED=TRUE.


## R11 external source-bound builder

r11_external_current_owner_source.py is the reviewed, versioned source
of an external, separately SHA-256-pinned build_current_owners() module,
not an installed provider. The operator's original protected release workflow
must copy the exact reviewed bytes outside the Mission Control repository.

The canonical R11 outer factory first validates source file SHA and invokes
build_current_owners(). The inner builder requires all three immutable
environment properties for the independent original source provider:
LION_R11_CURRENT_OWNER_SOURCES_MODULE_PATH,
LION_R11_CURRENT_OWNER_SOURCES_MODULE_SHA256,
LION_R11_CURRENT_OWNER_SOURCES_MODULE_VERSION=1.0.0.
The independent upstream file must expose build_current_owner_sources() and
return exact CurrentOwnerSources. The loader compiles only SHA-pinned bytes,
rejects writable/indirect modules and checks source identity after import.

The source of actual RuntimeAdmission/PDP/authorization/currentness evidence is
not installed by this builder. These objects cannot be reconstructed from
Mission Control receipts or synthetic fixtures. An independent existing
authority/evidence producer remains necessary; NONE is provided as default.
The three-file source chain, isolated canary, real proof of currentness and
exact operator activation are independent gating steps.

The canonical SQLite is never copied from LION-AUTH-LAB to MOON and workers
receive no new raw canonical DB write permission. SOURCE_ONLY; no MD001 launch.


## Persistent RuntimeAdmission replay boundary

The original RuntimeAdmissionEngine protocol relies on a one-shot replay
guard. R11 now provides a narrowly scoped
cyber_lion.enterprise.r11_runtime_admission_replay.SQLiteR11RuntimeAdmissionReplayGuard.
The guard consumes exactly one original 64-character admission replay key
with SQLite BEGIN IMMEDIATE, rejects duplicates across process restarts
and racing workers, and pins a private, direct, single-link SQLite inode.
Missing, replaced, symlinked, group/world-readable or incompatible database
files deny rather than silently initializing a replacement.

CurrentOwnerSources.validate() now requires this durable guard to be
attached to the original RuntimeAdmissionEngine before R6.21/R6.16/R6.17
are constructed. The original independent owner producer must construct the
engine using that guard in a separate, private, explicitly admitted SQLite
path; in-memory replay guards or reused canonical Mission Control SQLite
are invalid for production. The test fixture injects the real durable guard
but uses synthetic canonical evidence only in disposable isolated tests.

This is a persistence and replay boundary, NOT a second issuer of
RuntimeAdmission and NOT an operator grant, approval, LPCL START, fleet
activation or production deployment.


## Original admission authority and PDP source unity

R11 CurrentOwnerSources.validate() explicitly binds the issuer-side
RuntimeAdmissionEngine._authority by Python object identity to the very
same original LiveAuthorityAdmission used by the R6.15/R6.16
evidence exporter and R6.17 qualification root. Two separately
constructed revalidators are not accepted just because they both have the
canonical class type; they could disagree about a revoked epoch,
current authority lineage or trust source at the issuance boundary.

Before opening any new R11 private journal, the composition also
reacquires the original RuntimeAdmissionEngine canonical PDP source
and its PDPSourceTrustBinding, checks exact source ID, instance,
implementation and trust anchors, and requires the independent
resolve / current_policy_binding consumers. These checks do not mint
a PDP decision or create the authoritative upstream source. The
independent original producer must furnish the same current objects
through a separately approved, SHA-pinned production module.

Synthetic test fixtures were reconciled to one FakeAdmission instance
only in the isolated test harness, with negative substitution tests.
authority_effect=NONE, runtime_effect=NONE, production=HOLD.


## Original PDP evidence producer and independent read-only source

The source-only r11_canonical_pdp_evidence.py adds one scoped original-PDP
evidence publisher and separate read-only SQLite consumer. It uses the
original CanonicalPolicyDecisionPoint and independently bound issuance
observation; it cannot mint a PDP ALLOW, extend its original lifetime
or infer current policy from a persisted record. Refer to
R11_ORIGINAL_PDP_EVIDENCE_R1.md for exact external owners and effects.
The original R11 source composition still requires a live, independently
qualified build_current_owner_sources() and production governance.
