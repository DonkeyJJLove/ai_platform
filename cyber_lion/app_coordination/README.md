# Application task assignment

This module proposes task assignments across application sessions, local models
and local processes. It filters candidates by mission role, task class, skills,
runtime revision, observation freshness, budget, deadline and data-egress rules.
Qualified local candidates are preferred unless the task requires an app session.

Inputs describing identity, qualification and availability are caller observations.
An eligible proposal is not authenticated identity, a lease, runtime admission or
permission to execute. No task is dispatched by this module. A changed input,
checkpoint, source head or runtime instance invalidates its previous proposal.

The runtime adapter, durable journal and reconciliation remain external unmerged
candidates. Deployment must establish independent provenance and the existing
canonical admission chain before acting on these proposals. This integration does
not establish Astra runtime authentication or close APP_COORDINATION_R2.

Validation: thirteen assignment tests. Adding these source files changes the scan
digest, but all 259 existing surface digests and the resolved taxonomy remain
identical. Only current scan pins are refreshed; historical evidence is preserved.
