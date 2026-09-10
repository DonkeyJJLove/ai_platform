from __future__ import annotations

from typing import Any


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, adapter: Any) -> None:
        adapter_id = str(getattr(adapter, "adapter_id", ""))
        if not adapter_id:
            raise ValueError("adapter_id required")
        if adapter_id in self._adapters:
            raise ValueError("duplicate adapter")
        self._adapters[adapter_id] = adapter

    def all(self) -> list[Any]:
        return [self._adapters[k] for k in sorted(self._adapters)]

    def describe(self) -> list[dict[str, Any]]:
        result = []
        for adapter in self.all():
            result.append({
                "adapter_id": adapter.adapter_id,
                "supported_process_classes": list(getattr(adapter, "supported_process_classes", ())),
                "control_authority": "NONE",
            })
        return result
