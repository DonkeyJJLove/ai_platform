# R11 — original canonical PDP evidence source

STATUS = SOURCE_ONLY_CANDIDATE
AUTHORITY_EFFECT = NONE
PRODUCTION_INSTALL = NOT_DONE
GENUINE_ORIGINAL_PDP_ISSUER = NOT_PROVEN

The canonical RuntimeAdmissionEngine consumes CanonicalPDPDecisionEvidence via
its exact CanonicalPDPDecisionSource, separate from the caller's PDPResult.
This is a source/consumer boundary, not a second PDP or a source of ALLOW.

## Original process ownership

- The ORIGINAL CanonicalPolicyDecisionPoint runs its existing authenticated
  LiveAuthorityAdmission and canonical graph/status/policy/observability gates.
- Only a PDPResult that is the EXACT object retained in that original
  owner's process cache may be exported. This restriction does not itself
  grant runtime authority.
- A DIFFERENT and separately trusted original issuance-observation owner
  must provide an exact OriginalPDPIssuanceObservation that binds request,
  gate, gate digest, original policy binding, issuance window, implementation
  digest, source instance and trust anchor. Its source trust is checked before
  publication and each issuance. The timestamp cannot be taken from the
  publisher's current clock alone; otherwise an old cached ALLOW could be
  extended silently.
- The expiry written by the exporter is bounded by BOTH the original
  issuance-observation expiry and the short configured maximum TTL.
- The operator's separately authorized release/provisioning process creates
  the PRIVATE SQLite database and the exact schema BEFORE startup.
  The publisher itself has no CREATE TABLE or open(O_CREAT) fallback.
- The publisher then inserts precisely one already-issued PDP evidence
  record. Unique request/gate identity forbids duplicate issuance; no
  automatic retry follows an ambiguous DB error.
- The reader opens only the existing DB with mode=ro and
  PRAGMA query_only=ON, validates file identity and permissions, strict
  record schema/digest/trust, exact request/gate and bounded timestamps.
- Current policy is read from an INDEPENDENT original current-policy owner
  every time, never inferred from the stored decision. Returning a
  different policy binding makes original RuntimeAdmissionEngine deny.
- No step in this module obtains an authority grant, creates a canonical
  PDPResult, provisions a worker or executes an effect.

RuntimeAdmissionEngine -> canonical PDP source reader:
  resolve(request_id,gate_event_id) -> original canonical sealed evidence
  current_policy_binding(policy_binding) -> separate real policy readback

The reader is compatible with the original RuntimeAdmissionEngine. Existing
CurrentOwnerSources.validate() already checks the exact canonical PDP source
identity against the original PDPSourceTrustBinding immediately before
assembly and also requires issuer/exporter LiveAuthorityAdmission object
identity and persistent admission replay SQLite.

## Production prerequisites and proof scope

The original owner and independent issuance/policy sources must be REAL,
separately authorized and currently bound to the exact Application Factory
mission, authority epoch, trust anchors, observation and permitted effect.
No such source was found in the current LION-AUTH-LAB installation when
this candidate was authored. Local test fixtures are explicitly simulated:
they exercise an original CanonicalPolicyDecisionPoint and original
RuntimeAdmissionEngine over disposable private SQLite, but not an admitted
production trust anchor, independently signed observation or a live
R11 registry.

The protected installation and canary require original PR #446 merge
governance to resolve the prior platform-security refusal and consumed
one-shot grant without bypass, new exact-source merge/deploy authority,
current real producer/policy currentness, readback of a single MD001
qualification, and a separate operator LPCL START.

The conservative effect scanner records the connection-local
PRAGMA query_only=ON as persistent_state.write, even though the option
sets a read-only connection. It also captures the actual bounded
publisher INSERT as persistent_state.write. Both call sites remain
explicitly inventoried. The schema-provisioning effect is a distinct,
separately admitted installer responsibility outside this source.

## Falsification / regression

- Original admitted ALLOW plus trusted independent issuance window can be
  read by original RuntimeAdmissionEngine through the SQLite reader.
- Missing DB / schema, stale or not-yet-valid issuance, wrong anchor,
  policy drift, changed inode, duplicate JSON, digest substitution,
  wrong coordinates and unissued/cached counterfeit PDPResult are denied.
- Original issuance expiring earlier than requested publication TTL
  caps the published lifetime. Cached ALLOW cannot be reissued after its
  source's own issue window closes.
- Read-only caller cannot silently initialize a missing PDP database.

ALL TESTS RUN IN DISPOSABLE SQLite WITH SIMULATED ISSUANCE/CURRENT POLICY.
NO ACTUAL AUTHORITY OR OPERATOR EFFECT IS PROVIDED BY THIS FILE.
