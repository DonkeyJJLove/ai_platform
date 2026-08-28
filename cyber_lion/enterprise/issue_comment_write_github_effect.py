"""Fail-closed compatibility tombstone for the historical direct issue-comment provider.

The sole raw issue-comment POST/PATCH is owned by issue_comment_write_runtime where the
canonical mediator also owns authority re-resolution, exact target currentness, durable
ATTEMPTED-before-effect fencing, independent observation, and reconciliation. Direct
provider construction is intentionally disabled.
"""
from __future__ import annotations

from cyber_lion.enterprise.issue_comment_write_mediation import (
    IssueCommentWriteMediationError,
)


class ExactIssueCommentWriteEffectProvider:
    """Historical symbol retained only to fail closed before any network effect."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        raise IssueCommentWriteMediationError(
            "direct issue-comment effect provider disabled; "
            "use canonical issue_comment_write_runtime"
        )

    def write_exact(self, *args, **kwargs) -> int:
        del args, kwargs
        raise IssueCommentWriteMediationError(
            "direct issue-comment effect provider disabled; "
            "use canonical issue_comment_write_runtime"
        )
