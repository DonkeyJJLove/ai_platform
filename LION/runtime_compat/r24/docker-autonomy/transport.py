from __future__ import annotations

import http.client
import io
import json
import socket
import urllib.error
import urllib.parse
from typing import Callable


class PersistentJsonTransport:
    """Small HTTP/1.1 client with per-endpoint connection reuse.

    The worker remains single-threaded. Connections are bounded to endpoints
    explicitly supplied by the worker configuration and are dropped on any
    transport exception or server-requested close.
    """

    def __init__(self, *, user_agent: str, resolver: Callable[[str], str] | None = None):
        self.user_agent = str(user_agent)
        self.resolver = resolver or socket.gethostbyname
        self._connections: dict[tuple[str, str, int], http.client.HTTPConnection] = {}
        self.connection_creations = 0
        self.reconnects = 0

    def _target(self, url: str) -> tuple[urllib.parse.SplitResult, tuple[str, str, int]]:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "http" or not parsed.hostname:
            raise ValueError("persistent worker transport requires http endpoint")
        port = parsed.port or 80
        host = self.resolver(parsed.hostname)
        return parsed, (parsed.scheme, host, port)

    def _drop(self, key: tuple[str, str, int]) -> None:
        conn = self._connections.pop(key, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _connection(self, key: tuple[str, str, int], timeout: float) -> http.client.HTTPConnection:
        conn = self._connections.get(key)
        if conn is None:
            _, host, port = key
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            self._connections[key] = conn
            self.connection_creations += 1
        else:
            conn.timeout = timeout
            if conn.sock is not None:
                conn.sock.settimeout(timeout)
        return conn

    def request_json(self, url: str, body=None, *, timeout: float = 10.0):
        parsed, key = self._target(url)
        data = None if body is None else json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        headers = {
            "User-Agent": self.user_agent,
            "Host": parsed.netloc,
            "Accept": "application/json",
            "Connection": "keep-alive",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))

        last_exc = None
        for attempt in range(2):
            conn = self._connection(key, timeout)
            try:
                conn.request("POST" if data is not None else "GET", path, body=data, headers=headers)
                response = conn.getresponse()
                raw = response.read()
                if response.will_close or response.getheader("Connection", "").lower() == "close":
                    self._drop(key)
                if not 200 <= response.status < 300:
                    raise urllib.error.HTTPError(
                        url,
                        response.status,
                        response.reason,
                        response.headers,
                        io.BytesIO(raw),
                    )
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError:
                raise
            except (http.client.HTTPException, OSError, TimeoutError, ConnectionError) as exc:
                last_exc = exc
                self._drop(key)
                if attempt == 0:
                    self.reconnects += 1
                    continue
                raise
        raise last_exc or RuntimeError("persistent transport failed")

    def close(self) -> None:
        for key in tuple(self._connections):
            self._drop(key)

    @property
    def open_connections(self) -> int:
        return len(self._connections)
