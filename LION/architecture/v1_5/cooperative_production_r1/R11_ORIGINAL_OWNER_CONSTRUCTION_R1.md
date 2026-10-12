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
