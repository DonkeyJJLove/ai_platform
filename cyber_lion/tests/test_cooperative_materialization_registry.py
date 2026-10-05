from __future__ import annotations

import unittest

from cyber_lion.mission_control.cooperative_materialization_registry import (
    AUTHORITY_EFFECT,
    PROVIDER_ID,
    CooperativeMaterializationProvider,
    CooperativeMaterializationRegistry,
    CooperativeMaterializationRegistryError,
)


def write(_):
    return {"ok": True}


def verify(_):
    return {"ok": True}


class CooperativeMaterializationRegistryTests(unittest.TestCase):
    def test_missing_provider_is_non_authorizing_not_ready(self):
        registry=CooperativeMaterializationRegistry()
        self.assertIsNone(registry.current())
        self.assertEqual(registry.status(), {
            "state":"NOT_BOUND","provider_id":PROVIDER_ID,"authority_effect":"NONE",
        })
        with self.assertRaisesRegex(CooperativeMaterializationRegistryError,"not installed"):
            registry.require()

    def test_exact_provider_installs_once(self):
        registry=CooperativeMaterializationRegistry()
        provider=CooperativeMaterializationProvider(write,verify)
        self.assertIs(registry.install(provider),provider)
        self.assertIs(registry.current(),provider)
        self.assertEqual(registry.status(), {
            "state":"READY","provider_id":PROVIDER_ID,"authority_effect":AUTHORITY_EFFECT,
        })
        with self.assertRaisesRegex(CooperativeMaterializationRegistryError,"already installed"):
            registry.install(provider)

    def test_identity_or_authority_substitution_fails_closed(self):
        registry=CooperativeMaterializationRegistry()
        with self.assertRaisesRegex(CooperativeMaterializationRegistryError,"identity/authority"):
            registry.install(CooperativeMaterializationProvider(write,verify,provider_id="other"))
        with self.assertRaisesRegex(CooperativeMaterializationRegistryError,"identity/authority"):
            registry.install(CooperativeMaterializationProvider(write,verify,authority_effect="ALLOW"))

    def test_noncallable_materializer_is_rejected(self):
        with self.assertRaisesRegex(CooperativeMaterializationRegistryError,"callables"):
            CooperativeMaterializationProvider(None,verify).validate()


if __name__=="__main__":
    unittest.main()
