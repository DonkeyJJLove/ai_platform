#!/usr/bin/env python3
"""One-worker R6.17 qualification; no runtime activation and no assignment claim."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cyber_lion.mission_control.cooperative_worker_bootstrap import (
    qualify_released_assignment_from_environment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignment-id", required=True)
    parser.add_argument("--worker-id", required=True)
    args = parser.parse_args()
    result = qualify_released_assignment_from_environment(
        os.environ,
        assignment_id=args.assignment_id,
        material_worker_id=args.worker_id,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
