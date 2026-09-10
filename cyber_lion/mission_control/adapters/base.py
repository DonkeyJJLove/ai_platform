from __future__ import annotations

from typing import Any, Protocol


class ObservationAdapter(Protocol):
    adapter_id: str
    supported_process_classes: tuple[str, ...]

    def poll(self) -> list[dict[str, Any]]:
        ...
