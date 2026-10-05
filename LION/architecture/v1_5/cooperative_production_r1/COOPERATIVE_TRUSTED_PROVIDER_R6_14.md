# Cooperative production R6.14 — pinned trusted dependency provider

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.14 supplies the concrete source artifact and read-only mount contract required by the R6.12 TRUSTED_EXTERNAL_R1 worker bootstrap, while deliberately leaving the live worker bootstrap mode UNBOUND.

The trusted dependency provider composes only already-existing canonical evidence. It does not run PDP, issue RuntimeAdmission, create LiveAdmittedAuthority, provision an executor, create a fleet dispatch or schedule a mission. RuntimeAdmission, CooperativeContextPin, FleetDispatchBinding, ProvisioningBinding, RuntimeIdentityBinding, live authority/currentness and transfer bindings are published into a bounded external evidence database by an independent trusted producer and are consumed by read-only worker sources with exact digest, provenance, expiry and database-identity checks.

The provider's authority revalidator reuses TrustedControlPlaneAuthoritySource over the existing authority_lineage schema, read-only authority epoch/root providers over the existing authority-state database, the existing LiveAuthorityAdmission contract and an externally mounted SHA-256-pinned verifier. Local worker-private authority state is used only for the existing replay/finalization interfaces required by LiveAuthorityAdmission; it cannot create authority and canonical revalidation still depends on the external authority source, epoch and root state.

The small cooperative-provider.py shim is copied outside /src during materialization and is SHA-256 pinned by the worker bootstrap. It contains only the canonical factory delegation. The compose source adds bounded read-only mount points for provider evidence, control-plane evidence and the Mission Control database. Default host paths point to empty unbound directories, so an ordinary source rematerialization remains fail-closed.

The compose source still declares LION_COOPERATIVE_BOOTSTRAP_MODE=UNBOUND. Therefore R6.14 source publication alone cannot install the runtime root, publish cooperative_runtime_provider=READY, bind effectful cooperative capabilities or execute a cooperative artifact assignment.

Activation requires a separately prepared external provider state containing fresh exact evidence, a provider config and context carriers, plus exact external control-plane/authority/verifier material and a read-only Mission Control database. The next boundary is the independent trusted evidence publisher/exporter and an operator-authorized qualification rematerialization; no live fleet restart or activation is part of R6.14.
