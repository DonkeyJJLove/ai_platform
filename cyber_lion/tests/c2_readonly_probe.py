from __future__ import annotations

import errno
import os
from pathlib import Path
import socket


def _expect_denied(label, fn):
    try:
        fn()
    except OSError as exc:
        if exc.errno not in {errno.EPERM, errno.EACCES, errno.EROFS}:
            raise AssertionError(f"{label} unexpected errno {exc.errno}") from exc
        print(f"{label}=DENIED:{exc.errno}")
        return
    raise AssertionError(f"{label} unexpectedly allowed")


def main() -> int:
    print("READ_OS_RELEASE=" + str(Path("/etc/os-release").is_file()).upper())
    print("UNAME_SYSNAME=" + os.uname().sysname)
    _expect_denied("WORKSPACE_WRITE", lambda: Path("/workspace/c2-forbidden-write").write_text("x"))
    _expect_denied("NETWORK_SOCKET", lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    _expect_denied("PROCESS_FORK", os.fork)
    tmp = Path("/tmp/c2-allowed-temp")
    tmp.write_text("ephemeral")
    print("ISOLATED_TMP_WRITE=PASS")
    tmp.unlink()
    print("C2_PROBE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
