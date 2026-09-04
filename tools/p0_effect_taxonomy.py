"""Structural reconciliation of conservative effect-surface scanner UNKNOWN entries."""
from __future__ import annotations
import ast,re
from typing import Mapping,Tuple

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from tools.p0_effect_taxonomy_contract import EffectTaxonomyResolution,EffectTaxonomyReconciliationReport

class EffectTaxonomyError(RuntimeError):pass
_READ_ONLY_SQL=re.compile(r"^\s*(SELECT\b|WITH\b|EXPLAIN\b|PRAGMA\s+(?:table_info|table_xinfo|query_only|foreign_keys)\b)",re.I)
_MUTATING_SQL=re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|VACUUM|ATTACH|DETACH|PRAGMA\s+[^;=]+\s*=)",re.I)

def _call_name(node:ast.Call)->str:
    def q(n):
        if isinstance(n,ast.Name):return n.id
        if isinstance(n,ast.Attribute):
            left=q(n.value);return f"{left}.{n.attr}" if left else n.attr
        return ""
    return q(node.func)

def _functions(tree:ast.AST):
    return [n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]

def _enclosing_function(tree:ast.AST,line:int):
    candidates=[f for f in _functions(tree) if getattr(f,'lineno',0)<=line<=getattr(f,'end_lineno',-1)]
    return min(candidates,key=lambda f:getattr(f,'end_lineno',0)-f.lineno) if candidates else None

def _literal_strings(node:ast.AST)->Tuple[str,...]:
    return tuple(x.value for x in ast.walk(node) if isinstance(x,ast.Constant) and isinstance(x.value,str))

def _ro_helper(tree:ast.AST,name:str)->bool:
    funcs=[f for f in _functions(tree) if f.name==name]
    if len(funcs)!=1:return False
    f=funcs[0];has_connect=False;has_mode_ro=False;has_query_only=False
    for n in ast.walk(f):
        if isinstance(n,ast.Call):
            call=_call_name(n)
            if call.endswith("sqlite3.connect") or call=="sqlite3.connect":
                has_connect=True
                if any("mode=ro" in s for s in _literal_strings(n)):has_mode_ro=True
            if call.endswith(".execute") and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=="PRAGMA query_only=ON":has_query_only=True
        if isinstance(n,(ast.Assign,ast.AnnAssign,ast.AugAssign,ast.BinOp)) and any("mode=ro" in s for s in _literal_strings(n)):has_mode_ro=True
    return has_connect and has_mode_ro and has_query_only

def _assigned_ro_connection(tree:ast.AST,fn:ast.AST,var:str)->bool:
    for n in ast.walk(fn):
        if not isinstance(n,(ast.Assign,ast.AnnAssign)):continue
        targets=n.targets if isinstance(n,ast.Assign) else [n.target]
        if not any(isinstance(t,ast.Name) and t.id==var for t in targets):continue
        value=n.value
        if isinstance(value,ast.Call):
            name=_call_name(value)
            if name and _ro_helper(tree,name.split('.')[-1]):return True
    return False

def _arg_for_parameter(call:ast.Call,fn:ast.AST,param:str):
    names=[a.arg for a in fn.args.args]
    if param not in names:return None
    idx=names.index(param)
    if idx<len(call.args):return call.args[idx]
    for kw in call.keywords:
        if kw.arg==param:return kw.value
    return None

def _argument_is_ro_connection(tree:ast.AST,call:ast.Call,arg:ast.AST)->bool:
    caller=_enclosing_function(tree,getattr(call,'lineno',0))
    return bool(caller and isinstance(arg,ast.Name) and _assigned_ro_connection(tree,caller,arg.id))

def _connection_is_ro(tree:ast.AST,fn:ast.AST,receiver:str)->bool:
    if _assigned_ro_connection(tree,fn,receiver):return True
    params=[a.arg for a in fn.args.args]
    if receiver not in params:return False
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and _call_name(n).split('.')[-1]==fn.name and _enclosing_function(tree,getattr(n,'lineno',0)) is not fn]
    if not calls:return False
    return all((arg:=_arg_for_parameter(c,fn,receiver)) is not None and _argument_is_ro_connection(tree,c,arg) for c in calls)

