"""Authored static rig variants for the ordinary POTC ship-family reconstructions.

Coordinates are provided by ctx.p(x, forward_m, height_m). Mast height is ABOVE
its actual local deck; sail z is its head fraction. rake is aft shift/height.
The geometry is newly constructed, not imported from retail game assets.
"""
import json
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def build_rig(spec, ctx):
    L=float(spec['length']); B=float(spec['beam']); rig=spec.get('rig',{})
    ledger={'mast_count':0,'masts':[],'sails':[],'spars':[],'ropes':[],
            'attachments':[],'geometry_scope':'authored static rig pose; no sail-trim or cloth simulation'}
    joints=set(); area_total=0.; area_centroid=Vector(); cloth_trees=[]

    def joint(a,b,reason):
        if a is None or b is None:return
        names=tuple(sorted((a if isinstance(a,str) else a.name,b if isinstance(b,str) else b.name)))
        if names[0]==names[1] or names in joints:return
        joints.add(names);ctx.joint(a,b,reason)

    def rod(name,points,radii,kind='spar',material='spar'):
        points=[Vector(v) for v in points]; sides=12 if kind=='mast' else 8
        if isinstance(radii,(float,int)):radii=[radii]*len(points)
        verts=[];faces=[]
        previous=None
        for i,(point,radius) in enumerate(zip(points,radii)):
            tangent=points[min(i+1,len(points)-1)]-points[max(i-1,0)]
            if tangent.length<1e-8:raise ValueError('Collapsed spar '+name)
            tangent.normalize();axis=Vector((1,0,0)) if abs(tangent.x)<.85 else Vector((0,1,0))
            n=(axis-tangent*axis.dot(tangent)).normalized()
            if previous is not None and n.dot(previous)<0:n=-n
            binormal=tangent.cross(n).normalized();previous=n
            for j in range(sides):
                angle=2*math.pi*j/sides
                verts.append(point+float(radius)*(math.cos(angle)*n+math.sin(angle)*binormal))
        for i in range(len(points)-1):
            for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
        faces.extend([tuple(reversed(range(sides))),tuple((len(points)-1)*sides+j for j in range(sides))])
        obj=ctx.mesh(name,verts,faces,material=material,kind=('spar' if kind=='mast' else kind),grain_path=points,
                     extras={'preserve_solid_lod':True,'rig_member':kind})
        ledger['spars'].append(obj.name)
        return obj

    def rope(name,points,start,end,reason='Rope end tied to the named rig member.'):
        clean=[]
        for point in points:
            q=Vector(point)
            if not clean or (clean[-1]-q).length>.0001:clean.append(q)
        if len(clean)<2:return None
        obj=ctx.tube(name,clean,max(.009,min(.026,B*.0024)),material='rope',kind='rope',sides=6)
        obj['preserve_solid_lod']=True
        obj['rope_path_json']=json.dumps({'axes':'blender_world','points':[list(q) for q in clean]})
        obj['attachment_start']=start if isinstance(start,str) else start.name
        obj['attachment_end']=end if isinstance(end,str) else end.name
        ledger['ropes'].append(obj.name)
        ledger['attachments'].append({'rope':obj.name,'start':obj['attachment_start'],'end':obj['attachment_end'],
                                      'points_blender_m':[list(q) for q in clean],'reason':reason})
        joint(obj,start,reason);joint(obj,end,reason)
        return obj

    def cloth(name,corners,kind,normal,belly):
        nonlocal area_total,area_centroid
        corners=[Vector(p) for p in corners];normal=Vector(normal).normalized()
        n=10;verts=[];faces=[];boundary=[]
        if len(corners)==4:
            # corners: head fore/left, head aft/right, foot aft/right, foot fore/left.
            for j in range(n+1):
                v=j/n
                for i in range(n+1):
                    u=i/n
                    head=corners[0].lerp(corners[1],u);foot=corners[3].lerp(corners[2],u)
                    verts.append(head.lerp(foot,v)+normal*belly*math.sin(math.pi*u)*math.sin(math.pi*v))
            for j in range(n):
                for i in range(n):
                    a=j*(n+1)+i;faces.append((a,a+1,a+n+2,a+n+1))
            boundary=[[corners[i].lerp(corners[(i+1)%4],j/n) for j in range(n+1)] for i in range(4)]
        else:
            indices={}
            for i in range(n+1):
                for j in range(n+1-i):
                    u=i/n;v=j/n;w=1-u-v
                    indices[i,j]=len(verts)
                    verts.append(corners[0]*w+corners[1]*u+corners[2]*v+normal*belly*27*u*v*w)
            for i in range(n):
                for j in range(n-i):
                    faces.append((indices[i,j],indices[i+1,j],indices[i,j+1]))
                    if j<n-i-1:faces.append((indices[i+1,j],indices[i+1,j+1],indices[i,j+1]))
            boundary=[[corners[i].lerp(corners[(i+1)%3],j/n) for j in range(n+1)] for i in range(3)]
        obj=ctx.mesh(name,verts,faces,material='canvas',kind='sail',
                     extras={'sail_kind':kind,'topology_reason':'Open woven cloth panel; not a collision solid.',
                             'physics':'none','rig_member':'sail','sail_boundary_json':json.dumps([[list(p) for p in e] for e in boundary])})
        cloth_trees.append(BVHTree.FromPolygons(verts,faces,all_triangles=False))
        for face in faces:
            for i in range(1,len(face)-1):
                a,b,c=(verts[k] for k in (face[0],face[i],face[i+1]))
                area=(b-a).cross(c-a).length*.5
                area_total+=area;area_centroid+=(a+b+c)/3*area
        for i,path in enumerate(boundary):
            edge=rope(name+'_bolt_%d'%i,path,obj,obj,'Own sewn bolt rope follows this exact cloth boundary.')
            joint(obj,edge,'Own sewn bolt rope follows this exact cloth boundary.')
        ledger['sails'].append({'node':obj.name,'kind':kind,'corners_blender_m':[list(p) for p in corners]})
        return obj

    def cloth_clear(points):
        for a,b in zip(points,points[1:]):
            direction=Vector(b)-Vector(a);length=direction.length
            if length<1e-7:continue
            for tree in cloth_trees:
                hit=tree.ray_cast(a,direction.normalized(),length)
                if hit[0] is not None:return False
                for j in range(max(2,math.ceil(length/.08))+1):
                    q=Vector(a).lerp(Vector(b),j/max(2,math.ceil(length/.08)))
                    nearest=tree.find_nearest(q)
                    if nearest[0] is not None and nearest[3]<max(.009,min(.026,B*.0024))+.012:return False
        return True

    anchor_cache=[]
    def anchor_position(name, proposed):
        ss=max(-L*.43,min(L*.43,-proposed.y))
        ports=getattr(ctx,'ports',[])
        # Put fastening blocks between gun stations rather than inside carriages.
        for _ in range(3):
            conflicts=[v for v in ports if abs(ss-v['s'])<v['w']/2+.23]
            if not conflicts:break
            candidates=[v['s']+sign*(v['w']/2+.24) for v in conflicts for sign in(-1,1)]
            valid=[v for v in candidates if abs(v)<L*.44 and ('chainplate' not in name or v<=-proposed.y+.001) and all(abs(v-g['s'])>=g['w']/2+.22 for g in ports)]
            if valid:ss=min(valid,key=lambda v:abs(v-ss))
            else:break
        width=ctx.width(ss) if hasattr(ctx,'width') else B/2
        xx=math.copysign(min(abs(proposed.x),max(.10,width*.84)),proposed.x)
        zz=ctx.deck_height(ss)
        point=ctx.p(xx,ss,zz+.14)
        return next((old_point for old_point,obj in anchor_cache if (point-old_point).length<.25),point)

    def deck_anchor(name, proposed):
        point=anchor_position(name,proposed);xx=point.x;ss=-point.y;zz=point.z-.14
        for old_point,obj in anchor_cache:
            if (point-old_point).length<.25:return old_point,obj
        obj=ctx.box(name,ctx.p(xx,ss,zz+.07),(.14,.20,.14),material='iron',kind='fitting')
        obj['rig_member']='deck_fastening';obj['preserve_solid_lod']=True
        anchor_cache.append((point,obj))
        return point,obj

    def yawed(corners,mast,angle):
        angle=math.radians(angle);c=math.cos(angle);sn=math.sin(angle);result=[]
        for v in corners:
            ds=-v.y-mast['s']
            result.append(ctx.p(v.x*c-ds*sn,mast['s']+v.x*sn+ds*c,v.z))
        return result

    masts=[]
    for index,mast in enumerate(rig.get('masts',[])):
        name=str(mast.get('name','mast_%d'%index));s=float(mast['at'])*L
        base=float(ctx.deck_height(s));height=float(mast['height_m'])
        rake=float(mast.get('rake',.025))
        if 'rake_deg' in mast:rake=math.tan(math.radians(float(mast['rake_deg'])))
        if height<=0:raise ValueError('Nonpositive mast height')
        radius=max(.075,height/80)
        def centre(z,s=s,base=base,rake=rake):return ctx.p(0,s-rake*(z-base),z)
        heel=float(mast.get('heel_z_m',base-.20))
        stations=[heel,base+height*.60,base+height*.82,base+height]
        trunk=rod(name,[centre(z) for z in stations],[radius,radius*.76,radius*.50,radius*.28],kind='mast')
        masts.append({'spec':mast,'name':name,'s':s,'base':base,'height':height,'rake':rake,'radius':radius,
                      'centre':centre,'object':trunk,'yards':[]})
        ledger['masts'].append({'node':trunk.name,'at_fraction':mast['at'],'height_above_deck_m':height,
                                'base_blender_m':list(centre(base)),'heel_blender_m':list(centre(heel)),'top_blender_m':list(centre(base+height))})
        ctx.marker(name+'_heel',centre(heel),extras={'rig_anchor':'mast_heel'})
        ctx.marker(name+'_head',centre(base+height),extras={'rig_anchor':'mast_head'})
    ledger['mast_count']=len(masts)

    for mast in masts:
        name=mast['name'];base=mast['base'];height=mast['height'];radius=mast['radius'];centre=mast['centre']
        square=[s for s in mast['spec'].get('sails',[]) if s['kind']=='square']
        square.sort(key=lambda s:float(s['z']))
        lower_yard=None
        sail_index=0
        # Low-to-high courses permit sheets to terminate at the next lower yard.
        ordered=square+[s for s in mast['spec'].get('sails',[]) if s['kind']!='square']
        for sail in ordered:
            kind=str(sail['kind']).lower();head=base+height*float(sail['z'])
            W=float(sail['width_m']);H=float(sail['height_m']);tag=name+'_'+kind+'_%02d'%sail_index;sail_index+=1
            if min(W,H)<=0:raise ValueError('Nonpositive sail dimension')
            s=-centre(head).y;x=radius*1.55+.035;foot=head-H
            if kind in ('lateen','gaff','lug'):
                # Raked trunks must also clear the yawed fore-and-aft panel at its lowest point.
                angle0=math.radians(float(sail.get('yaw_deg',mast['spec'].get('sail_yaw_deg',25 if kind=='lateen' else 15))))
                x+=abs(mast['rake'])*H*abs(math.sin(angle0))+.08
            if kind=='square':
                yard_r=max(.045,W/100);yard_s=s+radius*1.6+.05
                corners=[ctx.p(-W*.45,yard_s,head),ctx.p(W*.45,yard_s,head),
                         ctx.p(W*.5,-centre(foot).y+radius*1.6+.05,foot),ctx.p(-W*.5,-centre(foot).y+radius*1.6+.05,foot)]
                canvas=cloth(tag,corners,kind,ctx.p(0,1,0),min(.40,W*.035))
                ends=[ctx.p(-W*.56,yard_s,head+yard_r+.04),ctx.p(W*.56,yard_s,head+yard_r+.04)]
                yard=rod(tag+'_yard',ends,[yard_r*.65,yard_r*.65])
                # Parrel is an open U around the mast, its two ends actually on the yard.
                back_s=-centre(head).y-radius*1.14
                path=[ctx.p(-radius*.45,yard_s-yard_r*.65,head+yard_r+.04),ctx.p(-radius*1.15,s,head+yard_r+.04),
                      ctx.p(0,back_s,head+yard_r+.04),ctx.p(radius*1.15,s,head+yard_r+.04),ctx.p(radius*.45,yard_s-yard_r*.65,head+yard_r+.04)]
                parrel=rope(tag+'_parrel',path,yard,yard,'Parrel embraces the mast and secures this yard.')
                joint(parrel,mast['object'],'Parrel embraces the mast and secures this yard.')
                for side,corner in [(-1,corners[0]),(1,corners[1])]:
                    tied=ctx.p(side*W*.45,yard_s,head+.04+yard_r*.35)
                    rope(tag+'_head_tie_'+('port' if side>0 else 'starboard'),[corner,tied],canvas,yard,'Head tie joins the sail boundary to its own yard.')
                    low=corners[2] if side>0 else corners[3]
                    target=(lower_yard[1] if side>0 else lower_yard[0]) if lower_yard else ctx.p(side*B*.49,mast['s']-min(.08*L,W*.25),ctx.deck_height(mast['s'])+.12)
                    target_name=lower_yard[2] if lower_yard else None
                    if not lower_yard:target,target_name=deck_anchor(tag+'_sheet_cleat_'+str(side).replace('-','minus'),target)
                    rope(tag+'_sheet_'+('port' if side>0 else 'starboard'),[low,target],canvas,target_name,'Sheet leads down from a clew to the lower yard or deck belaying point.')
                    brace_end=ctx.p(side*B*.48,mast['s']-.09*L,ctx.deck_height(mast['s']-.09*L)+.15)
                    brace_end,brace_anchor=deck_anchor(tag+'_brace_cleat_'+str(side).replace('-','minus'),brace_end)
                    rope(tag+'_brace_'+('port' if side>0 else 'starboard'),[ends[1] if side>0 else ends[0],brace_end],yard,brace_anchor,'Yard brace leads aft to a deck belaying point.')
                lower_yard=(ends[0],ends[1],yard)
                mast['yards'].append(yard.name)
            elif kind in ('gaff','lug'):
                # Four-corner fore-and-aft cloth with its luff beside the mast.
                if kind=='gaff':
                    corners=[ctx.p(x,s,head-H*.20),ctx.p(x,s-W,head),ctx.p(x,s-W,foot),ctx.p(x,s,foot)]
                else:
                    corners=[ctx.p(x,s+W*.28,head-H*.16),ctx.p(x,s-W*.72,head),ctx.p(x,s-W*.65,foot),ctx.p(x,s+W*.20,foot)]
                angle=float(sail.get('yaw_deg',mast['spec'].get('sail_yaw_deg',25 if kind=='lateen' else 15)))
                corners=yawed(corners,mast,angle)
                normal=ctx.p(math.cos(math.radians(angle)),math.sin(math.radians(angle)),0)
                canvas=cloth(tag,corners,kind,normal,min(.22,B*.035))
                spar_r=max(.035,W/115)
                ends=[corners[0]+Vector((0,0,spar_r+.04)),corners[1]+Vector((0,0,spar_r+.04))]
                yard=rod(tag+('_gaff' if kind=='gaff' else '_lug_yard'),ends,spar_r)
                joint(yard,mast['object'],'Spar throat is carried beside the mast by its fitting.')
                rope(tag+'_halyard',[ends[1],centre(base+height)],yard,mast['object'],'Halyard supports the peak from the mast head.')
                for i in (0,1):rope(tag+'_head_tie_%d'%i,[corners[i],ends[i]],canvas,yard,'Boundary head tie to the own gaff or lug yard.')
                if kind=='gaff':
                    boom_ends=[corners[3]-Vector((0,0,spar_r+.04)),corners[2]-Vector((0,0,spar_r+.04))]
                    boom=rod(tag+'_boom',boom_ends,spar_r)
                    joint(boom,mast['object'],'Boom gooseneck is seated beside the mast at the sail tack.')
                    for i,q in enumerate((corners[3],corners[2])):
                        rope(tag+'_foot_tie_%d'%i,[q,boom_ends[i]],canvas,boom,'Foot tie at the own boom and sail boundary.')
                clew=corners[2];target=ctx.p(B*.46,mast['s']-min(.45*L,W*1.05),ctx.deck_height(mast['s'])+.12)
                target,cleat=deck_anchor(tag+'_sheet_cleat',target)
                rope(tag+'_sheet',[clew,target],canvas,cleat,'Sheet leads from the after clew below the sail foot to its belaying point.')
            elif kind=='lateen':
                corners=[ctx.p(x,s+W*.45,head-H*.82),ctx.p(x,s-W*.55,head),ctx.p(x,s-W*.62,foot)]
                angle=float(sail.get('yaw_deg',mast['spec'].get('sail_yaw_deg',25 if kind=='lateen' else 15)))
                corners=yawed(corners,mast,angle)
                normal=ctx.p(math.cos(math.radians(angle)),math.sin(math.radians(angle)),0)
                canvas=cloth(tag,corners,kind,normal,min(.22,B*.035))
                spar_r=max(.035,W/125)
                d=corners[1]-corners[0];outward=normal.cross(d).normalized()
                # Choose the side of the long yard away from the triangular cloth.
                middle=(corners[0]+corners[1])*.5
                if outward.dot(corners[2]-middle)>0:outward=-outward
                ends=[corners[0]+outward*(spar_r+.04),corners[1]+outward*(spar_r+.04)]
                yard=rod(tag+'_lateen_yard',ends,[spar_r*.65,spar_r*.65])
                for i in (0,1):rope(tag+'_head_tie_%d'%i,[corners[i],ends[i]],canvas,yard,'Lateen head corner tied to its own long yard.')
                candidates=sorted((ends[0].lerp(ends[1],j/50)+outward*spar_r*.65 for j in range(51)),key=lambda q:math.hypot(q.x,q.y+mast['s']))
                near=next((q for q in candidates if cloth_clear([q,centre(base+height)])),None)
                if near is None:raise ValueError('No cloth-clear lateen halyard attachment '+tag)
                rope(tag+'_halyard',[near,centre(base+height)],yard,mast['object'],'Halyard suspends the lateen yard beside the mast.')
                joint(yard,mast['object'],'Lateen yard is hoisted beside its mast, not merged into the cloth.')
                for i,label in [(0,'tack'),(2,'sheet')]:
                    q=corners[i];target=ctx.p(B*.45,-q.y,ctx.deck_height(-q.y)+.12)
                    target,cleat=deck_anchor(tag+'_'+label+'_cleat',target)
                    rope(tag+'_'+label,[q,target],canvas,cleat,'Tack or sheet runs below the corresponding boundary corner to the deck.')
            else:raise ValueError('Unsupported sail kind '+kind)
        # Top-attached shrouds remain abaft transverse cloth and outside fore-and-aft cloth.
        top=centre(base+height)
        for side in (-1,1):
            used_chainplates=[]
            lead=mast['spec'].get('shroud_lead_fraction')
            deltas=(float(lead),float(lead)+.015,float(lead)+.03) if lead is not None else (-.005,0,.005)
            if L<12:deltas=deltas[:1]
            for j,delta in enumerate(deltas):
                anchor_name=name+'_chainplate_'+('port' if side>0 else 'starboard')+'_%02d'%j
                candidates=[delta]+[v/1000 for v in range(-150,151,10)]
                possible=[]
                for d in candidates:
                    ss=mast['s']+L*d
                    if abs(ss)>L*.43:continue
                    proposal=ctx.p(side*B*.53,ss,ctx.deck_height(ss)+.08)
                    point=anchor_position(anchor_name,proposal)
                    if all((point-v).length>=.28 for v in used_chainplates) and cloth_clear([top,point]):possible.append((abs(d-delta),proposal))
                if not possible:
                    if j==0:raise ValueError('No cloth-clear shroud lead '+anchor_name)
                    continue  # Never duplicate a rope or put it through cloth to fill a nominal fan.
                proposal=min(possible,key=lambda item:item[0])[1]
                end,chainplate=deck_anchor(anchor_name,proposal)
                used_chainplates.append(end)
                if not cloth_clear([top,end]):raise ValueError('Cached fastening changes cloth clearance '+anchor_name)
                rope(name+'_shroud_'+('port' if side>0 else 'starboard')+'_%02d'%j,[top,end],mast['object'],chainplate,'Standing shroud from mast head to the outboard chainplate location.')

    # Inter-mast head stays are above the authored cloth, followed by the fore stay.
    forward=sorted(masts,key=lambda m:m['s'])
    for a,b in zip(forward,forward[1:]):
        rope(a['name']+'_head_stay',[a['centre'](a['base']+a['height']),b['centre'](b['base']+b['height'])],a['object'],b['object'],'Triatic stay connects the mast heads above the sail heads.')
    bow=rig.get('bowsprit')
    if bow and masts:
        length=float(bow['length_m']);angle=math.radians(float(bow.get('angle_deg',20)))
        start=ctx.p(0,L*.40,ctx.deck_height(L*.40)+.15)
        end=start+ctx.p(0,math.cos(angle)*length,math.sin(angle)*length)
        spar=rod('bowsprit',[start,end],[max(.055,B*.035),max(.032,B*.020)])
        fore=max(masts,key=lambda m:m['s'])
        top=fore['centre'](fore['base']+fore['height'])
        rope('fore_stay',[top,end],fore['object'],spar,'Fore stay connects the foremast head to the bowsprit end.')
        for side in (-1,1):
            fastener,fastener_obj=deck_anchor('bowsprit_chainplate_'+str(side).replace('-','minus'),ctx.p(side*B*.43,L*.36,ctx.deck_height(L*.36)+.1))
            rope('bowsprit_shroud_'+('port' if side>0 else 'starboard'),[end,fastener],spar,fastener_obj,'Bowsprit shroud returns to a bow fastening.')
        for index,jib in enumerate(rig.get('jibs',[])):
            h=float(jib.get('head_fraction',.78));f=float(jib.get('bowsprit_fraction',.85));offset=fore['radius']*1.6+.03
            # Jib is set on the forward stay, ahead of the foremast courses.
            high=top.lerp(end,1-h)+Vector((offset,0,0))
            tack=start.lerp(end,f)+Vector((offset,0,.06))
            clew=ctx.p(offset,fore['s']+L*.085,ctx.deck_height(fore['s'])+max(.8,B*.15))
            canvas=cloth('jib_%02d'%index,[high,tack,clew],'jib',ctx.p(1,0,0),min(.18,B*.025))
            rope('jib_%02d_halyard'%index,[high,top],canvas,fore['object'],'Jib head is hoisted from the foremast.')
            tack_support=start.lerp(end,f)+Vector((max(.055,B*.035)*(1-f)+max(.032,B*.020)*f,0,0))
            rope('jib_%02d_tack'%index,[tack,tack_support],canvas,spar,'Jib tack is fastened to the bowsprit.')
            target=ctx.p(B*.48,fore['s']-.04*L,ctx.deck_height(fore['s'])+.1)
            target,cleat=deck_anchor('jib_%02d_sheet_cleat'%index,target)
            rope('jib_%02d_sheet'%index,[clew,target],canvas,cleat,'Jib sheet leads aft from the clew to a deck belaying point.')
    ledger['sail_area_m2']=area_total
    ledger['sail_area_centroid_blender_m']=list(area_centroid/area_total) if area_total else None
    ledger['spar_count']=len(ledger['spars']);ledger['rope_count']=len(ledger['ropes']);ledger['sail_count']=len(ledger['sails'])
    return ledger
