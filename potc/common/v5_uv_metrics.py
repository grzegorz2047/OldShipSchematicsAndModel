"""Batched implementation of the frozen v2 UV equations, for v5 imports only.

No decision threshold, UV transform, material choice or triangle order changes.
The frozen implementation remains the fallback for singular batched algebra.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import json
import math
import time

import numpy as np


def _grain(obj, module, world):
    from mathutils import Vector
    covariance = np.cov(world.T) if len(world) > 2 else np.eye(3)
    values, vectors = np.linalg.eigh(covariance)
    axis = vectors[:, -1]
    elongated = values[-1] >= 2.5 ** 2 * max(values[-2], 1e-12)
    path = []
    authored = obj.get('grain_path_json')
    if authored:
        try:
            data = json.loads(authored) if isinstance(authored, str) else authored
            axes = data.get('axes', 'object_local') if isinstance(data, dict) else 'object_local'
            points = data.get('points', []) if isinstance(data, dict) else data
            if axes.lower() in ('gltf', 'gltf_world'):
                path = [np.array(module.ship_to_blender(q), dtype=float) for q in points]
            elif axes.lower() in ('blender', 'blender_world', 'world'):
                path = [np.array(q, dtype=float) for q in points]
            else:
                path = [np.array(obj.matrix_world @ Vector(q), dtype=float) for q in points]
        except (TypeError, ValueError, KeyError):
            path = []
    return axis, elongated, path


def _tangents(centers, axis, path):
    """Ordered strict-nearer update; ambiguous floating ties use frozen scalar math."""
    result = np.broadcast_to(axis, centers.shape).copy()
    best = np.full(len(centers), np.inf)
    second = np.full(len(centers), np.inf)
    segments = []
    for a, b in zip(path, path[1:]):
        ab = b - a
        length = float(np.linalg.norm(ab))
        if length < 1e-10:
            continue
        segments.append((a, ab, length))
        t = np.clip(np.dot(centers - a, ab) / (length * length), 0, 1)
        distance = np.linalg.norm(centers - (a + t[:, None] * ab), axis=1)
        nearer = distance < best
        second = np.where(nearer, best, np.minimum(second, distance))
        best = np.where(nearer, distance, best)
        result[nearer] = ab / length
    finite = np.isfinite(second)
    ambiguous = np.flatnonzero(finite)
    ambiguous = ambiguous[(second[finite] - best[finite]) <= 1e-12 * np.maximum(1., best[finite])]
    for i in ambiguous:
        nearest = None
        for a, ab, length in segments:
            t = max(0, min(1, float(np.dot(centers[i] - a, ab)) / (length * length)))
            distance = float(np.linalg.norm(centers[i] - (a + ab * t)))
            if nearest is None or distance < nearest[0]:
                nearest = (distance, ab / length)
        result[i] = nearest[1] if nearest else axis
    return result


def _rows_dot(a, b):
    return np.einsum('ij,ij->i', a, b)


def uv_metrics(obj, module, original):
    me = obj.data
    if not me.uv_layers:
        return {'missing_uv': True, 'materials': {}}
    layer = me.uv_layers.active.data
    stats = defaultdict(lambda: {'density': [], 'anisotropy': [], 'area': [],
                                 'degenerate_uv_area_m2': 0.0,
                                 'grain_area': 0.0, 'grain_aligned_area': 0.0})
    # Keep exact Blender matrix/vector evaluation used by the frozen auditor.
    world = np.array([tuple(obj.matrix_world @ v.co) for v in me.vertices], dtype=np.float64)
    axis, elongated, path = _grain(obj, module, world)
    material_info = {}
    groups = {}
    for order, tri in enumerate(me.loop_triangles):
        index = tri.material_index
        if index not in material_info:
            mat = me.materials[index] if index < len(me.materials) else None
            images = [n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image] if mat is not None and mat.use_nodes else []
            color = [im for im in images if any(s in im.name.lower() for s in ('color', 'colour', 'kolor', 'albedo', 'base'))]
            if not color:
                color = [im for im in images if im.colorspace_settings.name == 'sRGB']
            material_info[index] = (mat, color[0]) if color else None
        info = material_info[index]
        if info is None:
            continue
        mat, image = info
        groups.setdefault(mat.name, {'mat': mat, 'image': image, 'vertices': [], 'loops': [], 'order': []})
        group = groups[mat.name]
        group['vertices'].append(tuple(tri.vertices))
        group['loops'].append(tuple(tri.loops))
        group['order'].append(order)
    all_uv = np.array([tuple(item.uv) for item in layer], dtype=np.float64)
    first_valid_order = {}
    for name, group in groups.items():
        pts = world[np.asarray(group['vertices'], dtype=np.int64)]
        e1, e2 = pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0]
        cross = np.cross(e1, e2)
        double = np.linalg.norm(cross, axis=1)
        area = double / 2
        valid = area >= 1e-12
        if not np.any(valid):
            continue
        first_valid_order[name] = group['order'][int(np.flatnonzero(valid)[0])]
        pts, e1, e2, cross, double, area = [a[valid] for a in (pts, e1, e2, cross, double, area)]
        uv = all_uv[np.asarray(group['loops'], dtype=np.int64)[valid]]
        edges = np.stack((uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]), axis=2)
        uv_area = np.abs(np.linalg.det(edges)) / 2
        collapsed = uv_area < 1e-14
        density = np.zeros(len(area), dtype=float)
        anisotropy = np.full(len(area), 1e12, dtype=float)
        measured_grain = np.zeros(len(area), dtype=bool)
        aligned = np.zeros(len(area), dtype=bool)
        good = ~collapsed
        width, height = group['image'].size
        density[good] = np.sqrt(uv_area[good] * width * height / area[good])
        if np.any(good):
            q1, q2, qcross, qdouble = e1[good], e2[good], cross[good], double[good]
            a1 = q1 / np.maximum(np.linalg.norm(q1, axis=1), 1e-20)[:, None]
            normal = qcross / qdouble[:, None]
            a2 = np.cross(normal, a1)
            domain = np.stack((np.stack((_rows_dot(q1, a1), _rows_dot(q2, a1)), axis=1),
                               np.stack((_rows_dot(q1, a2), _rows_dot(q2, a2)), axis=1)), axis=1)
            try:
                physical = edges[good] @ np.linalg.inv(domain)
                pixel = np.diag((width, height)) @ physical
                singular = np.linalg.svd(pixel, compute_uv=False)
                anisotropy[good] = singular[:, 0] / np.maximum(singular[:, 1], 1e-12)
                local = _tangents(pts[good].mean(axis=1), axis, path)
                if (elongated or len(path) > 1) and any(s in name.lower() for s in ('wood', 'oak', 'pine', 'drew', 'deck', 'poklad', 'plank')):
                    measure = np.abs(_rows_dot(normal, local)) < .5
                    if np.any(measure):
                        # Frozen solve accepts one RHS per 2x2 physical Jacobian.
                        rhs = np.broadcast_to(np.array([1., 0.]), (int(measure.sum()), 2))
                        u_domain = np.linalg.solve(physical[measure], rhs[..., None])[..., 0]
                        u_world = a1[measure] * u_domain[:, :1] + a2[measure] * u_domain[:, 1:]
                        cosine = np.abs(_rows_dot(u_world, local[measure])) / np.maximum(np.linalg.norm(u_world, axis=1), 1e-12)
                        locations = np.flatnonzero(good)[measure]
                        measured_grain[locations] = True
                        aligned[locations] = cosine >= math.cos(math.radians(25))
            except np.linalg.LinAlgError:
                # A singular batch is uncommon. Preserve all scalar exception
                # boundaries by delegating the complete object unchanged.
                return original(obj)
        st = stats[name]
        st['density'] = density.tolist()
        st['anisotropy'] = anisotropy.tolist()
        st['area'] = area.tolist()
        # Python sum retains frozen triangle-order accumulation for each subset.
        st['degenerate_uv_area_m2'] = sum(area[collapsed].tolist())
        st['grain_area'] = sum(area[measured_grain].tolist())
        st['grain_aligned_area'] = sum(area[aligned].tolist())
    ordered = {name: stats[name] for name in sorted(stats, key=first_valid_order.get)}
    return {'missing_uv': False, 'materials': ordered}


@contextmanager
def vectorized_uv(module):
    original = module.uv_metrics
    stats = {'objects': 0, 'wall_s': 0., 'scalar_fallbacks': 0}

    def fallback(obj):
        stats['scalar_fallbacks'] += 1
        return original(obj)

    def batched(obj):
        start = time.perf_counter()
        stats['objects'] += 1
        try:
            return uv_metrics(obj, module, fallback)
        finally:
            stats['wall_s'] += time.perf_counter() - start

    module.uv_metrics = batched
    try:
        yield stats
    finally:
        module.uv_metrics = original


@contextmanager
def vectorized_records(v4):
    """Patch only frozen uv_metrics calls made during frozen object_records."""
    module = v4.A
    original = module.object_records

    def records(*args, **kwargs):
        with vectorized_uv(module) as stats:
            try:
                return original(*args, **kwargs)
            finally:
                print('V5_UV_METRICS', json.dumps(stats), flush=True)

    module.object_records = records
    try:
        yield
    finally:
        module.object_records = original
