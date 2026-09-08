#!/usr/bin/env python3
from __future__ import annotations
import importlib.util

EXPECTED_HOST = "LION-AUTH-LAB"
SENTINEL_USER = "sentinelx"
RUNNER_USER = "lion-maintenance-runner"
PROVIDER_GROUP = "lion-docker-p0"
TRUST_CLASS = "TEST_ONLY"
REQUIRED_OPERATIONS = ("PING", "PRECHECK_SCALE64", "PREPARE_SCALE64", "RUN_SCALE64", "READ_EVIDENCE")
IMPL = "/usr/local/libexec/lion-effect-admission-broker-impl.py"
RUNNER_EXEC = "/usr/local/libexec/lion-nnp-runner-exec.py"

def main() -> int:
    spec = importlib.util.spec_from_file_location("lion_effect_admission_impl", IMPL)
    if spec is None or spec.loader is None:
        raise SystemExit("broker implementation unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.runner_prefix = lambda: ["/usr/bin/python3", RUNNER_EXEC, "--"]
    return int(module.main())

if __name__ == "__main__":
    raise SystemExit(main())
