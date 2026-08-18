"""Minimal Cyber-Lion capability registry.

The registry stores declarations. It does not grant authority. A provider being
registered means it can be discovered; consequential execution still requires
an applied gate and deterministic execution contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple


class CapabilityValidationError(ValueError):
    pass


_CONSEQUENTIAL = {"write", "execute", "authority", "external", "memory"}


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str
    provider_entity: str
    version: str
    inputs: Tuple[str, ...] = ()
    outputs: Tuple[str, ...] = ()
    side_effects: Tuple[str, ...] = ("none",)
    required_authority: str = "none"
    required_gates: Tuple[str, ...] = ()
    observability_events: Tuple[str, ...] = ()
    epistemic_status: str = "UNKNOWN"

    def validate(self) -> "CapabilityDescriptor":
        if not self.capability_id or not self.provider_entity or not self.version:
            raise CapabilityValidationError("capability id/provider/version are required")
        effects = set(self.side_effects)
        if not effects:
            raise CapabilityValidationError("side_effects must be explicit")
        if "none" in effects and len(effects) > 1:
            raise CapabilityValidationError("side_effects 'none' cannot be combined")
        if effects & _CONSEQUENTIAL:
            if self.required_authority in {"", "none"}:
                raise CapabilityValidationError(
                    "consequential capability requires explicit authority"
                )
            if not self.required_gates:
                raise CapabilityValidationError(
                    "consequential capability requires at least one gate"
                )
        return self


@dataclass
class CapabilityRegistry:
    _items: Dict[str, CapabilityDescriptor] = field(default_factory=dict)

    def register(self, descriptor: CapabilityDescriptor) -> None:
        descriptor.validate()
        current = self._items.get(descriptor.capability_id)
        if current is not None and current != descriptor:
            raise CapabilityValidationError(
                f"capability already registered with different descriptor: {descriptor.capability_id}"
            )
        self._items[descriptor.capability_id] = descriptor

    def get(self, capability_id: str) -> CapabilityDescriptor:
        try:
            return self._items[capability_id]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability_id}") from exc

    def discover(self, *, provider_entity: str | None = None) -> List[CapabilityDescriptor]:
        items: Iterable[CapabilityDescriptor] = self._items.values()
        if provider_entity is not None:
            items = (item for item in items if item.provider_entity == provider_entity)
        return sorted(items, key=lambda item: item.capability_id)
