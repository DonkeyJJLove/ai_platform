# Mission Control source rebind candidate

`source_rebind.py` models an offline plan only. A target must equal a freshly observed master HEAD/TREE and is additionally bound to release, configuration, adapter-set and database-schema digests. The plan has `authority_effect=NONE`, `runtime_effect=NONE`, `service_restart=false` and `k3s_effect=NONE`.

This does not alter `/opt/lion`, systemd, K3s, Mission Control database state or credentials. `apply_source_rebind` fails closed because deployment requires a separate authority and runtime reconciliation.
