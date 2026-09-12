# E02 trust — R6

APP_SESSION is a candidate trust boundary, not a production trust decision. The local durable store atomically consumes replay identity and monotonic sequence state; it has restart/reopen and rollback/replay falsifiers. No private key, external trust anchor, production verifier installation or runtime activation was introduced. Runtime readiness remains false.
