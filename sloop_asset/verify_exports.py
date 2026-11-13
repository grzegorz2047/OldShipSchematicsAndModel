"""Validate the delivered sloop GLBs, not just the authoring scene.
blender -b --factory-startup --python-exit-code 1 --python sloop_asset/verify_exports.py -- build/sloop_1715
"""

from pathlib import Path
import hashlib, json, sys
import bpy, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit import audit_scene
from glb_io import validate
from build_sloop import Deck, PR, rzedne, kadlub
from check_asset import source_hashes, sha256


def clearance(deck, frames):
    results = []
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        mins = {}
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            # Material selection also works after LOD meshes have been merged.
            canvas = {
                i
                for i, m in enumerate(obj.data.materials)
                if m and m.name.startswith("flax_")
            }
            is_boom = obj.name == "boom_timber"
            if not canvas and not is_boom:
                continue
            ev = obj.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            samples = []
            for tri in me.loop_triangles:
                if not is_boom and tri.material_index not in canvas:
                    continue
                p = [obj.matrix_world @ me.vertices[i].co for i in tri.vertices]
                # Vertices, edge midpoints and centroid, on evaluated export triangles.
                samples.extend(
                    [
                        *p,
                        *[(a + b) / 2 for a, b in zip(p, p[1:] + p[:1])],
                        sum(p, p[0] * 0) / 3,
                    ]
                )
            ev.to_mesh_clear()
            if not samples:
                continue
            a = np.array(samples)
            x = a[:, 0]
            s = -a[:, 1]
            w = deck.width(s)
            inside = (s > deck.ss[0]) & (s < deck.ss[-1]) & (abs(x) < w - 0.1)
            if inside.any():
                mins[obj.name] = round(
                    float(np.min(a[inside, 2] - deck.heights(x[inside], s[inside]))), 4
                )
        results.append({"frame": frame, "minimum_by_mesh_m": mins})
    minimum = min(v for frame in results for v in frame["minimum_by_mesh_m"].values())
    assert minimum >= 2.2, ("canvas/boom clearance", minimum)
    return {
        "passed": True,
        "minimum_m": minimum,
        "samples": "vertices, three edge midpoints and centroid of each evaluated triangle over the working deck",
        "per_frame": results,
    }


def main(folder):
    folder = Path(folder).resolve()
    kd = rzedne.Kadlub(PR.KADLUB, PR.RZEDNE_H, PR.RZEDNE_S, PR.RZEDNE)
    deck = Deck(kadlub.Poszycie(kd, PR.KADLUB), kd)
    report = {
        "blender": bpy.app.version_string,
        "models": {},
        "scope": "Authored sail trim and wind morph loop only. No full boom rotation or dynamic rope simulation.",
    }
    manifest = json.loads((folder / "asset_manifest.json").read_text())
    assert manifest["source_file_sha256"] == source_hashes(Path(__file__).resolve().parents[1]), "Build sources changed; rebuild before verifying"
    report["source_file_sha256"] = manifest["source_file_sha256"]
    for key, filename in [
        ("lod0", "sloop_1715.glb"),
        ("lod1", "sloop_1715_lod1.glb"),
        ("lod2", "sloop_1715_lod2.glb"),
        ("collision", "sloop_1715_collision.glb"),
    ]:
        path = folder / filename
        g, b, triangles = validate(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert not any(n.get("name", "").startswith("preview_") for n in g["nodes"])
        if key == "collision":
            assert len(g.get("images", [])) == 0
            assert (
                len([n for n in g["nodes"] if "mesh" in n])
                == manifest["collision_objects"]
            )
            report["models"][key] = {
                "sha256": sha,
                "triangles": triangles,
                "result": "passed",
            }
            continue
        assert triangles == manifest["triangles"][key], (
            key,
            triangles,
            manifest["triangles"][key],
        )
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
        frames = tuple(range(0, 97, 12)) if key == "lod0" else (0,)
        rig = audit_scene(frames=frames)
        rig["source_glb_sha256"] = sha
        (folder / ("export_rigging_" + key + ".json")).write_text(
            json.dumps(rig, indent=2)
        )
        assert rig["passed"], ("rope/canvas intersections", key, rig["hits"][:2])
        clear = clearance(deck, frames)
        clear["source_glb_sha256"] = sha
        (folder / ("export_clearance_" + key + ".json")).write_text(
            json.dumps(clear, indent=2)
        )
        if key == "lod0":
            sails = [
                o
                for o in bpy.data.objects
                if o.type == "MESH" and o.name.endswith("_set")
            ]
            assert len(sails) == 3
            for sail in sails:
                assert {k.name for k in sail.data.shape_keys.key_blocks} == {
                    "Basis",
                    "wind_port",
                    "wind_starboard",
                }
            values = {}
            for frame in (0, 24, 72, 96):
                bpy.context.scene.frame_set(frame)
                values[frame] = [
                    round(
                        sum(
                            abs(k.value)
                            for k in o.data.shape_keys.key_blocks
                            if k.name != "Basis"
                        ),
                        4,
                    )
                    for o in sails
                ]
            assert max(values[0]) < 1e-5 and max(values[96]) < 1e-5
            assert min(values[24]) > 0.5 and min(values[72]) > 0.5
            report["wind_animation_weights"] = values
            assert len([n for n in g["nodes"] if n.get("name") == "main_mast"]) == 1
            assert (
                len(
                    [
                        n
                        for n in g["nodes"]
                        if n.get("name", "").startswith("gun_")
                        and n.get("name", "").endswith("_recoil")
                    ]
                )
                == 4
            )
            # The 3-pounders point outboard on both sides of the working deck.
            bpy.context.scene.frame_set(0)
            for obj in bpy.data.objects:
                if not obj.name.endswith("_hollow_barrel"):
                    continue
                points = [obj.matrix_world @ v.co for v in obj.data.vertices]
                xs = [p.x for p in points]
                s = -sum(p.y for p in points) / len(points)
                outboard = max(xs) if obj.name.startswith("port_") else -min(xs)
                assert outboard > float(deck.width(s)) + 0.15, (
                    obj.name,
                    outboard,
                    deck.width(s),
                )
        report["models"][key] = {
            "sha256": sha,
            "triangles": triangles,
            "embedded_images": len(g.get("images", [])),
            "minimum_headroom_m": clear["minimum_m"],
            "audit_frames": list(frames),
            "result": "passed",
        }
    assert (
        report["models"]["lod0"]["triangles"]
        > report["models"]["lod1"]["triangles"]
        > report["models"]["lod2"]["triangles"]
    )
    report["result"] = "passed"
    data_files = ["asset_manifest.json", "deck_access.json", "deck_layout.json", "workstations.json", "rigging_paths.json", "sail_measurements.json", "build_summary.json"]
    data_files += ["export_" + kind + "_" + level + ".json" for kind in ("rigging", "clearance") for level in ("lod0", "lod1", "lod2")]
    report["data_file_sha256"] = {name: sha256(folder / name) for name in data_files}
    (folder / "native_import_validation.json").write_text(json.dumps(report, indent=2))
    print("VERIFIED_SLOOP_EXPORTS", json.dumps(report), flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "build/sloop_1715")
