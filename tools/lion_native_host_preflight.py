"""Read-only storage/OS preflight for a caller-selected LION data directory.

No installers, downloads, VM operations, credential reads or inference calls.
Capacity observations do not establish runtime admission or deployment readiness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil

GIB = 1024 ** 3


def assess_capacity(free_bytes: int, required_free_gib: int) -> dict:
    if type(free_bytes) is not int or free_bytes < 0:
        raise ValueError('free_bytes must be a nonnegative integer')
    if type(required_free_gib) is not int or required_free_gib <= 0:
        raise ValueError('required_free_gib must be a positive integer')
    required_bytes = required_free_gib * GIB
    return {
        'free_bytes': free_bytes,
        'required_free_bytes': required_bytes,
        'shortfall_bytes': max(0, required_bytes - free_bytes),
        'status': 'SUFFICIENT' if free_bytes >= required_bytes else 'INSUFFICIENT',
    }


def observe(data_directory: Path, required_free_gib: int) -> dict:
    # Validate the budget before probing the filesystem. Resolve symlinks to the
    # actual volume; no directory is created and no files are traversed.
    assess_capacity(0, required_free_gib)
    directory = data_directory.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('data directory must be an existing directory')
    disk = shutil.disk_usage(directory)
    system, release = platform.system(), platform.release()
    wsl = system == 'Linux' and ('microsoft' in release.lower() or 'wsl' in release.lower())
    return {
        'schema': 'lion.native-host-preflight/v1',
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'STORAGE_AND_OS_ONLY',
        'data_directory': str(directory),
        'system': system,
        'kernel_release': release,
        'wsl_detected': wsl,
        'physical_failure_domain': 'NOT_ATTESTED',
        'capacity': assess_capacity(disk.free, required_free_gib),
        'volume_total_bytes': disk.total,
        'volume_used_bytes': disk.used,
        'authority_effect': 'NONE',
        'deployment_readiness': 'NOT_ASSESSED',
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-directory', type=Path, required=True)
    parser.add_argument('--required-free-gib', type=int, required=True,
                        help='Operator budget including model, VM growth and reserve')
    args = parser.parse_args(argv)
    try:
        result = observe(args.data_directory, args.required_free_gib)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['capacity']['status'] == 'SUFFICIENT' and not result['wsl_detected'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
