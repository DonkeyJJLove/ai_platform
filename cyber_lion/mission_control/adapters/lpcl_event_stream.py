from __future__ import annotations


class LpclEventStreamAdapter:
    adapter_id = "LPCL_EVENT_STREAM"
    supported_process_classes = ("*",)

    def poll(self):
        self.empty_reason = "EVENT_STREAM_ONLY"
        return []
