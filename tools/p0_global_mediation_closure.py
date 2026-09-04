"""Materialize a fail-closed current global mediation closure carrier."""
from __future__ import annotations
from typing import Tuple
from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from tools.p0_effect_taxonomy_contract import EffectTaxonomyReconciliationReport
from cyber_lion.contracts.production_mediation import MediationClosureRecord
from tools.p0_global_mediation_contract import GlobalMediationClosureCarrier,GlobalMediationSurfaceStatus

class GlobalMediationClosureError(RuntimeError):pass

class GlobalMediationClosureCarrierBuilder:
    def materialize(self,*,inventory:EffectSurfaceInventory,taxonomy_report:EffectTaxonomyReconciliationReport,closure_records:Tuple[MediationClosureRecord,...]=(),explicit_unknown_surface_digests:Tuple[str,...]=(),evidence_refs:Tuple[str,...]=())->GlobalMediationClosureCarrier:
        inventory.validate();taxonomy_report.validate();inv_digest=inventory.digest()
        if taxonomy_report.reconciled_inventory_digest!=inv_digest:raise GlobalMediationClosureError("taxonomy report does not bind current inventory")
        if taxonomy_report.unresolved_refs or inventory.unclassified_refs:raise GlobalMediationClosureError("unresolved effect taxonomy blocks closure carrier")
        known={s.digest():s for s in inventory.surfaces};records={}
        for record in closure_records:
            record.validate()
            if record.inventory_digest!=inv_digest:raise GlobalMediationClosureError("stale closure record inventory")
            if record.surface_digest not in known:raise GlobalMediationClosureError("foreign closure record surface")
            if record.surface_digest in records:raise GlobalMediationClosureError("duplicate closure record surface")
            records[record.surface_digest]=record
        if set(explicit_unknown_surface_digests)-set(known):raise GlobalMediationClosureError("explicit unknown surface outside current inventory")
        statuses=[]
        for sd in sorted(known):
            record=records.get(sd)
            if sd in explicit_unknown_surface_digests:
                if record is not None and record.status!="UNKNOWN":raise GlobalMediationClosureError("explicit UNKNOWN surface cannot be promoted")
                statuses.append(GlobalMediationSurfaceStatus(sd,"UNKNOWN",record.digest() if record else "",record.evidence_refs if record else ()).validate())
            elif record is None:statuses.append(GlobalMediationSurfaceStatus(sd,"UNKNOWN","",()).validate())
            else:statuses.append(GlobalMediationSurfaceStatus(sd,record.status,record.digest(),record.evidence_refs).validate())
        complete=bool(statuses) and all(x.status=="MEDIATED" for x in statuses) and not explicit_unknown_surface_digests and bool(evidence_refs)
        return GlobalMediationClosureCarrier(inventory.repository,inventory.revision,inventory.tree_digest,inv_digest,inventory.scan_digest,taxonomy_report.digest(),len(inventory.surfaces),len(inventory.unclassified_refs),tuple(statuses),tuple(sorted(explicit_unknown_surface_digests)),tuple(evidence_refs),"PASS" if complete else "UNKNOWN").validate()
