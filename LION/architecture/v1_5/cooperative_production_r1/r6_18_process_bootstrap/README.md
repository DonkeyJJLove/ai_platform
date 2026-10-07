# R6.18 process bootstrap — formalization preview

Status: `STACKED_SOURCE_CANDIDATE / NOT_DEPLOYED`.

Parent source: `7d04359d6d3ce3c9054057fb86c22f1e0e3c54dc` (Project Reality R1 candidate).

Non-generated source tree: `d38e9380652dab1cf0464a94c9cebe2c37bb5e82`.

Candidate digest: `9425e43795e9da21a9e53dc69d107e178921eb3b0a255b470a830ac55cf67868`.

Compilation digest: `96120677db23d5bc12432ae484e379ec06d15c6b7a1ad0d5966ca2ba317faeac`.

The existing ArchitectureCompiler derives 36 formalization surfaces and stops before admission. This package does not assert FCR PASS, deployment, provider availability or worker readiness.

R6.18 adds the missing process-local installation path for the existing cooperative materialization registry. Default mode is UNBOUND. Trusted mode accepts only a SHA-256 pinned external process-composition module returning exact R6.16 control-plane materializer plus the existing runtime composition root for verifier transfer. It does not construct upstream authority/currentness/runtime evidence.
