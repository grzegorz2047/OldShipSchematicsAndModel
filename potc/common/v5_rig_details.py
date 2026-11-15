"""Physical rig fittings and cloth-clear ratlines for the ordinary POTC fleet.

This augments the frozen v4 rig.  Shroud endpoints are rebuilt together with
their actual closed tube and attachment ledger; decorative running-line blocks
leave the original truthful endpoints unchanged.  No nominal ratline survives
an actual cloth intersection or insufficient tube-to-cloth clearance.
"""
import json
import math
import re

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def build_rig_details(spec, ctx):
    # Outfit may author the real rig hardware before reserving cargo space,
    # then request its ledger again at the end. Never duplicate those meshes.
    cached=getattr(ctx,'_v5_rig_details_ledger',None)
    if cached is not None:return cached
    p=ctx.p;ledger=getattr(ctx,'rig_ledger',None)
    if not ledger:return {'nodes':[],'reason':'No rig ledger supplied.'}
    added=[];cloth=[];skipped=[];reterminated=[];ratlines=[];deadeyes=[];leadblocks=[]
    rope_r=max(.009,min(.026,ctx.B*.0024))
    for ob in ctx.vis:
        if ob.type=='MESH' and ob.get('kind')=='sail':
            verts=[ob.matrix_world@v.co for v in ob.data.vertices]
            cloth.append((ob.name,BVHTree.FromPolygons(verts,[list(f.vertices) for f in ob.data.polygons])))

    def clear(points,radius=.015):
        for a,b in zip(points,points[1:]):
            a=Vector(a);b=Vector(b);d=b-a;length=d.length
            if length<1e-7:continue
            for name,tree in cloth:
                if tree.ray_cast(a,d.normalized(),length)[0] is not None:return False
                n=max(2,math.ceil(length/.055))
                for j in range(n+1):
                    nearest=tree.find_nearest(a.lerp(b,j/n))
                    if nearest[0] is not None and nearest[3]<radius+.018:return False
        return True

    def tag(ob,component):
        ob['detail_feature']='rig_fittings';ob['rig_detail_component']=component
        ob['preserve_solid_lod']=True;added.append(ob)
        return ob

    def newrope(name,points,start,end,radius=.010,material='rope'):
        points=list(map(Vector,points))
        ob=tag(ctx.tube(name,points,radius,material,'rope',sides=6),'rig_rope')
        ob['attachment_start']=start.name;ob['attachment_end']=end.name
        ob['rope_path_json']=json.dumps({'axes':'blender_world','points':[list(q) for q in points]})
        ledger['ropes'].append(ob.name)
        ledger['attachments'].append({'rope':ob.name,'start':start.name,'end':end.name,
            'points_blender_m':[list(q) for q in points],
            'reason':'A physical detailed-rig line terminates on the named closed fitting or standing shroud.'})
        ctx.joint(ob,start,'This actual rope end is fastened to its named physical rig support.')
        ctx.joint(ob,end,'This actual rope end is fastened to its named physical rig support.')
        return ob

    def discard(ob):
        if ob in ctx.vis:ctx.vis.remove(ob)
        mesh=ob.data;bpy.data.objects.remove(ob,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)

    def drilled_deadeye(name,centre,radius=.16,thickness=.085):
        """A real solid hardwood disk with three full through-bores."""
        centre=Vector(centre)
        # Perform all exact cuts close to the origin. At long ship coordinates
        # a Boolean cap can contain a sub-micrometre collinear triangle that
        # the GLB exporter drops, opening three edges after import.
        ob=ctx.tube(name,[Vector((0,-thickness/2,0)),Vector((0,thickness/2,0))],radius,'spar','fitting',sides=20)
        bore=radius*.205;holes=[]
        for j in range(3):
            a=math.pi/2+j*2*math.pi/3
            q=Vector((math.cos(a)*radius*.48,0,math.sin(a)*radius*.48))
            # Rotate the finished disk about Z so its drilled faces are
            # outboard-facing (normal X), as required by guide chapter 06.
            holes.append(centre+Vector((-q.y,q.x,q.z)))
            cutter=ctx.tube(name+'_temporary_bore_%d'%j,[q+Vector((0,-thickness*2,0)),q+Vector((0,thickness*2,0))],bore,'iron','fitting',sides=10)
            modifier=ob.modifiers.new('actual_through_bore_%d'%j,'BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
            bpy.context.view_layer.objects.active=ob
            with bpy.context.temp_override(object=ob,active_object=ob):bpy.ops.object.modifier_apply(modifier=modifier.name)
            discard(cutter)
        from v2_mesh_finish import finish_mesh
        numeric_finish=finish_mesh(ob)
        if numeric_finish['after']['non_manifold_edges'] or numeric_finish['after']['zero_area_faces']:
            raise ValueError('Drilled deadeye template is not a sound closed timber solid: '+name)
        for vertex in ob.data.vertices:
            q=vertex.co.copy();vertex.co=centre+Vector((-q.y,q.x,q.z))
        ob.data.update();ob['numeric_cap_finish_json']=json.dumps(numeric_finish)
        # Boolean bore walls receive metric coordinates as actual geometry.
        from v2_boats import physical_uv
        for layer in list(ob.data.uv_layers):ob.data.uv_layers.remove(layer)
        physical_uv(ob,Vector((0,0,1)),[centre-Vector((0,0,radius)),centre+Vector((0,0,radius))])
        # Drilling changes the axial ring topology; the physical planar timber
        # charts above must not be mistaken for a simple uncut tube on export.
        if 'rope_path_json' in ob:del ob['rope_path_json']
        ob['bore_count']=3;ob['bore_diameter_m']=2*bore
        ob['bore_axis_blender']=[1.,0.,0.]
        return tag(ob,'three_hole_deadeye'),holes

    def replace_shroud(ob,points,newtarget):
        """One transaction updates geometry, UV path, target and rig record."""
        oldtarget=ob.get('attachment_end');points=list(map(Vector,points))
        fresh=ctx.tube('v5_rebuilt_'+ob.name,points,rope_r,'ropeTar','rope',sides=6)
        oldmesh=ob.data;ob.data=fresh.data.copy()
        for key in ('rope_path_json','diameter_m','preserve_solid_lod'):ob[key]=fresh[key]
        ob['material_roles_json']=json.dumps(['ropeTar']);ob['attachment_end']=newtarget.name
        discard(fresh)
        if oldmesh.users==0:bpy.data.meshes.remove(oldmesh)
        for row in ledger['attachments']:
            if row['rope']==ob.name:
                row['end']=newtarget.name;row['points_blender_m']=[list(q) for q in points]
                row['reason']='Standing shroud is seized to the upper drilled deadeye; physical tube and attachment path rebuilt together.'
        ctx.joints=[r for r in ctx.joints if not ({r['a'],r['b']}=={ob.name,oldtarget})]
        ctx.joint(ob,newtarget,'The rebuilt standing shroud terminates on the upper deadeye rim.')
        reterminated.append({'rope':ob.name,'old_target':oldtarget,'new_target':newtarget.name,
            'points_blender_m':[list(q) for q in points],'cloth_clear':True})

    shrouds=[ob for ob in list(ctx.vis) if ob.type=='MESH' and re.search(r'_shroud_(port|starboard)_\d+$',ob.name)]
    for index,shroud in enumerate(shrouds):
        path=json.loads(shroud['rope_path_json'])['points'];top=Vector(path[0]);oldend=Vector(path[-1]);s=-oldend.y;side=1 if oldend.x>0 else -1
        deck=ctx.deck_height(s);rail=float(ctx.hull.get('bulwark_height',.8))
        legacy_radius=max(.105,min(.19,ctx.B*.018))
        # D = 1.5 shroud circumferences (guide 06). Leave real room for the
        # adjoining strops in each measured fan, instead of overlapping disks.
        radius=max(.065,min(.14,1.5*math.pi*rope_r))
        fan_prefix=shroud.name.rsplit('_',1)[0]
        pitch=min([abs(Vector(json.loads(other['rope_path_json'])['points'][-1]).y-oldend.y)
                   for other in shrouds if other is not shroud and other.name.rsplit('_',1)[0]==fan_prefix]or[100.])
        radius=min(radius,pitch/2-.040);thickness=radius*.56
        # The channel stands outside the actual top planking; no invented inboard chainplate.
        # The inboard strop edge clears the cap rail, including its real radius.
        outx=side*(ctx.width(s,deck+rail)+legacy_radius+.11)
        # Retain the already validated standing-shroud endpoint exactly while
        # fitting a 2.7D-centre-distance deadeye pair below it.
        endpoint=p(outx,s,deck+rail+.16+legacy_radius*4.3+.005)
        uppercentre=endpoint-Vector((0,0,radius+.005))
        lowercentre=uppercentre-Vector((0,0,radius*5.4))
        if not clear([top,endpoint],rope_r):
            skipped.append({'candidate':shroud.name,'component':'deadeye_retermination','reason':'Candidate standing-shroud tube would enter the actual cloth clearance envelope.'});continue
        # Both disks and all lanyard geometry remain well below the cloth.
        if not clear([lowercentre,uppercentre],radius+.03):
            skipped.append({'candidate':shroud.name,'component':'deadeye_pair','reason':'Actual cloth would overlap the deadeye assembly.'});continue
        lower,lowerholes=drilled_deadeye('deadeye_lower_'+shroud.name,lowercentre,radius,thickness)
        upper,upperholes=drilled_deadeye('deadeye_upper_'+shroud.name,uppercentre,radius,thickness)
        previous_target=shroud.get('attachment_end')
        replace_shroud(shroud,[top,endpoint],upper)
        # The original temporary shroud shoe is obsolete after retermination.
        # Delete it only when no other real rope still uses that exact support.
        if previous_target and not any(previous_target in (row.get('start'),row.get('end')) for row in ledger['attachments']):
            obsolete=bpy.data.objects.get(previous_target)
            if obsolete and obsolete.get('rig_member')=='deck_fastening':
                ctx.joints=[row for row in ctx.joints if previous_target not in (row['a'],row['b'])]
                discard(obsolete)
        # Continuous lanyard alternates through all six real holes and around the faces.
        normal=Vector((side,0,0))
        pts=[uppercentre+Vector((0,radius*.72,0))+normal*(thickness/2+.005)]
        for j in range(3):
            u=upperholes[j];l=lowerholes[j]
            pts.extend([u+normal*(thickness*.64),u-normal*(thickness*.64),
                        l-normal*(thickness*.64),l+normal*(thickness*.64)])
        pts.append(lowercentre+Vector((0,-radius*.72,0))+normal*(thickness/2+.005))
        lanyard=newrope('lanyard_'+shroud.name,pts,upper,lower,radius*.055)
        # Seized shroud and iron lower strop follow the actual deadeye circumferences.
        strops={}
        for label,centre,mat in [('upper',uppercentre,'ropeTar'),('lower',lowercentre,'iron')]:
            ring=[centre+Vector((0,math.cos(j*2*math.pi/20)*(radius+.012),math.sin(j*2*math.pi/20)*(radius+.012))) for j in range(21)]
            strop=tag(ctx.tube('deadeye_%s_strop_%s'%(label,shroud.name),ring,.014,mat,'fitting',sides=6),'deadeye_strop')
            strops[label]=strop
            ctx.joint(strop,upper if label=='upper' else lower,'The strop embraces the actual drilled deadeye rim.')
        hullx=side*(ctx.width(s,deck+rail-.08)-.015)
        channel=tag(ctx.box('channel_'+shroud.name,p((outx+hullx)/2,s,deck+rail-.065),(abs(outx-hullx)+radius*.65,.24,.11),'spar','fitting'),'channel')
        # A real open-ended chainplate slot prevents the lower iron strop
        # disappearing through a solid channel board on larger vessels.
        slot=ctx.box('temporary_chainplate_slot_'+shroud.name,p(outx,s,deck+rail-.065),(.24,.075,.32),'iron','fitting')
        modifier=channel.modifiers.new('physical_chainplate_slot','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=slot
        bpy.context.view_layer.objects.active=channel
        with bpy.context.temp_override(object=channel,active_object=channel):bpy.ops.object.modifier_apply(modifier=modifier.name)
        discard(slot)
        from v2_boats import physical_uv
        for layer in list(channel.data.uv_layers):channel.data.uv_layers.remove(layer)
        physical_uv(channel,Vector((1,0,0)),[p(hullx,s,deck+rail-.065),p(outx,s,deck+rail-.065)])
        channel['physical_chainplate_slot_width_m']=.075
        ctx.joint(channel,lower,'The actual lower deadeye heel bears on its outboard timber channel.')
        for hull in ctx.hull_nodes:
            ctx.joint(channel,hull,'The inner channel heel is bolted into the actual upper hull planking.')
        for gunwale in [ob for ob in ctx.vis if ob.name=='gunwale_'+('port' if side>0 else 'starboard')]:
            ctx.joint(channel,gunwale,'The channel heel is housed into the actual timber cap rail at its bolted mounting.')
        strap_top=lowercentre-Vector((0,0,radius+.02))
        strap_bottom=p(side*(ctx.width(s,deck-.45)+.055),s,deck-.45)
        strap=tag(ctx.beam('chainplate_strap_'+shroud.name,strap_bottom,strap_top,.065,.045,'iron','fitting'),'chainplate')
        ctx.joint(strap,lower,'The real lower deadeye strop is secured by its iron chainplate.')
        ctx.joint(strap,strops['lower'],'The forged chainplate is joined to the actual lower-deadeye iron strop.')
        ctx.joint(strap,channel,'The chainplate rises through its actual outboard channel support.')
        for k,z in enumerate((deck-.42,deck-.22)):
            x=side*(ctx.width(s,z)+.055)
            bolt=tag(ctx.tube('chainplate_bolt_%s_%d'%(shroud.name,k),[p(x-side*.07,s,z),p(x+side*.055,s,z)],.026,'iron','fitting',sides=8),'chainplate_bolt')
            ctx.joint(bolt,strap,'The real iron bolt pins the chainplate to the hull timber.')
            for hull in ctx.hull_nodes:
                ctx.joint(bolt,hull,'This actual chainplate bolt passes into the real hull timber.')
        deadeyes.append({'shroud':shroud.name,'upper':upper.name,'lower':lower.name,'lanyard':lanyard.name,'channel':channel.name,'chainplate':strap.name})

    # Original running-line anchors remain truthful named closed supports.
    anchors=[ob for ob in list(ctx.vis) if ob.get('rig_member')=='deck_fastening' and 'chainplate' not in ob.name]
    gun_bounds=[]
    for ob in ctx.vis:
        if ob.type!='MESH' or not ob.name.startswith('gun_'):continue
        vv=[ob.matrix_world@v.co for v in ob.data.vertices]
        gun_bounds.append(([min(v[k] for v in vv) for k in range(3)],[max(v[k] for v in vv) for k in range(3)]))
    for n,anchor in enumerate(anchors):
        vertices=[anchor.matrix_world@v.co for v in anchor.data.vertices]
        q=sum(vertices,Vector())/len(vertices);q.z=max(v.z for v in vertices)
        scale=max(.65,min(1.30,ctx.B/8))
        # Frame heads stand substantially proud of the shell's inner face.
        # Reserve their full timber depth as well as the planking thickness.
        inner_width=min(ctx.width(-q.y+ds,q.z+dz) for ds in(-.16*scale,.16*scale) for dz in(.02,.30*scale))-.35
        if abs(q.x)+.13*scale>inner_width:
            skipped.append({'candidate':anchor.name,'component':'lead_block','reason':'The actual inner hull and frame-head envelope leave insufficient width for closed block cheeks; original truthful rope endpoint is retained.'});continue
        inward=-1 if q.x>0 else 1
        lo=[q.x-(.30 if inward<0 else .14)*scale,q.y-.15*scale,q.z-.10*scale]
        hi=[q.x+(.14 if inward<0 else .30)*scale,q.y+.15*scale,q.z+.30*scale]
        if any(all(lo[k]<b[k]+.025 and hi[k]>a[k]-.025 for k in range(3)) for a,b in gun_bounds):
            skipped.append({'candidate':anchor.name,'component':'lead_block','reason':'The measured gun/carriage working envelope cannot contain this closed block and pin assembly; original truthful rope endpoint is retained.'});continue
        if not clear([q,q+Vector((0,0,.32*scale))],.16*scale):
            skipped.append({'candidate':anchor.name,'component':'lead_block','reason':'No cloth-clear block volume at the existing running-line fastening.'});continue
        members=[]
        for side in(-1,1):
            cheek=tag(ctx.box('leadblock_%03d_cheek_%s'%(n,side),q+Vector((side*.10*scale,0,.12*scale)),(.035*scale,.23*scale,.24*scale),'spar','fitting'),'lead_block_cheek');members.append(cheek)
            ctx.joint(cheek,anchor,'The hardwood cheek is secured to the original physical deck fastening.')
        sheave=tag(ctx.tube('leadblock_%03d_sheave'%n,[q+Vector((-.078*scale,0,.13*scale)),q+Vector((.078*scale,0,.13*scale))],.081*scale,'brass','fitting',sides=12),'lead_block_sheave');members.append(sheave)
        axle=tag(ctx.tube('leadblock_%03d_pin'%n,[q+Vector((-.135*scale,0,.13*scale)),q+Vector((.135*scale,0,.13*scale))],.019*scale,'iron','fitting',sides=8),'lead_block_pin');members.append(axle)
        for cheek in members[:2]:ctx.joint(axle,cheek,'The actual sheave axle passes through both hardwood block cheeks.')
        ctx.joint(sheave,axle,'The physical sheave turns on its central metal pin.')
        # A belaying pin is planted in an actual fastener-side timber socket.
        pinbase=q+Vector((inward*.19*scale,0,-.04*scale));socket=tag(ctx.box('belaying_socket_%03d'%n,pinbase,(.15*scale,.20*scale,.10*scale),'spar','fitting'),'belaying_socket')
        pinbottom=pinbase-Vector((0,0,.07*scale));pinbottom.z=max(pinbottom.z,ctx.deck_height(-q.y)+.085)
        pin=tag(ctx.tube('belaying_pin_%03d'%n,[pinbottom,pinbase+Vector((0,0,.14*scale)),pinbase+Vector((0,0,.22*scale))],[.018*scale,.024*scale,.034*scale],'wood','fitting',sides=8),'belaying_pin')
        ctx.joint(pin,socket,'The belaying pin is seated through its real hardwood socket.')
        ctx.joint(socket,members[0 if inward<0 else 1],'The pin socket is housed into the actual adjacent hardwood lead-block cheek.')
        leadblocks.append({'anchor':anchor.name,'nodes':[m.name for m in members]+[socket.name,pin.name]})

    # Each ratline joins two actual standing shrouds at the same world height.
    groups={}
    for ob in shrouds:
        match=re.match(r'(.+)_shroud_(port|starboard)_\d+$',ob.name)
        if match:groups.setdefault(match.groups(),[]).append(ob)
    for (mast,side),fan in sorted(groups.items()):
        if len(fan)<2:continue
        paths={ob.name:[Vector(q) for q in json.loads(ob['rope_path_json'])['points']] for ob in fan}
        fan.sort(key=lambda ob:paths[ob.name][-1].y)
        low=max(paths[ob.name][-1].z for ob in fan)+.42
        high=min(paths[ob.name][0].z for ob in fan)
        high=low+(high-low)*(.52 if ctx.L>12 else .38)
        count=max(0,math.floor((high-low)/.36))
        for level in range(count+1):
            z=low+level*.36
            for j,(a,b) in enumerate(zip(fan,fan[1:])):
                def atheight(ob):
                    top,foot=paths[ob.name][0],paths[ob.name][-1]
                    return foot.lerp(top,(z-foot.z)/(top.z-foot.z))
                pa,pb=atheight(a),atheight(b)
                if (pa-pb).length<.12:continue
                sag=(pa+pb)/2-Vector((0,0,.018))
                if not clear([pa,sag,pb],.008):
                    skipped.append({'candidate':'ratline_%s_%s_%02d_%d'%(mast,side,level,j),'component':'ratline','reason':'Actual authored cloth clearance failed.'});continue
                ob=newrope('ratline_%s_%s_%02d_%d'%(mast,side,level,j),[pa,sag,pb],a,b,.008,'ropeTar')
                ob['rig_detail_component']='ratline';ratlines.append(ob.name)
    # Original v4 deck-fastening shoes are real line supports.  Measure their
    # actual timber seating and add visible through-bolts when mounted into a
    # hull side; broad name patterns never authorize a joint by themselves.
    mounts=[ob for ob in list(ctx.vis) if ob.get('rig_member')=='deck_fastening']
    supports=list(dict.fromkeys(ctx.hull_nodes+ctx.deck_nodes+list(getattr(ctx,'structure_nodes',[]))+[ob for ob in ctx.vis if ob.name.startswith('gunwale_')]))
    mount_trees={};mount_bounds={}
    def actual_tree(ob):
        if ob.name not in mount_trees:
            pts=[ob.matrix_world@v.co for v in ob.data.vertices]
            mount_trees[ob.name]=BVHTree.FromPolygons(pts,[list(f.vertices) for f in ob.data.polygons])
            mount_bounds[ob.name]=([min(q[k] for q in pts) for k in range(3)],[max(q[k] for q in pts) for k in range(3)])
        return mount_trees[ob.name]
    def meets(first,second):
        actual_tree(first);actual_tree(second);a,b=mount_bounds[first.name];c,d=mount_bounds[second.name]
        return all(a[k]<=d[k]+.0001 and c[k]<=b[k]+.0001 for k in range(3)) and bool(mount_trees[first.name].overlap(mount_trees[second.name]))
    for anchor in mounts:
        touched=[]
        for support in supports:
            if meets(anchor,support):
                touched.append(support);ctx.joint(anchor,support,'This actual iron line-fastening shoe is bedded and through-bolted into the measured intersecting timber support.')
        if not any(ob in ctx.hull_nodes for ob in touched):continue
        pts=[anchor.matrix_world@v.co for v in anchor.data.vertices];q=sum(pts,Vector())/len(pts);side=1 if q.x>0 else -1;s=-q.y
        for j,ds in enumerate((-.045,.045)):
            outer=side*(ctx.width(s+ds,q.z)+.026);inner=q.x-side*.105
            bolt=tag(ctx.tube('deckfastener_throughbolt_%s_%d'%(anchor.name,j),[p(inner,s+ds,q.z),p(outer,s+ds,q.z)],.015,'iron','fitting',sides=8),'deck_fastening_bolt')
            ctx.joint(bolt,anchor,'The visible transverse bolt passes through the actual iron fastening shoe.')
            for support in supports:
                if meets(bolt,support):ctx.joint(bolt,support,'This actual transverse line-fastening bolt passes through the measured timber mounting.')
    for bolt in [ob for ob in added if ob.get('rig_detail_component')=='chainplate_bolt']:
        for support in supports:
            if meets(bolt,support):ctx.joint(bolt,support,'This actual chainplate bolt passes through the measured hull timber, deck bearing or cap rail at its physical mounting.')
    ledger['rope_count']=len(ledger['ropes'])
    result={'version':5,'nodes':[ob.name for ob in added],'deadeye_pairs':deadeyes,'lead_blocks':leadblocks,
            'ratlines':ratlines,'skipped_candidates':skipped,
            'skipped_for_actual_cloth_clearance':[row for row in skipped if 'cloth' in row['reason'].lower()],
            'skipped_for_hull_clearance':[row for row in skipped if 'hull' in row['reason'].lower()],
            'reterminated_shrouds':reterminated,
            'method':'Actual solid drilled deadeyes, sewn/iron strops, six-hole lanyards, channels, chainplate straps and bolts; running-line blocks retain original endpoints; each proposed ratline checked against actual cloth BVHs.'}
    ledger['physical_fittings']=result
    ctx.detail_features.setdefault('rig_fittings',[]).extend(result['nodes'])
    ctx._v5_rig_details_ledger=result
    return result
