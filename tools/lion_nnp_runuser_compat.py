#!/usr/bin/env python3
from __future__ import annotations
import grp, os, pwd, sys

RUNTIME_USER = "lion-container-runtime-lab"
RUNNER_USER = "lion-maintenance-runner"
PROVIDER_GROUP = "lion-docker-p0"
PROVIDER_SOCKET = "/run/lion-docker-p0/provider.sock"

def deny(msg: str) -> None:
    raise SystemExit("DENY:" + msg)

def drop(user: str, supplementary: list[int]) -> None:
    pw = pwd.getpwnam(user)
    if pw.pw_uid == 0:
        deny("target-root")
    os.setgroups(supplementary)
    os.setgid(pw.pw_gid)
    os.setuid(pw.pw_uid)

def runtime_case(args: list[str]) -> None:
    if args[:3] != ["-u", RUNTIME_USER, "--"]:
        deny("runtime-prefix")
    cmd = args[3:]
    if not cmd or cmd[0] != "env":
        deny("runtime-env")
    i=1; assignments=[]
    while i < len(cmd) and "=" in cmd[i]:
        k=cmd[i].split("=",1)[0]
        if k not in {"HOME","XDG_RUNTIME_DIR","DOCKER_HOST"}:
            deny("runtime-env-key:"+k)
        assignments.append(cmd[i]); i+=1
    if cmd[i:] != ["/usr/bin/docker","version","--format","{{.Server.Version}}"]:
        deny("runtime-command")
    drop(RUNTIME_USER, [])
    env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    os.execve("/usr/bin/env", ["/usr/bin/env",*assignments,*cmd[i:]], env)

def runner_case(args: list[str]) -> None:
    prefix=["-u",RUNNER_USER,"-g",RUNNER_USER,"-G",PROVIDER_GROUP,"--"]
    if args[:len(prefix)] != prefix:
        deny("runner-prefix")
    cmd=args[len(prefix):]
    if len(cmd) != 6 or cmd[0] != "/usr/bin/python3" or not cmd[1].endswith("/tools/p0_rootless_docker_provider_client.py") or cmd[2] != "--request" or cmd[4:] != ["--socket",PROVIDER_SOCKET]:
        deny("runner-command")
    provider_gid=grp.getgrnam(PROVIDER_GROUP).gr_gid
    drop(RUNNER_USER,[provider_gid])
    env={"PATH":"/usr/bin:/bin","HOME":pwd.getpwnam(RUNNER_USER).pw_dir,"LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    os.execve("/usr/bin/python3",cmd,env)

def main() -> int:
    if os.geteuid() != 0:
        deny("parent-not-root")
    args=sys.argv[1:]
    if args[:2] == ["-u",RUNTIME_USER]: runtime_case(args)
    elif args[:2] == ["-u",RUNNER_USER]: runner_case(args)
    else: deny("identity-not-allowlisted")
    return 127
if __name__ == "__main__": raise SystemExit(main())
