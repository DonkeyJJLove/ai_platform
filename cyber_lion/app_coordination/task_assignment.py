"""E01: pure assignment proposals; no dispatch, lease issuance or authority.

Qualification and availability inputs are caller-supplied observations, not
authenticated attestations. E02 must resolve their provenance before use.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re

from cyber_lion.process_language.fleet_mission import FleetMissionIR

WORKLOADS = frozenset({'DOCUMENT_SUMMARY', 'DOCUMENT_CLASSIFICATION', 'TEST_RESULT_REVIEW'})
ACCESS = frozenset({'APP_SESSION', 'LOCAL_MODEL', 'LOCAL_PROCESS'})


def text(value, name):
    if type(value) is not str or not value.strip() or '\x00' in value:
        raise ValueError(name)


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(name)


def digest(value, name):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError(name)


def strings(value, name, nonempty=True):
    if type(value) is not tuple or (nonempty and not value):
        raise ValueError(name)
    for item in value:
        text(item, name)
    if len(set(value)) != len(value):
        raise ValueError(name + ': duplicate')


def seal(value):
    return sha256(b'LION/E01-ASSIGNMENT-CANDIDATE/1\0' + json.dumps(
        asdict(value), sort_keys=True, separators=(',', ':'), allow_nan=False
    ).encode()).hexdigest()


@dataclass(frozen=True)
class Budget:
    seconds: int
    tokens: int
    attempts: int

    def validate(self):
        for name in ('seconds', 'tokens', 'attempts'):
            integer(getattr(self, name), name, 1)

    def fits(self, capacity):
        return all(getattr(self, n) <= getattr(capacity, n)
                   for n in ('seconds', 'tokens', 'attempts'))


@dataclass(frozen=True)
class Task:
    mission_id: str
    mission_digest: str
    task_id: str
    role_id: str
    transition_id: str
    repository: str
    source_head: str
    input_digest: str
    checkpoint_revision: int
    objective: str
    workload: str
    required_skills: tuple[str, ...]
    source_refs: tuple[str, ...]
    acceptance_refs: tuple[str, ...]
    dependencies: tuple[str, ...]
    allowed_access: tuple[str, ...]
    app_required: bool
    data_may_leave_host: bool
    budget: Budget
    deadline: int

    def validate(self, mission):
        if type(mission) is not FleetMissionIR:
            raise ValueError('exact FleetMissionIR required')
        mission.validate()
        if self.mission_id != mission.mission_id or self.mission_digest != mission.digest():
            raise ValueError('mission binding')
        if dict(mission.routing).get(self.transition_id) != self.role_id:
            raise ValueError('transition/role binding')
        for name in ('task_id', 'repository', 'objective'):
            text(getattr(self, name), name)
        if type(self.source_head) is not str or re.fullmatch('[0-9a-f]{40}', self.source_head) is None:
            raise ValueError('source head')
        digest(self.input_digest, 'input digest')
        integer(self.checkpoint_revision, 'checkpoint revision')
        integer(self.deadline, 'deadline', 1)
        for name in ('required_skills', 'source_refs', 'acceptance_refs', 'allowed_access'):
            strings(getattr(self, name), name)
        strings(self.dependencies, 'dependencies', nonempty=False)
        if self.task_id in self.dependencies:
            raise ValueError('self dependency')
        if self.workload not in WORKLOADS or not set(self.allowed_access) <= ACCESS:
            raise ValueError('unsupported workload/access')
        if type(self.app_required) is not bool or type(self.data_may_leave_host) is not bool:
            raise ValueError('explicit boolean constraints required')
        if self.app_required and 'APP_SESSION' not in self.allowed_access:
            raise ValueError('inconsistent app requirement')
        if type(self.budget) is not Budget:
            raise ValueError('exact Budget required')
        self.budget.validate()


@dataclass(frozen=True)
class Qualification:
    executor_id: str
    runtime_revision: str
    workload: str
    skills: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evaluated_at: int
    expires_at: int

    def validate(self):
        text(self.executor_id, 'qualified executor')
        text(self.runtime_revision, 'qualified runtime revision')
        if self.workload not in WORKLOADS:
            raise ValueError('qualification workload')
        strings(self.skills, 'qualified skills')
        strings(self.evidence_refs, 'qualification evidence')
        integer(self.evaluated_at, 'evaluation time')
        integer(self.expires_at, 'qualification expiry', self.evaluated_at + 1)


@dataclass(frozen=True)
class Executor:
    executor_id: str
    access: str
    execution_domain: str
    runtime_revision: str
    instance_id: str
    observed_at: int
    available_until: int
    available: bool
    capacity: Budget
    qualification: Qualification

    def validate(self):
        for name in ('executor_id', 'runtime_revision', 'instance_id'):
            text(getattr(self, name), name)
        if self.access not in ACCESS or self.execution_domain not in {'LOGICAL', 'LOCAL'}:
            raise ValueError('executor placement')
        if self.access == 'APP_SESSION' and self.execution_domain != 'LOGICAL':
            raise ValueError('application session is a logical role')
        if self.access == 'LOCAL_PROCESS' and self.execution_domain != 'LOCAL':
            raise ValueError('process is a material role')
        if type(self.available) is not bool:
            raise ValueError('availability')
        integer(self.observed_at, 'observation time')
        integer(self.available_until, 'availability expiry', self.observed_at + 1)
        if type(self.capacity) is not Budget or type(self.qualification) is not Qualification:
            raise ValueError('exact capacity/qualification required')
        self.capacity.validate()
        self.qualification.validate()
        if (self.qualification.executor_id, self.qualification.runtime_revision) != (
                self.executor_id, self.runtime_revision):
            raise ValueError('qualification identity substitution')


@dataclass(frozen=True)
class AssignmentProposal:
    task_digest: str
    executor_digest: str | None
    executor_id: str | None
    instance_id: str | None
    checkpoint_revision: int
    valid_until: int | None
    reason: str
    authority_effect: str = 'NONE'
    runtime_effect: str = 'NONE'
    lease_effect: str = 'NONE'
    evidence_trust: str = 'CALLER_OBSERVATIONS_NOT_ATTESTED'


def propose_assignment(task, mission, executors, *, now, observation_ttl,
                       completed_dependencies=()):
    """Return only a proposal. Positive eligibility is never runtime admission."""
    if type(task) is not Task or type(executors) is not tuple:
        raise ValueError('exact task and immutable executor snapshot required')
    task.validate(mission)
    integer(now, 'now')
    integer(observation_ttl, 'observation ttl', 1)
    strings(completed_dependencies, 'completed dependencies', nonempty=False)
    seen = set()
    for executor in executors:
        if type(executor) is not Executor:
            raise ValueError('exact Executor required')
        executor.validate()
        if executor.executor_id in seen:
            raise ValueError('ambiguous executor snapshot')
        seen.add(executor.executor_id)

    def blocked(reason):
        return AssignmentProposal(seal(task), None, None, None,
                                  task.checkpoint_revision, None, reason)

    if now + task.budget.seconds > task.deadline:
        return blocked('INSUFFICIENT_TIME_BUDGET')
    if not set(task.dependencies) <= set(completed_dependencies):
        return blocked('WAITING_FOR_DEPENDENCIES')
    domain = next(r.execution_domain for r in mission.roles if r.role_id == task.role_id)
    eligible = []
    waiting_app = False
    for executor in executors:
        q = executor.qualification
        if (executor.execution_domain != domain or executor.access not in task.allowed_access
                or (task.app_required and executor.access != 'APP_SESSION')
                or (executor.access == 'APP_SESSION' and not task.data_may_leave_host)
                or q.workload != task.workload or not set(task.required_skills) <= set(q.skills)
                or not q.evaluated_at <= now < q.expires_at
                or not task.budget.fits(executor.capacity)):
            continue
        expiry = min(task.deadline, executor.available_until, q.expires_at,
                     executor.observed_at + observation_ttl)
        if (executor.available and executor.observed_at <= now
                and now + task.budget.seconds < expiry):
            eligible.append((executor, expiry))
        elif executor.access == 'APP_SESSION':
            waiting_app = True
    if not eligible:
        return blocked('WAITING_FOR_APP_SESSION' if waiting_app else 'NO_QUALIFIED_EXECUTOR')
    # Small qualified local models precede app sessions; competence filters first.
    priority = {'LOCAL_PROCESS': 0, 'LOCAL_MODEL': 1, 'APP_SESSION': 2}
    executor, expiry = min(eligible, key=lambda item: (priority[item[0].access], item[0].executor_id))
    return AssignmentProposal(seal(task), seal(executor), executor.executor_id,
                              executor.instance_id, task.checkpoint_revision, expiry,
                              'ELIGIBLE_CANDIDATE_REQUIRES_ADMISSION')


def validate_proposal(proposal, task, mission, executors, **clock_and_dependencies):
    """Reject substitutions or changed observations; does not consume a lease."""
    if type(proposal) is not AssignmentProposal:
        raise ValueError('exact AssignmentProposal required')
    fresh = propose_assignment(task, mission, executors, **clock_and_dependencies)
    if proposal != fresh:
        raise ValueError('proposal no longer matches task and observations')
    return proposal
