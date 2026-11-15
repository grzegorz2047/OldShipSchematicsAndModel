"""Exact-lookup adapter for the frozen guide auditor's concrete joint rules.

No geometric predicate or acceptance threshold is changed. Any pattern rule,
foreign design object or malformed pattern falls back to the original function.
The index is built for one immutable design during one quality call only.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import fnmatch
import json
from pathlib import Path
from types import SimpleNamespace
import time


def literal_index(design):
    result = {}
    rules = design.get('intended_joints', [])
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get('reason'):
            continue
        first, second = rule.get('a', ''), rule.get('b', '')
        if first in ('', '*') and second in ('', '*'):
            continue
        if not isinstance(first, str) or not isinstance(second, str) or any(
                c in first or c in second for c in '*?[]'):
            # A wildcard can precede an exact rule: using the dictionary for
            # only some pairs would violate the frozen first-reason semantics.
            return None
        result.setdefault(tuple(sorted((first, second))), rule['reason'])
    return result


@contextmanager
def indexed_joints(module, design):
    original = module.intended_joint
    start = time.perf_counter()
    index = literal_index(design)
    stats = {'rules': len(design.get('intended_joints', [])),
             'literal_pairs': len(index) if index is not None else None,
             'index_build_s': time.perf_counter()-start, 'indexed_queries': 0,
             'fallback_queries': 0, 'semantics': 'Frozen first-reason symmetric exact-name lookup; no geometry/threshold changes.'}

    def lookup(first, second, candidate):
        if candidate is design and index is not None and isinstance(first, str) and isinstance(second, str):
            stats['indexed_queries'] += 1
            return index.get(tuple(sorted((first, second))))
        stats['fallback_queries'] += 1
        return original(first, second, candidate)

    module.intended_joint = lookup
    try:
        yield stats
    finally:
        module.intended_joint = original


@contextmanager
def indexed_quality(v4):
    """Temporarily adapt only v4 quality calls made by the new v5 entry point."""
    original = v4.quality

    def quality(records, doc, structural, design, full_detail):
        start = time.perf_counter()
        with indexed_joints(v4.A, design) as stats:
            try:
                return original(records, doc, structural, design, full_detail)
            finally:
                print('V5_JOINT_INDEX', json.dumps({**stats, 'quality_wall_s': time.perf_counter()-start}), flush=True)

    v4.quality = quality
    try:
        yield
    finally:
        v4.quality = original


def frozen_function(root):
    """Use the exact frozen function in portable controls without Blender."""
    path = Path(root)/'sailertales/common/v2_audit.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'intended_joint')
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {'fnmatch': fnmatch}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace['intended_joint']


def self_test(root, design=None):
    original = frozen_function(root)
    design = design or {'intended_joints': [
        {'a':'member_%03d'%i, 'b':'support_%03d'%i, 'reason':'first literal reason %d'%i}
        for i in range(320)]}
    rules = [rule for rule in design.get('intended_joints', []) if isinstance(rule, dict)
             and rule.get('reason') and isinstance(rule.get('a'), str) and isinstance(rule.get('b'), str)]
    present = [(rule['a'], rule['b']) for rule in rules[:240]]
    absent = [('__definitely_absent_%04d'%i, pair[1]) for i, pair in enumerate(present)]
    pairs = present + [(b,a) for a,b in present] + absent
    if len(pairs) < 200:
        raise ValueError('At least 200 real/synthetic present, reversed and absent comparison pairs required')
    start = time.perf_counter()
    expected = [original(a,b,design) for a,b in pairs]
    original_s = time.perf_counter()-start
    module = SimpleNamespace(intended_joint=original)
    start = time.perf_counter()
    with indexed_joints(module, design) as stats:
        actual = [module.intended_joint(a,b,design) for a,b in pairs]
        # Identity, not equality, guards the immutability assumption.
        foreign = dict(design)
        if module.intended_joint(*pairs[0], foreign) != original(*pairs[0], foreign):
            raise ValueError('Foreign-design fallback changed semantics')
    indexed_s = time.perf_counter()-start
    if actual != expected or module.intended_joint is not original:
        raise ValueError('Exact joint index changed a real frozen result or was not restored')
    tests = [
        {'intended_joints':[{'a':'a','b':'b','reason':'first'}, {'a':'b','b':'a','reason':'second'}]},
        {'intended_joints':[{'a':'a*','b':'b','reason':'wildcard first'}, {'a':'a','b':'b','reason':'literal second'}]},
        {'intended_joints':[{'a':'a','b':'b','reason':'literal first'}, {'a':'a*','b':'b','reason':'wildcard second'}]},
        {'intended_joints':[{'a':'*','b':'*','reason':'ignored global'}, {'a':'a','b':'b','reason':'specific'}]},
        {'intended_joints':[None, {'a':'a','b':'b','reason':''}, {'a':'a','b':'b','reason':'first meaningful'}]},
    ]
    for candidate in tests:
        with indexed_joints(module, candidate):
            for a,b in [('a','b'), ('b','a'), ('absent','b'), ('abc','b'), ('a','absent')]:
                if module.intended_joint(a,b,candidate) != original(a,b,candidate):
                    raise ValueError('Duplicate/pattern/negative control changed first-reason semantics')
        if module.intended_joint is not original:
            raise ValueError('Original frozen lookup not restored')
    try:
        with indexed_joints(module, design):
            raise RuntimeError('synthetic quality exception')
    except RuntimeError:
        pass
    if module.intended_joint is not original:
        raise ValueError('Original lookup not restored after exception')
    return {'passed':True, 'comparison_pairs':len(pairs), 'actual_rules':len(rules),
            'original_lookup_s':original_s, 'indexed_total_s':indexed_s, 'indexed_stats':stats,
            'controls':['real present/reversed/absent pairs equal', 'duplicate first reason retained',
                        'wildcard before literal fallback equal', 'literal before wildcard fallback equal',
                        'global wildcard remains ignored', 'empty/malformed ignored rows equal',
                        'foreign design identity falls back', 'original restored after success and exception']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--design',type=Path)
    args=parser.parse_args()
    result=self_test(args.source_root,json.loads(args.design.read_text()) if args.design else None)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