def _static_sql(expr:ast.AST)->str|None:
    if isinstance(expr,ast.Constant) and isinstance(expr.value,str):return expr.value
    if isinstance(expr,ast.JoinedStr):
        out=[]
        for value in expr.values:
            if isinstance(value,ast.Constant) and isinstance(value.value,str):out.append(value.value)
            else:out.append("X")
        return ''.join(out)
    return None

def _read_only_statement(sql:str|None)->bool:
    return bool(sql and _READ_ONLY_SQL.search(sql) and not _MUTATING_SQL.search(sql))

def _resolve_local_name(fn:ast.AST,name:str):
    values=[]
    for n in ast.walk(fn):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets):values.append(n.value)
        elif isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id==name:values.append(n.value)
    return values[0] if len(values)==1 else None

def _parameter_sql_is_read_only(tree:ast.AST,fn:ast.AST,param:str)->bool:
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and _call_name(n).split('.')[-1]==fn.name and _enclosing_function(tree,getattr(n,'lineno',0)) is not fn]
    if not calls:return False
    for call in calls:
        arg=_arg_for_parameter(call,fn,param)
        if arg is None or not _read_only_statement(_static_sql(arg)):return False
    return True

def _sql_expr_read_only(tree:ast.AST,fn:ast.AST,expr:ast.AST)->bool:
    sql=_static_sql(expr)
    if sql is not None:return _read_only_statement(sql)
    if isinstance(expr,ast.Name):
        local=_resolve_local_name(fn,expr.id)
        if local is not None:return _sql_expr_read_only(tree,fn,local)
        if expr.id in [a.arg for a in fn.args.args]:return _parameter_sql_is_read_only(tree,fn,expr.id)
    return False

def _prove_read_only_dynamic_sql(source:str,line:int)->Tuple[str,...]|None:
    tree=ast.parse(source);node=None
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and getattr(n,'lineno',0)==line and _call_name(n).split('.')[-1] in {"execute","executemany"}:
            node=n;break
    if node is None or not node.args:return None
    fn=_enclosing_function(tree,line)
    if fn is None:return None
    name=_call_name(node);receiver=name.rsplit('.',1)[0] if '.' in name else ''
    if not receiver or not _connection_is_ro(tree,fn,receiver):return None
    if not _sql_expr_read_only(tree,fn,node.args[0]):return None
    ro_helpers=tuple(sorted(f.name for f in _functions(tree) if _ro_helper(tree,f.name)))
    return (f"readonly-connection:{','.join(ro_helpers)}",f"readonly-statement:{fn.name}:{line}","sqlite-mode=ro","sqlite-query_only=ON")

def _method(tree:ast.AST,name:str):
    xs=[f for f in _functions(tree) if f.name==name]
    return xs[0] if len(xs)==1 else None

def _canonical_delete_alias(raw:EffectSurfaceInventory,sources:Mapping[str,str],source_ref:str)->EffectTaxonomyResolution|None:
    path=source_ref.split(':',1)[0];source=sources.get(path)
    if not source or not source_ref.endswith(":backend.authorize_canonical_delete"):return None
    tree=ast.parse(source);method=_method(tree,"authorize_canonical_delete");legacy=_method(tree,"authorize_delete")
    if method is None or legacy is None:return None
    calls={_call_name(n).split('.')[-1] for n in ast.walk(method) if isinstance(n,ast.Call)}
    if "delete_exact_branch_ref" in calls:return None
    attrs={n.attr for n in ast.walk(method) if isinstance(n,ast.Attribute)}
    required={"validate","master_sha","branch_sha","master_tree","compare_branch_to_master","open_prs_for_branch","ownership_observation","_pending_delete"}
    if not required.issubset(attrs):return None
    if not any(isinstance(n,ast.Raise) for n in ast.walk(legacy)):return None
    targets=[s for s in raw.surfaces if s.effect_class=="repository_ref.delete" and s.mutation_kind.endswith("delete_exact_branch_ref")]
    if len(targets)!=1:return None
    target=targets[0]
    return EffectTaxonomyResolution(source_ref,"MEDIATION_GATE_ALIAS",target.digest(),target.entrypoints[0],(
        f"{path}:{method.lineno}:authorize_canonical_delete-structural-gate",
        f"{path}:{legacy.lineno}:legacy-authority-disabled",
        target.entrypoints[0],
    )).validate()

