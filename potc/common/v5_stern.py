"""Cabin lights cut through the actual stern timber, with curved fluit glazing.

The v4 terminal outline is retained.  The closed terminal mesh is rebuilt as
an outer and inner grid, omitting window cells and capping every aperture edge.
No opaque timber lies behind a window. Dimensions and decorative joinery are
explicitly authored period-style interpretations, not recovered game details.
"""
import json
import math
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from v2_boats import physical_uv


def _closed_skin(positions,faces,inner_positions):
    """Double one perforated surface and cap each true boundary loop."""
    edges={}
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    count=len(positions);closed=list(faces)+[tuple(count+i for i in reversed(face)) for face in faces]
    for linked in edges.values():
        if len(linked)==1:
            a,b=linked[0];closed.append((a,b,b+count,a+count))
    return positions+inner_positions,closed


def _recalculate(mesh):
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()


def _needle_cuddy_light(spec,ctx,cabin):
    """A genuine high forward casement for a cabin in a pointed after hull.

    The needle transom cannot carry useful rear windows.  A modest light in
    the forward cuddy wall instead faces the weather deck, above its camber
    and below the low quarterdeck beam.  This is an authored small-cuddy
    inference, not a claim that a historic Xebec drawing shows this casement.
    """
    definition=ctx.layout['cabin'];s=float(definition['to'])*ctx.L
    main=ctx.main_height(s);roof=main
    for i,castle in enumerate(ctx.castles):
        if definition.get('ceiling_deck_id')=='castle_%d'%i:roof+=float(castle['height_m'])
    z0=main+.125;z1=roof-.20
    if z1-z0<.14:raise ValueError('No real above-weatherdeck light band in '+spec['id'])
    width=.55;door=float(definition.get('door_x_m',0))
    # Clear the forward companion coaming as well as the doorway.  The
    # casement is retained from inside the wall, behind the weather stair's
    # actual timber envelope; its pane-centre sightlines still face open air.
    door_half=float(definition.get('door_width_m',1.0))/2
    cx=(-1 if door>=0 else 1)*max(.10,width/2+.25-(abs(door)-door_half))
    x0,x1=cx-width/2,cx+width/2
    room=next(r for r in ctx.rooms if r['id']=='cabin')
    wall=[bpy.data.objects.get(name) for name in room['wall_nodes']]
    wall=[o for o in wall if o is not None and o.name.startswith('aft_cabin_plank_')]
    def bounds(ob):
        points=[ob.matrix_world@v.co for v in ob.data.vertices]
        return [min(q[k] for q in points) for k in range(3)],[max(q[k] for q in points) for k in range(3)]
    cut=[]
    for ob in wall:
        a,b=bounds(ob)
        if a[0]<x1 and b[0]>x0 and a[2]<z1 and b[2]>z0:cut.append(ob)
    if len(cut)<2:raise ValueError('Forward casement does not cross actual cuddy planks')
    cutter=ctx.box('temporary_forward_cuddy_light_cutter',ctx.p(cx,s,(z0+z1)/2),
                   (width,.50,z1-z0),'wood','fitting')
    try:
        for ob in cut:
            modifier=ob.modifiers.new('true_forward_cuddy_light','BOOLEAN')
            modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
            bpy.context.view_layer.objects.active=ob
            with bpy.context.temp_override(object=ob,active_object=ob):bpy.ops.object.modifier_apply(modifier=modifier.name)
            if not ob.data.vertices:raise ValueError('Casement unexpectedly removed a complete wall plank')
            from v2_mesh_finish import finish_scene
            finish_scene([ob])
            path=json.loads(ob['grain_path_json'])['points'] if ob.get('grain_path_json') else None
            physical_uv(ob,Vector(ob.get('grain_axis',[0,0,1])),[Vector(q) for q in path] if path else None)
            ob['actual_forward_cuddy_light']=True
    finally:
        ctx.vis.remove(cutter);mesh=cutter.data;bpy.data.objects.remove(cutter,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    ident='forward_cuddy_light';nodes=[];framing=[];glass=[]
    def tag(ob,role):
        ob['detail_feature']='cabin_joinery';ob['room_id']='cabin';ob['structural_role']=role
        ob['window_id']=ident;ob['preserve_solid_lod']=True;nodes.append(ob);return ob
    for label,z in [('sill',z0-.007),('head',z1+.007)]:
        framing.append(tag(ctx.box(ident+'_'+label,ctx.p(cx,s-.046,z),
                                   (width+.08,.04,.04),'wood','joinery'),'window_frame'))
    for label,x in [('left',x0-.007),('right',x1+.007)]:
        framing.append(tag(ctx.box(ident+'_jamb_'+label,ctx.p(x,s-.046,(z0+z1)/2),
                                   (.04,.04,z1-z0+.08),'wood','joinery'),'window_frame'))
    framing.append(tag(ctx.box(ident+'_central_mullion',ctx.p(cx,s-.046,(z0+z1)/2),
                               (.025,.04,z1-z0+.02),'wood','joinery'),'window_mullion'))
    for col in range(2):
        a=x0+width*col/2+.008;b=x0+width*(col+1)/2-.008
        za,zb=z0+.008,z1-.008
        outer=[ctx.p(a,s-.024,za),ctx.p(b,s-.024,za),ctx.p(b,s-.024,zb),ctx.p(a,s-.024,zb)]
        inner=[ctx.p(a,s-.030,za),ctx.p(b,s-.030,za),ctx.p(b,s-.030,zb),ctx.p(a,s-.030,zb)]
        ob=ctx.mesh(ident+'_glass_%d'%col,outer+inner,
                    [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],'glass','joinery')
        _recalculate(ob.data);glass.append(tag(ob,'window_glass'))
    # The casement rebates, individual panes and cut wall are specific housed
    # contacts.  No unrelated object or whole ship is excused from inspection.
    from v5_decks import _join_near
    _join_near(ctx,framing,framing+cut,
               'The named forward cuddy casement member is housed into this actual contacting wall plank or frame rebate.',padding=.005)
    _join_near(ctx,glass,framing,
               'The individual closed pane is retained in this actual contacting casement rebate.',padding=.005)
    vertices=[];faces=[];owners=[]
    for ob in ctx.vis:
        if ob.type!='MESH' or ob in glass:continue
        offset=len(vertices);vertices.extend(ob.matrix_world@v.co for v in ob.data.vertices)
        for f in ob.data.polygons:faces.append(tuple(offset+i for i in f.vertices));owners.append(ob.name)
    tree=BVHTree.FromPolygons(vertices,faces,epsilon=.000001);axis=Vector((0,-1,0));rays=[]
    for pane in glass:
        a,b=bounds(pane);center=Vector(tuple((a[k]+b[k])/2 for k in range(3)));origin=center-axis*.42
        hit=tree.ray_cast(origin,axis,.85)
        rays.append({'glass_node':pane.name,'origin':list(origin),'direction':list(axis),
                     'distance_m':.85,'timber_clear':hit[0] is None,
                     'blocker':owners[hit[2]] if hit[2] is not None else None})
    if not all(r['timber_clear'] for r in rays):raise ValueError('Forward cuddy light remains blocked: '+str(rays))
    record={'id':ident,'kind':'window','from':'cabin','to':'exterior',
            'center':list(ctx.p(cx,s-.027,(z0+z1)/2)),'axis':list(axis),
            'width_m':width,'height_m':z1-z0,'hull_node':cut[0].name,
            'boundary_kind':'forward_cuddy_bulkhead','boundary_nodes':[o.name for o in cut],
            'frame_nodes':[o.name for o in framing],'glass_nodes':[o.name for o in glass],
            'access_nodes':[],'aperture_ray':rays[0],'pane_rays':rays,
            'outside_weatherdeck_baseline_z_m':main,'roof_baseline_z_m':roof,
            'curved_with_round_stern':False}
    ctx.detail_features.setdefault('cabin_joinery',[]).extend(o.name for o in nodes)
    ledger={'windows':[record],'window_count':1,'nodes':[o.name for o in nodes],
            'method':'Real Boolean aperture through original forward cuddy wall planks, above the outside weatherdeck, with two closed retained panes.',
            'shape':'modest high forward casement; original pointed terminal untouched',
            'scope':'Authored light for a small pointed-hull cuddy. Historical sources confirm the xebec raised poop, not this exact glazing arrangement.'}
    ctx.stern_ledger=ledger;ctx.detail_contract['windows']=[record]
    return ledger


def build_stern(spec,ctx):
    cabin=ctx.room_planes.get('cabin')
    stern=next((obj for obj in ctx.hull_nodes if obj.name=='stern_closure'),None)
    if cabin is None or stern is None:return {'windows':[],'scope':'No aft cabin requiring stern lights.'}
    family=spec.get('id',spec.get('family',''));round_stern=bool(ctx.stern_extension)
    stern_s=-ctx.L/2;bulwark=float(ctx.hull.get('bulwark_height',.8))
    bottom=-ctx.draft+ctx.profile_curve(stern_s,2);top=ctx.deck_height(stern_s)+bulwark
    floor=float(cabin['floor'](stern_s))
    definition=ctx.layout.get('cabin',{});ceiling_id=definition.get('ceiling_deck_id','main')
    roof=ctx.main_height(stern_s)
    for i,castle in enumerate(ctx.castles):
        if ceiling_id=='castle_%d'%i:roof+=float(castle['height_m'])
    clearance=roof-floor
    if clearance<1.2:return {'windows':[],'scope':'Cabin too low for genuine stern lights.'}
    window_bottom=floor+max(.58,min(.92,clearance*.35));window_top=min(roof-.30,window_bottom+min(1.02,clearance*.40))
    if family=='galeoth':
        # The lowered cabin stops forward of the round terminal. Its original
        # aft main-sole strip is real timber, so the modest lights must sit
        # above that intact strip rather than appear glazed over solid deck.
        window_bottom=max(window_bottom,ctx.main_height(stern_s)+.24)
    if family=='yacht':
        # The original main-deck hanging knees are real cabin structure. Keep
        # every pane above their measured tops, retaining the roof-limited
        # head of the light and its casing's legitimate structural bearings.
        knee_tops=[];sole_tops=[];rear=-stern_s
        for ob in ctx.vis:
            knee=ob.get('structural_role')=='deck_knee' and ob.name.startswith('main_')
            sole=ob.name.startswith('main_plank_')
            if not(knee or sole):continue
            points=[ob.matrix_world@v.co for v in ob.data.vertices]
            if min(q.y for q in points)<=rear+.45 and max(q.y for q in points)>=rear-.65:
                (knee_tops if knee else sole_tops).append(max(q.z for q in points))
        if knee_tops:window_bottom=max(window_bottom,max(knee_tops)+.035)
        # The aft main sole continues behind the lowered cabin cutout. The
        # sill's complete 97.5mm downward envelope must also clear that timber.
        if sole_tops:window_bottom=max(window_bottom,max(sole_tops)+.105)
    if window_top-window_bottom<.35:return {'windows':[],'scope':'No adequate clear window height.'}
    center_z=(window_bottom+window_top)/2
    width=ctx.width(stern_s,center_z)+(.02 if not round_stern else 0)
    if ctx.hull.get('stern_style')=='pointed' and width<.35:
        return _needle_cuddy_light(spec,ctx,cabin)
    ornate=family in ('yacht','galleon','battleship','pinnace')
    count=2 if family in ('schooner','fleut') or width<1.55 else 5 if family in ('yacht','galleon','battleship') and width>2.05 else 3
    # Galleon's central rudder post and its real upper hinge require solid
    # timber here. Four symmetric side lights retain that structural centre.
    if family=='galleon':count=4
    if round_stern:
        # Two modest quarter lights follow the original elliptical round stern.
        centers=[-.83,.83] if family=='fleut' else [(-.75+1.5*i/max(1,count-1)) for i in range(count)]
        half_u=min(.20,.37/max(width,.5));umin,umax=-math.pi/2,math.pi/2
    else:
        maximum=min(.72,width*.75);centers=[-maximum+2*maximum*i/max(1,count-1) for i in range(count)] if count>1 else [0]
        half_u=min(.13,.32/max(width,.5));umin,umax=-1.,1.
    apertures=[{'id':'stern_cabin_light_%02d'%i,'u0':u-half_u,'u1':u+half_u,'z0':window_bottom,'z1':window_top,'u':u} for i,u in enumerate(centers)]
    us={umin,umax};zs={bottom,top}
    us.update(umin+(umax-umin)*i/(20 if round_stern else 16) for i in range((20 if round_stern else 16)+1))
    zs.update(bottom+(top-bottom)*i/24 for i in range(25))
    for opening in apertures:us.update((opening['u0'],opening['u1']));zs.update((opening['z0'],opening['z1']))
    us=sorted(us);zs=sorted(zs)
    # Interpolate the accepted v4 row/segment edges, so the terminal silhouette
    # remains precisely the same piecewise planar surface after subdivision.
    def point(u,z,inset=0):
        t=max(0.,min(24.,(z-bottom)/max(top-bottom,.001)*24));j=min(23,int(t));f=t-j
        za=bottom+(top-bottom)*j/24;zb=bottom+(top-bottom)*(j+1)/24
        wa=ctx.width(stern_s,za)+(.02 if not round_stern else 0);wb=ctx.width(stern_s,zb)+(.02 if not round_stern else 0)
        if round_stern:
            w=max(.015,wa-inset)*(1-f)+max(.015,wb-inset)*f
            a=max(0.,min(20.,(u+math.pi/2)/math.pi*20));k=min(19,int(a));q=a-k
            aa=-math.pi/2+math.pi*k/20;ab=-math.pi/2+math.pi*(k+1)/20
            return ctx.p(w*((1-q)*math.sin(aa)+q*math.sin(ab)),stern_s-(ctx.stern_extension-inset)*((1-q)*math.cos(aa)+q*math.cos(ab)),z)
        w=wa*(1-f)+wb*f
        return ctx.p(w*u,stern_s-.09+inset,z)
    vertices=[];inner=[];faces=[];lookup={}
    def vertex(i,j):
        key=(i,j)
        if key not in lookup:
            lookup[key]=len(vertices);vertices.append(point(us[i],zs[j]));inner.append(point(us[i],zs[j],.08 if round_stern else .18))
        return lookup[key]
    for j in range(len(zs)-1):
        for i in range(len(us)-1):
            u=(us[i]+us[i+1])/2;z=(zs[j]+zs[j+1])/2
            if any(op['u0']<u<op['u1'] and op['z0']<z<op['z1'] for op in apertures):continue
            faces.append((vertex(i,j),vertex(i+1,j),vertex(i+1,j+1),vertex(i,j+1)))
    positions,polygons=_closed_skin(vertices,faces,inner)
    mesh=bpy.data.meshes.new(stern.name+'_perforated_mesh');mesh.from_pydata(positions,[],polygons);mesh.update();_recalculate(mesh)
    for material in stern.data.materials:mesh.materials.append(material)
    old=stern.data;stern.data=mesh
    if old.users==0:bpy.data.meshes.remove(old)
    physical_uv(stern,Vector((1,0,0)),[ctx.p(-width,stern_s,center_z),ctx.p(width,stern_s,center_z)])
    stern['actual_window_apertures']=len(apertures);stern['stern_outline_preserved']=True
    stern['window_method']='Watertight outer/inner transom grid with omitted aperture cells and capped reveals'
    nodes=[];windows=[]
    def tag(obj,opening,role):
        obj['detail_feature']='cabin_joinery';obj['room_id']='cabin';obj['structural_role']=role;obj['window_id']=opening['id'];obj['preserve_solid_lod']=True;nodes.append(obj)
        return obj
    # Keep decorative timber outside the opening: heads, sills and jambs frame
    # the real light, while glass occupies only the void between timber reveals.
    for opening in apertures:
        ident=opening['id'];u0,u1=opening['u0'],opening['u1'];z0,z1=opening['z0'],opening['z1'];glass=[];framing=[]
        for name,z in [('sill',z0-.045),('head',z1+.045)]:
            steps=5 if round_stern else 2
            for i in range(steps):
                a=u0+(u1-u0)*i/steps;b=u0+(u1-u0)*(i+1)/steps
                framing.append(tag(ctx.beam(ident+'_'+name+'_%d'%i,point(a,z,.025),point(b,z,.025),.095,.105,'paintTrim','joinery'),opening,'window_frame'))
        for name,u in [('left',u0),('right',u1)]:
            if family in('lugger','galeoth'):
                # A narrow tapered transom needs a proportionate casing that
                # follows the actual row-by-row reveal. A single thick chord
                # across this changing width cuts across the outer glass pane.
                breaks=sorted(set([z0-.075,z1+.075]+[bottom+(top-bottom)*i/24 for i in range(25) if z0-.075<bottom+(top-bottom)*i/24<z1+.075]))
                for i,(za,zb) in enumerate(zip(breaks,breaks[1:])):
                    framing.append(tag(ctx.beam(ident+'_jamb_'+name+'_%d'%i,point(u,za,.025),point(u,zb,.025),.065,.065,'paintTrim','joinery'),opening,'window_frame'))
            else:
                framing.append(tag(ctx.beam(ident+'_jamb_'+name,point(u,z0-.075,.025),point(u,z1+.075,.025),.10,.10,'paintTrim','joinery'),opening,'window_frame'))
        # Six individual closed thin glass panes, divided by true timber bars.
        cols=2;rows=3
        for col in range(cols):
            for row in range(rows):
                aa=u0+(u1-u0)*col/cols+.006;bb=u0+(u1-u0)*(col+1)/cols-.006;za=z0+(z1-z0)*row/rows+.012;zb=z0+(z1-z0)*(row+1)/rows-.012
                outer=[point(aa,za,.035),point(bb,za,.035),point(bb,zb,.035),point(aa,zb,.035)]
                inside=[point(aa,za,.041),point(bb,za,.041),point(bb,zb,.041),point(aa,zb,.041)]
                ob=ctx.mesh(ident+'_glass_%d_%d'%(col,row),outer+inside,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],'glass','joinery')
                _recalculate(ob.data);glass.append(tag(ob,opening,'window_glass'))
        mid=(u0+u1)/2
        framing.append(tag(ctx.beam(ident+'_central_mullion',point(mid,z0,.028),point(mid,z1,.028),.035,.045,'wood','joinery'),opening,'window_mullion'))
        for row in range(1,rows):
            zz=z0+(z1-z0)*row/rows
            framing.append(tag(ctx.beam(ident+'_cross_mullion_%d'%row,point(u0,zz,.028),point(u1,zz,.028),.032,.042,'wood','joinery'),opening,'window_mullion'))
        u=opening['u'];center=point(u,center_z)
        normal=Vector((math.sin(u)/max(width,.1),math.cos(u)/max(ctx.stern_extension,.1),0)).normalized() if round_stern else Vector((0,1,0))
        origin=center-normal*.42
        tree=BVHTree.FromPolygons([stern.matrix_world@v.co for v in stern.data.vertices],[tuple(f.vertices) for f in stern.data.polygons])
        hit=tree.ray_cast(origin,normal,.85)
        clear=hit[0] is None
        record={'id':ident,'kind':'window','from':'cabin','to':'exterior','center':list(center),'axis':list(normal),'width_m':(point(u1,center_z)-point(u0,center_z)).length,'height_m':z1-z0,'hull_node':stern.name,'frame_nodes':[o.name for o in framing],'glass_nodes':[o.name for o in glass],'access_nodes':[],'aperture_ray':{'origin':list(origin),'direction':list(normal),'distance_m':.85,'timber_clear':clear},'curved_with_round_stern':round_stern}
        if not clear:raise RuntimeError('Stern light remains blocked by timber: '+ident)
        windows.append(record)
        for ob in framing:ctx.joint(stern,ob,'The window casing frames the real aperture in the terminal timber.')
        # Jambs, sill/head members and crossing bars are actual housed joinery.
        # Declare their mutual contacts only where their solid bounds meet.
        frame_bounds={}
        for ob in framing:
            points=[ob.matrix_world@v.co for v in ob.data.vertices]
            frame_bounds[ob.name]=([min(q[k] for q in points) for k in range(3)],[max(q[k] for q in points) for k in range(3)])
        for i,ob in enumerate(framing):
            a,b=frame_bounds[ob.name]
            for other in framing[i+1:]:
                c,d=frame_bounds[other.name]
                if all(a[k]<=d[k]+.005 and c[k]<=b[k]+.005 for k in range(3)):
                    ctx.joint(ob,other,'The actual window mullion or crossbar is housed into its contacting jamb, sill or head timber.')
        for ob in glass:
            for frame in framing:ctx.joint(ob,frame,'The thin individual glazing pane is retained by the real window joinery.')
    # Restrained pilasters and an upper frieze stay clear of the window apertures.
    if ornate and not round_stern:
        for i,u in enumerate([umin*.90,umax*.90]):
            ob=ctx.beam('stern_pilaster_%d'%i,point(u,max(floor+.20,window_bottom-.35),-.065),point(u,min(roof-.16,window_top+.27),-.065),.13,.15,'paintTrim','joinery');tag(ob,apertures[0],'stern_pilaster')
            if family=='yacht':
                for suffix,zz in [('base',window_bottom-.20),('capital',window_top+.16)]:tag(ctx.box('stern_pilaster_%d_%s'%(i,suffix),point(u,zz,-.08),(.23,.16,.14),'brass','joinery'),apertures[0],'stern_pilaster')
        for row in range(2 if family in ('galleon','pinnace','battleship') else 1):
            zz=min(roof-.12,window_top+.20+row*.13)
            # The rudder stock rises outside the centreline of the transom;
            # terminate the applied frieze on either side of that real stock.
            gap=min(.25,.13/max(width,.1))
            for side,(a,b) in enumerate(((-.92,-gap),(gap,.92))):
                tag(ctx.beam('stern_frieze_%d_%d'%(row,side),point(a,zz,-.07),point(b,zz,-.07),.09,.11,'paintTrim','joinery'),apertures[0],'stern_frieze')
    # Applied pilasters, capitals and split friezes are built after the lights.
    # Register their actual finite mounting contacts as well as each light's
    # internal housed joints; no glass or unrelated ship member is waived.
    from v5_decks import _join_near
    applied=[o for o in nodes if o.get('structural_role') in ('stern_pilaster','stern_frieze')]
    solid_joinery=[o for o in nodes if o.get('structural_role')!='window_glass']
    _join_near(ctx,applied,solid_joinery+[stern],'The specifically named applied stern frieze, capital or pilaster bears on this contacting casing or terminal timber at its real mounting.',padding=.005)
    group=ctx.detail_features.setdefault('cabin_joinery',[]);group.extend(o.name for o in nodes)
    ledger={'windows':windows,'window_count':len(windows),'nodes':[o.name for o in nodes],'method':stern['window_method'],'shape':'curved fluit quarter lights' if round_stern else 'original tapered transom with framed lights','scope':'Authored period-style joinery; exact game/historical stern decoration is not established.'}
    ctx.stern_ledger=ledger
    if hasattr(ctx,'detail_contract'):ctx.detail_contract['windows']=windows
    return ledger
