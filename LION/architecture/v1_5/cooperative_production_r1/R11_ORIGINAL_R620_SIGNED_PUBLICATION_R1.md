# R11 — original R6.20 create-only signed-row publication

STATUS = SOURCE_ONLY_CANDIDATE
LIVE_ISSUER_AND_KEY_AUTHORIZATION = NOT_PROVEN
AUTHORITY_EFFECT = NONE_FROM_DOCUMENT
PRODUCTION_RELEASE = NOT_INSTALLED

The original R6.20 input boundary now has a consumer plus a separate,
consequential signed-record publication owner. The existing
SQLiteSignedOriginalR620PartsSource reads a preprovisioned private database
without writes, while CreateOnlyOriginalSignedR620Publisher can INSERT one
already issued signed record only under independently current ORIGINAL
LiveAuthorityAdmission for the exact action
PUBLISH_ORIGINAL_R620_SIGNED_PARTS, exact SQLite resource path and the
separately bound PR number, base SHA and HEAD SHA of the authorized release.

This module contains NO signer or private key, generates no grant, does not
call the PDP to obtain ALLOW, does not issue RuntimeAdmission, starts no
worker and does not establish trust from a model output, Git commit or RAG.
A separate ORIGINAL upstream issuer must already have signed exact canonical
bytes and must provide them through a separately trusted source with
resolve_issued_exact(assignment,mission,generation,input_digest,now).
No fallback source, auto-sign, simulated READY or environment-selected key.

The publisher reuses original R6.20 MD001 HELD assignment, operator/driver
and revocation fences, existing canonical PDP and current policy reader,
original LiveAuthorityAdmission.revalidate and explicit signed grant action
and resource scope. It validates Ed25519 with the independently pinned
public key and all twelve input contracts BEFORE any write. Revalidates
the original operator fence, grant epoch/source and publication clock again
immediately before the effect. Separate DB transactions cannot atomically
lock original operator state across the entire source chain, so canonical
HELD->READY and effect-time currentness remain mandatory, independently
enforced fences.

The publisher's only new effect is one CREATE-ONLY SQLite INSERT under
BEGIN IMMEDIATE into an existing pre-provisioned schema. No CREATE TABLE,
UPSERT, REPLACE, automatic retry or outside DB write. A duplicate
publication is REPLAY_DENIED. A possible committed write with failed
readback is EFFECT_UNKNOWN, requiring independent reconciliation before
an explicitly authorized next action. The existing signed reader performs
the independent post-COMMIT readback, still using mode=ro/query_only=ON.

Disposable regression tests exercise exact existing classes with a fake
original authority receipt and a throwaway in-memory Ed25519 signer. This
is NOT production authorization or proof of the real issuer's identity.
The real original issuer, protected signer/key provenance and issuer
source trust, separate exact-release grant, actual signed records and
protected installer remain unavailable/unproven on LION-AUTH-LAB.

Original PR #446 platform-security refusal remains unadjudicated;
its prior single-use grant remains consumed. PR #455 source-only CI
cannot authorize merging PR #446, installing provider releases, issuing
MD001 RuntimeAdmission or an LPCL operator START.

NEXT: acquire original authorized issuer and signer provenance in original
control plane; reconcile governance and source exact release before effects.
