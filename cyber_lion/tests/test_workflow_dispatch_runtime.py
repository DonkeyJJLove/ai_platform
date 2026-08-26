from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest

from cyber_lion.enterprise.workflow_dispatch_mediation import WorkflowDispatchMediationError
from cyber_lion.enterprise.workflow_dispatch_runtime import load_pinned_workflow_dispatch_admission_resolver


class RuntimeLoaderTests(unittest.TestCase):
    def test_repository_local_runtime_is_denied(self):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root=Path(td.name); module=root/"runtime.py"
        module.write_text("def build_workflow_dispatch_admission_resolver():\n    return object()\n", encoding="utf-8")
        saved={k:os.environ.get(k) for k in ("GITHUB_WORKSPACE","LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH","LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST")}
        os.environ["GITHUB_WORKSPACE"]=str(root)
        os.environ["LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH"]=str(module)
        os.environ["LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST"]=sha256(module.read_bytes()).hexdigest()
        try:
            with self.assertRaisesRegex(WorkflowDispatchMediationError, "outside repository"):
                load_pinned_workflow_dispatch_admission_resolver()
        finally:
            for k,v in saved.items():
                if v is None: os.environ.pop(k,None)
                else: os.environ[k]=v

    def test_digest_substitution_is_denied(self):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        module=Path(td.name)/"runtime.py"; module.write_text("x=1\n", encoding="utf-8")
        saved={k:os.environ.get(k) for k in ("GITHUB_WORKSPACE","LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH","LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST")}
        os.environ.pop("GITHUB_WORKSPACE",None)
        os.environ["LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_PATH"]=str(module)
        os.environ["LION_WORKFLOW_DISPATCH_RUNTIME_MODULE_DIGEST"]="0"*64
        try:
            with self.assertRaisesRegex(WorkflowDispatchMediationError, "digest mismatch"):
                load_pinned_workflow_dispatch_admission_resolver()
        finally:
            for k,v in saved.items():
                if v is None: os.environ.pop(k,None)
                else: os.environ[k]=v


if __name__ == "__main__": unittest.main()
