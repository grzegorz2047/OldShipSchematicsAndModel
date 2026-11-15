"""Period-analogue merchant equipment fitted into measured, reserved spaces.

The caller supplies its physical floor/occupancy placement functions. Nothing
is placed from a nominal room box alone. The three-metre carried boat is a
hollow closed timber skin; close-stool seats and their pots have real openings.
"""
import math
from mathutils import Vector

MERCHANTS={'barque','schooner','caravel','fleut','pinnace'}



def reserve_merchant_spaces(spec,ctx,place):
    """Reserve functional facilities before loose cargo and cabin furniture."""
    if spec['id'] not in MERCHANTS:return None
    if getattr(ctx,'merchant_reservations_done',False):return
    ctx.merchant_reservations_done=True
    if 'cabin' in ctx.room_planes:
        plane=ctx.room_planes['cabin'];aa,bb=plane['from'],plane['to'];found=None
        for side in(1,-1):
            for t in(.18,.40,.62,.84,.30,.72):
                ss=aa+(bb-aa)*t
                for xx in(1.28,1.16,1.04,.92,.86):
                    x=side*min(xx,plane['width_m']/2-.40)
                    z=place('cabin',x,ss,.54,.54,1.05)
                    if z is not None:found=(x,ss,z);break
                if found:break
            if found:break
        if found:ctx.merchant_reserved_stool=found
    if spec['id']=='schooner' and 'hold' in ctx.room_planes:
        plane=ctx.room_planes['hold'];aa,bb=plane['from'],plane['to'];found=None
        for side in(-1,1):
            for t in(.80,.76,.85,.70,.89,.65):
                ss=aa+(bb-aa)*t;x=side*min(1.42,plane['width_m']/2-.55)
                if any(q.get('deck_id','hold')=='hold' and abs(float(q['at'])*ctx.L-ss)<1.18/2+.18 for q in ctx.layout.get('partitions',[])):continue
                z=place('hold',x,ss,.93,1.18,1.32)
                if z is not None:found=(x,ss,z);break
            if found:break
        if found:ctx.merchant_reserved_galley=found
    return {'sanitation':getattr(ctx,'merchant_reserved_stool',None),'galley':getattr(ctx,'merchant_reserved_galley',None)}

