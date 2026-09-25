"""Matched HMK-9D ablation contract; no training, reward or authority semantics."""
from dataclasses import dataclass
import re
HEX=re.compile(r"^[0-9a-f]{64}$")
class HMK9DAblationError(ValueError):pass
@dataclass(frozen=True)
class HMK9DMatchedAblation:
    corpus_digest:str;model_release_ref:str;prompt_profile_digest:str;tool_schema_digest:str;runtime_digest:str;hkm9d_annotation_source_ref:str;variant_a_annotation:bool;variant_b_annotation:bool;authority_effect:str="NONE";training_effect:str="NONE"
    def validate(self):
        for n in ("corpus_digest","prompt_profile_digest","tool_schema_digest","runtime_digest"):
            if not isinstance(getattr(self,n),str) or not HEX.fullmatch(getattr(self,n)):raise HMK9DAblationError(n)
        if not self.model_release_ref or not self.hkm9d_annotation_source_ref:raise HMK9DAblationError("identity")
        if self.variant_a_annotation is not False or self.variant_b_annotation is not True:raise HMK9DAblationError("matched variants")
        if self.authority_effect!="NONE" or self.training_effect!="NONE":raise HMK9DAblationError("effects forbidden")
        return self
# chunk-chunk may provide trajectory annotation / transition semantics / diagnostics only.
# HMK-9D annotation is not authority, ground truth, declared reward, or hardware-energy measurement.