def _budget_release_alias(raw:EffectSurfaceInventory,sources:Mapping[str,str],source_ref:str)->EffectTaxonomyResolution|None:
    path=source_ref.split(':',1)[0];source=sources.get(path)
    if not source or not source_ref.endswith(":self._budget_provider.release"):return None
    tree=ast.parse(source);port=next((n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=="FleetEffectBudgetPort"),None)
    if port is None or not any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="release" for n in port.body):return None
    target_path="cyber_lion/enterprise/fleet_effect_budget.py";target_source=sources.get(target_path)
    if not target_source:return None
    target_tree=ast.parse(target_source);release=_method(target_tree,"release");terminal=_method(target_tree,"_terminal")
    if release is None or terminal is None:return None
    terminal_calls=[n for n in ast.walk(release) if isinstance(n,ast.Call) and _call_name(n).endswith("._terminal")]
    if len(terminal_calls)!=1 or not any(s=="RELEASED" for s in _literal_strings(terminal_calls[0])):return None
    update_nodes=[]
    for n in ast.walk(terminal):
        if isinstance(n,ast.Call) and _call_name(n).split('.')[-1]=="execute" and n.args:
            sql=_static_sql(n.args[0])
            if sql and re.search(r"^\s*UPDATE\s+fleet_effect_reservation\s+SET\s+state",sql,re.I):update_nodes.append(n)
    if len(update_nodes)!=1:return None
    line=update_nodes[0].lineno
    targets=[s for s in raw.surfaces if s.implementation_refs==(target_path,) and s.effect_class=="persistent_state.write" and s.entrypoints[0].startswith(f"{target_path}:{line}:")]
    if len(targets)!=1:return None
    target=targets[0]
    return EffectTaxonomyResolution(source_ref,"EFFECT_ALIAS",target.digest(),target.entrypoints[0],(
        f"{path}:{getattr(port,'lineno',0)}:FleetEffectBudgetPort.release",
        f"{target_path}:{release.lineno}:release-to-terminal-RELEASED",
        target.entrypoints[0],
    )).validate()

class EffectTaxonomyReconciler:
    def reconcile(self,*,raw_inventory:EffectSurfaceInventory,sources:Mapping[str,str])->tuple[EffectSurfaceInventory,EffectTaxonomyReconciliationReport,Tuple[EffectTaxonomyResolution,...]]:
        raw_inventory.validate()
        if not isinstance(sources,Mapping) or not sources:raise EffectTaxonomyError("exact source mapping required")
        resolutions=[];unresolved=[]
        for ref in raw_inventory.unclassified_refs:
            parts=ref.split(':',3);path=parts[0];resolution=None
            if ref.endswith(":dynamic-sql") and len(parts)>=3:
                try:line=int(parts[1])
                except ValueError:line=-1
                proof=_prove_read_only_dynamic_sql(sources.get(path,""),line) if line>0 and sources.get(path) else None
                if proof:resolution=EffectTaxonomyResolution(ref,"NON_CONSEQUENTIAL_READ_ONLY","","",(f"{path}:{line}:dynamic-sql",)+proof).validate()
            if resolution is None:resolution=_canonical_delete_alias(raw_inventory,sources,ref)
            if resolution is None:resolution=_budget_release_alias(raw_inventory,sources,ref)
            if resolution is None:unresolved.append(ref)
            else:resolutions.append(resolution)
        if len({r.source_ref for r in resolutions})!=len(resolutions):raise EffectTaxonomyError("duplicate taxonomy resolution")
        ordered=tuple(sorted(resolutions,key=lambda x:x.source_ref))
        evidence=tuple(raw_inventory.evidence_refs)+tuple(f"taxonomy-resolution:{r.digest()}" for r in ordered)
        reconciled=EffectSurfaceInventory(raw_inventory.repository,raw_inventory.revision,raw_inventory.tree_digest,raw_inventory.scan_digest,raw_inventory.surfaces,tuple(sorted(unresolved)),evidence).validate()
        report=EffectTaxonomyReconciliationReport(raw_inventory.digest(),reconciled.digest(),tuple(r.digest() for r in ordered),tuple(sorted(unresolved)),"PASS" if not unresolved else "UNKNOWN").validate()
        return reconciled,report,ordered
