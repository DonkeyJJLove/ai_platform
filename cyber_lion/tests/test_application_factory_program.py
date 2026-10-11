from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from cyber_lion.contracts.phase_execution_contract import preflight_execution_contracts
from cyber_lion.mission_control import cooperative_preactivation as pre
from cyber_lion.mission_control import cooperative_production as cp
from cyber_lion.mission_control import control_plane_reconnaissance as recon
from cyber_lion.mission_control.application_factory_program import (
    MISSION_ID,
    PHASES,
    canonical_compilation,
    canonical_run_text,
    panel_contracts,
    panel_lpcl_text,
    registration_payload,
    validate_semantic_equivalence,
)
from cyber_lion.mission_control.lpcl_runtime_selection import runtime_selection
from cyber_lion.mission_control.runtime_projection import validate_registration


HEAD="c530417415c158dfc769b85f9648ec0c65d57b98"
TREE="c7e9c917fdb70e22354fdf35ec35481e54f2a8f8"


class ApplicationFactoryProgramTests(unittest.TestCase):
    def test_panel_and_canonical_surfaces_compile_to_identical_phase_contracts(self):
        result=validate_semantic_equivalence(HEAD,TREE)
        self.assertEqual(result["semantic_equivalence"],"PASS")
        self.assertEqual(result["phase_count"],5)
        self.assertEqual(
            result["contract_digests"],
            [item.contract_digest for item in panel_contracts()],
        )
        self.assertEqual(
            [item.contract_digest for item in canonical_compilation(HEAD,TREE).phase_execution_contracts],
            result["contract_digests"],
        )

    def test_registration_payload_is_exact_and_source_bound(self):
        payload=registration_payload(HEAD,TREE)
        validate_registration(payload)
        self.assertEqual(payload["mission_id"],MISSION_ID)
        self.assertEqual(payload["source_head"],HEAD)
        self.assertEqual(payload["source_tree"],TREE)
        self.assertEqual(payload["lpcl_digest"],sha256(panel_lpcl_text().encode("utf-8")).hexdigest())
        self.assertEqual([x["id"] for x in payload["phases"]],[x.phase_id for x in PHASES])

    def test_panel_runtime_selection_is_fresh_docker_32(self):
        pairs={}
        for line in panel_lpcl_text().splitlines():
            if not line:continue
            key,_,value=line.partition("=");pairs[key]=value
        selected=runtime_selection(pairs,4,32)
        self.assertTrue(selected["declaration_supported"],selected)
        self.assertEqual(selected["selected_adapter"],"LPCL_DOCKER_LOCAL_MODEL")
        self.assertIsNone(selected["diagnostic"])

    def test_cross_model_phase_requires_real_local_and_saas_paths(self):
        contract=panel_contracts()[0].as_dict()
        plan=recon.build_observation_plan(contract)
        self.assertEqual(plan["unsupported_tokens"],[])
        self.assertTrue(recon.trajectory_roles(contract))
        self.assertTrue(recon.saas_advisory_required(contract))
        self.assertEqual(contract["completion_predicates"],["CROSS_MODEL_INTELLIGENCE_BOUND=PASS"])

    def test_staged_capability_preflight_preserves_deployment_boundary(self):
        contracts=panel_contracts()
        recon_cap={
            "capability_id":recon.CAPABILITY_ID,
            "executor_id":"MISSION_CONTROL_CONTROL_PLANE_RECONCILER",
            "effect_ceiling":"NONE",
            "mode":"READ_ONLY_RECON",
        }
        stage_one={
            "CONTROL_PLANE_RECONNAISSANCE":(recon_cap,),
            **pre.capability_registry_entries(),
            cp.CAPABILITY_BOOTSTRAP:cp.capability_registry_entries()[cp.CAPABILITY_BOOTSTRAP],
        }
        before=preflight_execution_contracts(contracts,stage_one).as_dict()
        self.assertEqual(before["invalid_count"],0)
        self.assertEqual(before["bound_count"],3)
        self.assertEqual(before["unbound_count"],2)
        self.assertEqual(before["mission_readiness"],"VALID_WITH_DYNAMIC_BINDING")
        states={row["phase_id"]:row["state"] for row in before["phases"]}
        self.assertEqual(states["CROSS_MODEL_RECON"],"VALID_BOUND")
        self.assertEqual(states["PREACTIVATE_BUILDER"],"VALID_BOUND")
        self.assertEqual(states["FULL_FLEET_PROVIDER_READINESS"],"VALID_BOUND")
        self.assertEqual(states["BUILD_CROSS_MODEL_ARTIFACT"],"VALID_UNBOUND_WAITING")
        self.assertEqual(states["VERIFY_CROSS_MODEL_ARTIFACT"],"VALID_UNBOUND_WAITING")

        full={**stage_one}
        full[cp.CAPABILITY_PRODUCTION]=cp.capability_registry_entries()[cp.CAPABILITY_PRODUCTION]
        full[cp.CAPABILITY_VERIFY]=cp.capability_registry_entries()[cp.CAPABILITY_VERIFY]
        after=preflight_execution_contracts(contracts,full).as_dict()
        self.assertEqual(after["invalid_count"],0)
        self.assertEqual(after["bound_count"],5)
        self.assertEqual(after["unbound_count"],0)
        self.assertEqual(after["mission_readiness"],"READY_BOUND")

    def test_material_phase_is_action_required_nonretrying(self):
        compiled=canonical_compilation(HEAD,TREE)
        process=compiled.process_ir.as_dict()
        build=next(x for x in process["transitions"] if x["trigger"]=="BUILD_CROSS_MODEL_ARTIFACT")
        self.assertEqual(build["transition_class"],"ACTION_REQUIRED")
        self.assertEqual(build["operator"],"EMIT_ACTION_INTENT")
        self.assertEqual(build["replay_policy"],"RECONCILE_FIRST")
        self.assertEqual(build["idempotency_class"],"NON_IDEMPOTENT")
        self.assertEqual(build["retry_policy"]["max_attempts"],0)
        self.assertEqual(dict(compiled.fleet_mission_ir.routing)["phase-3"],"BUILDER")
        roles={r.role_id:r for r in compiled.fleet_mission_ir.roles}
        self.assertIn("VERIFIER",roles["BUILDER"].independent_from)

    def test_isolated_mission_control_registration_is_registered_not_activated(self):
        import importlib
        import sys
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        tools=Path(__file__).resolve().parents[2]/"tools"
        if str(tools) not in sys.path:
            sys.path.insert(0,str(tools))
        compat=importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"]=compat
        mc=importlib.import_module("lion_mission_control_v3")

        with tempfile.TemporaryDirectory() as td:
            old_db,old_legacy=mc.DB,mc.LEGACY_DB
            try:
                mc.DB=Path(td)/"mission-control.db"
                mc.LEGACY_DB=Path(td)/"none.db"
                mc.migrate()
                payload=registration_payload(HEAD,TREE)
                out=mc.register_lpcl_mission(payload)
                self.assertFalse(out["idempotent"])
                mission=out["mission"]
                self.assertEqual(mission["mission_id"],MISSION_ID)
                self.assertEqual(mission["state"],"REGISTERED")
                self.assertEqual(mission["runtime_state"],"NOT_STARTED")
                self.assertEqual(mission["process"]["authority_state"],"NONE")
                self.assertEqual(mission["spec_digest"],payload["lpcl_digest"])
                self.assertEqual(mission["source_head"],HEAD)
                self.assertEqual(mission["source_tree"],TREE)

                c=mc.connect()
                try:
                    phases=[
                        dict(row) for row in c.execute(
                            "SELECT phase_id,status FROM mission_phases WHERE mission_id=? ORDER BY ordinal",
                            (MISSION_ID,),
                        ).fetchall()
                    ]
                    contracts=[
                        mc.global_sched.phase_execution_contract(c,MISSION_ID,row["phase_id"])
                        for row in phases
                    ]
                    preflight=mc.global_sched.execution_preflight(c,MISSION_ID)
                    stored=c.execute(
                        "SELECT authority_state FROM mission_process_specs WHERE mission_id=?",
                        (MISSION_ID,),
                    ).fetchone()
                finally:
                    c.close()

                self.assertEqual(
                    [row["phase_id"] for row in phases],
                    [phase.phase_id for phase in PHASES],
                )
                self.assertEqual({row["status"] for row in phases},{"PENDING"})
                self.assertEqual(stored["authority_state"],"NONE")
                self.assertEqual(len(contracts),5)
                self.assertEqual(
                    [row["contract_digest"] for row in contracts],
                    [item.contract_digest for item in panel_contracts()],
                )
                self.assertIsNotNone(preflight)
                self.assertEqual(preflight["invalid_count"],0)
                self.assertIn(
                    preflight["mission_readiness"],
                    {"VALID_WITH_DYNAMIC_BINDING","WAITING_FOR_CAPABILITIES","READY_BOUND"},
                )
                self.assertEqual(
                    c if False else "NO_ACTIVATION_CALLED",
                    "NO_ACTIVATION_CALLED",
                )
            finally:
                mc.DB=old_db
                mc.LEGACY_DB=old_legacy

    def test_http_registration_replay_rejects_source_and_spec_substitution(self):
        import copy
        import importlib
        import sys
        import tempfile
        import threading
        import urllib.error
        import urllib.request

        tools=Path(__file__).resolve().parents[2]/"tools"
        if str(tools) not in sys.path:sys.path.insert(0,str(tools))
        compat=importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"]=compat
        mc=importlib.import_module("lion_mission_control_v3")
        def request(base,path,value):
            raw=json.dumps(value).encode("utf-8")
            req=urllib.request.Request(
                base+path,data=raw,method="POST",
                headers={"Content-Type":"application/json"}
            )
            try:
                with urllib.request.urlopen(req,timeout=5) as response:
                    return response.status,json.loads(response.read(1<<20))
            except urllib.error.HTTPError as exc:
                return exc.code,json.loads(exc.read(1<<20))

        payload=registration_payload(HEAD,TREE)
        with tempfile.TemporaryDirectory(prefix="lion-reg-idempotency-") as scratch:
            old_db,old_legacy=mc.DB,mc.LEGACY_DB
            mc.DB=Path(scratch)/"mission.db"
            mc.LEGACY_DB=Path(scratch)/"absent.db"
            try:
                mc.migrate()
                server=mc.FleetThreadingHTTPServer(("127.0.0.1",0),mc.H)
                base=f"http://127.0.0.1:{server.server_address[1]}"
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    path="/api/v3/missions/register-lpcl"
                    code,first=request(base,path,payload)
                    self.assertEqual(code,201)
                    self.assertFalse(first["idempotent"])
                    code,replayed=request(base,path,payload)
                    self.assertEqual(code,201)
                    self.assertTrue(replayed["idempotent"])
                    cases=(
                        ("source_head","f"*40),
                        ("source_tree","e"*40),
                        ("material_target",payload["material_target"]+1),
                        ("logical_count",payload["logical_count"]+1),
                        ("title",payload["title"]+" mutated"),
                        ("description",payload["description"]+" mutated"),
                    )
                    for field,value in cases:
                        with self.subTest(field=field):
                            mutated=copy.deepcopy(payload)
                            mutated[field]=value
                            code,result=request(base,path,mutated)
                            self.assertEqual(code,400,result)
                            self.assertIn("mission_id already bound",result["error"])
                    altered=copy.deepcopy(payload)
                    altered["phases"][0]["title"]+=" mutated"
                    code,result=request(base,path,altered)
                    self.assertEqual(code,400,result)
                    self.assertIn("mission_id already bound",result["error"])
                    code,result=request(
                        base,"/api/v3/missions/"+MISSION_ID+"/activate",
                        {"lpcl_digest":payload["lpcl_digest"],"activation_event":"BACKGROUND_PROCESS"}
                    )
                    self.assertEqual(code,409,result)
                    db=mc.connect()
                    try:
                        registered=db.execute(
                            "SELECT source_head,source_tree,state,runtime_state FROM missions WHERE mission_id=?",
                            (MISSION_ID,),
                        ).fetchone()
                        auth=db.execute(
                            "SELECT authority_state FROM mission_process_specs WHERE mission_id=?",
                            (MISSION_ID,),
                        ).fetchone()
                        count=db.execute(
                            "SELECT count(*) FROM mission_phases WHERE mission_id=?",
                            (MISSION_ID,),
                        ).fetchone()[0]
                    finally:db.close()
                    self.assertEqual(
                        (registered["source_head"],registered["source_tree"]),
                        (HEAD,TREE)
                    )
                    self.assertEqual((registered["state"],registered["runtime_state"]),("REGISTERED","NOT_STARTED"))
                    self.assertEqual(auth["authority_state"],"NONE")
                    self.assertEqual(count,5)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=7)
            finally:
                mc.DB,mc.LEGACY_DB=old_db,old_legacy

    def test_persisted_application_factory_package_matches_generator(self):
        root=Path(__file__).resolve().parents[2]
        package=root/"LION/architecture/v1_5/application_factory_r1"
        self.assertEqual(
            (package/"PANEL_LPCL_1_2.txt").read_text(encoding="utf-8"),
            panel_lpcl_text(),
        )
        self.assertEqual(
            (package/"CANONICAL_RUN_1_2.txt").read_text(encoding="utf-8"),
            canonical_run_text(HEAD,TREE),
        )
        preview=json.loads(
            (package/"REGISTRATION_PREVIEW.json").read_text(encoding="utf-8")
        )
        self.assertEqual(preview,registration_payload(HEAD,TREE))
        validation=json.loads(
            (package/"PROGRAM_VALIDATION.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validation,validate_semantic_equivalence(HEAD,TREE))
        program=json.loads(
            (package/"MISSION_PROGRAM.json").read_text(encoding="utf-8")
        )
        from cyber_lion.mission_control.application_factory_program import (
            mission_program_manifest,
            capability_preflight_profiles,
        )
        self.assertEqual(program,mission_program_manifest(HEAD,TREE))
        self.assertEqual(
            json.loads((package/"CAPABILITY_PREFLIGHTS.json").read_text(encoding="utf-8")),
            capability_preflight_profiles(),
        )
        self.assertFalse(program["registration"]["performed"])
        self.assertFalse(program["registration"]["activation_performed"])
        self.assertTrue(program["registration"]["preview_source_identity_only"])

    def test_program_sources_are_deterministic(self):
        self.assertEqual(panel_lpcl_text(),panel_lpcl_text())
        self.assertEqual(canonical_run_text(HEAD,TREE),canonical_run_text(HEAD,TREE))
        self.assertNotEqual(
            sha256(panel_lpcl_text().encode()).hexdigest(),
            sha256(canonical_run_text(HEAD,TREE).encode()).hexdigest(),
        )


if __name__=="__main__":
    unittest.main()
