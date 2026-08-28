from __future__ import annotations

import inspect
import os
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.contracts.issue_comment_write import (
    CanonicalIssueCommentWriteAdmission,
    IssueCommentWriteContractError,
    IssueCommentWriteRequest,
    body_digest,
)
from cyber_lion.enterprise.issue_comment_write_github_effect import (
    ExactIssueCommentWriteEffectProvider,
)
from cyber_lion.enterprise.issue_comment_write_mediation import (
    CanonicalIssueCommentWriteMediator,
    DurableIssueCommentWriteFence,
    IssueCommentWriteMediationError,
)
import cyber_lion.enterprise.issue_comment_write_github_effect as provider_module
import cyber_lion.enterprise.issue_comment_write_runtime as runtime_module

REPO = "DonkeyJJLove/ai_platform"
HEAD = "a" * 40


def req(**overrides):
    values = dict(
        repository=REPO,
        issue_number=144,
        action="CREATE_COMMENT",
        semantic_capability="actions.control-ledger.create",
        body="LION-DISPATCH-CLAIM v1\nrequest_id=x",
        request_id="req:1",
        replay_key="1" * 64,
        expected_repository_head=HEAD,
        authority_context="test",
    )
    values.update(overrides)
    return IssueCommentWriteRequest(**values).sealed()


def adm(request):
    return CanonicalIssueCommentWriteAdmission(
        request.request_digest,
        request.repository,
        request.issue_number,
        request.action,
        request.semantic_capability,
        body_digest(request.body),
        request.expected_repository_head,
        "2" * 64,
        "3" * 64,
        1,
        7,
        "test-provider",
        test_only=request.test_only,
    ).sealed()


class Resolver:
    def __init__(self):
        self.calls = 0

    def resolve(self, request):
        self.calls += 1
        return adm(request)


class Repo:
    def __init__(self):
        self.head = HEAD
        self.comments = {}
        self.old = None

    def ref_head(self, ref):
        if ref != "master":
            raise AssertionError(ref)
        return self.head

    def get_comment(self, comment_id):
        return self.comments.get(comment_id, {"id": comment_id, "body": self.old})


class Effect:
    def __init__(self, repo):
        self.repo = repo
        self.calls = 0

    def write_exact(self, request, admission):
        admission.binds(request)
        self.calls += 1
        comment_id = request.expected_existing_comment_id or 777
        self.repo.comments[comment_id] = {"id": comment_id, "body": request.body}
        return comment_id


