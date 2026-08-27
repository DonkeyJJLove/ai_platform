from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

REPOSITORY = "DonkeyJJLove/ai_platform"
CONTROL_ISSUE = 144
RUNNER_NAME = "lion-moon-r9d8-test"
BASE_DIR = "/home/d2j3"
FENCE_BASENAME = ".lion-moon-file-write-fence.sqlite3"
MAX_CONTENT_BYTES = 4096
_OPERATION_MODES = {"CREATE_ONLY", "REPLACE_EXPECTED_DIGEST"}
_PREVIOUS_STATES = {"ABSENT", "PRESENT_EXACT"}
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FILENAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class MoonFileWriteContractError(ValueError):
    pass


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hex64(value: str, name: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise MoonFileWriteContractError(f"{name} invalid")
    return value


def _validate_target(path: str) -> str:
    prefix = BASE_DIR + "/"
    if not isinstance(path, str) or not path.startswith(prefix):
        raise MoonFileWriteContractError("target must be direct child of /home/d2j3")
    name = path[len(prefix):]
    if not name or "/" in name or "\\" in name or name in {".", "..", FENCE_BASENAME} or _FILENAME.fullmatch(name) is None:
        raise MoonFileWriteContractError("target filename invalid")
    return name


@dataclass(frozen=True)
class MoonFileWriteRequest:
    schema_version: str
    request_id: str
    repository: str
    control_issue: int
    actor_login: str
    runner_name: str
    target_path: str
    operation_mode: str
    expected_previous_state: str
    expected_previous_sha256: str | None
    intended_content_sha256: str
    intended_content_size: int
    source_event_digest: str
    request_digest: str = ""

    def payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("request_digest")
        return value

    def validate(self) -> "MoonFileWriteRequest":
        if self.schema_version != "1.0.0":
            raise MoonFileWriteContractError("schema_version invalid")
        if not isinstance(self.request_id, str) or _REQUEST_ID.fullmatch(self.request_id) is None:
            raise MoonFileWriteContractError("request_id invalid")
        if self.repository != REPOSITORY or self.control_issue != CONTROL_ISSUE or self.runner_name != RUNNER_NAME:
            raise MoonFileWriteContractError("fixed execution context mismatch")
        if not isinstance(self.actor_login, str) or not self.actor_login or len(self.actor_login) > 128:
            raise MoonFileWriteContractError("actor_login invalid")
        _validate_target(self.target_path)
        if self.operation_mode not in _OPERATION_MODES or self.expected_previous_state not in _PREVIOUS_STATES:
            raise MoonFileWriteContractError("operation/pre-state invalid")
        if self.operation_mode == "CREATE_ONLY":
            if self.expected_previous_state != "ABSENT" or self.expected_previous_sha256 is not None:
                raise MoonFileWriteContractError("CREATE_ONLY requires ABSENT pre-state")
        else:
            if self.expected_previous_state != "PRESENT_EXACT" or self.expected_previous_sha256 is None:
                raise MoonFileWriteContractError("REPLACE_EXPECTED_DIGEST requires exact pre-state")
            _hex64(self.expected_previous_sha256, "expected_previous_sha256")
        _hex64(self.intended_content_sha256, "intended_content_sha256")
        _hex64(self.source_event_digest, "source_event_digest")
        if not isinstance(self.intended_content_size, int) or isinstance(self.intended_content_size, bool) or not (0 <= self.intended_content_size <= MAX_CONTENT_BYTES):
            raise MoonFileWriteContractError("intended_content_size invalid")
        expected = sha256(b"LION/MOON-FILE-WRITE-REQUEST/1\0" + canonical_json(self.payload())).hexdigest()
        if self.request_digest and self.request_digest != expected:
            raise MoonFileWriteContractError("request digest mismatch")
        return self

    def sealed(self) -> "MoonFileWriteRequest":
        self.validate()
        payload = self.payload()
        digest = sha256(b"LION/MOON-FILE-WRITE-REQUEST/1\0" + canonical_json(payload)).hexdigest()
        return MoonFileWriteRequest(**payload, request_digest=digest).validate()

    def digest(self) -> str:
        sealed = self.sealed() if not self.request_digest else self.validate()
        return sealed.request_digest