def build_merchant_details(spec,ctx,place=None,join_group=None,support=None):
    family=spec['id']
    if family not in MERCHANTS:return {'nodes':[],'scope':'Merchant-specific equipment is not applied to this family.'}
    if not all(callable(x) for x in (place,join_group,support)):
        raise ValueError('Merchant details require the main outfitter measured placement/join/support callbacks')
    p=ctx.p;added=[];items=[];omissions=[];deck_tree=None
    def measured_deck(x,s):
        nonlocal deck_tree
        if deck_tree is None:
            from mathutils.bvhtree import BVHTree
            verts=[];faces=[]
            for ob in ctx.deck_nodes:
                offset=len(verts);verts.extend(ob.matrix_world@v.co for v in ob.data.vertices)
                faces.extend(tuple(offset+i for i in face.vertices) for face in ob.data.polygons)
            deck_tree=BVHTree.FromPolygons(verts,faces)
        hit=deck_tree.ray_cast(p(x,s,ctx.deck_height(s)+.35),Vector((0,0,-1)),1.0)
        return hit[0].z if hit[0] is not None else None
    room_floor_trees={}
    def measured_room_floor(room,x,ss):
        from mathutils.bvhtree import BVHTree
        if room not in room_floor_trees:
            names=set(next(q for q in ctx.rooms if q['id']==room)['floor_nodes']);verts=[];faces=[]
            for ob in ctx.deck_nodes:
                if ob.name not in names:continue
                offset=len(verts);verts.extend(ob.matrix_world@v.co for v in ob.data.vertices);faces.extend(tuple(offset+i for i in f.vertices) for f in ob.data.polygons)
            room_floor_trees[room]=BVHTree.FromPolygons(verts,faces)
        baseline=ctx.room_planes[room]['floor'](ss)
        hit=room_floor_trees[room].ray_cast(p(x,ss,baseline+.30),Vector((0,0,-1)),.70)
        return hit[0].z if hit[0] is not None else None

    def tag(ob,feature,room,assembly):
        ob['detail_feature']=feature;ob['room_id']=room;ob['assembly_id']=assembly;ob['preserve_solid_lod']=True
        ctx.detail_features.setdefault(feature,[]).append(ob.name);added.append(ob);return ob
    def box(name,c,size,mat,feature,room,assembly):return tag(ctx.box(name,c,size,mat,'fitting'),feature,room,assembly)
    def beam(name,a,b,w,d,mat,feature,room,assembly):return tag(ctx.beam(name,a,b,w,d,mat,'fitting'),feature,room,assembly)
    def tube(name,path,r,mat,feature,room,assembly,sides=12):return tag(ctx.tube(name,path,r,mat,'fitting',sides=sides),feature,room,assembly)
    def finish(start,room,feature,ident,extra=None):
        group=added[start:];join_group(group);support(group,room)
        items.append({'id':ident,'room':room,'feature':feature,'nodes':[o.name for o in group],**(extra or {})})
    def avoid_partition(room,s,length):
        return any(q.get('deck_id','hold')==room and abs(float(q['at'])*ctx.L-s)<length/2+.18 for q in ctx.layout.get('partitions',[]))

    def flue_partition_openings(start_x,start_s,end_x,end_s,z):
        # Service holes are not walking portals. Rebuild each intersected
        # rectangular partition plank as a perforated, capped timber skin.
        import bpy,bmesh
        from v2_boats import physical_uv
        from mathutils.bvhtree import BVHTree
        result=[]
        if abs(end_s-start_s)<1e-6:return result
        for i,definition in enumerate(ctx.layout.get('partitions',[])):
            if definition.get('deck_id','hold')!='hold':continue
            ss=float(definition['at'])*ctx.L;t=(ss-start_s)/(end_s-start_s)
            if not 0<t<1:continue
            hx=start_x+(end_x-start_x)*t;cut=(hx-.075,hx+.075,z-.075,z+.075);changed=[]
            for ob in ctx.vis:
                if not ob.name.startswith('partition_%d_'%i) or ob.type!='MESH':continue
                points=[ob.matrix_world@v.co for v in ob.data.vertices]
                lo=[min(q[k] for q in points) for k in range(3)];hi=[max(q[k] for q in points) for k in range(3)]
                if not(lo[0]<cut[1] and hi[0]>cut[0] and lo[2]<cut[3] and hi[2]>cut[2]):continue
                xs=sorted(set([lo[0],hi[0]]+[v for v in cut[:2] if lo[0]<v<hi[0]]));zs=sorted(set([lo[2],hi[2]]+[v for v in cut[2:] if lo[2]<v<hi[2]]));outer=[];inner=[];faces=[];lookup={}
                def vertex(a,b):
                    key=(a,b)
                    if key not in lookup:
                        lookup[key]=len(outer);outer.append(Vector((xs[a],lo[1],zs[b])));inner.append(Vector((xs[a],hi[1],zs[b])))
                    return lookup[key]
                for a in range(len(xs)-1):
                    for b in range(len(zs)-1):
                        xx=(xs[a]+xs[a+1])/2;zz=(zs[b]+zs[b+1])/2
                        if cut[0]<xx<cut[1] and cut[2]<zz<cut[3]:continue
                        faces.append((vertex(a,b),vertex(a+1,b),vertex(a+1,b+1),vertex(a,b+1)))
                if not faces:raise ValueError('Flue cut would remove a complete structural member')
                from v5_stern import _closed_skin
                verts,polygons=_closed_skin(outer,faces,inner);mesh=bpy.data.meshes.new(ob.name+'_service_opening');mesh.from_pydata(verts,[],polygons);mesh.update()
                bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
                for mat in ob.data.materials:mesh.materials.append(mat)
                old=ob.data;ob.data=mesh
                if old.users==0:bpy.data.meshes.remove(old)
                physical_uv(ob,Vector((0,0,1)),[p(hx,ss,z-.2),p(hx,ss,z+.2)]);ob['actual_flue_service_opening']=True;changed.append(ob)
            if changed:
                verts=[];faces=[]
                for ob in changed:
                    offset=len(verts);verts.extend(ob.matrix_world@v.co for v in ob.data.vertices);faces.extend(tuple(offset+j for j in f.vertices) for f in ob.data.polygons)
                tree=BVHTree.FromPolygons(verts,faces);origin=p(hx,ss-.25,z);axis=Vector((0,-1,0));clear=tree.ray_cast(origin,axis,.5)[0] is None
                if not clear:raise ValueError('A galley flue remains sealed by its partition')
                result.append({'id':'galley_flue_partition_%d'%i,'nodes':[o.name for o in changed],'center':list(p(hx,ss,z)),'axis':list(axis),'opening_m':[.15,.15],'timber_clear':clear})
        ctx.detail_contract.setdefault('service_apertures',[]).extend(result)
        return result

    def search_side_bays(room,wx,length,height,preferred=()):
        """Yield real-supported side stations without consuming rejected bays."""
        plane=ctx.room_planes[room];aa,bb=plane['from'],plane['to']
        low=aa+length/2+.13;high=bb-length/2-.13
        if high<low:return
        count=max(1,math.ceil((high-low)/.22))
        stations=list(dict.fromkeys([round(aa+(bb-aa)*t,6) for t in preferred if low<=aa+(bb-aa)*t<=high]+[round(low+(high-low)*i/count,6) for i in range(count+1)]))
        definition=ctx.layout.get('hold',{}) if room=='hold' else {}
        aisle=max(.24,float(definition.get('aisle_width_m',ctx.layout.get('clear_aisle_width_m',1.10)))/2)
        for ss in stations:
            if avoid_partition(room,ss,length):continue
            clear=min(ctx.width(yy,plane['floor'](yy)+zz) for yy in(ss-length/2,ss,ss+length/2) for zz in(.02,height))-.22
            inner=aisle+wx/2+.025;outer=min(3.,clear-wx/2-.025)
            if outer<inner:continue
            nx=max(1,math.ceil((outer-inner)/.065))
            for side in(-1,1):
                for i in range(nx+1):
                    x=side*(outer-(outer-inner)*i/nx)
                    if family=='fleut' and room=='hold' and length>2.:
                        if any(measured_room_floor(room,x+dx,ss+ds) is None for dx in(-.22,.22) for ds in(-.78,.78)):continue
                    z=place(room,x,ss,wx,length,height)
                    if z is not None:yield x,ss,z

    # Gun tools and ready stores belong in small physical planked lockers when
    # the final carriage/rope geometry has excluded all generic lower-deck cargo.
    for room in sorted(ctx.room_planes):
        if not room.startswith('gun_deck_'):continue
        if any(o.get('room_id')==room and o.get('detail_feature') in('stowage','interior_furniture') for o in ctx.vis):continue
        accepted=0
        for x,ss,z in search_side_bays(room,.35,.45,.52,(.18,.32,.46,.60,.74,.86)):
            start=len(added);ident=family+'_'+room+'_tool_locker_'+str(accepted);feature='stowage'
            for side in(-1,1):
                box(ident+'_side_'+str(side),p(x+side*.16,ss,z+.23),(.03,.45,.42),'wood',feature,room,ident)
                box(ident+'_end_'+str(side),p(x,ss+side*.21,z+.23),(.29,.03,.42),'wood',feature,room,ident)
                box(ident+'_hinge_'+str(side),p(x+side*.09,ss+.228,z+.43),(.045,.026,.075),'iron',feature,room,ident)
            box(ident+'_bottom',p(x,ss,z+.025),(.29,.39,.05),'deck',feature,room,ident)
            for side in(-1,1):box(ident+'_lid_board_'+str(side),p(x+side*.0875,ss,z+.4575),(.172,.45,.035),'wood',feature,room,ident)
            box(ident+'_iron_hasplock',p(x,ss-.235,z+.365),(.075,.025,.115),'iron',feature,room,ident)
            finish(start,room,feature,ident,{'footprint_m':[.35,.45],'basis':'Optional authored compact tool/shot locker in a measured clear bay of the preserved armed game-family lower deck; no exact historical caravel interior claim'})
            accepted+=1
            if accepted==2:break
        if not accepted:omissions.append({'feature':'optional '+room+' tool stores','reason':'No measured .35 by .45m locker bay clears the final guns, ropes, framing, real openings and authored aisle.'})

    # A fluit carries bulk cargo. The fallback searches measured inboard bays
    # only if the fixed generic branch found no genuine long-timber footprint.
    if family=='fleut' and 'hold' in ctx.room_planes and not any(o.name.startswith('fluit_timber_') for o in ctx.vis):
        accepted=0
        for x,ss,z in search_side_bays('hold',.44,2.42,.23,(.30,.64,.46,.18,.78,.38,.56,.88)):
            start=len(added);ident='fluit_timber_fitted_'+str(accepted);feature='stowage';room='hold'
            supports={}
            for ds in(-.78,.78):
                lo=measured_room_floor(room,x-.22,ss+ds);hi=measured_room_floor(room,x+.22,ss+ds);supports[ds]=(lo,hi)
                beam(ident+'_dunnage_'+str(ds),p(x-.22,ss+ds,lo+.035),p(x+.22,ss+ds,hi+.035),.12,.07,'spar',feature,room,ident)
            for j in range(3):
                dx=(j-1)*.13;t=(dx+.22)/.44
                za=supports[-.78][0]*(1-t)+supports[-.78][1]*t+.135;zb=supports[.78][0]*(1-t)+supports[.78][1]*t+.135;slope=(zb-za)/1.56
                beam(ident+'_baulk_'+str(j),p(x+dx,ss-1.21,za-.43*slope),p(x+dx,ss+1.21,zb+.43*slope),.115,.13,'wood',feature,room,ident)
            finish(start,room,feature,ident,{'length_m':2.42,'basis':'Dutch fluit bulk-timber cargo analogue; the authored baulks sit on real dunnage tops, clear of the measured hold aisle and existing cargo'})
            accepted+=1
            if accepted==2:break
        if not accepted:omissions.append({'feature':'fluit long timber cargo','reason':'No actual 2.42m timber bay clears the final hold contents, real partitions, frames and authored aisle.'})

    # Sultana's survey-backed small-schooner machinery is hand worked and lies
    # across the waist: an octagonal wooden windlass, not a warship capstan.
    if family=='schooner':
        found=None
        for t in dict.fromkeys([float(ctx.layout.get('machinery',{}).get('windlass_at',.095)),.10,.11,.12,.15,.17,.19]):
            ss=t*ctx.L;z=place('main_deck',.11,ss,2.65,.75,1.08,aisle=False)
            if z is not None:found=(ss,z);break
        if found:
            ss,z=found;wp=lambda x,s,z:p(x+.11,s,z);start=len(added);ident='schooner_hand_windlass';feature='capstan_windlass';room='main_deck'
            for side in(-1,1):
                xx=side*.98
                box(ident+'_bitt_'+str(side),wp(xx,ss,z+.47),(.17,.24,.94),'wood',feature,room,ident)
                box(ident+'_foot_'+str(side),wp(xx,ss,z+.055),(.32,.38,.11),'spar',feature,room,ident)
                box(ident+'_bearing_'+str(side),wp(xx,ss,z+.74),(.25,.29,.20),'iron',feature,room,ident)
            tube(ident+'_octagonal_barrel',[wp(-1.30,ss,z+.74),wp(1.30,ss,z+.74)],.18,'spar',feature,room,ident,8)
            for side in(-1,1):
                tube(ident+'_warping_drum_'+str(side),[wp(side*1.12,ss,z+.74),wp(side*1.32,ss,z+.74)],.23,'wood',feature,room,ident,12)
                beam(ident+'_wooden_heaver_'+str(side),wp(side*.56,ss-.11,z+.83),wp(side*.56,ss-.42,z+1.06),.045,.055,'wood',feature,room,ident)
            box(ident+'_pawl_post',wp(0,ss+.22,z+.46),(.16,.18,.92),'wood',feature,room,ident)
            beam(ident+'_iron_pawl',wp(0,ss+.22,z+.91),wp(0,ss+.12,z+.83),.045,.04,'iron',feature,room,ident)
            finish(start,room,feature,ident,{'basis':'Sultana 1768 survey-backed replica windlass; authored dimensions and location'})
        else:omissions.append({'feature':'schooner windlass','reason':'No measured clear waist reservation accepted; no nominal machinery proxy added.'})
    # Survey-backed side accommodation: full adult-length sleeping surfaces,
    # not tiny labelled boxes. The hold centre and door/hatch paths stay free.
    if family=='schooner' and 'hold' in ctx.room_planes:
        plane=ctx.room_planes['hold'];aa,bb=plane['from'],plane['to'];berths=0
        for side in(-1,1):
            found=None
            for t in(.31,.56,.17,.72,.40,.83):
                ss=aa+(bb-aa)*t;x=side*min(1.55,plane['width_m']/2-.52)
                if avoid_partition('hold',ss,1.96):continue
                z=place('hold',x,ss,.78,1.96,1.04)
                if z is not None:found=(x,ss,z);break
            if not found:continue
            x,ss,z=found;start=len(added);ident='schooner_crew_berth_'+str(side);feature='interior_furniture';room='hold'
            for dx in(-.31,.31):
                for ds in(-.84,.84):box(ident+'_post_%s_%s'%(dx,ds),p(x+dx,ss+ds,z+.28),(.075,.075,.56),'spar',feature,room,ident)
            for dx in(-.35,.35):box(ident+'_side_'+str(dx),p(x+dx,ss,z+.48),(.065,1.94,.19),'wood',feature,room,ident)
            for ds in(-.94,.94):box(ident+'_end_'+str(ds),p(x,ss+ds,z+.58),(.74,.06,.40),'wood',feature,room,ident)
            for j in range(5):box(ident+'_sole_'+str(j),p(x+(j-2)*.135,ss,z+.405),(.13,1.84,.045),'deck',feature,room,ident)
            box(ident+'_mattress',p(x,ss,z+.49),(.65,1.82,.12),'canvas',feature,room,ident)
            box(ident+'_blanket',p(x,ss-.15,z+.56),(.64,1.45,.035),'canvas',feature,room,ident)
            box(ident+'_pillow',p(x,ss+.68,z+.60),(.48,.28,.09),'canvas',feature,room,ident)
            finish(start,room,feature,ident,{'sleeping_surface_length_m':1.82,'basis':'Sultana main-hold side berths; authored game-family adaptation'});berths+=1
        if not berths:omissions.append({'feature':'crew berths','reason':'No adult-length side footprint clears the actual hold contents, framing and access reservations.'})
    # A protected forward galley, with its narrow flue routed through the unused
    # fore corner of an EXISTING open scuttle: no pipe passes through solid deck.
    if family=='schooner' and 'hold' in ctx.room_planes:
        plane=ctx.room_planes['hold'];aa,bb=plane['from'],plane['to'];found=getattr(ctx,'merchant_reserved_galley',None)
        for side in(() if found else (-1,1)):
            for t in(.80,.76,.85,.70,.89,.65):
                ss=aa+(bb-aa)*t;x=side*min(1.42,plane['width_m']/2-.55)
                if avoid_partition('hold',ss,1.18):continue
                z=place('hold',x,ss,.93,1.18,1.32)
                if z is not None:found=(x,ss,z);break
            if found:break
        if found:
            x,ss,z=found;start=len(added);ident='schooner_forward_galley';feature='interior_furniture';room='hold'
            box(ident+'_brick_hearth',p(x,ss,z+.075),(.92,1.16,.15),'brick',feature,room,ident)
            for dx in(-.30,.30):
                for ds in(-.37,.37):box(ident+'_iron_leg_%s_%s'%(dx,ds),p(x+dx,ss+ds,z+.26),(.065,.065,.23),'iron',feature,room,ident)
            box(ident+'_stove_firebox',p(x,ss,z+.59),(.72,.87,.58),'iron',feature,room,ident)
            box(ident+'_stove_top',p(x,ss,z+.90),(.81,.96,.07),'iron',feature,room,ident)
            box(ident+'_firing_door',p(x,ss-.45,z+.59),(.43,.045,.33),'iron',feature,room,ident)
            beam(ident+'_door_latch',p(x-.15,ss-.49,z+.60),p(x+.15,ss-.49,z+.60),.025,.035,'iron',feature,room,ident)
            for dx in(-.20,.20):
                tube(ident+'_copper_'+str(dx),[p(x+dx,ss+.04,z+.93),p(x+dx,ss+.04,z+1.12)],.13,'brass',feature,room,ident,12)
                tube(ident+'_lid_'+str(dx),[p(x+dx,ss+.04,z+1.125),p(x+dx,ss+.04,z+1.145)],.145,'iron',feature,room,ident,12)
            holes=[h for h in ctx.openings if h.get('deck_id')=='main' and h.get('target_deck_id')=='hold' and h['s0']>0]
            if holes:
                hole=max(holes,key=lambda h:h['s1']);fx=hole['x1']-.065 if x>0 else hole['x0']+.065;fs=hole['s1']-.12;deckz=ctx.main_height(fs)
                # The elbow stays above the useful headroom and reaches the
                # scuttle corner outside the audited inner 76 percent aperture.
                topz=min(ctx.main_height(ss+.23+(fs-ss-.23)*j/12) for j in range(13))-.37
                flue_partition_openings(x,ss+.23,fx,fs,topz)
                tube(ident+'_flue',[p(x,ss+.23,z+.93),p(x,ss+.23,topz),p(fx,fs,topz),p(fx,fs,deckz+.48)],.035,'iron',feature,room,ident,8)
                box(ident+'_rain_cap',p(fx,fs,deckz+.50),(.16,.18,.040),'iron',feature,room,ident)
            finish(start,room,feature,ident,{'basis':'Sultana forward brick-and-iron galley; small authored firebox with physical flue through an existing scuttle'})
        else:omissions.append({'feature':'forward galley','reason':'No hearth footprint clears the measured fore-hold cargo, partition and frame geometry.'})
    # A genuine period-style removable-pot facility, instead of inaccessible
    # exterior seats behind the current continuous bow bulwark.
    if 'cabin' in ctx.room_planes:
        plane=ctx.room_planes['cabin'];aa,bb=plane['from'],plane['to'];found=getattr(ctx,'merchant_reserved_stool',None)
        for side in(() if found else (1,-1)):
            for t in(.18,.40,.62,.84,.30,.72):
                ss=aa+(bb-aa)*t;x=side*min(1.28,plane['width_m']/2-.40)
                z=place('cabin',x,ss,.54,.54,1.05)
                if z is not None:found=(x,ss,z);break
            if found:break
        if found:
            x,ss,z=found;start=len(added);ident=family+'_cabin_close_stool';feature='interior_furniture';room='cabin'
            for dx in(-.21,.21):
                for ds in(-.21,.21):box(ident+'_leg_%s_%s'%(dx,ds),p(x+dx,ss+ds,z+.22),(.065,.065,.44),'spar',feature,room,ident)
            for dx in(-.22,.22):box(ident+'_side_'+str(dx),p(x+dx,ss,z+.28),(.055,.48,.32),'wood',feature,room,ident)
            for ds in(-.22,.22):box(ident+'_end_'+str(ds),p(x,ss+ds,z+.28),(.43,.055,.32),'wood',feature,room,ident)
            # Four separate closed seat boards surround a 0.30m square opening.
            for dx in(-.21,.21):box(ident+'_seat_side_'+str(dx),p(x+dx,ss,z+.47),(.12,.54,.06),'wood',feature,room,ident)
            for ds in(-.21,.21):box(ident+'_seat_end_'+str(ds),p(x,ss+ds,z+.47),(.30,.12,.06),'wood',feature,room,ident)
            box(ident+'_raised_lid',p(x,ss+.25,z+.76),(.51,.045,.51),'wood',feature,room,ident)
            for dx in(-.15,.15):box(ident+'_hinge_'+str(dx),p(x+dx,ss+.24,z+.50),(.055,.06,.11),'iron',feature,room,ident)
            box(ident+'_pot_shelf',p(x,ss,z+.04),(.40,.40,.05),'wood',feature,room,ident)
            verts=[];faces=[];profile=[(.10,.065),(.14,.40),(.123,.40),(.083,.09)];n=20
            for radius,height in profile:
                for j in range(n):
                    angle=2*math.pi*j/n;verts.append(p(x+radius*math.cos(angle),ss+radius*math.sin(angle),z+height))
            for row in range(3):
                for j in range(n):faces.append((row*n+j,row*n+(j+1)%n,(row+1)*n+(j+1)%n,(row+1)*n+j))
            # Separate inner and outer bottom disks make a closed-bottom cup.
            # Joining the last profile ring directly to the first would leave
            # a toroidal vessel with an open central hole through its base.
            inner_center=len(verts);verts.append(p(x,ss,z+.09))
            outer_center=len(verts);verts.append(p(x,ss,z+.065))
            for j in range(n):
                faces.append((3*n+j,3*n+(j+1)%n,inner_center))
                faces.append(((j+1)%n,j,outer_center))
            tag(ctx.mesh(ident+'_removable_pot',verts,[tuple(reversed(face)) for face in faces],'iron','fitting'),feature,room,ident)
            finish(start,room,feature,ident,{'seat_opening_m':[.30,.30],'basis':'Vasa Museum officers chamber-pot evidence and museum circa-1700 close-stool furniture analogue; authored facility, not established stock bow heads'})
        else:omissions.append({'feature':'cabin sanitation','reason':'No close-stool footprint clears the actual furnished cabin, berth and doorway.'})
    # Compact ship's boat, three metres overall, carried off the central aisle.
    # The two-layer open-rim hull is a closed timber solid, not a filled block.
    def stairs_clear(x,ss,wx,ls,height):
        zz=measured_deck(x,ss)
        if zz is None:return False
        lo=Vector((x-wx/2-.025,-ss-ls/2-.025,zz+.005));hi=Vector((x+wx/2+.025,-ss+ls/2+.025,zz+height))
        for ob in ctx.stair_nodes:
            points=[ob.matrix_world@v.co for v in ob.data.vertices]
            a=[min(q[k] for q in points) for k in range(3)];b=[max(q[k] for q in points) for k in range(3)]
            if all(lo[k]<b[k] and hi[k]>a[k] for k in range(3)):return False
        return True
    found=None
    for side in(1,-1):
        for t in(.17,.15,-.105,-.075,.015,.20,-.23,.26,.275,.30):
            ss=ctx.L*t
            for nudge in(-.004,0.,.008,-.008,.016):
                x=side*(min(1.26,ctx.B*.20)+nudge)
                # Probe ALL future chock feet and cambered-skid endpoints before
                # committing an occupied reservation. A plank seam or real
                # opening rejects this candidate; only actual ray hits count.
                samples=[(x+dx,ss+ds) for ds in(-.83,.83) for dx in(-.485,-.16,0.,.16,.485)]
                if any(measured_deck(xx,yy) is None for xx,yy in samples):continue
                if not stairs_clear(x,ss,1.13,3.12,.93):continue
                z=place('main_deck',x,ss,1.13,3.12,.93)
                if z is not None:found=(x,ss,z);break
            if found:break
        if found:break
    if found:
        x,ss,z=found;start=len(added);ident=family+'_carried_boat';feature='stowage';room='main_deck';base=z+.18;N=18;M=12;outer=[];inner=[];faces=[]
        def shape(t,a,inside=False):
            half=.54*(.075+.925*math.sin(math.pi*t)**.72);bottom=.13*(abs(t-.5)*2)**2;phi=-math.pi/2+math.pi*a
            xx=half*math.sin(phi);zz=bottom+.55*(1-math.cos(phi))
            if inside:xx*=.92;zz+=.042*math.cos(phi)
            return p(x+xx,ss+(t-.5)*3.,base+zz)
        for j in range(N+1):
            for k in range(M+1):outer.append(shape(j/N,k/M));inner.append(shape(j/N,k/M,True))
        count=len(outer)
        for j in range(N):
            for k in range(M):
                a=j*(M+1)+k;face=(a,a+1,a+M+2,a+M+1);faces.append(face);faces.append(tuple(count+i for i in reversed(face)))
        for j in range(N):
            for k in(0,M):
                a=j*(M+1)+k;b=(j+1)*(M+1)+k;faces.append((a,b,b+count,a+count))
        for j in(0,N):
            for k in range(M):
                a=j*(M+1)+k;faces.append((a,a+count,a+count+1,a+1))
        hull=tag(ctx.mesh(ident+'_hollow_timber_hull',outer+inner,faces,'wood','fitting'),feature,room,ident)
        # Recalculate consistent normals on the closed curved timber shell.
        import bmesh
        bm=bmesh.new();bm.from_mesh(hull.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(hull.data);bm.free()
        for i,ds in enumerate((-.83,0,.83)):
            t=ds/3+.5;half=.54*(.075+.925*math.sin(math.pi*t)**.72)
            beam(ident+'_thwart_'+str(i),p(x-half+.020,ss+ds,base+.48),p(x+half-.020,ss+ds,base+.48),.18,.045,'deck',feature,room,ident)
        for i,ds in enumerate((-.83,.83)):
            top=base+.13*(abs(ds)/1.5)**2;bottom=measured_deck(x,ss+ds)+.07
            box(ident+'_keel_chock_'+str(i),p(x,ss+ds,(bottom+top)/2),(.24,.23,top-bottom),'spar',feature,room,ident)
            xs=[x-.485,x-.16,x+.16,x+.485]
            for j,(xa,xb) in enumerate(zip(xs,xs[1:])):
                beam(ident+'_skid_%d_%d'%(i,j),p(xa,ss+ds,measured_deck(xa,ss+ds)+.035),p(xb,ss+ds,measured_deck(xb,ss+ds)+.035),.18,.07,'spar',feature,room,ident)
        for side2 in(-1,1):
            tube(ident+'_gunwale_'+str(side2),[shape(j/N,0 if side2<0 else 1) for j in range(N+1)],.025,'spar',feature,room,ident,6)
            beam(ident+'_oar_'+str(side2),p(x+side2*.21,ss-1.18,base+.518),p(x+side2*.21,ss+.93,base+.518),.033,.033,'spar',feature,room,ident)
            box(ident+'_oar_blade_'+str(side2),p(x+side2*.21,ss+1.12,base+.518),(.13,.44,.025),'deck',feature,room,ident)
        finish(start,room,feature,ident,{'length_m':3.0,'beam_m':1.08,'basis':'Period carried boat working-equipment analogue; authored compact open timber boat on measured skids'})
    else:omissions.append({'feature':'carried boat','reason':'No three-metre off-centre boat footprint clears all already occupied props, hatches, gun stations, rig and structural framing; no undersized proxy added.'})
    ledger={'family':family,'nodes':[o.name for o in added],'items':items,'omissions':omissions,'scope':'Source-informed authored merchant detail; actual measured placements and physical assemblies, no recovered stock interior claim.'}
    ctx.merchant_detail_ledger=ledger
    return ledger
