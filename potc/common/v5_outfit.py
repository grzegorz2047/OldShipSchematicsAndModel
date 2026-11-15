"""Physical deck machinery and fitted rooms for the researched ordinary fleet.

Props are closed timber/metal/canvas assemblies placed on measured deck faces.
The working centre aisle, real apertures, guns and cabin doors stay reserved.
"""
import math,json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from v4_shipkit import safe_name


def build_outfit(spec,ctx):
    p=ctx.p;family=spec['id'];openboat=ctx.layout['kind']=='open_boat';scale=max(.50,min(1.25,ctx.L/28));added=[];placements=[];occupied=[]
    features=ctx.detail_features
    from v5_rig_details import build_rig_details
    rig=build_rig_details(spec,ctx)
    from v5_gun_details import build_gun_details
    guns=build_gun_details(spec,ctx)
    bench_assemblies={}
    def tag(ob,feature,room=None,assembly=None):
        ob['detail_feature']=feature;ob['preserve_solid_lod']=True
        if room:ob['room_id']=room
        if assembly:ob['assembly_id']=assembly
        features.setdefault(feature,[]).append(ob.name);added.append(ob);return ob
    def box(name,c,size,mat='wood',feature='stowage',room=None):return tag(ctx.box(name,c,size,mat,'fitting'),feature,room,name.rsplit('_',1)[0])
    def tube(name,points,radius,mat='spar',feature='stowage',room=None,sides=12):return tag(ctx.tube(name,points,radius,mat,'fitting',sides=sides),feature,room,name.rsplit('_',1)[0])
    def beam(name,a,b,w,d,mat='wood',feature='stowage',room=None):return tag(ctx.beam(name,a,b,w,d,mat,'fitting'),feature,room,name.rsplit('_',1)[0])
    def ring(name,c,r,radius=.016,mat='iron',feature='stowage',room=None,axis='z',n=24):
        c=Vector(c);points=[]
        for i in range(n+1):
            a=2*math.pi*i/n
            points.append(c+(Vector((math.cos(a)*r,math.sin(a)*r,0)) if axis=='z' else Vector((math.cos(a)*r,0,math.sin(a)*r))))
        return tube(name,points,radius,mat,feature,room,6)
    bounds_cache={}
    def bounds(ob):
        if ob.name not in bounds_cache:
            vs=[ob.matrix_world@v.co for v in ob.data.vertices];bounds_cache[ob.name]=([min(q[i] for q in vs) for i in range(3)],[max(q[i] for q in vs) for i in range(3)])
        return bounds_cache[ob.name]
    # Use actual structural floor geometry, including camber, not a guessed box height.
    floorverts=[];floorfaces=[];floorowners=[]
    for ob in ctx.deck_nodes:
        offset=len(floorverts);floorverts.extend(ob.matrix_world@v.co for v in ob.data.vertices)
        for face in ob.data.polygons:floorfaces.append(tuple(offset+i for i in face.vertices));floorowners.append(ob.name)
    floor_tree=BVHTree.FromPolygons(floorverts,floorfaces)
    floor_sets={r['id']:set(r['floor_nodes']) for r in ctx.rooms}
    def floor_at(room,x,s):
        if room=='main_deck':z=ctx.deck_height(s)
        else:z=ctx.room_planes[room]['floor'](s)
        # A fitting foot spans a real caulking seam.  Keep the exact sample
        # first, then look only 9 mm to either side of that same bearing point.
        # Every fallback still hits an actual triangle of this room's floor;
        # the separate footprint and aperture tests retain the larger margins.
        for dx,ds in((0,0),(.009,0),(-.009,0),(0,.009),(0,-.009)):
            loc,normal,index,dist=floor_tree.ray_cast(p(x+dx,s+ds,z+.30),Vector((0,0,-1)),.70)
            if index is None:continue
            if room!='main_deck' and floorowners[index] not in floor_sets.get(room,set()):continue
            return loc.z
        return None
    reserved=[]
    for ob in ctx.vis:
        if ob.type=='MESH' and ob.get('kind')!='rope' and (ob.name.startswith(('gun_','belaying_','bowsprit','deck_lead_','leadblock_','deck_lead')) or ob.get('structural_role') in('bulkhead','mast_partner','mast_step','hold_ladder','deck_stair','companion_stair')):
            a,b=bounds(ob);reserved.append((a[0]-.10,b[0]+.10,-b[1]-.10,-a[1]+.10,a[2],b[2]))
    for h in ctx.openings:reserved.append((h['x0']-.19,h['x1']+.19,h['s0']-.19,h['s1']+.19,-20,40))
    cabin=ctx.layout.get('cabin')
    if cabin:
        ds=float(cabin['to'])*ctx.L;dx=float(cabin.get('door_x_m',0));corridor=max(.30,min(float(cabin.get('door_width_m',1.0))/2,float(cabin.get('aisle_width_m',ctx.layout.get('clear_aisle_width_m',1.10)))/2+.05));reserved.append((dx-corridor,dx+corridor,ds-1.0,ds+1.0,-20,40))
    obstacle_vertices=[];obstacle_faces=[]
    for obstacle in list(ctx.hull_nodes)+list(ctx.frame_nodes)+[o for o in ctx.vis if o.get('rig_member')=='mast' or o.get('kind')=='rope']:
        offset=len(obstacle_vertices);obstacle_vertices.extend(obstacle.matrix_world@v.co for v in obstacle.data.vertices)
        obstacle_faces.extend(tuple(offset+i for i in f.vertices) for f in obstacle.data.polygons)
    obstacle_tree=BVHTree.FromPolygons(obstacle_vertices,obstacle_faces)
    def aisle_half(room):
        if openboat and room=='open_boat':return .26
        definition=ctx.layout.get('cabin' if room=='cabin' else 'hold',{}) if room in('cabin','hold') else {}
        width=float(definition.get('aisle_width_m',ctx.layout.get('clear_aisle_width_m',ctx.layout.get('aisle_width_m',1.10))))
        return max(.24,width/2)
    def place(room,x,s,wx,ls,height,aisle=True):
        z=floor_at(room,x,s)
        if z is None:return None
        margin=.10
        if aisle and abs(x)-wx/2<aisle_half(room):return None
        rect=(x-wx/2-margin,x+wx/2+margin,s-ls/2-margin,s+ls/2+margin,z,z+height)
        if any(all((rect[0]<r[1],rect[1]>r[0],rect[2]<r[3],rect[3]>r[2],rect[4]<r[5],rect[5]>r[4])) for r in reserved+occupied):return None
        for xx in(x-wx/2,x+wx/2):
            for ss in(s-ls/2,s+ls/2):
                zz=floor_at(room,xx,ss)
                if zz is None or abs(zz-z)>.13:return None
                clear_width=min(ctx.width(ss,z+hh) for hh in(.02,min(.30,height),height))-.22
                if abs(xx)>clear_width:return None
        testverts=[p(x+dx*wx/2,s+ds*ls/2,z+zz) for zz in(.012,height) for ds in(-1,1) for dx in(-1,1)]
        testtree=BVHTree.FromPolygons(testverts,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)])
        if obstacle_tree.overlap(testtree):return None
        occupied.append(rect);placements.append({'room':room,'x_m':x,'s_m':s,'floor_z_m':z,'footprint_m':[wx,ls],'height_m':height});return z
    def fit_inward(room,sign,s,wx,ls,height):
        plane=ctx.room_planes.get(room)
        baseline=(plane['floor'] if plane else ctx.deck_height)
        samples=[s-ls/2,s,s+ls/2]
        clear=min(ctx.width(ss,baseline(ss)+hh) for ss in samples for hh in(.02,min(.30,height),height))-.22
        if plane:clear=min(clear,plane['width_m']/2-.045)
        inner=aisle_half(room)+wx/2+.015;outer=clear-wx/2-.015
        if outer<inner:return None
        count=max(1,math.ceil((outer-inner)/.09))
        for i in range(count+1):
            x=sign*(outer-(outer-inner)*i/count);z=place(room,x,s,wx,ls,height)
            if z is not None:return x,z
        return None
    def furniture_stations(plane,length):
        aa=plane['from']+length/2+.08;bb=plane['to']-length/2-.08
        if bb<aa:return []
        n=max(2,math.ceil((bb-aa)/.20))
        ts=[.35,.65,.50,.20,.80]+[i/n for i in range(n+1)]
        return list(dict.fromkeys(round(aa+(bb-aa)*t,6) for t in ts))
    def support(objects,room):
        floors=[o for o in ctx.deck_nodes if room=='main_deck' or o.name in floor_sets.get(room,set())]
        for ob in objects:
            a,b=bounds(ob)
            for floor in floors:
                c,d=bounds(floor)
                if all(a[i]<=d[i]+.025 and c[i]<=b[i]+.025 for i in range(3)):ctx.joint(ob,floor,'This actual fitting foot or dunnage timber bears on the measured structural deck plank.')
    def join_group(objects):
        cached=[(ob,*bounds(ob)) for ob in objects]
        for i,(ob,a,b) in enumerate(cached):
            for other,c,d in cached[i+1:]:
                if all(a[k]<=d[k]+.012 and c[k]<=b[k]+.012 for k in range(3)):ctx.joint(ob,other,'These physical assembly members meet at their real timber or metal mounting surfaces.')
    def cask(name,x,s,z,r=.33,h=.83,room='hold',feature='stowage'):
        start=len(added);sides=14;rows=[(0,.82),(.08,.90),(.28,1),(.72,1),(.92,.90),(1,.82)]
        for j in range(sides):
            a=2*math.pi*j/sides+.003;b=2*math.pi*(j+1)/sides-.003;verts=[]
            for t,f in rows:
                for radius,ang in((r*f-.035,a),(r*f,a),(r*f,b),(r*f-.035,b)):verts.append(p(x+math.cos(ang)*radius,s+math.sin(ang)*radius,z+h*t))
            faces=[(3,2,1,0),(20,21,22,23)]
            for k in range(len(rows)-1):
                for q in range(4):faces.append((k*4+q,k*4+(q+1)%4,(k+1)*4+(q+1)%4,(k+1)*4+q))
            tag(ctx.mesh(name+'_stave_%02d'%j,verts,faces,'wood','fitting',[p(x,s,z),p(x,s,z+h)]),feature,room,name)
        tube(name+'_bottom',[p(x,s,z+.025),p(x,s,z+.055)],r*.82,'deck',feature,room,14)
        tube(name+'_head',[p(x,s,z+h-.05),p(x,s,z+h-.02)],r*.82,'deck',feature,room,14)
        for i,t in enumerate((.09,.30,.70,.91)):ring(name+'_hoop_%d'%i,p(x,s,z+h*t),r*(.92 if t<.15 or t>.85 else 1.005),.024,'iron',feature,room,n=28)
        tube(name+'_bung',[p(x,s,z+h-.025),p(x,s,z+h+.005)],.035,'spar',feature,room,8)
        group=added[start:];join_group(group);support(group,room);return group
    def crate(name,x,s,z,wx=.75,ls=.65,h=.65,room='hold',feature='stowage',lid=True):
        start=len(added)
        # Individual boards form five sides; diagonal braces and iron corners are physical.
        for side in(-1,1):
            for j in range(max(2,math.ceil(ls/.15))):
                n=max(2,math.ceil(ls/.15));ss=s-ls/2+ls*(j+.5)/n
                box(name+'_side_%s_%d'%(side,j),p(x+side*(wx/2-.025),ss,z+h/2),(.05,ls/n-.003,h),'wood',feature,room)
            for j in range(max(2,math.ceil(wx/.15))):
                n=max(2,math.ceil(wx/.15));xx=x-wx/2+wx*(j+.5)/n
                box(name+'_end_%s_%d'%(side,j),p(xx,s+side*(ls/2-.025),z+h/2),(wx/n-.003,.05,h),'wood',feature,room)
            beam(name+'_diagonal_'+str(side),p(x-wx*.40,s+side*(ls/2+.005),z+.07),p(x+wx*.40,s+side*(ls/2+.005),z+h-.07),.055,.045,'spar',feature,room)
        box(name+'_base',p(x,s,z+.035),(wx-.08,ls-.08,.07),'spar',feature,room)
        if lid:box(name+'_lid',p(x,s,z+h-.035),(wx,ls,.07),'deck',feature,room)
        for side in(-1,1):
            box(name+'_band_'+str(side),p(x+side*wx*.31,s,z+h+.005),(.04,ls+.02,.025),'iron',feature,room)
        group=added[start:];join_group(group);support(group,room);return group
    def bench(name,x,s,z,length=1.35,room='cabin'):
        start=len(added);box(name+'_seat',p(x,s,z+.47),(.40,length,.075),'deck','interior_furniture',room)
        for ds in(-length*.35,length*.35):
            for dx in(-.13,.13):box(name+'_leg_%s_%s'%(dx,ds),p(x+dx,s+ds,z+.235),(.075,.075,.47),'spar','interior_furniture',room)
        beam(name+'_stretcher',p(x,s-length*.40,z+.20),p(x,s+length*.40,z+.20),.07,.08,'spar','interior_furniture',room)
        group=added[start:];join_group(group);support(group,room)
        bench_assemblies[room]={'name':name,'x':x,'s':s,'z':z,'length':length,'nodes':list(group)}
    def table(name,x,s,z,room='cabin'):
        start=len(added);wx=.84;ls=1.25
        for j in range(4):box(name+'_top_board_%d'%j,p(x-wx/2+(j+.5)*wx/4,s,z+.80),(wx/4-.003,ls,.055),'deck','interior_furniture',room)
        for dx in(-.31,.31):
            for ds in(-.48,.48):box(name+'_leg_%s_%s'%(dx,ds),p(x+dx,s+ds,z+.385),(.07,.07,.77),'spar','interior_furniture',room)
        for ds in(-.48,.48):box(name+'_apron_'+str(ds),p(x,s+ds,z+.69),(.72,.055,.15),'wood','interior_furniture',room)
        box(name+'_chart',p(x,s,z+.832),(.50,.72,.006),'paper','interior_furniture',room)
        for i in range(7):box(name+'_chart_course_%d'%i,p(x-.18+i*.052,s+.04*i,z+.836),(.009,.45-.025*i,.0018),'iron','interior_furniture',room)
        ring(name+'_divider',p(x+.23,s+.31,z+.844),.045,.005,'brass','interior_furniture',room,n=12)
        group=added[start:];join_group(group);support(group,room)
    def bed(name,x,s,z,room='cabin',width=.68,length=1.82):
        start=len(added);outer_width=width+.12;outer_length=length+.12
        box(name+'_mattress',p(x,s,z+.56),(width,length,.16),'canvas','interior_furniture',room)
        for side in(-1,1):
            box(name+'_long_board_'+str(side),p(x+side*(outer_width/2-.035),s,z+.40),(.07,outer_length,.27),'wood','interior_furniture',room)
            box(name+'_end_board_'+str(side),p(x,s+side*(outer_length/2-.035),z+.51),(outer_width,.07,.48),'wood','interior_furniture',room)
            for ds in(-length*.43,length*.43):
                dx=side*(outer_width/2-.075);foot=floor_at(room,x+dx,s+ds);foot=z if foot is None else foot;h=z+.40-foot
                box(name+'_leg_%s_%s'%(side,ds),p(x+dx,s+ds,foot+h/2),(.09,.09,h),'spar','interior_furniture',room)
        for j in range(7):box(name+'_slat_%d'%j,p(x,s-length*.42+j*length*.14,z+.44),(width+.02,.075,.045),'spar','interior_furniture',room)
        box(name+'_pillow',p(x,s+length*.34,z+.675),(width*.70,.29,.12),'canvas','interior_furniture',room)
        if family=='yacht':
            for side in(-1,1):box(name+'_head_finial_'+str(side),p(x+side*(outer_width/2-.035),s+outer_length/2-.035,z+.85),(.08,.08,.20),'brass','interior_furniture',room)
        group=added[start:];join_group(group);support(group,room)
    def sack(name,x,s,z,room,feature='interior_furniture'):
        start=len(added);rows=[(0,.19),(.08,.26),(.35,.28),(.59,.23),(.69,.10),(.76,.12)];verts=[];faces=[];n=12
        for h,r in rows:
            for k in range(n):
                a=2*math.pi*k/n;rr=r*(1+.06*math.sin(k*3.3+h*7));verts.append(p(x+rr*math.cos(a),s+rr*math.sin(a),z+h))
        faces=[tuple(reversed(range(n))),tuple((len(rows)-1)*n+k for k in range(n))]
        for j in range(len(rows)-1):
            for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
        tag(ctx.mesh(name+'_canvas',verts,faces,'canvas','fitting',[p(x,s,z),p(x,s,z+.76)]),feature,room,name)
        ring(name+'_tie',p(x,s,z+.69),.105,.012,'rope',feature,room,n=18)
        group=added[start:];join_group(group);support(group,room)
    def cargo_role(room,s):
        for q in ctx.layout.get('compartments',[]):
            if q.get('deck_id')==room and float(q.get('from',-.5))*ctx.L<=s<=float(q.get('to',.5))*ctx.L:return q.get('role','stores')
        return 'naval stores' if family in ('brig','galleon','corvette','frigate','battleship') else 'provisions'
    def lantern(name,x,s,z,room=None):
        start=len(added);r=.16;h=.42;feature='lighting'
        box(name+'_base',p(x,s,z+.025),(r*2,r*2,.05),'iron',feature,room)
        box(name+'_roof',p(x,s,z+h),(r*2.25,r*2.25,.05),'iron',feature,room)
        for dx in(-r,r):
            for ds in(-r,r):beam(name+'_corner_%s_%s'%(dx,ds),p(x+dx,s+ds,z+.04),p(x+dx,s+ds,z+h),.018,.018,'iron',feature,room)
        for side in(-1,1):
            box(name+'_pane_x_'+str(side),p(x+side*r,s,z+h/2),(.009,r*2-.025,h-.07),'glass',feature,room)
            box(name+'_pane_s_'+str(side),p(x,s+side*r,z+h/2),(r*2-.025,.009,h-.07),'glass',feature,room)
        tube(name+'_candle',[p(x,s,z+.06),p(x,s,z+.25)],.035,'canvas',feature,room,8)
        ring(name+'_handle',p(x,s,z+h+.10),.09,.012,'iron',feature,room,axis='y',n=16)
        group=added[start:];join_group(group);support(group,room);return group
    from v5_merchant_details import reserve_merchant_spaces
    reserve_merchant_spaces(spec,ctx,place)
    # Every room receives fitted side storage. Central working passages and the
    # exact hatch rectangles stay empty instead of being obscured by cargo.
    for room in ctx.rooms:
        rid=room['id'];plane=ctx.room_planes[rid];aa,bb=plane['from'],plane['to'];length=bb-aa
        if rid=='open_boat':continue
        is_cabin=rid=='cabin';count=0;edge=min(ctx.B*.30,plane['width_m']/2-.48)
        requested=list(ctx.layout.get('cabin',{}).get('furniture',['table','bench','berth','locker'])) if is_cabin else []
        sequence=[item for item in requested if item in('table','bench','locker','chest')]
        if is_cabin and 'berth' in requested:
            fitted_bed=False;definition=ctx.layout.get('cabin',{});bw=float(definition.get('berth_width_m',.68));bl=max(1.80,float(definition.get('berth_length_m',1.82)))
            for sign in(-1,1):
                for ss in furniture_stations(plane,bl+.12):
                    fit=fit_inward(rid,sign,ss,bw+.12,bl+.12,.95)
                    if fit is not None:
                        x,z=fit;bed(rid+'_adult_berth',x,ss,z,rid,bw,bl);fitted_bed=True;break
                if fitted_bed:break
            if not fitted_bed:placements.append({'room':rid,'furniture':'berth','placed':False,'clear_mattress_m':[bw,bl],'reason':'No actual supported adult berth footprint clears the frames, authored aisle and apertures.'})
        if is_cabin:
            # Full pieces are preferred. Compact working-ship benches and
            # lockers are tried only after every full-size supported footprint.
            for item in sequence:
                variants={'table':[(.86,1.28,.88)],'bench':[(.42,1.28,.55),(.42,.93,.55)],'locker':[(.70,1.18,.60),(.44,.52,.60)],'chest':[(.70,1.18,.60),(.44,.52,.60)]}[item]
                found=False
                for dims in variants:
                    for sign in(1,-1):
                        for ss in furniture_stations(plane,dims[1]):
                            fit=fit_inward(rid,sign,ss,*dims)
                            if fit is None:continue
                            x,z=fit;name=rid+'_'+item+'_'+str(count)
                            if item=='table':table(name,x,ss,z,rid)
                            elif item=='bench':bench(name,x,ss,z,dims[1]-.03,rid)
                            else:
                                group=crate(name,x,ss,z,dims[0],dims[1],.52,rid,'interior_furniture')
                                seating=next((q for q in placements if q.get('room')==rid and q.get('furniture')=='bench' and q.get('placed') is False),None)
                                if seating:
                                    hardware_start=len(added)
                                    for side in(-1,1):
                                        xx=x+side*min(.11,dims[0]*.24)
                                        box(name+'_seat_hinge_leaf_'+str(side),p(xx,ss+dims[1]/2-.055,z+.527),(.055,.10,.014),'iron','interior_furniture',rid)
                                        tube(name+'_seat_hinge_pin_'+str(side),[p(xx-.032,ss+dims[1]/2-.025,z+.531),p(xx+.032,ss+dims[1]/2-.025,z+.531)],.010,'iron','interior_furniture',rid,8)
                                    join_group(group+added[hardware_start:])
                                    for node in group:node['combined_seat_locker']=True;node['seat_height_m']=.52
                                    seating.update(placed=True,combined_with='locker',variant='one_person_seat_locker',actual_footprint_m=list(dims[:2]),reason='The fitted hollow locker has a strong 70mm timber lid, visible iron hinges and retention; it is the supported one-person cuddy seat.')
                            placements[-1].update(furniture=item,variant='full' if dims==variants[0] else 'compact',actual_footprint_m=list(dims[:2]))
                            count+=1;found=True;break
                        if found:break
                    if found:break
                if not found and item in('locker','chest') and rid in bench_assemblies:
                    seat=bench_assemblies[rid];x,ss,z=seat['x'],seat['s'],seat['z'];size=min(.85,seat['length']-.06);start=len(added)
                    body=crate(rid+'_bench_storage_locker',x,ss,z,.40,size,.435,rid,'interior_furniture',lid=False)
                    for hinge in(-1,1):box(rid+'_storage_seat_hinge_'+str(hinge),p(x+hinge*.11,ss+size/2,z+.435),(.055,.070,.13),'iron','interior_furniture',rid)
                    join_group(seat['nodes']+added[start:]);placements.append({'room':rid,'furniture':item,'placed':True,'combined_with':'bench','actual_footprint_m':[.40,size],'reason':'An actual hollow planked locker uses the already supported bench footprint; the seat forms its iron-hinged lid.'});found=True
                if not found:placements.append({'room':rid,'furniture':item,'placed':False,'reason':'No remaining full or compact floor footprint clears the actual frames, authored passage and room apertures.'})
        for side in(() if is_cabin else (1,-1)):
            for fraction in(.19,.43,.69,.90):
                ss=aa+length*fraction;localedge=min(edge,ctx.width(ss,plane['floor'](ss)+.10)-.72);x=side*localedge
                if is_cabin:
                    wx,ls,h=.72,1.30,.78
                else:wx,ls,h=.70,.70,.84
                fit=fit_inward(rid,side,ss,wx,ls,h)
                if fit is None:continue
                x,z=fit
                name=rid+'_fitted_%s_%d'%(side,count)
                if is_cabin and sequence and sequence[min(count,len(sequence)-1)]=='table':table(name,x,ss,z,rid)
                elif is_cabin and sequence and sequence[min(count,len(sequence)-1)]=='bench':bench(name,x,ss,z,1.25,rid)
                elif is_cabin:
                    crate(name,x,ss,z,.70,1.18,.52,rid,'interior_furniture')
                elif family=='fleut':sack(name+'_bulk_sack',x,ss,z,rid,'stowage')
                elif count%2==0 and cargo_role(rid,ss) not in('cable_store','magazine','powder'):cask(name,x,ss,z,.30,.82,rid,'stowage')
                else:
                    group=crate(name,x,ss,z,.70,.65,.66,rid,'stowage')
                    if 'cable' in cargo_role(rid,ss):
                        points=[]
                        for j in range(97):
                            turn=j/24;angle=2*math.pi*turn;radius=.20+.012*turn
                            points.append(p(x+radius*math.cos(angle),ss+radius*math.sin(angle),z+.672+.026*turn))
                        coil=tube(name+'_cable_coil',points,.014,'rope','stowage',rid,6);join_group(group+[coil])
                    elif family in('brig','galleon','corvette','frigate','battleship'):
                        fastening_start=len(added)
                        for j in(-1,1):box(name+'_forged_hinge_'+str(j),p(x+j*.22,ss+.34,z+.56),(.09,.025,.16),'iron','stowage',rid)
                        box(name+'_brass_lock',p(x,ss-.34,z+.40),(.10,.025,.15),'brass','stowage',rid)
                        join_group(group+added[fastening_start:])
                count+=1
                if count>=(max(1,len(sequence)) if is_cabin else 6):break
            if count>=(max(1,len(sequence)) if is_cabin else 6):break
        # A narrow forward-side locker is a fallback on heavily occupied decks.
        if count<2 and not is_cabin:
            for side in(-1,1):
                for k in range(3,18):
                    ss=aa+length*k/20;fit=fit_inward(rid,side,ss,.46,.52,.60)
                    if fit is None:continue
                    x,z=fit
                    ident=rid+'_locker_%s_%s'%(side,k)
                    crate(ident,x,ss,z,.46,.52,.60,rid,'stowage')
                    if family in('brig','galleon','corvette','frigate','battleship'):
                        box(ident+'_brass_hasplock',p(x,ss-.27,z+.37),(.085,.026,.14),'brass','stowage',rid)
                        for hinge in(-1,1):box(ident+'_iron_hinge_'+str(hinge),p(x+hinge*.15,ss+.27,z+.48),(.06,.025,.15),'iron','stowage',rid)
                    count+=1
                    if count>=2:break
                if count>=2:break
        # Lighting stands on a genuine locker/table top instead of a floating wall bracket.
        fitting=[o for o in added if o.get('room_id')==rid and o.name.endswith(('_lid','_seat'))]
        if fitting:
            ob=fitting[0];lo,hi=bounds(ob);light=lantern(rid+'_lantern',(lo[0]+hi[0])/2,-(lo[1]+hi[1])/2,hi[2],rid);join_group([ob]+light)
    if family=='fleut' and 'hold' in ctx.room_planes:
        plane=ctx.room_planes['hold']
        for side in(-1,1):
            for t in(.30,.64):
                ss=plane['from']+(plane['to']-plane['from'])*t;x=side*min(2.0,ctx.width(ss,plane['floor'](ss)+.10)-.65)
                z=place('hold',x,ss,.44,2.42,.34)
                if z is None:continue
                start=len(added)
                for k in range(3):beam('fluit_timber_%s_%s_%s'%(side,t,k),p(x+(k-1)*.13,ss-1.16,z+.115),p(x+(k-1)*.13,ss+1.16,z+.115),.115,.13,'wood','stowage','hold')
                for ds in(-.76,.76):box('fluit_timber_dunnage_%s_%s_%s'%(side,t,ds),p(x,ss+ds,z+.025),(.44,.10,.05),'spar','stowage','hold')
                join_group(added[start:]);support(added[start:],'hold');break
    # Coiled rope and drinking-water stowage stay outboard of the working aisle.
    for side in(-1,1):
        for i,t in enumerate((-.06,.18,.32)):
            ss=ctx.L*t;x=side*min(ctx.B*.32,2.8);z=place('main_deck',x,ss,.68,.70,.88)
            if z is None:continue
            cask('deck_water_%s_%s'%(side,i),x,ss,z,.30,.82,'main_deck','stowage')
            for j in range(3):ring('deck_rope_coil_%s_%s_%s'%(side,i,j),p(x,ss,z+.84+j*.018),.18+j*.014,.012,'rope','stowage','main_deck',n=28)
    # Cleats and bitts are grounded timber assemblies at clear side-deck stations.
    for side in(-1,1):
        for i,t in enumerate((-.34,.01,.28,.40)):
            wanted=ctx.L*t;stations=[wanted+offset for offset in(0.,-.35,.35,-.70,.70,-1.05,1.05)]
            port_stations=sorted({q['s'] for q in ctx.ports});stations.extend((a+b)/2 for a,b in zip(port_stations,port_stations[1:]))
            fitted=None
            for ss in sorted(set(stations),key=lambda q:abs(q-wanted)):
                if abs(ss)>ctx.L*.455:continue
                fitted=fit_inward('main_deck',side,ss,.46,.54,.68)
                if fitted is not None:break
            if fitted is None:continue
            x,z=fitted
            start=len(added)
            for ds in(-.16,.16):box('bitt_%s_%s_post_%s'%(side,i,ds),p(x,ss+ds,z+.32),(.13,.13,.64),'spar','mooring')
            beam('bitt_%s_%s_crossbar'%(side,i),p(x,ss-.28,z+.48),p(x,ss+.28,z+.48),.11,.11,'wood','mooring')
            for ds in(-.16,.16):box('bitt_%s_%s_cap_%s'%(side,i,ds),p(x,ss+ds,z+.65),(.18,.18,.05),'spar','mooring')
            group=added[start:];join_group(group);support(group,'main_deck')
    # Existing primary fittings receive their missing bearings, bindings and fastenings.
    for ob in list(ctx.vis):
        if ob.name.startswith(('anchor_shank_','anchor_stock_','anchor_fluke_')):
            features.setdefault('anchors',[]).append(ob.name)
        if ob.name.startswith('steering_'):features.setdefault('helm',[]).append(ob.name)
    for side in(-1,1):
        stock=next((o for o in ctx.vis if o.name==safe_name('anchor_stock_'+str(side))),None)
        if stock:
            a,b=bounds(stock);x=(a[0]+b[0])/2;s=-(a[1]+b[1])/2;z=(a[2]+b[2])/2
            for j,ds in enumerate((-.70*scale,0,.70*scale)):
                # Square iron bindings wrap the actual wooden stock.
                for axis in(-1,1):
                    ob=box('anchor_stock_binding_%s_%s_%s'%(side,j,axis),p(x+axis*.083*scale,s+ds,z),(.025,.075*scale,.19*scale),'iron','anchors');ctx.joint(ob,stock,'The iron binding bears on the actual wooden anchor stock.')
            eye=ring('anchor_crown_ring_'+str(side),p(x,s,z+.31*scale),.17*scale,.026*scale,'iron','anchors',axis='y');ctx.joint(eye,stock,'The anchor ring and upper stock fitting meet at the shank head.')
    # Reposition the old capstan to the researched machinery reservation, then
    # build pawl rim, whelps and removable bars around its real spindle.
    cap=next((o for o in ctx.vis if o.name=='capstan'),None)
    if cap and not openboat:
        at=float(ctx.layout.get('machinery',{}).get('capstan_at',.03));ss=ctx.L*at
        if any(h['s0']-.75<ss<h['s1']+.75 and h['x0']<.6 and h['x1']>-.6 for h in ctx.openings):ss=ctx.L*.02
        z=floor_at('main_deck',.06,ss)
        if z is not None:
            a,b=bounds(cap);oldcenter=Vector(((a[0]+b[0])/2,(a[1]+b[1])/2,a[2]));delta=p(0,ss,z)-oldcenter
            for v in cap.data.vertices:v.co+=delta
            bounds_cache.pop(cap.name,None)
            features.setdefault('capstan_windlass',[]).append(cap.name)
            start=len(added);ring('capstan_pawl_rim',p(0,ss,z+.07),.36*scale,.045*scale,'iron','capstan_windlass',n=32)
            for i in range(8):
                angle=2*math.pi*i/8;x=math.cos(angle)*.23*scale;ds=math.sin(angle)*.23*scale
                box('capstan_whelp_%d'%i,p(x,ss+ds,z+.38*scale),(.075*scale,.075*scale,.57*scale),'wood','capstan_windlass')
            tube('capstan_drumhead',[p(0,ss,z+.70*scale),p(0,ss,z+.79*scale)],.37*scale,'spar','capstan_windlass',sides=16)
            for i in range(4):
                angle=math.pi*i/2;beam('capstan_bar_%d'%i,p(math.cos(angle)*.27*scale,ss+math.sin(angle)*.27*scale,z+.745*scale),p(math.cos(angle)*.89*scale,ss+math.sin(angle)*.89*scale,z+.745*scale),.045*scale,.055*scale,'wood','capstan_windlass')
            for i in range(3):ring('capstan_messenger_%d'%i,p(0,ss,z+.18*scale+i*.033),.24*scale,.014,'rope','capstan_windlass',n=28)
            group=added[start:];join_group([cap]+group);support(group,'main_deck')
    if not openboat:
        # Elm-tree pump twins with timber barrels, iron hoops and a physical brake. Small collection tubs stand alongside.
        for side in(-1,1):
            found=None
            for t in(-.15,-.08,.02,.18):
                ss=ctx.L*t;x=side*.97;z=place('main_deck',x,ss,.48,.70,1.10)
                if z is not None:found=(x,ss,z);break
            if not found:continue
            x,ss,z=found;start=len(added)
            tube('elm_pump_%s_barrel'%side,[p(x,ss,z),p(x,ss,z+.80)],.105,'wood','pumps',sides=12)
            for i,h in enumerate((.12,.62,.78)):ring('elm_pump_%s_band_%s'%(side,i),p(x,ss,z+h),.108,.018,'iron','pumps')
            beam('elm_pump_%s_fork'%side,p(x,ss,z+.78),p(x,ss,z+1.04),.055,.07,'iron','pumps')
            beam('elm_pump_%s_brake'%side,p(x,ss-.24,z+1.01),p(x,ss+.39,z+.92),.045,.055,'spar','pumps')
            beam('elm_pump_%s_spear'%side,p(x,ss,z+.72),p(x,ss,z+1.03),.025,.025,'iron','pumps')
            box('elm_pump_%s_dale'%side,p(x,ss+.20,z+.39),(.15,.42,.065),'wood','pumps')
            group=added[start:];join_group(group);support(group,'main_deck')
    # Compass furniture enriches the physical primary helm without blocking its pedestal.
    helm_s=float(spec.get('fittings',{}).get('helm_at',-.40))*ctx.L
    for sign in(() if openboat else (1,-1)):
        xx=sign*1.05;ss=helm_s+.80;z=place('main_deck',xx,ss,.55,.98,1.0)
        if z is None:continue
        start=len(added);box('binnacle_case',p(xx,ss,z+.46),(.50,.40,.82),'wood','helm')
        box('binnacle_base',p(xx,ss,z+.06),(.57,.47,.12),'spar','helm')
        box('binnacle_top',p(xx,ss,z+.90),(.58,.48,.06),'deck','helm')
        tube('binnacle_compass_card',[p(xx,ss,z+.935),p(xx,ss,z+.944)],.14,'paper','helm',sides=24)
        ring('binnacle_compass_gimbal',p(xx,ss,z+.95),.16,.014,'brass','helm',n=32)
        tube('binnacle_compass_glass',[p(xx,ss,z+.949),p(xx,ss,z+.956)],.143,'glass','helm',sides=24)
        for i in range(8):
            a=math.pi*i/4;beam('binnacle_card_mark_%d'%i,p(xx+math.cos(a)*.10,ss+math.sin(a)*.10,z+.946),p(xx+math.cos(a)*.13,ss+math.sin(a)*.13,z+.946),.006,.002,'iron','helm')
        group=added[start:];join_group(group);support(group,'main_deck')
        shelfs=ss+.45
        box('binnacle_lantern_shelf',p(xx,shelfs,z+.90),(.34,.34,.07),'wood','helm')
        beam('binnacle_lantern_shelf_brace',p(xx,ss+.20,z+.60),p(xx,shelfs,z+.865),.045,.055,'spar','helm')
        lantern('helm_lantern',xx,shelfs,z+.935)
        join_group(added[start:]);break
    if openboat:
        # Small hand cleats are housed into the actual end platforms.
        for i,t in enumerate((-.43,.33)):
            ss=ctx.L*t;cleatx=0.;z=floor_at('main_deck',cleatx,ss)
            if z is None:continue
            start=len(added);box('boat_hand_cleat_%d_base'%i,p(cleatx,ss,z+.025),(.16,.24,.05),'spar','mooring')
            beam('boat_hand_cleat_%d_horns'%i,p(cleatx,ss-.17,z+.12),p(cleatx,ss+.17,z+.12),.04,.045,'wood','mooring')
            box('boat_hand_cleat_%d_neck'%i,p(cleatx,ss,z+.075),(.065,.07,.10),'spar','mooring');join_group(added[start:]);support(added[start:],'main_deck')
        room='open_boat';plane=ctx.room_planes[room];aa,bb=plane['from'],plane['to'];side=min(.52,plane['width_m']/2-.20)
        fitted=0
        for sign in(-1,1):
            for k in range(3,18):
                x=sign*.40;ss=aa+(bb-aa)*k/20;z=place(room,x,ss,.25,.23,.22)
                if z is None:continue
                crate('fishing_tackle_box_%d'%fitted,x,ss,z,.25,.23,.22,room,'interior_furniture',lid=False);fitted+=1;break
        # Small tackle boxes fit between the exposed futtocks; large crates do
        # not get pushed into the frames merely to populate the open well.
        # Oars are solid looms plus broad blades, resting fore and aft on the thwarts.
        for side in(-1,1):
            x=side*min(.67,ctx.B*.27);ss=(aa+bb)/2;z=ctx.main_height(ss)-.09
            beam('boat_oar_%s_loom'%side,p(x,ss-1.45,z),p(x,ss+.95,z),.045,.045,'spar','stowage',room)
            box('boat_oar_%s_blade'%side,p(x,ss+1.25,z),(.18,.62,.035),'deck','stowage',room)
        from v5_decks import _join_near
        _join_near(ctx,[o for o in ctx.vis if o.name.startswith('boat_oar_')],[o for o in ctx.vis if o.get('structural_role')=='thwart'],'The named stowed oar loom rests on this actual open-boat thwart at the measured timber contact.')
        ss=aa+(bb-aa)*.48;x=-.40;z=plane['floor'](ss);points=[]
        for j in range(121):
            turn=j/24;angle=2*math.pi*turn;radius=.15+.020*turn
            points.append(p(x+radius*math.cos(angle),ss+radius*math.sin(angle),z+.008+.018*turn))
        tube('fishing_net_rope_coil',points,.008,'rope','stowage',room,6)
        if 'capstan_windlass' not in features:ctx.detail_contract['feature_groups'].append({'id':'capstan_windlass','required':False,'reason':'The researched tiny open Tartane has hand-worked fishing and anchoring gear; a full capstan or windlass would obstruct its narrow well and is not supported by the open-boat analogue.'})
        if 'pumps' not in features:ctx.detail_contract['feature_groups'].append({'id':'pumps','required':False,'reason':'The open Tartane working well is bailed by hand; no enclosed pump well or paired ship pumps is invented for the tiny boat.'})
    for side in(-1,1):
        assembly=[o for o in ctx.vis if o.type=='MESH' and o.name.startswith(('anchor_shank_','anchor_stock_','anchor_fluke_','anchor_stock_binding_','anchor_crown_ring_')) and (o.name.endswith('_'+safe_name(side)) or ('_'+safe_name(side)+'_') in o.name)]
        join_group(assembly)
    # Family helpers own their assembly ledgers and add their concrete groups.
    from v5_stern import build_stern
    from v5_rig_details import build_rig_details
    from v5_gun_details import build_gun_details
    for physical in added+[o for o in ctx.vis if o.name=='capstan']:
        lo,hi=bounds(physical);reserved.append((lo[0],hi[0],-hi[1],-lo[1],lo[2],hi[2]))
    from v5_merchant_details import build_merchant_details
    merchant=build_merchant_details(spec,ctx,place=place,join_group=join_group,support=support)
    stern=build_stern(spec,ctx);rig=build_rig_details(spec,ctx);guns=build_gun_details(spec,ctx)
    if not ctx.gun_nodes:ctx.detail_contract['feature_groups'].append({'id':'gun_tackle','required':False,'reason':'The verified stock Tartane is unarmed. Cannon breeching and gun tackle would invent equipment outside its ordinary source-game contract.'})
    if openboat and not features.get('lighting'):ctx.detail_contract['feature_groups'].append({'id':'lighting','required':False,'reason':'The researched tiny open fishing boat has no enclosed cabin or lower hold requiring permanent lantern fittings; no unsupported enclosed lighting installation is invented.'})
    return {'placements':placements,'nodes':[o.name for o in added],'stern':stern,'rig_details':rig,'gun_details':guns,'merchant_details':merchant,'scope':'Closed physical fittings and measured static room furnishing; no crew or interaction controller claim.'}