class IssueCommentWriteMediationTests(unittest.TestCase):
    def test_contract_denies_wrong_scope_and_action_capability_mismatch(self):
        with self.assertRaises(IssueCommentWriteContractError):
            req(repository="other/repo")
        with self.assertRaises(IssueCommentWriteContractError):
            req(issue_number=145)
        with self.assertRaises(IssueCommentWriteContractError):
            req(
                action="UPDATE_OWN_CREATED_COMMENT",
                semantic_capability="actions.control-ledger.create",
                expected_existing_comment_id=1,
                expected_existing_body_digest="4" * 64,
            )

    def test_test_canary_scope_is_exact_and_structurally_test_only(self):
        request = req(
            issue_number=226,
            semantic_capability="test.issue-comment-canary.create",
            test_only=True,
            request_id="req:canary",
        )
        self.assertEqual(request.issue_number, 226)
        self.assertTrue(request.test_only)
        adm(request).binds(request)
        for bad in (
            dict(
                issue_number=144,
                semantic_capability="test.issue-comment-canary.create",
                test_only=True,
            ),
            dict(
                issue_number=198,
                semantic_capability="test.issue-comment-canary.create",
                test_only=True,
            ),
            dict(
                issue_number=226,
                semantic_capability="test.issue-comment-canary.create",
                test_only=False,
            ),
            dict(
                issue_number=226,
                semantic_capability="actions.control-ledger.create",
                test_only=True,
            ),
        ):
            with self.subTest(bad=bad), self.assertRaises(IssueCommentWriteContractError):
                req(**bad)

    def test_admission_cannot_relabel_test_scope(self):
        request = req(
            issue_number=226,
            semantic_capability="test.issue-comment-canary.create",
            test_only=True,
            request_id="req:canary2",
        )
        admission = CanonicalIssueCommentWriteAdmission(
            request.request_digest,
            request.repository,
            request.issue_number,
            request.action,
            request.semantic_capability,
            body_digest(request.body),
            request.expected_repository_head,
            "2" * 64,
            "3" * 64,
            1,
            7,
            "test-provider",
            test_only=False,
        )
        with self.assertRaises(IssueCommentWriteContractError):
            admission.sealed()

    def test_complete_create_reconciles_exactly_once(self):
        with tempfile.TemporaryDirectory() as td:
            request = req()
            repo = Repo()
            resolver = Resolver()
            effect = Effect(repo)
            fence = DurableIssueCommentWriteFence(td + "/f.sqlite")
            mediator = CanonicalIssueCommentWriteMediator(
                admissions=resolver,
                repository=repo,
                effect=effect,
                fence=fence,
            )
            out = mediator.execute(request)
            self.assertEqual(out["fence_state"], "RECONCILED")
            self.assertEqual(effect.calls, 1)
            self.assertEqual(resolver.calls, 2)
            self.assertEqual(fence.get(out["effect_key"]).state, "RECONCILED")
            with self.assertRaises(IssueCommentWriteMediationError):
                mediator.execute(request)
            self.assertEqual(effect.calls, 1)

    def test_currentness_drift_denied_before_attempt(self):
        with tempfile.TemporaryDirectory() as td:
            request = req()
            repo = Repo()
            repo.head = "c" * 40
            effect = Effect(repo)
            fence = DurableIssueCommentWriteFence(td + "/f.sqlite")
            with self.assertRaisesRegex(IssueCommentWriteMediationError, "head drift"):
                CanonicalIssueCommentWriteMediator(
                    admissions=Resolver(),
                    repository=repo,
                    effect=effect,
                    fence=fence,
                ).execute(request)
            self.assertEqual(effect.calls, 0)

    def test_update_binds_exact_previous_comment_body(self):
        with tempfile.TemporaryDirectory() as td:
            old = "old"
            request = req(
                action="UPDATE_OWN_CREATED_COMMENT",
                semantic_capability="actions.control-ledger.update",
                expected_existing_comment_id=5,
                expected_existing_body_digest=body_digest(old),
                body="new",
                request_id="req:u",
            )
            repo = Repo()
            repo.old = old
            repo.comments[5] = {"id": 5, "body": old}
            effect = Effect(repo)
            fence = DurableIssueCommentWriteFence(td + "/f.sqlite")
            out = CanonicalIssueCommentWriteMediator(
                admissions=Resolver(),
                repository=repo,
                effect=effect,
                fence=fence,
            ).execute(request)
            self.assertEqual(out["comment_id"], 5)

    def test_historical_direct_provider_is_fail_closed_tombstone(self):
        with self.assertRaisesRegex(
            IssueCommentWriteMediationError, "direct issue-comment effect provider disabled"
        ):
            ExactIssueCommentWriteEffectProvider(
                repository=REPO,
                token="t",
                fence=object(),
            )
        source = inspect.getsource(provider_module)
        self.assertNotIn('method="POST"', source)
        self.assertNotIn('method="PATCH"', source)
        self.assertNotIn("urllib.request.Request", source)

    def test_canonical_runtime_is_only_raw_issue_comment_write_owner(self):
        source = inspect.getsource(runtime_module)
        self.assertIn('method="POST"', source)
        self.assertIn('method="PATCH"', source)
        self.assertIn("issue-comment authority drift at effect boundary", source)
        self.assertIn("issue-comment repository head drift at effect boundary", source)
        self.assertIn("exact durable ATTEMPTED fence", source)
        self.assertIn("_github_token_from_environment", source)

    def test_environment_facade_does_not_accept_repository_substitution(self):
        with self.assertRaisesRegex(
            IssueCommentWriteMediationError, "repository substitution denied"
        ):
            runtime_module.EnvironmentIssueCommentMediator("other/repo", "ignored")

    def test_runtime_without_external_dependencies_fails_closed_before_effect(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                IssueCommentWriteMediationError, "trusted issue-comment runtime unavailable"
            ):
                runtime_module.execute_issue_comment_write(req())


if __name__ == "__main__":
    unittest.main()
