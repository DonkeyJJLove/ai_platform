from __future__ import annotations

import ast
from pathlib import Path
import unittest


class MoonFileWriteFalsificationTests(unittest.TestCase):
    def test_workflow_invokes_only_canonical_module_and_no_checkout(self):
        source=Path(".github/workflows/moon-file-write.yml").read_text(encoding="utf-8")
        self.assertIn("python3 -m cyber_lion.enterprise.moon_file_write",source)
        self.assertNotIn("actions/checkout",source)
        self.assertNotIn("MOON-FILE-WRITE v1",source)
        for token in ("git push","gh api","curl -X","Invoke-RestMethod"):
            self.assertNotIn(token,source)

    def test_selected_host_write_calls_are_confined_to_exact_provider(self):
        path=Path("cyber_lion/enterprise/moon_file_write.py")
        tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        parents={}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node): parents[child]=node
        interesting=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call): continue
            func=node.func
            name=""
            if isinstance(func,ast.Attribute):
                left=func.value.id if isinstance(func.value,ast.Name) else ""
                name=f"{left}.{func.attr}" if left else func.attr
            if name in {"os.write","os.replace","os.link"}:
                cur=node; owner=None
                while cur in parents:
                    cur=parents[cur]
                    if isinstance(cur,(ast.FunctionDef,ast.AsyncFunctionDef)):
                        owner=cur.name; break
                interesting.append((name,owner))
        self.assertTrue(interesting)
        self.assertTrue(all(owner=="write_exact" for _,owner in interesting),interesting)

    def test_no_generic_atomic_write_helper_remains(self):
        source=Path("cyber_lion/enterprise/moon_file_write.py").read_text(encoding="utf-8")
        self.assertNotIn("def _atomic_write",source)
        self.assertNotIn("def write_anywhere",source)

    def test_public_effect_signature_is_exact(self):
        tree=ast.parse(Path("cyber_lion/enterprise/moon_file_write.py").read_text(encoding="utf-8"))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="ExactMoonFileWriteEffectProvider")
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="write_exact")
        self.assertEqual([a.arg for a in fn.args.args],["self","request","admission"])

    def test_fence_and_observer_are_separate_from_effect_provider(self):
        source=Path("cyber_lion/enterprise/moon_file_write_mediation.py").read_text(encoding="utf-8")
        self.assertIn("class DurableMoonFileWriteFence",source)
        self.assertIn("class MoonFileWriteObserver",source)
        self.assertIn("class CanonicalMoonFileWriteMediator",source)
        self.assertIn("PREPARED",source); self.assertIn("ATTEMPTED",source); self.assertIn("RECONCILED",source)

    def test_fence_has_no_generic_dynamic_transition_builder(self):
        path=Path("cyber_lion/enterprise/moon_file_write_mediation.py")
        tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        fence=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="DurableMoonFileWriteFence")
        names={n.name for n in fence.body if isinstance(n,ast.FunctionDef)}
        self.assertNotIn("_transition",names)
        for forbidden in ("old","new","assignments","values"):
            for fn in (n for n in fence.body if isinstance(n,ast.FunctionDef)):
                self.assertNotIn(forbidden,[a.arg for a in fn.args.args],(fn.name,forbidden))

    def test_update_sql_in_fence_is_static_literal_only(self):
        path=Path("cyber_lion/enterprise/moon_file_write_mediation.py")
        tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        update_calls=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute) or node.func.attr!="execute" or not node.args:
                continue
            first=node.args[0]
            text=""
            if isinstance(first,ast.Constant) and isinstance(first.value,str):
                text=first.value
            elif isinstance(first,ast.BinOp) and isinstance(first.op,ast.Add):
                parts=[]
                stack=[first]
                while stack:
                    item=stack.pop(0)
                    if isinstance(item,ast.BinOp) and isinstance(item.op,ast.Add):
                        stack[0:0]=[item.left,item.right]
                    elif isinstance(item,ast.Constant) and isinstance(item.value,str):
                        parts.append(item.value)
                    else:
                        parts=[]; break
                text="".join(parts)
            if "UPDATE moon_file_write_effect" in text:
                update_calls.append(first)
        self.assertEqual(len(update_calls),4)
        for expr in update_calls:
            for node in ast.walk(expr):
                self.assertNotIsInstance(node,(ast.JoinedStr,ast.FormattedValue,ast.Call),ast.dump(expr))


if __name__ == "__main__": unittest.main()
