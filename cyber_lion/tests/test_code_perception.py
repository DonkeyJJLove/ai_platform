import hashlib
import unittest

from cyber_lion.contracts.code_perception import SourceIdentity
from cyber_lion.enterprise.code_perception import BlobInput, CodePerceptionBuildError, build_code_graph


def blob(path: str, data: bytes) -> BlobInput:
    framed = f"blob {len(data)}\0".encode() + data
    return BlobInput(path, hashlib.sha1(framed, usedforsecurity=False).hexdigest(), len(data), data)


def call_edges(graph, qname: str):
    source_id = next(s.node_id for s in graph.symbols if s.qualified_name == qname)
    return [e for e in graph.edges if e.edge_type == "CALLS" and e.source_node_id == source_id]


def assert_one_resolved_one_unresolved(testcase, graph, qname: str, resolved_target: str, unresolved_name: str):
    calls = call_edges(graph, qname)
    testcase.assertEqual(len(calls), 2)
    testcase.assertEqual(sum(e.target_node_id == resolved_target for e in calls), 1)
    testcase.assertEqual(sum(e.target_node_id is None and e.unresolved_target == unresolved_name for e in calls), 1)


class CodePerceptionExtractionTests(unittest.TestCase):
    def test_git_empty_blob_identity_uses_compatibility_sha1(self):
        object_id = hashlib.sha1(b"blob 0\0", usedforsecurity=False).hexdigest()
        self.assertEqual(object_id, "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def setUp(self):
        self.source = SourceIdentity("DonkeyJJLove/ai_platform", "1" * 40, "2" * 40).validate()

    def test_all_blobs_are_covered_and_python_is_deep_indexed(self):
        graph = build_code_graph(
            self.source,
            (
                blob("README.md", b"# x\n"),
                blob("pkg/__init__.py", b"from .b import helper\n"),
                blob("pkg/b.py", b"def helper():\n    return 1\n"),
                blob(
                    "pkg/a.py",
                    b"import pkg.b as b\nfrom pkg.b import helper\n\n"
                    b"class Base:\n    pass\n\nclass Child(Base):\n"
                    b"    def method(self):\n        return helper()\n\n"
                    b"def outer():\n    return b.helper()\n",
                ),
            ),
        )
        self.assertEqual(len(graph.files), 4)
        self.assertEqual({f.path for f in graph.files}, {"README.md", "pkg/__init__.py", "pkg/a.py", "pkg/b.py"})
        self.assertEqual(next(f for f in graph.files if f.path == "README.md").parse_state, "NOT_APPLICABLE")
        names = {s.qualified_name for s in graph.symbols}
        self.assertTrue({"pkg.a", "pkg.a.Base", "pkg.a.Child", "pkg.a.Child.method", "pkg.a.outer", "pkg.b", "pkg.b.helper"} <= names)
        edge_types = {e.edge_type for e in graph.edges}
        self.assertTrue({"CONTAINS", "DEFINES", "IMPORTS", "CALLS", "INHERITS"} <= edge_types)
        helper_id = next(s.node_id for s in graph.symbols if s.qualified_name == "pkg.b.helper")
        self.assertTrue(any(e.edge_type == "CALLS" and e.target_node_id == helper_id for e in graph.edges))
        outer_call = call_edges(graph, "pkg.a.outer")[0]
        self.assertIsNone(outer_call.target_node_id)
        self.assertEqual(outer_call.unresolved_target, "b.helper")
        base_id = next(s.node_id for s in graph.symbols if s.qualified_name == "pkg.a.Base")
        self.assertTrue(any(e.edge_type == "INHERITS" and e.target_node_id == base_id for e in graph.edges))

    def test_dynamic_or_unknown_calls_remain_unresolved(self):
        graph = build_code_graph(self.source, (blob("a.py", b"def f(x):\n    return getattr(x, 'm')()\n"),))
        calls = [e for e in graph.edges if e.edge_type == "CALLS"]
        self.assertTrue(calls)
        self.assertTrue(all(e.target_node_id is None for e in calls))
        self.assertTrue(any(e.unresolved_target == "getattr" for e in calls))

    def test_parameter_shadowing_does_not_resolve_module_function(self):
        graph = build_code_graph(
            self.source,
            (blob("a.py", b"def target():\n    return 1\n\ndef caller(target):\n    return target()\n"),),
        )
        calls = call_edges(graph, "a.caller")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0].target_node_id)
        self.assertEqual(calls[0].unresolved_target, "target")

    def test_local_assignment_and_lambda_shadowing_remain_unresolved(self):
        for source in (
            b"def target():\n    return 1\n\ndef caller():\n    target = other\n    return target()\n",
            b"def target():\n    return 1\n\ndef caller():\n    target = lambda: 1\n    return target()\n",
        ):
            graph = build_code_graph(self.source, (blob("a.py", source),))
            self.assertIsNone(call_edges(graph, "a.caller")[0].target_node_id)

    def test_nested_import_does_not_leak_and_attribute_call_stays_unresolved(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob(
                    "a.py",
                    b"def a():\n    import pkg.x as x\n    return x.f()\n\n"
                    b"def b():\n    return x.f()\n",
                ),
            ),
        )
        for qname in ("a.a", "a.b"):
            call = call_edges(graph, qname)[0]
            self.assertIsNone(call.target_node_id)
            self.assertEqual(call.unresolved_target, "x.f")

    def test_local_import_attribute_call_stays_unresolved_without_attribute_proof(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"def caller():\n    import pkg.x as x\n    return x.f()\n"),
            ),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "x.f")

    def test_local_import_after_call_is_not_guessed(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"def caller():\n    x.f()\n    import pkg.x as x\n"),
            ),
        )
        self.assertIsNone(call_edges(graph, "a.caller")[0].target_node_id)

    def test_nested_function_scope_shadowing_is_correct(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def target():\n    return 1\n\n"
                b"def outer():\n    def inner(target):\n        return target()\n    return target()\n",
            ),),
        )
        module_target = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        self.assertIsNone(call_edges(graph, "a.outer.inner")[0].target_node_id)
        self.assertEqual(call_edges(graph, "a.outer")[0].target_node_id, module_target)

    def test_explicit_global_binding_can_resolve_module_symbol(self):
        graph = build_code_graph(
            self.source,
            (blob("a.py", b"def target():\n    return 1\n\ndef caller():\n    global target\n    return target()\n"),),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        self.assertEqual(call_edges(graph, "a.caller")[0].target_node_id, target_id)

    def test_global_reassignment_is_not_guessed(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def target():\n    return 1\n\ndef caller():\n    global target\n    target = lambda: 2\n    return target()\n",
            ),),
        )
        self.assertIsNone(call_edges(graph, "a.caller")[0].target_node_id)

    def test_nonlocal_binding_is_not_guessed(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def outer():\n"
                b"    def target():\n        return 1\n"
                b"    def inner():\n        nonlocal target\n        return target()\n"
                b"    return inner()\n",
            ),),
        )
        self.assertIsNone(call_edges(graph, "a.outer.inner")[0].target_node_id)

    def test_known_unshadowed_module_and_imported_symbol_calls_resolve(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob(
                    "a.py",
                    b"from pkg.x import f\n\ndef target():\n    return 1\n\n"
                    b"def caller():\n    target()\n    return f()\n",
                ),
            ),
        )
        target_ids = {
            next(s.node_id for s in graph.symbols if s.qualified_name == "a.target"),
            next(s.node_id for s in graph.symbols if s.qualified_name == "pkg.x.f"),
        }
        self.assertEqual({e.target_node_id for e in call_edges(graph, "a.caller")}, target_ids)

    def test_self_method_without_visible_subclass_is_still_dynamic_dispatch(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    def target(self):\n        return 1\n"
                b"    def caller(self):\n        return self.target()\n",
            ),),
        )
        call = call_edges(graph, "a.C.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "self.target")

    def test_base_method_self_call_with_subclass_override_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    def target(self):\n        return 'C'\n"
                b"    def caller(self):\n        return self.target()\n\n"
                b"class D(C):\n"
                b"    def target(self):\n        return 'D'\n",
            ),),
        )
        c_target = next(s.node_id for s in graph.symbols if s.qualified_name == "a.C.target")
        d_target = next(s.node_id for s in graph.symbols if s.qualified_name == "a.D.target")
        call = call_edges(graph, "a.C.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertNotIn(call.target_node_id, {c_target, d_target})
        self.assertEqual(call.unresolved_target, "self.target")

    def test_inherited_method_dispatch_is_not_guessed(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class Base:\n"
                b"    def target(self):\n        return 1\n\n"
                b"class Child(Base):\n"
                b"    def caller(self):\n        return self.target()\n",
            ),),
        )
        call = call_edges(graph, "a.Child.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "self.target")

    def test_self_static_looking_method_is_not_assumed_final(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    @staticmethod\n"
                b"    def target():\n        return 1\n"
                b"    def caller(self):\n        return self.target()\n",
            ),),
        )
        call = call_edges(graph, "a.C.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "self.target")

    def test_cls_attribute_dispatch_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    @classmethod\n"
                b"    def target(cls):\n        return 1\n"
                b"    @classmethod\n"
                b"    def caller(cls):\n        return cls.target()\n",
            ),),
        )
        call = call_edges(graph, "a.C.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "cls.target")

    def test_class_qualified_call_without_attribute_proof_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    def target(self):\n        return 1\n\n"
                b"def caller(obj):\n    return C.target(obj)\n",
            ),),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "C.target")

    def test_class_method_reassigned_before_call_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    def target(self):\n        return 'original'\n\n"
                b"def replacement(obj):\n    return 'replacement'\n\n"
                b"C.target = replacement\n\n"
                b"def caller(obj):\n    return C.target(obj)\n",
            ),),
        )
        call = call_edges(graph, "a.caller")[0]
        original = next(s.node_id for s in graph.symbols if s.qualified_name == "a.C.target")
        replacement = next(s.node_id for s in graph.symbols if s.qualified_name == "a.replacement")
        self.assertIsNone(call.target_node_id)
        self.assertNotIn(call.target_node_id, {original, replacement})
        self.assertEqual(call.unresolved_target, "C.target")

    def test_class_method_reassigned_inside_caller_before_call_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    def target(self):\n        return 'original'\n\n"
                b"def replacement(obj):\n    return 'replacement'\n\n"
                b"def caller(obj):\n    C.target = replacement\n    return C.target(obj)\n",
            ),),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "C.target")

    def test_staticmethod_reassigned_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    @staticmethod\n"
                b"    def target():\n        return 1\n\n"
                b"def replacement():\n    return 2\n"
                b"C.target = replacement\n"
                b"def caller():\n    return C.target()\n",
            ),),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "C.target")

    def test_classmethod_reassigned_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class C:\n"
                b"    @classmethod\n"
                b"    def target(cls):\n        return 1\n\n"
                b"def replacement():\n    return 2\n"
                b"C.target = replacement\n"
                b"def caller():\n    return C.target()\n",
            ),),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "C.target")

    def test_descriptor_bearing_class_attribute_call_is_unresolved(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"class Descriptor:\n"
                b"    def __get__(self, obj, owner):\n        return lambda: 1\n\n"
                b"class C:\n"
                b"    target = Descriptor()\n\n"
                b"def caller():\n    return C.target()\n",
            ),),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "C.target")

    def test_lambda_parameter_shadowing_parent_global_is_anonymous_barrier(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def target():\n    return 1\n\n"
                b"def caller():\n    target()\n    f = lambda target: target()\n    return f\n",
            ),),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        assert_one_resolved_one_unresolved(self, graph, "a.caller", target_id, "target")

    def test_lambda_parameter_shadowing_parent_import_is_anonymous_barrier(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"from pkg.x import f\n\ndef caller():\n    f()\n    return (lambda f: f())\n"),
            ),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "pkg.x.f")
        assert_one_resolved_one_unresolved(self, graph, "a.caller", target_id, "f")

    def test_lambda_inner_call_never_falls_back_to_parent_local_definition(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def caller():\n"
                b"    def target():\n        return 1\n"
                b"    target()\n"
                b"    return (lambda: target())\n",
            ),),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.caller.target")
        assert_one_resolved_one_unresolved(self, graph, "a.caller", target_id, "target")

    def _assert_comprehension_barrier(self, expression: bytes):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def target():\n    return 1\n\n"
                b"def caller(xs):\n    target()\n    return " + expression + b"\n",
            ),),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        assert_one_resolved_one_unresolved(self, graph, "a.caller", target_id, "target")

    def test_listcomp_target_shadowing_is_anonymous_barrier(self):
        self._assert_comprehension_barrier(b"[target() for target in xs]")

    def test_setcomp_target_shadowing_is_anonymous_barrier(self):
        self._assert_comprehension_barrier(b"{target() for target in xs}")

    def test_dictcomp_target_shadowing_is_anonymous_barrier(self):
        self._assert_comprehension_barrier(b"{target(): target for target in xs}")

    def test_genexpr_target_shadowing_is_anonymous_barrier(self):
        self._assert_comprehension_barrier(b"(target() for target in xs)")

    def test_anonymous_scope_fallback_never_resolves_parent_symbol(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"def target():\n    return 1\n\n"
                b"def caller(xs):\n"
                b"    outer = target()\n"
                b"    inner = [target() for target in xs]\n"
                b"    nested = (lambda target: target())\n"
                b"    return outer, inner, nested\n",
            ),),
        )
        calls = call_edges(graph, "a.caller")
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.target")
        self.assertEqual(sum(e.target_node_id == target_id for e in calls), 1)
        self.assertEqual(sum(e.target_node_id is None and e.unresolved_target == "target" for e in calls), 2)

    def test_if_false_definition_is_symbol_but_not_exact_runtime_binding(self):
        graph = build_code_graph(
            self.source,
            (blob(
                "a.py",
                b"if False:\n"
                b"    def target():\n        return 1\n\n"
                b"def caller():\n    return target()\n",
            ),),
        )
        self.assertTrue(any(s.qualified_name == "a.target" for s in graph.symbols))
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "target")

    def test_conditional_from_import_is_not_exact_binding(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"def caller(flag):\n    if flag:\n        from pkg.x import f\n    return f()\n"),
            ),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "f")

    def test_loop_bound_import_is_not_exact_binding(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"def caller(xs):\n    for _ in xs:\n        from pkg.x import f\n    return f()\n"),
            ),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "f")

    def test_try_bound_import_is_not_exact_binding(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob(
                    "a.py",
                    b"def caller():\n"
                    b"    try:\n        from pkg.x import f\n"
                    b"    except Exception:\n        pass\n"
                    b"    return f()\n",
                ),
            ),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "f")

    def test_match_bound_import_is_not_exact_binding(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob(
                    "a.py",
                    b"def caller(value):\n"
                    b"    match value:\n"
                    b"        case 1:\n            from pkg.x import f\n"
                    b"    return f()\n",
                ),
            ),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "f")

    def test_with_bound_import_is_not_exact_binding(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"def caller(cm):\n    with cm:\n        from pkg.x import f\n    return f()\n"),
            ),
        )
        call = call_edges(graph, "a.caller")[0]
        self.assertIsNone(call.target_node_id)
        self.assertEqual(call.unresolved_target, "f")

    def test_direct_unconditional_local_definition_may_resolve(self):
        graph = build_code_graph(
            self.source,
            (blob("a.py", b"def caller():\n    def target():\n        return 1\n    return target()\n"),),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "a.caller.target")
        self.assertEqual(call_edges(graph, "a.caller")[0].target_node_id, target_id)

    def test_direct_unconditional_local_from_import_may_resolve(self):
        graph = build_code_graph(
            self.source,
            (
                blob("pkg/x.py", b"def f():\n    return 1\n"),
                blob("a.py", b"def caller():\n    from pkg.x import f\n    return f()\n"),
            ),
        )
        target_id = next(s.node_id for s in graph.symbols if s.qualified_name == "pkg.x.f")
        self.assertEqual(call_edges(graph, "a.caller")[0].target_node_id, target_id)

    def test_malformed_python_is_explicit_not_silently_dropped(self):
        graph = build_code_graph(self.source, (blob("bad.py", b"def broken(:\n"), blob("x.txt", b"x")))
        bad = next(f for f in graph.files if f.path == "bad.py")
        self.assertTrue(bad.parse_state.startswith("PARSE_ERROR:"))
        self.assertEqual(len(graph.files), 2)
        self.assertFalse(any(s.path == "bad.py" for s in graph.symbols))

    def test_symbol_identity_survives_content_change_but_semantic_digest_changes(self):
        one = build_code_graph(self.source, (blob("a.py", b"def f():\n    return 1\n"),))
        two = build_code_graph(self.source, (blob("a.py", b"def f():\n    return 2\n"),))
        s1 = next(s for s in one.symbols if s.qualified_name == "a.f")
        s2 = next(s for s in two.symbols if s.qualified_name == "a.f")
        self.assertEqual(s1.node_id, s2.node_id)
        self.assertNotEqual(s1.semantic_digest, s2.semantic_digest)

    def test_rename_changes_symbol_identity(self):
        one = build_code_graph(self.source, (blob("a.py", b"def f():\n    return 1\n"),))
        two = build_code_graph(self.source, (blob("renamed.py", b"def f():\n    return 1\n"),))
        s1 = next(s for s in one.symbols if s.qualified_name == "a.f")
        s2 = next(s for s in two.symbols if s.qualified_name == "renamed.f")
        self.assertNotEqual(s1.node_id, s2.node_id)

    def test_blob_substitution_fails_closed(self):
        item = blob("a.py", b"x = 1\n")
        corrupted = BlobInput(item.path, item.blob_sha, item.size, b"x = 2\n")
        with self.assertRaisesRegex(CodePerceptionBuildError, "blob substitution"):
            build_code_graph(self.source, (corrupted,))

    def test_duplicate_path_fails_closed(self):
        item = blob("a.py", b"x = 1\n")
        with self.assertRaisesRegex(CodePerceptionBuildError, "duplicate blob path"):
            build_code_graph(self.source, (item, item))


if __name__ == "__main__":
    unittest.main()
