"""Fail-closed compatibility tombstone for the historical direct cancel provider.

The sole raw Actions-run cancel POST is owned by actions_run_cancel_runtime where the
canonical mediator also owns authority re-resolution, currentness, durable fencing,
observation and reconciliation. Direct provider construction is intentionally disabled.
"""
from __future__ import annotations

from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelMediationError,
)


class ExactActionsRunCancelEffectProvider:
    """Historical symbol retained only to fail closed before any network effect."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        raise ActionsRunCancelMediationError(
            "direct actions-run-cancel effect provider disabled; "
            "use canonical actions_run_cancel_runtime"
        )

    def cancel_exact(self, *args, **kwargs) -> None:
        del args, kwargs
        raise ActionsRunCancelMediationError(
            "direct actions-run-cancel effect provider disabled; "
            "use canonical actions_run_cancel_runtime"
        )
