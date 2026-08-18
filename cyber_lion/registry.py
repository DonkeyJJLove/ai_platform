"""Cyber-Lion capability registry. Registration enables discovery, never authority."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

class CapabilityValidationError(ValueError): pass
_CONSEQUENTIAL={"write","execute","authority","external","memory"}

@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id:str; provider_entity:str; version:str
    inputs:Tuple[str,...]=(); outputs:Tuple[str,...]=(); side_effects:Tuple[str,...] = ("none",)
    required_authority:str="none"; required_gates:Tuple[str,...]=(); observability_events:Tuple[str,...]=(); epistemic_status:str="UNKNOWN"
    def validate(self):
        if not self.capability_id or not self.provider_entity or not self.version: raise CapabilityValidationError("id/provider/version required")
        effects=set(self.side_effects)
        if not effects: raise CapabilityValidationError("side_effects must be explicit")
        if "none" in effects and len(effects)>1: raise CapabilityValidationError("none cannot be combined")
        if effects & _CONSEQUENTIAL:
            if self.required_authority in {"","none"}: raise CapabilityValidationError("consequential capability requires authority")
            if not self.required_gates: raise CapabilityValidationError("consequential capability requires gate")
        return self

@dataclass
class CapabilityRegistry:
    _items:Dict[str,CapabilityDescriptor]=field(default_factory=dict)
    def register(self,descriptor:CapabilityDescriptor)->None:
        descriptor.validate(); current=self._items.get(descriptor.capability_id)
        if current is not None and current!=descriptor: raise CapabilityValidationError(f"capability changed under same id: {descriptor.capability_id}")
        self._items[descriptor.capability_id]=descriptor
    def get(self,capability_id:str)->CapabilityDescriptor:
        if capability_id not in self._items: raise KeyError(f"unknown capability: {capability_id}")
        return self._items[capability_id]
    def discover(self,provider_entity:str|None=None)->List[CapabilityDescriptor]:
        items:Iterable[CapabilityDescriptor]=self._items.values()
        if provider_entity is not None: items=(x for x in items if x.provider_entity==provider_entity)
        return sorted(items,key=lambda x:x.capability_id)
