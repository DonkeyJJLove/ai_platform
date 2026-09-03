from __future__ import annotations

from dataclasses import replace
import inspect
import json
from pathlib import Path
import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.physical_action_simulation import (
    CalibrationBinding, DigitalTwinProviderIdentity, DigitalTwinSimulator,
    DigitalTwinSnapshot, PhysicalActionSpec, PhysicalAuthorityEnvelope,
    PhysicalSimulationError, Pose6D, SafetyPreconditions,
)

ROOT=Path(__file__).resolve().parents[2]
H="a"*64


def fixture():
    pose=Pose6D("cell_A/world","m","rad",0.1,0.2,0.3,0.0,0.0,0.0)
    calibration=CalibrationBinding("cal:cell_A:7",H,"cell_A/world","m","rad",7)
    authority=PhysicalAuthorityEnvelope("physical.simulation","simulate_pose_transition","SIMULATION_ONLY","part-17","cell_A/world",1000,2000,0.25,0.2,20.0,5.0)
    safety=SafetyPreconditions(True,True,"READY",True,True,True)
    spec=PhysicalActionSpec("e0.translate.1","intent:e0","part-17","pose.translate",pose,(0.05,-0.01,0.0),0.1,4.0,0.5,calibration,authority,safety,("digital twin target pose computed",),("physical actuation","human safety zone entry","unplanned contact"))
    snapshot=DigitalTwinSnapshot("snapshot:e0:1","part-17",pose,H,7,safety).sealed()
    provider=DigitalTwinProviderIdentity("lion-digital-twin-e0","DIGITAL_TWIN_ONLY","b"*64,"NONE","NONE","NONE")
    return spec,snapshot,provider


