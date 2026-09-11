# Native host capacity preflight

The Windows/Linux migration must measure the selected host volume before downloading models or provisioning guests. A WSL virtual disk's nominal capacity is not evidence of free storage on its physical Windows host.

Run from the repository root using Python 3, with an existing data directory:

```text
python tools/lion_native_host_preflight.py --data-directory . --required-free-gib 64
```

The 64 GiB value is an example operator budget, not a measured LION requirement or a reservation. Select the budget from model size, VM growth, artifacts and a host reserve. The tool reports free bytes, shortfall, observation time, the resolved directory and whether the kernel identifies WSL. It creates no directory and changes no host configuration. Run it on the intended host, not inside a guest when assessing physical-host storage. Repeat immediately before a download; the observation can become stale.

Exit 0 means the supplied free-space budget is met and the kernel is not identified as WSL. Exit 2 means insufficient space, WSL detected, or invalid input. Output distinguishes capacity from deployment readiness: a successful check does not attest physical independence, GPU compatibility, virtualization, permission to execute, or readiness of LION. No inference or VM is started.
