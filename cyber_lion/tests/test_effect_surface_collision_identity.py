import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner


class EffectSurfaceCollisionIdentityTests(unittest.TestCase):
    def scan(self, source):
        return EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={"cyber_lion/x.py": source},
        )

    def test_same_line_mutating_sql_calls_keep_distinct_surfaces(self):
        compact = self.scan(
            "def f(conn):\n"
            "    conn.execute('UPDATE t SET x=1'); conn.execute('DELETE FROM t')\n"
        )
        expanded = self.scan(
            "def f(conn):\n"
            "    conn.execute('UPDATE t SET x=1')\n"
            "    conn.execute('DELETE FROM t')\n"
        )
        self.assertEqual(len(compact.surfaces), 2)
        self.assertEqual(len(expanded.surfaces), 2)
        refs = sorted(ref for surface in compact.surfaces for ref in surface.entrypoints)
        self.assertIn("cyber_lion/x.py:2:conn.execute", refs)
        self.assertEqual(
            sum(ref.startswith("cyber_lion/x.py:2:conn.execute:col-") for ref in refs),
            1,
        )
        self.assertEqual(len({surface.surface_id for surface in compact.surfaces}), 2)

    def test_same_line_dynamic_sql_calls_keep_distinct_unclassified_refs(self):
        inv = self.scan(
            "def f(conn,a,b):\n"
            "    conn.execute(a); conn.execute(b)\n"
        )
        self.assertFalse(inv.surfaces)
        self.assertEqual(len(inv.unclassified_refs), 2)
        self.assertIn("cyber_lion/x.py:2:conn.execute:dynamic-sql", inv.unclassified_refs)
        self.assertEqual(
            sum(
                ref.startswith("cyber_lion/x.py:2:conn.execute:dynamic-sql:col-")
                for ref in inv.unclassified_refs
            ),
            1,
        )

    def test_mutating_sql_fstring_with_literal_verb_is_classified(self):
        inv = self.scan(
            "def f(conn,name,ddl):\n"
            "    conn.execute(f'ALTER TABLE t ADD COLUMN {name} {ddl}')\n"
        )
        self.assertEqual(len(inv.surfaces), 1)
        self.assertEqual(inv.surfaces[0].effect_class, "persistent_state.write")
        self.assertFalse(inv.unclassified_refs)

    def test_sql_fstring_with_dynamic_verb_remains_unclassified(self):
        inv = self.scan(
            "def f(conn,verb,name):\n"
            "    conn.execute(f'{verb} t SET x={name}')\n"
        )
        self.assertFalse(inv.surfaces)
        self.assertEqual(len(inv.unclassified_refs), 1)
        self.assertIn("dynamic-sql", inv.unclassified_refs[0])


if __name__ == "__main__":
    unittest.main()
