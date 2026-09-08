#!/usr/bin/env python3
from __future__ import annotations
import grp, os, pwd, sys

RUNNER_USER = "lion-maintenance-runner"
PROVIDER_GROUP = "lion-docker-p0"
ALLOWED_ENV = {"PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "LION_PRECHECK_REQUEST"}

def deny(msg: str) -> None:
    raise SystemExit("DENY:" + msg)

def main() -> int:
    if os.geteuid() != 0:
        deny("parent-not-root")
    if len(sys.argv) < 4 or sys.argv[1] != "--":
        deny("argv-shape")
    argv = sys.argv[2:]
    if argv[0] != "/usr/bin/env":
        deny("fixed-env-entry-required")
    i = 1
    while i < len(argv) and "=" in argv[i]:
        key = argv[i].split("=", 1)[0]
        if key not in ALLOWED_ENV:
            deny("env-key:" + key)
        i += 1
    if i >= len(argv) or argv[i] != "/usr/bin/python3":
        deny("python-entry-required")
    runner = pwd.getpwnam(RUNNER_USER)
    provider_gid = grp.getgrnam(PROVIDER_GROUP).gr_gid
    if runner.pw_uid == 0:
        deny("runner-root")
    os.setgroups([provider_gid])
    os.setgid(runner.pw_gid)
    os.setuid(runner.pw_uid)
    env = {"PATH":"/usr/bin:/bin","HOME":"/tmp","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    os.execve("/usr/bin/env", argv, env)
    return 127

if __name__ == "__main__":
    raise SystemExit(main())
