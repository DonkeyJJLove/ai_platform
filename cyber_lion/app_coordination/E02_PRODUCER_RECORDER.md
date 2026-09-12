# E02 local producer and recorder candidate

This is an inactive local implementation. No installation, service, signing key,
application session, runtime qualification or canonical admission source is created.

producer_records.py provides pure constructors for caller-supplied application and
local-process observations and complete supplied qualification measurements. A PID,
boot, process start, model and configuration change changes the observation; this
does not automatically invalidate any real runtime cache. No OS or application
collector is installed. PASS on supplied measurements is not runtime qualification.

RecordVerifier checks a bounded strict JSON envelope, producer policy, domain,
exact subject, freshness, boot identity, caller-supplied sequence lower bound and
current key status before and after verification. It delegates signature checking
to the existing TrustedSignatureVerifierAdapter with an explicit external backend.
The result remains SIGNATURE_CHECKED_NOT_RUNTIME_AUTHORITY. Payload contents are
objects covered by the checked signature; kind-specific semantics still require
trusted decoders. Durable sequence state, a trusted time source, policy provenance,
real cryptographic verification and authenticated collectors remain integration
requirements. APP_SESSION_ATTESTATION and runtime resolve are refused.

result_recorder.py creates only a new, explicitly marked offline SQLite database.
A prior matching reservation is mandatory. Receipt, request index and recorded
state commit in one transaction; identical duplicates return the same candidate,
conflicts cannot overwrite, and one receipt cannot be reassigned. Readback checks
stored hashes, canonical receipt validity and task/provisioning consistency.
Hashes and the store UUID detect local inconsistency; they do not authenticate
the writer or resist an actor able to rewrite the database and its metadata.

An unresolved reservation stays UNKNOWN_REQUIRES_RECONCILIATION and never permits
retry or dispatch. record_canonical and resolve always refuse. Synthetic fixtures
are accepted solely through the explicitly named record_candidate offline API.
This module does not call RuntimeAdmissionEngine or couple its replay consumption
to the result transaction. A crash after replay consumption and before recording
still needs separately reviewed engine integration. Do not infer end-to-end
atomicity, power-loss guarantees or runtime admission from these tests.

The offline suite includes real subprocess termination between receipt insertion
and index insertion, abrupt exit after commit, concurrent duplicate writers,
conflict preservation, current key-status changes and malformed trust inputs.
The injected signature callback is a test double, not cryptographic evidence.
The harness also composes with existing local TaskActionBinding/BoundTaskAdmission
types and repeats source-adapter and E01 assignment regression tests.

e02-installation.inactive.json is a reviewed proposal, not an executable installer
or a runtime configuration. Its null fields are unresolved, not defaults.
Changing a flag does not implement an activation path.

Two new Python modules add external callback invocation and SQLite file-write
surfaces to the local candidate inventory. Integration must refresh source census
and dependent truth carriers on the final candidate; historical CI and inventory
cannot certify these uncommitted files. Review here is by the implementing agent,
not an independent physical verifier. Publication and live operation remain outside
this stage.
