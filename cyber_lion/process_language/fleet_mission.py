"""Non-authoritative fleet mission contract for LPCL execution topology."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

SCHEMA_VERSION = "1.0.0"
DIGEST_DOMAIN = b"LION/FLEET-MISSION-IR/1\0"
FLEET_CLASSES = frozenset({"LOGICAL", "LOCAL", "HYBRID"})
EXECUTION_DOMAINS = frozenset({"LOGICAL", "LOCAL"})
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:/-]{0,255}$")


class FleetMissionContractError(ValueError):
    pass


def _identifier(value: str, name: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise FleetMissionContractError(f"{name} has invalid identifier syntax")
    return value


@dataclass(frozen=True)
class FleetRoleSpec:
    role_id: str
    execution_domain: str
    capabilities: tuple[str, ...] = ()
    independent_from: tuple[str, ...] = ()

    def validate(self) -> "FleetRoleSpec":
        _identifier(self.role_id, "role_id")
        if self.execution_domain not in EXECUTION_DOMAINS:
            raise FleetMissionContractError("execution_domain invalid")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise FleetMissionContractError("capabilities must be unique")
        if len(self.independent_from) != len(set(self.independent_from)):
            raise FleetMissionContractError("independent_from must be unique")
        for item in self.capabilities:
            _identifier(item, "capability")
        for item in self.independent_from:
            _identifier(item, "independent_from")
        if self.role_id in self.independent_from:
            raise FleetMissionContractError("role cannot be independent from itself")
        return self


@dataclass(frozen=True)
class FleetMissionIR:
    schema_version: str
    mission_id: str
    fleet_class: str
    roles: tuple[FleetRoleSpec, ...]
    routing: tuple[tuple[str, str], ...]
    authority_effect: str = "NONE"
    runtime_effect: str = "NONE"
    effect_provider_effect: str = "NONE"

    def validate(self) -> "FleetMissionIR":
        if self.schema_version != SCHEMA_VERSION:
            raise FleetMissionContractError("schema_version mismatch")
        _identifier(self.mission_id, "mission_id")
        if self.fleet_class not in FLEET_CLASSES:
            raise FleetMissionContractError("fleet_class invalid")
        if not self.roles:
            raise FleetMissionContractError("at least one role is required")
        role_ids = [role.role_id for role in self.roles]
        if len(role_ids) != len(set(role_ids)):
            raise FleetMissionContractError("role_id values must be unique")
        domains = set()
        for role in self.roles:
            role.validate()
            domains.add(role.execution_domain)
        if self.fleet_class == "LOGICAL" and domains != {"LOGICAL"}:
            raise FleetMissionContractError("LOGICAL fleet may contain only LOGICAL roles")
        if self.fleet_class == "LOCAL" and domains != {"LOCAL"}:
            raise FleetMissionContractError("LOCAL fleet may contain only LOCAL roles")
        if self.fleet_class == "HYBRID" and domains != {"LOGICAL", "LOCAL"}:
            raise FleetMissionContractError("HYBRID fleet requires LOGICAL and LOCAL roles")
        if not self.routing:
            raise FleetMissionContractError("routing must not be empty")
        route_keys = [item[0] for item in self.routing]
        if len(route_keys) != len(set(route_keys)):
            raise FleetMissionContractError("routing keys must be unique")
        role_set = set(role_ids)
        role_domains = {role.role_id: role.execution_domain for role in self.roles}
        routed_domains = set()
        for transition_id, role_id in self.routing:
            _identifier(transition_id, "routing transition_id")
            if role_id not in role_set:
                raise FleetMissionContractError("routing references undeclared role")
            routed_domains.add(role_domains[role_id])
        if self.fleet_class == "HYBRID" and routed_domains != {"LOGICAL", "LOCAL"}:
            raise FleetMissionContractError("HYBRID routing must exercise LOGICAL and LOCAL domains")
        if (self.authority_effect, self.runtime_effect, self.effect_provider_effect) != ("NONE", "NONE", "NONE"):
            raise FleetMissionContractError("fleet mission IR must remain non-authoritative and non-effectful")
        known = role_set
        for role in self.roles:
            if not set(role.independent_from) <= known:
                raise FleetMissionContractError("independent_from references undeclared role")
        return self

    def as_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "fleet_class": self.fleet_class,
            "roles": [asdict(role) for role in self.roles],
            "routing": [{"transition_id": key, "role_id": value} for key, value in self.routing],
            "authority_effect": self.authority_effect,
            "runtime_effect": self.runtime_effect,
            "effect_provider_effect": self.effect_provider_effect,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def digest(self) -> str:
        return sha256(DIGEST_DOMAIN + self.canonical_bytes()).hexdigest()

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "FleetMissionIR":
        if type(value) is not dict:
            raise FleetMissionContractError("FleetMissionIR must be an object")
        expected = {
            "schema_version", "mission_id", "fleet_class", "roles", "routing",
            "authority_effect", "runtime_effect", "effect_provider_effect",
        }
        if set(value) != expected:
            raise FleetMissionContractError("FleetMissionIR keys are not canonical")
        raw_roles = value["roles"]
        if type(raw_roles) is not list:
            raise FleetMissionContractError("roles must be an array")
        roles = []
        for raw in raw_roles:
            if type(raw) is not dict or set(raw) != {"role_id", "execution_domain", "capabilities", "independent_from"}:
                raise FleetMissionContractError("role fields are not canonical")
            capabilities = raw["capabilities"]
            independent = raw["independent_from"]
            if type(capabilities) is not list or type(independent) is not list:
                raise FleetMissionContractError("role list fields invalid")
            roles.append(FleetRoleSpec(
                role_id=raw["role_id"],
                execution_domain=raw["execution_domain"],
                capabilities=tuple(capabilities),
                independent_from=tuple(independent),
            ))
        raw_routing = value["routing"]
        if type(raw_routing) is not list:
            raise FleetMissionContractError("routing must be an array")
        routing = []
        for raw in raw_routing:
            if type(raw) is not dict or set(raw) != {"transition_id", "role_id"}:
                raise FleetMissionContractError("routing item fields are not canonical")
            routing.append((raw["transition_id"], raw["role_id"]))
        return cls(
            schema_version=value["schema_version"],
            mission_id=value["mission_id"],
            fleet_class=value["fleet_class"],
            roles=tuple(roles),
            routing=tuple(routing),
            authority_effect=value["authority_effect"],
            runtime_effect=value["runtime_effect"],
            effect_provider_effect=value["effect_provider_effect"],
        ).validate()
