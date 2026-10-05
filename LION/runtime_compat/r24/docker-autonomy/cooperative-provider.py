"""Pinned external shim for the cooperative trusted dependency provider.

materialize.py copies these exact bytes outside /src. worker bootstrap verifies the SHA-256
before importing this module.
"""
from cyber_lion.enterprise.cooperative_dependency_provider import build_dependencies_from_environment

def build_dependencies():
    return build_dependencies_from_environment()
