"""Fail-closed process bootstrap for one cooperative preactivation provider."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import re
import stat
from types import ModuleType
from typing import Mapping

from cyber_lion.enterprise.cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProvider,
)
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteEvidenceRuntimeAdmissionSource,
)

from cyber_lion.mission_control.cooperative_preactivation import (
    CooperativePreactivationProvider,
    CooperativePreactivationRegistry,
)

BOOTSTRAP_VERSION="1.0.0"
UNBOUND_MODE="UNBOUND"
TRUSTED_EXTERNAL_MODE="TRUSTED_EXTERNAL_R1"
SOURCE_BOUND_MODE="SOURCE_BOUND_PRODUCTION_R11"
_FACTORY=re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_SHA=re.compile(r"^[0-9a-f]{64}$")


class CooperativePreactivationBootstrapError(RuntimeError):
    pass


def _require(condition:bool,reason:str)->None:
    if not condition:
        raise CooperativePreactivationBootstrapError(reason)


def _required(env:Mapping[str,str],name:str,*,limit:int=4096)->str:
    value=env.get(name)
    _require(isinstance(value,str) and bool(value.strip()) and len(value)<=limit and "\x00" not in value,
             "cooperative preactivation bootstrap configuration:"+name)
    return value


def _direct_dir(value:str|Path,label:str)->Path:
    path=Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(),label)
    resolved=path.resolve(strict=True)
    _require(path==resolved,label+" symlink indirection")
    _require(stat.S_ISDIR(resolved.stat().st_mode),label+" directory type")
    return resolved


def _direct_file(value:str|Path,label:str)->Path:
    path=Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(),label)
    resolved=path.resolve(strict=True)
    st=resolved.stat()
    _require(path==resolved and stat.S_ISREG(st.st_mode) and st.st_nlink==1,label)
    return resolved


def _load_module(path:Path,expected:str)->ModuleType:
    _require(_SHA.fullmatch(expected) is not None,"preactivation dependency module digest")
    actual=sha256(path.read_bytes()).hexdigest()
    _require(actual==expected,"preactivation dependency module digest mismatch")
    name="_lion_cooperative_preactivation_"+actual[:20]
    try:
        spec=importlib.util.spec_from_file_location(name,path)
        _require(spec is not None and spec.loader is not None,"preactivation dependency module unavailable")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except CooperativePreactivationBootstrapError:
        raise
    except Exception as exc:
        raise CooperativePreactivationBootstrapError("preactivation dependency module failed closed") from exc


@dataclass(frozen=True)
class CooperativeSourceBoundPreactivation:
    """R11 composition of canonical R6.21, R6.16 and one R6.17 worker root.

    No source is generated here. A separately SHA-pinned external factory must
    supply existing current, independently governed components. This object
    neither admits authority nor executes, launches or claims assignments.
    """
    preparation: CooperativeRuntimePreparationProvider
    control_materializer: CooperativeControlPlaneMaterializer
    worker_root: CooperativeRuntimeCompositionRoot
    worker_id: str
    authority_effect: str="NONE"

    def validate(self)->"CooperativeSourceBoundPreactivation":
        _require(type(self) is CooperativeSourceBoundPreactivation,
                 "exact R11 production composition required")
        _require(type(self.preparation) is CooperativeRuntimePreparationProvider,
                 "exact R6.21 durable preparation required")
        _require(type(self.control_materializer) is CooperativeControlPlaneMaterializer,
                 "exact R6.16 materializer required")
        _require(type(self.worker_root) is CooperativeRuntimeCompositionRoot,
                 "exact R6.17 worker qualification root required")
        _require(re.fullmatch(r"MD[0-9]{3}",self.worker_id or "") is not None,
                 "production worker identity")
        _require(self.authority_effect=="NONE","production binding authority")

        prep=self.preparation
        mat=self.control_materializer
        root=self.worker_root
        exp=mat.exporter

        # All three owners must read the very same canonical mission SQLite.
        _require(
            _direct_file(prep.mission_db,"preparation mission DB").samefile(
                _direct_file(mat.mission_db,"materializer mission DB"))
            and _direct_file(prep.mission_db,"preparation mission DB").samefile(
                _direct_file(root.mission_db,"worker qualification mission DB")),
            "production Mission Control DB mismatch",
        )
        # R6.16's context and admission must come from R6.21, not from a
        # fixture, a caller-supplied receipt, or a parallel mutable provider.
        _require(exp.context_source is prep,"production preparation context substitution")
        _require(exp.admission_source is prep.admission_source,
                 "production durable admission source substitution")
        _require(exp.admission_trust.binding()==prep.admission_trust().binding(),
                 "production admission trust substitution")
        _require(type(root.upstream_admission_source) is SQLiteEvidenceRuntimeAdmissionSource,
                 "production external admission evidence reader required")
        _require(
            _direct_file(root.upstream_admission_source.path,"worker admission evidence DB").samefile(
                _direct_file(exp.publisher.path,"control-plane evidence publisher DB")
            ),
            "production worker evidence DB mismatch",
        )
        _require(root.upstream_admission_trust.binding()==exp.admission_trust.binding(),
                 "production worker admission trust mismatch")
        _require(
            _direct_dir(root.artifact_root,"worker artifact root")
            ==_direct_dir(prep.artifact_root,"preparation artifact root"),
            "production artifact root mismatch",
        )
        _require(_direct_dir(root.context_parent,"worker context parent")
                 !=_direct_dir(mat.context_root,"control-plane carrier root"),
                 "worker private context must not alias control-plane carrier")
        return self

    def provider(self)->CooperativePreactivationProvider:
        self.validate()

        def qualify_exact(assignment_id:str,worker_id:str):
            # Re-evaluate source identities before the R6.17 qualification
            # call. R6.17 independently rereads admission/policy/currentness.
            self.validate()
            _require(worker_id==self.worker_id,"production worker substitution")
            return self.worker_root.qualify_released_write_assignment(
                assignment_id,material_worker_id=worker_id
            )

        return CooperativePreactivationProvider(
            write_materializer=self.control_materializer,
            qualifier=qualify_exact,
            worker_id=self.worker_id,
        ).validate()


def bootstrap_preactivation_provider(
    environment:Mapping[str,str]|None=None,*,
    registry:CooperativePreactivationRegistry,
)->dict[str,object]:
    env=os.environ if environment is None else environment
    _require(type(registry) is CooperativePreactivationRegistry,"exact preactivation registry required")
    mode=env.get("LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_MODE",UNBOUND_MODE)
    if mode==UNBOUND_MODE:
        _require(registry.current() is None,"UNBOUND preactivation cannot coexist with provider")
        return {
            "schema":"lion.cooperative-preactivation-bootstrap/v1",
            "state":"UNBOUND",
            "mode":UNBOUND_MODE,
            "bootstrap_version":BOOTSTRAP_VERSION,
            "authority_effect":"NONE",
            "execution_effect":"NONE",
        }

    _require(mode in {TRUSTED_EXTERNAL_MODE,SOURCE_BOUND_MODE},
             "unsupported preactivation bootstrap mode")
    _require(
        _required(env,"LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_VERSION",limit=64)==BOOTSTRAP_VERSION,
        "preactivation bootstrap version mismatch",
    )
    _require(registry.current() is None,"preactivation provider already installed")
    repo=_direct_dir(
        _required(env,"LION_COOPERATIVE_PREACTIVATION_REPOSITORY_ROOT"),
        "preactivation repository root",
    )
    module_path=_direct_file(
        _required(env,"LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_PATH"),
        "preactivation dependency module",
    )
    _require(repo not in module_path.parents and module_path!=repo,
             "preactivation dependency module must be outside repository")
    expected=_required(env,"LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_SHA256",limit=64)
    factory_name=_required(env,"LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_FACTORY",limit=128)
    _require(_FACTORY.fullmatch(factory_name) is not None,"preactivation factory name")
    module=_load_module(module_path,expected)
    factory=getattr(module,factory_name,None)
    _require(callable(factory),"preactivation dependency factory unavailable")
    try:
        value=factory()
    except Exception as exc:
        raise CooperativePreactivationBootstrapError("preactivation dependency factory failed closed") from exc
    if mode==SOURCE_BOUND_MODE:
        _require(type(value) is CooperativeSourceBoundPreactivation,
                 "source-bound production composition required")
        provider=value.validate().provider()
    else:
        _require(type(value) is CooperativePreactivationProvider,
                 "preactivation dependency factory returned wrong type")
        provider=value.validate()
    registry.install(provider)
    _require(registry.current() is provider,"preactivation provider install readback")
    return {
        "schema":"lion.cooperative-preactivation-bootstrap/v1",
        "state":"READY",
        "mode":mode,
        "bootstrap_version":BOOTSTRAP_VERSION,
        "provider_id":provider.provider_id,
        "worker_id":provider.worker_id,
        "dependency_module_sha256":expected,
        "authority_effect":"NONE",
        "execution_effect":"NONE",
    }
