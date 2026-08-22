"""Bounded runtime entrypoint for F005-K live repository observation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

from cyber_lion.contracts.branch_ownership_registry import (
    BranchOwnershipProviderConfig,
    RUNTIME_SOURCE_INSTANCE_ID,
)
from cyber_lion.contracts.fleet_repository_observation_source import (
    ObservationConfig,
    REPOSITORY,
)
from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths
from cyber_lion.enterprise.branch_ownership_registry import (
    FileBranchOwnershipRegistryProvider,
)
from cyber_lion.enterprise.fleet_repository_observation_source import (
    materialize_observation,
)
from cyber_lion.enterprise.github_repository_read_source import (
    GitHubRESTReadSource,
)


class RepositoryObservationRuntimeError(RuntimeError):
    pass


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def run_runtime_observation(
    *,
    expected_master: str,
    expected_master_tree: str,
    inventory_revision: int,
) -> dict[str, object]:
    paths = resolve_fleet_runtime_paths()
    output = Path(paths.repository_inventory_path)
    if output.exists():
        raise RepositoryObservationRuntimeError("repository inventory output already exists")

    provider = FileBranchOwnershipRegistryProvider(
        BranchOwnershipProviderConfig(
            repository=REPOSITORY,
            source_instance_id=RUNTIME_SOURCE_INSTANCE_ID,
            registry_path=paths.branch_ownership_registry_path,
            minimum_registry_revision=1,
        )
    )
    github = GitHubRESTReadSource.from_environment()
    config = ObservationConfig(
        repository=REPOSITORY,
        expected_master=expected_master,
        expected_master_tree=expected_master_tree,
        inventory_revision=inventory_revision,
        output_path=paths.repository_inventory_path,
    ).validate()

    receipt = materialize_observation(
        config,
        github=github,
        ownership=provider,
        clock=_clock,
    )
    return asdict(receipt)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="F005-K live repository observation runtime")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--inventory-revision", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.repository != REPOSITORY:
        raise RepositoryObservationRuntimeError("repository substitution denied")
    receipt = run_runtime_observation(
        expected_master=args.expected_master,
        expected_master_tree=args.expected_master_tree,
        inventory_revision=args.inventory_revision,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
