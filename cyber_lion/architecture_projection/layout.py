from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DISPLAY_PLANES: Final = (
    "WORLD_AND_GOALS",
    "EVIDENCE_AND_REASONING",
    "EVOLUTION",
    "ORGANIZATION_AND_FLEET",
    "AUTHORITY_AND_GOVERNANCE",
    "BUILD_AND_IMPLEMENTATION",
    "TRUSTED_RUNTIME",
    "EFFECT",
    "OBSERVATION_AND_RECONCILIATION",
)

PLANE_LAYER_BINDINGS: Final = {
    "WORLD_AND_GOALS": ("SYSTEM_CONTEXT", "TARGET_BEAN_FACTORY"),
    "EVIDENCE_AND_REASONING": ("EVIDENCE_AND_EPISTEMIC_PLANE", "CODE_PERCEPTION"),
    "EVOLUTION": ("EVOLUTIONARY_EPOCH", "STARTUP_EVOLUTION"),
    "ORGANIZATION_AND_FLEET": ("FLEET_AND_SWARM",),
    "AUTHORITY_AND_GOVERNANCE": ("CONSTITUTION_AND_GOVERNANCE", "AUTHORITY_AND_EFFECT"),
    "BUILD_AND_IMPLEMENTATION": ("GOVERNED_SELF_IMPLEMENTATION", "REPOSITORY_MUTATION", "ARCHITECTURE_PROJECTION"),
    "TRUSTED_RUNTIME": ("TRUSTED_RUNTIME", "QUARANTINED_AND_NONCANONICAL"),
    "EFFECT": ("AUTHORITY_AND_EFFECT", "REPOSITORY_MUTATION"),
    "OBSERVATION_AND_RECONCILIATION": ("OBSERVABILITY_AND_RECONCILIATION",),
}


@dataclass(frozen=True, order=True)
class LayoutHint:
    plane: str
    rank: int
    layers: tuple[str, ...]

    def validate(self) -> "LayoutHint":
        if self.plane not in DISPLAY_PLANES:
            raise ValueError("unknown display plane")
        if self.rank < 0:
            raise ValueError("layout rank must be non-negative")
        if self.layers != PLANE_LAYER_BINDINGS[self.plane]:
            raise ValueError("layout plane/layer binding mismatch")
        return self


def canonical_layout() -> tuple[LayoutHint, ...]:
    return tuple(
        LayoutHint(plane, index, PLANE_LAYER_BINDINGS[plane]).validate()
        for index, plane in enumerate(DISPLAY_PLANES)
    )