class PhysicalActionSimulationTests(unittest.TestCase):
    def test_exact_simulation_produces_reconciled_nonphysical_receipt(self):
        spec,snapshot,provider=fixture()
        receipt=DigitalTwinSimulator(provider).simulate(spec,snapshot,observed_at_ms=1500)
        self.assertEqual(receipt.simulation_state,"SIMULATED_VERIFIED")
        self.assertEqual(receipt.physical_effect,"NONE")
        self.assertEqual(receipt.hardware_safety_proof,"NOT_PROVEN_BY_SIMULATION")
        self.assertEqual(receipt.simulated_pose.x,0.15)
        self.assertEqual(receipt.simulated_pose.y,0.19)
        self.assertEqual(receipt.action_spec_digest,spec.digest())
        self.assertEqual(receipt.snapshot_digest,snapshot.snapshot_digest)
        receipt.validate()

    def test_unit_substitution_fails_closed(self):
        spec,snapshot,provider=fixture()
        bad=replace(spec,source_pose=replace(spec.source_pose,linear_unit="mm"))
        with self.assertRaises(PhysicalSimulationError): DigitalTwinSimulator(provider).simulate(bad,snapshot,observed_at_ms=1500)

    def test_coordinate_frame_substitution_fails_closed(self):
        spec,snapshot,provider=fixture()
        bad=replace(spec,source_pose=replace(spec.source_pose,frame_id="cell_B/world"))
        with self.assertRaises(PhysicalSimulationError): DigitalTwinSimulator(provider).simulate(bad,snapshot,observed_at_ms=1500)

    def test_calibration_substitution_fails_closed(self):
        spec,snapshot,provider=fixture()
        bad=replace(snapshot,calibration_digest="c"*64).sealed()
        with self.assertRaises(PhysicalSimulationError): DigitalTwinSimulator(provider).simulate(spec,bad,observed_at_ms=1500)

    def test_calibration_revision_substitution_fails_closed(self):
        spec,snapshot,provider=fixture()
        bad=replace(snapshot,calibration_revision=8).sealed()
        with self.assertRaises(PhysicalSimulationError): DigitalTwinSimulator(provider).simulate(spec,bad,observed_at_ms=1500)

    def test_safety_substitutions_fail_closed(self):
        spec,snapshot,provider=fixture()
        for changes in (
            {"emergency_stop_available":False},{"protected_zone_clear":False},
            {"safety_controller_state":"FAULT"},{"sensors_current":False},
            {"heartbeat_current":False},{"calibration_current":False},
        ):
            bads=replace(spec.safety,**changes)
            with self.subTest(changes=changes),self.assertRaises(PhysicalSimulationError):
                replace(spec,safety=bads).validate()

    def test_hardware_authority_and_actuation_mode_fail_closed(self):
        spec,_,provider=fixture()
        with self.assertRaises(PhysicalSimulationError): replace(spec.authority,hardware_effect_capability="physical.actuation").validate()
        with self.assertRaises(PhysicalSimulationError): replace(spec.authority,domain="physical.actuation").validate()
        with self.assertRaises(PhysicalSimulationError): DigitalTwinProviderIdentity(provider.provider_id,provider.provider_class,provider.implementation_digest,"physical.actuation","NONE","NONE").validate()

    def test_spatial_temporal_and_limit_substitution_fail_closed(self):
        spec,snapshot,provider=fixture()
        simulator=DigitalTwinSimulator(provider)
        with self.assertRaises(PhysicalSimulationError): simulator.simulate(spec,snapshot,observed_at_ms=999)
        with self.assertRaises(PhysicalSimulationError): simulator.simulate(spec,snapshot,observed_at_ms=2001)
        with self.assertRaises(PhysicalSimulationError): replace(spec,translation_m=(0.3,0.0,0.0)).validate()
        with self.assertRaises(PhysicalSimulationError): replace(spec,requested_speed_m_s=0.3).validate()
        with self.assertRaises(PhysicalSimulationError): replace(spec,requested_force_n=21.0).validate()
        with self.assertRaises(PhysicalSimulationError): replace(spec,requested_energy_j=6.0).validate()

    def test_object_pose_and_safety_currentness_substitution_fail_closed(self):
        spec,snapshot,provider=fixture(); sim=DigitalTwinSimulator(provider)
        with self.assertRaises(PhysicalSimulationError): sim.simulate(spec,replace(snapshot,object_id="part-18").sealed(),observed_at_ms=1500)
        with self.assertRaises(PhysicalSimulationError): sim.simulate(spec,replace(snapshot,observed_pose=replace(snapshot.observed_pose,x=0.2)).sealed(),observed_at_ms=1500)
        changed=replace(snapshot.safety,protected_zone_clear=False)
        with self.assertRaises(PhysicalSimulationError): replace(snapshot,safety=changed).sealed()

    def test_digest_and_provider_identity_substitution_fail_closed(self):
        spec,snapshot,provider=fixture()
        forged=replace(snapshot,snapshot_digest="0"*64)
        with self.assertRaises(PhysicalSimulationError): DigitalTwinSimulator(provider).simulate(spec,forged,observed_at_ms=1500)
        with self.assertRaises(PhysicalSimulationError): DigitalTwinSimulator(replace(provider,provider_class="ROBOT_ACTUATOR"))

    def test_schema_is_simulation_only_and_does_not_claim_hardware_proof(self):
        schema=json.loads((ROOT/'cyber_lion/contracts/v1/physical_action_spec.schema.json').read_text())
        meta=schema['x-lion-e0']
        self.assertEqual(meta['authority'],'NONE/SIMULATION_ONLY')
        self.assertEqual(meta['hardware_effect'],'NONE')
        self.assertEqual(meta['robotics_runtime'],'NONE')
        self.assertFalse(meta['simulation_success_is_hardware_safety_proof'])

    def test_module_has_no_runtime_hardware_or_external_effect_surface(self):
        source=inspect.getsource(__import__('cyber_lion.physical_action_simulation',fromlist=['*']))
        for forbidden in ('subprocess','socket','urlopen','requests','serial','gpio','ros2','os.system','Popen'):
            self.assertNotIn(forbidden,source)
        path='cyber_lion/physical_action_simulation.py'
        inv=EffectSurfaceScanner().scan(repository='DonkeyJJLove/ai_platform',revision='1'*40,tree_digest='2'*40,sources={path:(ROOT/path).read_text()})
        self.assertEqual(inv.surfaces,())
        self.assertEqual(inv.unclassified_refs,())


if __name__=='__main__': unittest.main()
