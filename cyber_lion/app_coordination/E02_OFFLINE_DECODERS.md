# E02 offline decoders

offline_decoders.py implements the reviewed passive-timing/v1 contract and exact
decoders for APP_TASK_OBSERVATION, LOCAL_RUNTIME_OBSERVATION and
QUALIFICATION_RESULT. Source decoders reuse existing constructors and compare the
derived canonical payload, so an incomplete report cannot claim PASS or change
its supplied-measurement scope.

decode_passive_timing accepts at most 16384 bytes, strict exact-field JSON, bounded
integers, opaque ASCII identifiers and calendar-valid UTC timestamps. It preserves
up to nine fractional digits, validates same-record monotonic duration arithmetic,
and distinguishes a reported gap from a duration. It does not compare clocks or
establish freshness. All returned timing observations remain UNVERIFIED even when
the input declares VERIFIED_EXTERNAL_SOURCE and supplies an evidence reference.

decode_source_payload accepts bounded strict JSON and only the three supported
semantic domains. TASK_BINDING_RECORD and APP_SESSION_ATTESTATION are refused.
This function does not establish the subject, origin, qualification measurement
provenance or permission. Callers must compose these checks before future source
activation. The existing RecordVerifier remains an envelope verifier; callers
must explicitly invoke the decoder for its payload. No automatic runtime binding
is introduced by this module.

Both decoders are pure and perform no file, network, subprocess, authority or
runtime action. They are not a telemetry collector, diode, durable sequence
ledger, detector or controller. They cannot prove that identifiers or timestamps
supplied by a caller came from a trusted collector.

Compatibility testing uses the existing F009 RuntimeAdmissionReplayAdapter and
SQLiteSingleUseGuard with a temporary database, without invoking admission/effect
execution. The test exposed unclosed SQLite connections during Windows cleanup.
The existing guard now explicitly closes both connections while preserving the
transaction context, API and single-use behavior. This is a resource-lifetime fix,
not a new replay engine or a claim of replay/result atomicity.

Source inventory delta for this stage: one new pure production module, one new
test module, this document, and the connection-lifetime change to the existing
F009 proof module. Exact hashes and patch are in the local evidence package.
Whole-repository census/truth carriers and CI have not been rebound; the changed
F009 module digest invalidates old exact-module pins for this candidate. No
installed module, external pin, service, credential or host was changed.
