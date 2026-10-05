"""Source-level adapter selection; not fleet readiness or execution permission.

Report the same explicit Docker discriminator used by Mission Control. Never
infer Docker from a PILOT_* hint, a container name or the active UI tab. Existing
12/64 and 128/64 declarations retain the legacy adapter selection. Other missing
runtime declarations remain language-valid but are not executable declarations.
"""
from __future__ import annotations
from typing import Mapping


def runtime_selection(pairs: Mapping[str, str], logical_count: int, material_count: int) -> dict:
    if type(logical_count) is not int or not 1 <= logical_count <= 512:
        raise ValueError('logical count')
    if type(material_count) is not int or not 0 <= material_count <= 4096:
        raise ValueError('material count')
    declared = pairs.get('MATERIAL_RUNTIME', '')
    if type(declared) is not str:
        raise ValueError('MATERIAL_RUNTIME must be text')
    declared = declared.strip().upper()
    result = {'schema':'lion.lpcl-runtime-selection/v1', 'declared_runtime':declared or None,
              'logical_count':logical_count, 'material_count':material_count,
              'selected_adapter':None, 'declaration_supported':False,
              'fleet_observed':False, 'authority_effect':'NONE'}
    if declared == 'DOCKER_LOCAL_MODEL':
        if material_count != 32:
            return {**result, 'diagnostic':'LPCL_DOCKER_MATERIAL_COUNT_MUST_BE_32'}
        if (pairs.get('CONTINUE_EXISTING_EPOCH3_MISSION') == 'TRUE'
                or pairs.get('CONTINUE_EXISTING_EPOCH3_LINEAGE') == 'TRUE'
                or str(pairs.get('PARENT_MISSION_ID') or '').strip()):
            return {**result, 'diagnostic':'LPCL_DOCKER_REQUIRES_FRESH_MISSION'}
        return {**result, 'selected_adapter':'LPCL_DOCKER_LOCAL_MODEL',
                'declaration_supported':True, 'diagnostic':None}
    if not declared and material_count == 64 and logical_count in {12,128}:
        return {**result, 'selected_adapter':'EPOCH3_COMPATIBILITY',
                'declaration_supported':True, 'diagnostic':None}
    if declared:
        return {**result, 'diagnostic':'LPCL_MATERIAL_RUNTIME_UNSUPPORTED'}
    return {**result, 'diagnostic':'LPCL_MATERIAL_RUNTIME_REQUIRED'}


def require_runtime_selection(pairs: Mapping[str, str], logical_count: int, material_count: int) -> str:
    value = runtime_selection(pairs, logical_count, material_count)
    if not value['declaration_supported']:
        raise ValueError(value['diagnostic'])
    return value['selected_adapter']
