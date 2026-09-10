# VKT-R3 runtime image

Runtime workload image is digest-pinned. The current candidate is `python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` (`python:3.12-slim-bookworm` index digest observed during VKT-R3 execution). Runtime acceptance requires empirical non-root Pod execution; the tag name is not evidence. Vendor traffic remains disabled.
