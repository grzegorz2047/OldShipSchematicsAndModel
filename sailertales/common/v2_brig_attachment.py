"""Finish the brig's inspected clew/luff and railing-eye attachments."""
import json
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _world(q):return Vector((q[0],-q[2],q[1]))
def _gltf(q):return [q.x,q.z,-q.y]


def finish(objects,design,out=None):
    names={o.name:o for o in objects}
    def find(*candidates):
        return next((names[n] for n in candidates if n in names),None)
    eye=find('sheet_eye_14');rope=find('jib_sheet')
    if eye is None or rope is None:raise RuntimeError('Inspected jib eye and sheet missing')
    if not design.get('brig_jib_eye_relocation'):
        rails=[o for o in objects if o.type=='MESH' and (o.name=='kadlub_reling' or o.name=='hull_rail' or
            o.name.startswith('hull_rail_timber_') or o.get('source_assembly')=='kadlub_reling')]
        old=eye.matrix_world.translation.copy();new_y=old.y+.35;section=[];verts=[];faces=[]
        for ob in rails:
            ob.data.calc_loop_triangles();points=[ob.matrix_world@v.co for v in ob.data.vertices]
            offset=len(verts);verts.extend(points)
            for tri in ob.data.loop_triangles:
                faces.append(tuple(offset+i for i in tri.vertices))
                qs=[points[i] for i in tri.vertices]
                for a,b in zip(qs,qs[1:]+qs[:1]):
                    dy=b.y-a.y
                    if abs(dy)<1e-10:continue
                    t=(new_y-a.y)/dy
                    if -.000001<=t<=1.000001:
                        q=a.lerp(b,t)
                        if q.x>0:section.append(q)
        if not section:raise RuntimeError('Port railing cross-section missing at new jib eye')
        tree=BVHTree.FromPolygons(verts,faces,all_triangles=True)
        old_hit=tree.ray_cast(old+Vector((0,0,1)),Vector((0,0,-1)),3)[0]
        x=(min(q.x for q in section)+max(q.x for q in section))/2
        high=max(q.z for q in section)+1
        hit=tree.ray_cast(Vector((x,new_y,high)),Vector((0,0,-1)),3)[0]
        if hit is None or old_hit is None:raise RuntimeError('Railing top does not support inspected eye')
        new=Vector((x,new_y,hit.z+old.z-old_hit.z));delta=new-old
        paths=design['rigging']['rigging_paths'];row=next(r for r in paths if r['name']=='jib_sheet')
        start,end=map(_world,(row['points_gltf_m'][0],row['points_gltf_m'][-1]))
        new_end=end+delta;axis=end-start;length=axis.length;direction=axis/length
        rotation=direction.rotation_difference((new_end-start).normalized())
        inverse=rope.matrix_world.inverted()
        for v in rope.data.vertices:
            p=rope.matrix_world@v.co;t=(p-start).dot(direction)/length
            center=start+axis*t;v.co=inverse@(start+(new_end-start)*t+rotation@(p-center))
        rope.data.update();matrix=eye.matrix_world.copy();matrix.translation=new;eye.matrix_world=matrix
        row['points_gltf_m'][-1]=_gltf(new_end)
        design['brig_jib_eye_relocation']={'eye':eye.name,'sheet':rope.name,'from_gltf_m':_gltf(old),'to_gltf_m':_gltf(new),
            'reason':'Jib sheet fixing eye moved 350 mm aft along the actual port rail to clear the forward swivel gun; sheet cross-sections follow the relocated end.'}
    rules=design.setdefault('intended_joints',[])
    hull=find('hull','kadlub')
    additions=[{'a':'gaff_sail_set','b':'spars_timber_068','reason':'The gaff sail luff is attached to the split snow-mast timber; independent rig audit only permits actual cloth-boundary contact within 25 mm.'},
        {'a':hull.name,'b':'captain_companionway_plank_04','reason':'This embedded tread strip belongs to the companionway slab housed into its cabin landing and remains below the tested walking plane.'}]
    for row in additions:
        if not any(r.get('a')==row['a'] and r.get('b')==row['b'] for r in rules):rules.append(row)
    if out is not None:
        from pathlib import Path
        (Path(out)/'rigging-working.json').write_text(json.dumps(design['rigging'],indent=2)+'\n')
    return design['brig_jib_eye_relocation']
