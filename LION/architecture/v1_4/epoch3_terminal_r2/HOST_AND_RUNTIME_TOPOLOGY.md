# Host and runtime topology

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

Source endpoints: Mission Control 8766, local-intelligence/LPCL panel 8780, local proposal model 8772. Existing broker paths are local and mediated. Port numbers describe configured logical services, not independent hosts or failure domains.

The historical closure document described an RTX 5090/Vulkan0 model runtime and a 64-pod Kubernetes fleet within one physical/kernel failure domain. Preserve these as dated observations. This document does not reacquire GPU, container, kernel, host or pod readiness.

The recorded 2026-09-14T18:33:29Z baseline returned HTTP 200 from both browser-facing services. An HTML response alone does not prove current candidate deployment or working interaction. The R2 database snapshot at 18:45:26Z observed mission-control-v3.db and reported integrity_check=ok. Neither observation certifies all host paths.

Repository audits distinguish Windows and WSL checkout carriers, nested repositories and sentinelx runtime carriers. A missing Git pointer is not a usable canonical checkout; a directory name does not establish role or authority. Final acceptance must record deployed package digests, listener identities, backend/UI behavior and restart readback on the actual hosts. Sources: live-page-baseline.json; r2-live-db.json; r2-repository-notes.md.
