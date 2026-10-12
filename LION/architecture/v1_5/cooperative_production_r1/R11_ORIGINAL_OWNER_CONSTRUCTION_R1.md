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


## Original worker verifier exact-byte import

The existing R24 cooperative worker source
cyber_lion/enterprise/cooperative_dependency_provider.py remains the
original source for read-only worker authority/epoch/root lookups. Before
an R11 production owner can trust that worker-side verifier, the
externally pinned verifier Python module MUST run only the SHA-256
checked bytes; an importlib SourceFileLoader reopen after prehash is a
time-of-check/time-of-use executable-source substitution hazard.

The source-only fix compiles/executes the very same checked bytes,
requires a direct non-group/world-writable original file and parent,
rechecks (device,inode) and SHA-256 after import and after ready(),
and cleans the transient module namespace on failures. The original
TrustedSignatureVerifierAdapter and issuer key/epoch/root validation are
reused; this does not generate a key, signature, grant, RuntimeAdmission,
current PDP result or operator activation.

Negative tests swap the verifier source after the first digest-bound
read and prove the substituted code does not execute (a harmless
temporary-file marker stays absent). Tests also deny writable modules
and verify no importlib second loader read is invoked. These
are isolated source tests with an intentionally fake verifier fixture;
they do not establish live cryptographic trust or production deployment.

Source-only; original PR #446 platform-security refusal and exact
release/runtime/operator admission remain separate hard boundaries.


## Original source service handle assembly — R11

The source-only r11_original_current_owner_builder.py supplies an
explicitly parameterized build_current_owner_sources(OriginalR11ServiceOwners).
It accepts already-existing control-plane service objects, not a document,
inferred receipt, self-asserted authority or a generic default constructor.

The original service must independently supply:
- exactly scoped Application Factory / MD001 paths and source identity;
- an independent exact preparation-evidence resolver with its own
  source/trust binding and validated R6.20 preparation evidence;
- an original read-only SQLiteR11CanonicalPDPEvidenceReader and its
  distinct canonical PDP source-trust binding;
- the SAME existing LiveAuthorityAdmission instance reused for original
  R6.21 issuer and downstream exporter, with real verified issuer roots;
- the original private durable RuntimeAdmission replay guard and
  PREEXISTING R6.21 admission SQLite source;
- original currentness, dispatch, provisioned identity/binding, transfer,
  worker durable source trust and timezone-aware trusted clock.

The function constructs the ORIGINAL RuntimeAdmissionEngine from these
objects and returns an exact CurrentOwnerSources, after both its own and
the original CurrentOwnerSources source-only validation. No file, journal
or signature is created by this function. Preparation resolver callbacks
re-check original trust before and after their original owner call, and
the exact verified mission ID is captured in the closure rather than
reinterpreted later from global configuration.

The original separately SHA-pinned external zero-argument
build_current_owner_sources() implementation can invoke this bounded
constructor after the ORIGINAL owner service acquired the trusted handles.
A disposable integration test exercises exactly that loader path, using
clearly marked synthetic original service handles. The production
zero-argument upstream owner service itself remains NOT INSTALLED and
NOT VERIFIED on LION-AUTH-LAB. This constructor is not an issuer,
registry, provisioning source, authority grant, LPCL activation or
material execution mechanism.

SOURCE_ONLY; ORIGINAL_PLATFORM_SECURITY_REFUSAL=UNRESOLVED;
RUNTIME_ADMISSION=NOT_PROVEN; PRODUCTION_MD001=HOLD.
