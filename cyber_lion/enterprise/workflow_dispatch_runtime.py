"""Pinned external trust composition loader for canonical workflow dispatch.

The repository cannot manufacture workflow-dispatch authority. The external module is
pinned by absolute path + SHA-256 and must live outside GITHUB_WORKSPACE. Its factory
must return an admission resolver whose resolve() emits CanonicalWorkflowDispatchAdmission
values backed by the externally trusted LiveAuthorityAdmission/PDP composition.
"""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import os
from pathlib import Path

from cyber_lion.enterprise.workflow_dispatch_mediation import WorkflowDispatchMediationError

_FACTORY = "build_workflow_dispatch_admission_resolver"


def load_pinned_workflow_dispatch_admission_resolver():
    path_raw = os.environ.get("LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH", "")
    digest = os.environ.get("LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST", "")
    if not path_raw or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise WorkflowDispatchMediationError("trusted workflow dispatch runtime unavailable")
    path = Path(path_raw)
    if not path.is_absolute():
        raise WorkflowDispatchMediationError("trusted workflow dispatch runtime path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WorkflowDispatchMediationError("trusted workflow dispatch runtime unavailable") from exc
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise WorkflowDispatchMediationError("trusted workflow dispatch runtime must remain outside repository")
    if not resolved.is_file() or resolved.suffix != ".py":
        raise WorkflowDispatchMediationError("trusted workflow dispatch runtime invalid")
    if sha256(resolved.read_bytes()).hexdigest() != digest:
        raise WorkflowDispatchMediationError("trusted workflow dispatch runtime digest mismatch")
    spec = importlib.util.spec_from_file_location("_lion_workflow_dispatch_runtime_" + digest[:20], resolved)
    if spec is None or spec.loader is None:
        raise WorkflowDispatchMediationError("trusted workflow dispatch runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, _FACTORY, None)
    if not callable(factory):
        raise WorkflowDispatchMediationError("trusted workflow dispatch admission factory unavailable")
    resolver = factory()
    if not callable(getattr(resolver, "resolve", None)):
        raise WorkflowDispatchMediationError("trusted workflow dispatch admission resolver unavailable")
    return resolver


def fence_database_path_from_environment() -> str:
    raw = os.environ.get("LION_WORKFLOW_DISPATCH_FENCE_DATABASE_PATH", "")
    path = Path(raw)
    if not raw or not path.is_absolute():
        raise WorkflowDispatchMediationError("trusted workflow dispatch fence database unavailable")
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        resolved = path.resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise WorkflowDispatchMediationError("workflow dispatch fence must remain outside repository")
    return str(path)
