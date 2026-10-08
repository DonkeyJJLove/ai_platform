"""Fail-closed process bootstrap for one cooperative preactivation provider."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import re
import stat
from types import ModuleType
from typing import Mapping

from cyber_lion.mission_control.cooperative_preactivation import (
    CooperativePreactivationProvider,
    CooperativePreactivationRegistry,
)

BOOTSTRAP_VERSION="1.0.0"
UNBOUND_MODE="UNBOUND"
TRUSTED_EXTERNAL_MODE="TRUSTED_EXTERNAL_R1"
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

    _require(mode==TRUSTED_EXTERNAL_MODE,"unsupported preactivation bootstrap mode")
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
    _require(type(value) is CooperativePreactivationProvider,
             "preactivation dependency factory returned wrong type")
    provider=value.validate()
    registry.install(provider)
    _require(registry.current() is provider,"preactivation provider install readback")
    return {
        "schema":"lion.cooperative-preactivation-bootstrap/v1",
        "state":"READY",
        "mode":TRUSTED_EXTERNAL_MODE,
        "bootstrap_version":BOOTSTRAP_VERSION,
        "provider_id":provider.provider_id,
        "worker_id":provider.worker_id,
        "dependency_module_sha256":expected,
        "authority_effect":"NONE",
        "execution_effect":"NONE",
    }
