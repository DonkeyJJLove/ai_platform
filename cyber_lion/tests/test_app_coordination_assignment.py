from dataclasses import replace
import unittest
from cyber_lion.process_language.fleet_mission import FleetMissionIR, FleetRoleSpec
from cyber_lion.app_coordination.task_assignment import (Budget, Task, Qualification, Executor, propose_assignment,
                             validate_proposal)


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.mission = FleetMissionIR('1.0.0', 'mission:e01', 'HYBRID',
            (FleetRoleSpec('analyst', 'LOGICAL'), FleetRoleSpec('worker', 'LOCAL')),
            (('phase-0', 'analyst'), ('phase-1', 'worker'))).validate()
        self.task = Task(self.mission.mission_id, self.mission.digest(), 'task:e01',
            'analyst', 'phase-0', 'fixture/repository', 'a'*40, 'b'*64, 0,
            'Summarize the supplied document', 'DOCUMENT_SUMMARY', ('grounded-summary',),
            ('fixture:source',), ('fixture:acceptance',), (), ('LOCAL_MODEL','APP_SESSION'),
            False, True, Budget(10, 128, 1), 300)
        self.local = self.executor('local', 'LOCAL_MODEL')
        self.app = self.executor('astra', 'APP_SESSION')

    def executor(self, name, access):
        q = Qualification(name, 'fixture-revision-1', 'DOCUMENT_SUMMARY',
                          ('grounded-summary',), ('fixture:qualification',), 1, 300)
        return Executor(name, access, 'LOGICAL', q.runtime_revision, name+':instance',
                        90, 300, True, Budget(30, 256, 2), q)

    def propose(self, task=None, executors=None, **kw):
        return propose_assignment(task or self.task, self.mission,
            executors if executors is not None else (self.app, self.local),
            now=kw.pop('now',100), observation_ttl=kw.pop('observation_ttl',100), **kw)

    def test_small_qualified_local_preferred_independent_of_input_order(self):
        self.assertEqual(self.propose().executor_id, 'local')
        self.assertEqual(self.propose(executors=(self.local,self.app)), self.propose())

    def test_app_requirement_not_downgraded(self):
        task = replace(self.task, app_required=True)
        self.assertEqual(self.propose(task).executor_id, 'astra')
        p = self.propose(task, (replace(self.app,available=False),self.local))
        self.assertEqual(p.reason,'WAITING_FOR_APP_SESSION')
        self.assertIsNone(p.executor_id)

    def test_unqualified_local_not_chosen(self):
        q = replace(self.local.qualification, skills=('classification',))
        self.assertEqual(self.propose(executors=(replace(self.local,qualification=q),self.app)).executor_id,'astra')

    def test_no_app_data_egress(self):
        p=self.propose(replace(self.task,data_may_leave_host=False), (self.app,))
        self.assertEqual(p.reason,'NO_QUALIFIED_EXECUTOR')

    def test_future_stale_expired_and_short_lived_observations(self):
        for changes in ({'observed_at':101}, {'observed_at':0}, {'available_until':100},
                        {'available_until':110}, {'available':False}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.propose(executors=(replace(self.local,**changes),)).executor_id)

    def test_qualification_bound_to_revision_and_time(self):
        with self.assertRaises(ValueError):
            self.propose(executors=(replace(self.local,runtime_revision='new'),))
        for q in (replace(self.local.qualification,expires_at=100),
                  replace(self.local.qualification,evaluated_at=101)):
            self.assertIsNone(self.propose(executors=(replace(self.local,qualification=q),)).executor_id)

    def test_qualification_requires_evidence(self):
        with self.assertRaises(ValueError):
            self.propose(executors=(replace(self.local,qualification=replace(self.local.qualification,evidence_refs=())),))

    def test_budget_and_dependencies_are_restrictive(self):
        self.assertIsNone(self.propose(replace(self.task,budget=Budget(10,1000,1))).executor_id)
        self.assertEqual(self.propose(replace(self.task,deadline=105)).reason,'INSUFFICIENT_TIME_BUDGET')
        task=replace(self.task,dependencies=('task:parent',))
        self.assertEqual(self.propose(task).reason,'WAITING_FOR_DEPENDENCIES')
        self.assertEqual(self.propose(task,completed_dependencies=('task:parent',)).executor_id,'local')

    def test_role_domain_not_model_location(self):
        task=replace(self.task,role_id='worker',transition_id='phase-1')
        self.assertIsNone(self.propose(task).executor_id)
        worker=replace(self.local,execution_domain='LOCAL')
        self.assertEqual(self.propose(task,(worker,)).executor_id,'local')

    def test_mission_role_and_transition_substitution_rejected(self):
        for changes in ({'mission_id':'other'},{'mission_digest':'c'*64},
                        {'role_id':'worker'},{'transition_id':'other'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.propose(replace(self.task,**changes))

    def test_invalid_numeric_types_and_ambiguous_executor_rejected(self):
        for value in (True,0,-1,float('nan'),float('inf'),1.5):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.propose(replace(self.task,budget=Budget(10,value,1)))
        with self.assertRaises(ValueError):self.propose(executors=(self.local,self.local))
        with self.assertRaises(ValueError):self.propose(now=True)

    def test_assignment_cannot_be_reused_after_input_checkpoint_session_change(self):
        p=self.propose()
        for task, executors in (
            (replace(self.task,input_digest='c'*64),(self.app,self.local)),
            (replace(self.task,checkpoint_revision=1),(self.app,self.local)),
            (self.task,(self.app,replace(self.local,instance_id='replacement'))),
            (replace(self.task,source_head='c'*40),(self.app,self.local))):
            with self.assertRaises(ValueError):
                validate_proposal(p,task,self.mission,executors,now=100,observation_ttl=100)

    def test_positive_proposal_still_has_no_authority_or_lease(self):
        p=self.propose()
        self.assertEqual((p.authority_effect,p.runtime_effect,p.lease_effect),('NONE',)*3)
        self.assertEqual(p.evidence_trust,'CALLER_OBSERVATIONS_NOT_ATTESTED')
        with self.assertRaises(ValueError):
            validate_proposal(replace(p,authority_effect='ALLOW'),self.task,self.mission,
                              (self.app,self.local),now=100,observation_ttl=100)


if __name__ == '__main__':
    unittest.main()
