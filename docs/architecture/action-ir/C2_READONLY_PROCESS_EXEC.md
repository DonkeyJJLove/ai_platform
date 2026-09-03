# C2 Read-Only Process Execution — Candidate Freeze

```text
PHASE=C2-READONLY-PROCESS-EXEC
STATUS=LOCAL_UNPUBLISHED_CANDIDATE
PARENT_C1_HEAD=0f75af9212a814177e08a5c206d1a8504b0937d5
PARENT_C1_TREE=e722488cda090e62a379584c12f7cee8daa43de1
TARGET_HOST=LAB-DEBIAN
AUTHORITY=READ_ONLY/TEST_ONLY
SHELL=FALSE
NETWORK=DENY
EXTERNAL_EFFECT=NONE
REPOSITORY_MUTATION=NONE
MASTER_MUTATION=NONE
MERGE=FORBIDDEN
ATTACH=FORBIDDEN
PHYSICAL_INDEPENDENCE_CLAIM=NO
```

C2 materializes the first capability-reduced local-console process boundary on top of the exact C1 LCMS candidate. It accepts only canonical C1 `CompiledActionSpec` objects of kind `process.exec`; it is not a raw-shell interface and it is not a generic command runner.

## Exact catalog

The candidate admits only two exact recipes:

```text
/usr/bin/git rev-parse HEAD
/usr/bin/git rev-parse HEAD^{tree}
```

Caller-selected executables, arbitrary argv, remote refs, `git -c`, shell strings, pipes, redirections, command substitution and background execution are not representable through the C2 adapter.

## Exact substrate binding

```text
EXECUTION_WORKSPACE=/tmp/lion-c2-exec-workspace
WORKSPACE_REPOSITORY=DonkeyJJLove/ai_platform
WORKSPACE_COMMIT=0f75af9212a814177e08a5c206d1a8504b0937d5
WORKSPACE_TREE=e722488cda090e62a379584c12f7cee8daa43de1
WORKSPACE_REMOTE_COUNT=0
TARGET_EXECUTABLE=/usr/bin/git
TARGET_EXECUTABLE_SHA256=356db14e102d68a1a37d8a1ac577dfd678d45d46e92f468bef8b7154e7bfdc60
SANDBOX_WRAPPER=/usr/bin/unshare
SANDBOX_WRAPPER_SHA256=d82900dfd64b5dd01493d206236575623c2dcf306c466dbe127e171c18cb4614
```

The target executes as the current unprivileged UID inside a new user and network namespace using the fixed wrapper:

```text
/usr/bin/unshare -Urn --map-current-user -- <exact-executable> <exact-argv>
```

Observed baseline preserved the operator UID (`995`) inside the namespace. The isolated network namespace had no route. C2 therefore does not use `sudo`, does not create a privileged host identity, and does not depend on an application-level promise of no network.

## Environment and resources

Environment inheritance is forbidden. The exact environment is reduced to `LC_ALL=C`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`, and `HOME=/nonexistent`. stdin is `NONE`; stdout/stderr are captured; TTY is forbidden. C2 sets bounded address space, file-size and file-descriptor limits, requires one represented process, and applies a maximum five-second timeout ceiling. Filesystem write authority is an empty set.

## Effect-time currentness

Immediately before the target process is spawned, C2 independently rechecks:

```text
workspace exact path
target executable SHA-256
sandbox wrapper SHA-256
absence of configured Git remote
HEAD == ActionSpec.workspace.commit
HEAD^{tree} == ActionSpec.workspace.tree
```

HEAD/TREE probes themselves run under the same network-denied wrapper. Any drift denies before target `Popen`.

## Observation and reconciliation

The process adapter, observer and reconciler are separate modules. The observer has no process-launch or network-client API. It records a bounded workspace manifest before and after execution, observes the target PID for socket descriptors and child PIDs, and verifies that the target exits. The reconciler is a pure function.

A zero exit code is not success evidence by itself. `MATCH` additionally requires exact stdout, empty stderr, unchanged workspace digest/cardinality, no observed socket, no observed child process, target termination, and exact ActionSpec/executable/sandbox identity binding. Any disagreement becomes `MISMATCH`.

The observer is independent only as a software role/process capability boundary in this C2 lab experiment. It is not an independent physical failure domain, and this candidate makes no physical-independence claim.

## Current local evidence

```text
C2_REAL_HEAD_READ=PASS
C2_REAL_TREE_READ=PASS
C2_RECONCILIATION=MATCH
C2_SOCKET_SEEN=FALSE
C2_CHILD_PIDS=0
C2_WORKSPACE_UNCHANGED=TRUE
C2_TARGETED_TESTS=11/11 PASS
C0_C1_C2_TARGETED_REGRESSION=30/30 PASS
PARENT_C1_FULL_CORE=2092 PASS / 3 SKIPPED
```

The full Core result above is a regression run on the clean exact C1 parent workspace, not a claim about an exact committed C2 tree. C2 remains uncommitted and unpublished because the active authorization explicitly forbids repository mutation.

## Publication boundary

No Git add, commit, ref update, push, branch publication, pull request creation, merge, attach or master mutation is authorized by this C2 execution grant. Publication requires a separate human authorization.
