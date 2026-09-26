from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class R24DynamicDockerRematerializationTests(unittest.TestCase):
    def module(self):
        tools=Path(__file__).resolve().parents[2]/"tools"
        if str(tools) not in sys.path:
            sys.path.insert(0,str(tools))
        compat=importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"]=compat
        return importlib.import_module("lion_mission_control_v3")

    def test_rematerialized_container_ids_force_rebind_then_become_idempotent(self):
        mc=self.module()
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        old_db,old_legacy=mc.DB,mc.LEGACY_DB
        self.addCleanup(lambda:setattr(mc,"DB",old_db))
        self.addCleanup(lambda:setattr(mc,"LEGACY_DB",old_legacy))
        mc.DB=Path(td.name)/"mc.db";mc.LEGACY_DB=Path(td.name)/"none.db";mc.migrate()

        mid="R24-REMATERIALIZE-TEST"
        stamp=mc.now()
        c=mc.connect()
        c.execute(
            "INSERT INTO missions(mission_id,title,adapter,spec_digest,source_head,source_tree,namespace,state,runtime_state,logical_count,material_target,materialized,ready,created_at,authorized_at,updated_at,last_error,spec_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid,mid,mc.LPCL_DOCKER_LOCAL_MODEL_ADAPTER,"a"*64,"b"*40,"c"*40,None,"RUNNING","DOCKER_LOCAL_MODEL_FLEET_BOUND",64,32,32,32,stamp,stamp,stamp,None,"{}"),
        )
        c.execute(
            "INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid,mid,"o","d","a"*64,"MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\nLOGICAL_ROLE_PREFIX=R24\n",json.dumps(["LPCL","AUTHORITY","CURRENTNESS","ASSIGNMENT"]), "EXPLICIT_USER_ACTIVATION","FREEZE_AND_BIND",0.0,stamp,stamp),
        )
        c.execute(
            "INSERT INTO mission_phases VALUES(?,?,?,?,?,?,?,?,?,?)",
            (mid,"FREEZE_AND_BIND",1,"Freeze and bind","WAITING",0.0,None,stamp,None,stamp),
        )
        for i in range(1,65):
            lid=f"LD{i:03d}"
            c.execute("INSERT INTO logical_drones VALUES(?,?,?,?,?,?)",(mid,lid,"R24",1,1,1))
        old_uids=[]
        for i in range(1,33):
            material=f"MD{i:03d}";uid=f"{i:064x}";old_uids.append(uid)
            c.execute("INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",(mid,f"old-{material.lower()}",uid,material,"DOCKER_LOCAL_MODEL",1,0,None,stamp))
        for i in range(1,65):
            lid=f"LD{i:03d}";material=f"MD{((i-1)%32)+1:03d}"
            value={"material_worker_id":material,"container_id":old_uids[(i-1)%32],"binding_class":"DOCKER_LOCAL_MODEL"}
            c.execute(
                "INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"old-topology-{i}",mid,"__TOPOLOGY__",lid,material,mc._payload_digest(value),json.dumps(value,sort_keys=True),"BOUND",1,stamp,stamp,stamp),
            )
        c.commit();c.close()

        new_workers=[]
        for i in range(1,33):
            material=f"MD{i:03d}"
            new_workers.append({
                "material_worker_id":material,
                "pod_name":f"lion-r24-md{i:03d}",
                "pod_uid":f"{i+1000:064x}",
                "container_id":f"{i+1000:064x}",
                "ready":1,
                "phase":"DOCKER_LOCAL_MODEL",
                "restarts":0,
                "pod_ip":None,
                "model":"gpt-oss-20b-MXFP4",
            })
        observed={"digest":"d"*64,"observed_at":stamp,"workers":new_workers,"physical_failure_domains":1}

        common=[
            patch.object(mc.operator_control,"autonomy_allowed",return_value=True),
            patch.object(mc,"_docker_local_model_currentness",return_value=observed),
            patch.object(mc.global_sched,"compile_phase_specs",return_value=None),
            patch.object(mc,"ensure_driver",return_value=None),
            patch.object(mc,"driver_snapshot",return_value=None),
            patch.object(mc,"driver_activate",return_value={"generation":1}),
            patch.object(mc,"_process_message",return_value={"authority_effect":"NONE"}),
            patch.object(mc,"process_snapshot",side_effect=lambda mission_id:{"mission_id":mission_id}),
        ]
        with common[0],common[1],common[2],common[3],common[4],common[5],common[6],common[7]:
            mc.bind_lpcl_execution(mid)

        c=mc.connect()
        rebound=sorted(r["pod_uid"] for r in c.execute("SELECT pod_uid FROM material_workers WHERE mission_id=?",(mid,)))
        topology_before=[r["assignment_id"] for r in c.execute("SELECT assignment_id FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' ORDER BY assignment_id",(mid,))]
        c.close()
        self.assertEqual(rebound,sorted(w["pod_uid"] for w in new_workers))
        self.assertEqual(len(topology_before),64)

        with patch.object(mc.operator_control,"autonomy_allowed",return_value=True), patch.object(mc,"_docker_local_model_currentness",return_value=observed), patch.object(mc,"process_snapshot",side_effect=lambda mission_id:{"mission_id":mission_id}), patch.object(mc.global_sched,"bind_dynamic_local_model_fleet",wraps=mc.global_sched.bind_dynamic_local_model_fleet) as rebinder:
            mc.bind_lpcl_execution(mid)
            self.assertEqual(rebinder.call_count,0)

        c=mc.connect()
        topology_after=[r["assignment_id"] for r in c.execute("SELECT assignment_id FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' ORDER BY assignment_id",(mid,))]
        c.close()
        self.assertEqual(topology_after,topology_before)



    def test_dynamic_docker_binding_can_select_eight_workers_from_live_pool(self):
        mc=self.module()
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        old_db,old_legacy=mc.DB,mc.LEGACY_DB
        self.addCleanup(lambda:setattr(mc,"DB",old_db));self.addCleanup(lambda:setattr(mc,"LEGACY_DB",old_legacy))
        mc.DB=Path(td.name)/"mc.db";mc.LEGACY_DB=Path(td.name)/"none.db";mc.migrate()
        mid="R24-16L8M-TEST";stamp=mc.now();c=mc.connect()
        c.execute("INSERT INTO missions(mission_id,title,adapter,spec_digest,source_head,source_tree,namespace,state,runtime_state,logical_count,material_target,materialized,ready,created_at,authorized_at,updated_at,last_error,spec_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,mid,"LPCL_MISSION","a"*64,"b"*40,"c"*40,None,"AUTHORIZED","NOT_STARTED",16,8,0,0,stamp,stamp,stamp,None,"{}"))
        c.execute("INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(mid,mid,"o","d","a"*64,"MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\nLOGICAL_ROLE_PREFIX=R24\n",json.dumps(["LPCL","AUTHORITY","CURRENTNESS","ASSIGNMENT"]),"EXPLICIT_USER_ACTIVATION","P",0.0,stamp,stamp))
        c.execute("INSERT INTO mission_phases VALUES(?,?,?,?,?,?,?,?,?,?)",(mid,"P",1,"P","PENDING",0.0,None,None,None,stamp));c.commit();c.close()
        workers=[{"material_worker_id":f"MD{i:03d}","pod_name":f"lion-r24-md{i:03d}","pod_uid":f"{1000+i:064x}","container_id":f"{1000+i:064x}","ready":1,"phase":"DOCKER_LOCAL_MODEL","restarts":0,"pod_ip":None,"model":"gpt-oss-20b-MXFP4"} for i in range(1,9)]
        observed={"digest":"d"*64,"observed_at":stamp,"workers":workers,"physical_failure_domains":1,"pool_materialized":32,"pool_ready":32,"selected_material":8}
        with patch.object(mc.operator_control,"autonomy_allowed",return_value=True),patch.object(mc,"_docker_local_model_currentness",return_value=observed),patch.object(mc.global_sched,"compile_phase_specs",return_value=None),patch.object(mc,"ensure_driver",return_value=None),patch.object(mc,"driver_snapshot",return_value=None),patch.object(mc,"driver_activate",return_value={"generation":1}),patch.object(mc,"_process_message",return_value={"authority_effect":"NONE"}),patch.object(mc,"process_snapshot",side_effect=lambda mission_id:{"mission_id":mission_id}):
            mc.bind_lpcl_execution(mid)
        c=mc.connect()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(mid,)).fetchone()[0],8)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM logical_drones WHERE mission_id=?",(mid,)).fetchone()[0],16)
        dist=dict(c.execute("SELECT material_drone_id,COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' GROUP BY material_drone_id",(mid,)).fetchall())
        c.close()
        self.assertEqual(sorted(dist),[f"MD{i:03d}" for i in range(1,9)])
        self.assertTrue(all(v==2 for v in dist.values()))

    def test_mission_control_http_backlog_supports_fleet_bursts(self):
        mc=self.module()
        self.assertGreaterEqual(mc.FleetThreadingHTTPServer.request_queue_size,128)
        self.assertTrue(mc.FleetThreadingHTTPServer.daemon_threads)
        self.assertTrue(mc.FleetThreadingHTTPServer.allow_reuse_address)


if __name__=="__main__":
    unittest.main()
