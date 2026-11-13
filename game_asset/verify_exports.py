"""Reimport the actual game GLBs and repeat rope/canvas intersection checks.

blender -b --factory-startup --python-exit-code 1 --python game_asset/verify_exports.py -- build/game_ship
"""
from pathlib import Path
import hashlib
import json
import sys

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
from rigging_collisions import audit_scene


def main(folder):
    folder=Path(folder).resolve()
    report={"blender":bpy.app.version_string,"models":{}}
    for level,filename in (("lod0","snow_sailing.glb"),("lod1","snow_sailing_lod1.glb"),("lod2","snow_sailing_lod2.glb")):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=folder/filename
        bpy.ops.import_scene.gltf(filepath=str(path))
        frames=tuple(range(0,97,12)) if level=="lod0" else (0,)
        check=audit_scene(frames=frames)
        check["source_glb_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
        (folder/("export_rigging_collisions_"+level+".json")).write_text(json.dumps(check,indent=2))
        if not check["passed"]:
            raise RuntimeError("Exported "+level+" contains rope/canvas intersections")
        report["models"][level]={"passed":True,"frames":list(frames),"sails":check["sails"],"rope_objects":check["rope_objects"],"source_glb_sha256":check["source_glb_sha256"]}
        if level=="lod0":
            sails=[o for o in bpy.data.objects if o.name.endswith("_set")]
            assert len(sails)==12
            for obj in sails:
                assert set(k.name for k in obj.data.shape_keys.key_blocks)=={"Basis","wind_port","wind_starboard"}
            weights={}
            for frame in (0,24,72,96):
                bpy.context.scene.frame_set(frame)
                sums=[sum(abs(k.value) for k in o.data.shape_keys.key_blocks if k.name!="Basis") for o in sails]
                weights[frame]=[round(min(sums),5),round(max(sums),5)]
            assert weights[0][1]<1e-5 and weights[96][1]<1e-5
            assert weights[24][0]>.5 and weights[72][0]>.5
            report["animation_key_weight_sum_by_frame"]=weights
    report["result"]="passed"
    (folder/"native_import_validation.json").write_text(json.dumps(report,indent=2))
    print("VERIFIED_EXPORTED_GLB",json.dumps(report),flush=True)


if __name__=="__main__":
    main(sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "build/game_ship")
