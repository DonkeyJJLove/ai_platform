"""Regression tests for observed cooperative-candidate defects; no live effects."""
from __future__ import annotations
import json
import os
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cyber_lion.mission_control.cooperative_artifacts import materialize_text, verify_text, CooperativeArtifactError
from tools.lion_cooperative_worker_adapter import cooperative_assignment_once

class CooperativeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = {'kind':'COOPERATIVE_ARTIFACT_WRITE','mission_id':'M1','assignment_id':'assignment-1','generation':1,'artifact_name':'p.txt','content':'candidate\n','expected_sha256':sha256(b'candidate\n').hexdigest(),'producer_model_call_id':'modelcall-1','parent_response_digest':sha256(b'candidate').hexdigest()}

    def test_invalid_worker_is_rejected_before_any_write(self):
        with self.assertRaises(CooperativeArtifactError):
            materialize_text(self.root,self.payload,worker_id='not a valid id')
        self.assertEqual(list(self.root.iterdir()),[])

    def test_concurrent_publication_never_overwrites_existing_artifact(self):
        old_replace = os.replace
        old_link = os.link
        def racing_replace(src,dst,*args,**kwargs):
            Path(dst).write_bytes(b'other writer')
            return old_replace(src,dst,*args,**kwargs)
        def racing_link(src,dst,*args,**kwargs):
            fd=kwargs.get('dst_dir_fd')
            if fd is None:
                Path(dst).write_bytes(b'other writer')
            else:
                out=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=fd)
                os.write(out,b'other writer');os.close(out)
            return old_link(src,dst,*args,**kwargs)
        with patch('os.replace',side_effect=racing_replace),patch('os.link',side_effect=racing_link):
            with self.assertRaises((CooperativeArtifactError,FileExistsError)):
                materialize_text(self.root,self.payload,worker_id='MD001')
        self.assertEqual((self.root/'M1/g00000001/p.txt').read_bytes(),b'other writer')

    def test_symlink_ancestor_inside_root_is_rejected(self):
        actual=self.root/'actual';actual.mkdir()
        (self.root/'M1').symlink_to(actual,target_is_directory=True)
        with self.assertRaises((CooperativeArtifactError,OSError)):
            materialize_text(self.root,self.payload,worker_id='MD001')
        self.assertEqual(list(actual.iterdir()),[])

    def test_hardlinked_artifact_is_not_accepted_as_isolated_product(self):
        p=self.root/'M1/g00000001/p.txt';p.parent.mkdir(parents=True)
        outside=self.root/'elsewhere.txt';outside.write_bytes(b'candidate\n')
        os.link(outside,p)
        v={'kind':'COOPERATIVE_ARTIFACT_VERIFY','mission_id':'M1','source_assignment_id':'assignment-1','generation':1,'artifact_name':'p.txt','expected_sha256':self.payload['expected_sha256'],'expected_producer_worker_id':'MD001'}
        with self.assertRaises((CooperativeArtifactError,OSError)):
            verify_text(self.root,v,worker_id='MD002')

    def test_claimed_assignment_cannot_substitute_mission(self):
        listed={'assignment_id':'assignment-1','mission_id':'M1','material_drone_id':'MD001','lease_generation':1,'input':dict(self.payload)}
        claimed={**listed,'mission_id':'M2','state':'CLAIMED','lease_expires_at':'2099-01-01T00:00:00Z'}
        receipts=[]
        def control(op,args):
            if op=='local_assignment_claim': return claimed
            receipts.append(args); return args
        out=cooperative_assignment_once(control,material_drone_id='MD001',artifact_root=self.root,pending=[listed])
        self.assertNotEqual(out.get('status'),'PASS')
        self.assertEqual(list(self.root.iterdir()),[])

    def test_expired_claim_cannot_write(self):
        row={'assignment_id':'assignment-1','mission_id':'M1','material_drone_id':'MD001','lease_generation':1,'state':'CLAIMED','lease_expires_at':'2000-01-01T00:00:00Z','input':dict(self.payload)}
        def control(op,args): return row if op=='local_assignment_claim' else args
        out=cooperative_assignment_once(control,material_drone_id='MD001',artifact_root=self.root,pending=[row])
        self.assertNotEqual(out.get('status'),'PASS')
        self.assertEqual(list(self.root.iterdir()),[])

    def test_missing_canonical_runtime_writer_cannot_write(self):
        row={'assignment_id':'assignment-1','mission_id':'M1','material_drone_id':'MD001','lease_generation':1,'state':'CLAIMED','lease_expires_at':'2099-01-01T00:00:00Z','input':dict(self.payload)}
        def control(op,args): return row if op=='local_assignment_claim' else args
        out=cooperative_assignment_once(control,material_drone_id='MD001',artifact_root=self.root,pending=[row])
        self.assertNotEqual(out.get('status'),'PASS')
        self.assertEqual(list(self.root.iterdir()),[])

if __name__=='__main__':unittest.main()
