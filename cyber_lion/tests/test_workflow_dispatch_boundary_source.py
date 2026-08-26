from __future__ import annotations

from pathlib import Path
import unittest

from cyber_lion.enterprise import workflow_dispatch_mediation as mediation


class WorkflowDispatchBoundarySourceTests(unittest.TestCase):
    def test_mediator_contains_no_github_http_write(self):
        source=Path(mediation.__file__).read_text(encoding="utf-8")
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("api.github.com", source)
        self.assertNotIn("GITHUB_TOKEN", source)

    def test_mediator_has_durable_states(self):
        source=Path(mediation.__file__).read_text(encoding="utf-8")
        for state in ("PREPARED","ATTEMPTED","OBSERVED","RECONCILED","UNKNOWN"):
            self.assertIn(state, source)


if __name__ == "__main__": unittest.main()
