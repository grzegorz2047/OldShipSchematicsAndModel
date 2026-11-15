"""Research-layout-driven timber decks, visible framing and connected interiors.

All apertures are constructed by omitting timber. No black planes or hidden
solid deck is allowed across a hatch or a cabin door. Coordinates use the
repository's s-positive-forward, x-positive-port convention.
"""
import copy,json,math
import bpy
from mathutils import Vector
from v5_gun_details import CARRIAGE_INSET_M


def layout_for(ctx):
    """Normalize authored layout; dimensions remain explicitly authored estimates."""
    source=copy.deepcopy(ctx.spec.get('detailed_layout',{}))
    source.setdefault('kind','open_boat' if ctx.hull.get('cockpit') and ctx.L<12 else 'warship' if len(ctx.spec.get('guns',{}).get('rows',[]))>1 else 'decked')
    source.setdefault('frame_spacing_m',max(.42,min(.66,ctx.L/58)))
    source.setdefault('plank_width_m',.22 if ctx.B>5 else .18)
    source.setdefault('aisle_width_m',1.25 if ctx.B>6 else .95)
    if source['kind']!='open_boat':
        source.setdefault('hold',{'from':-.38,'to':.34,'floor_z_m':max(-ctx.draft+.58,ctx.freeboard-2.55)})
        source.setdefault('hatch',{'at':.10,'length_m':max(1.8,min(3.4,ctx.L*.085)),'width_m':max(1.15,min(2.25,ctx.B*.25))})
        if not source.get('cabin') and ctx.castles:
            c=min(ctx.castles,key=lambda q:q['from'])
            if c['from']<-.2:
                source['cabin']={'from':max(-.48,c['from']+.01),'to':c['to'],'floor_z_m':ctx.freeboard+float(c['height_m'])-2.10,'clear_height_m':1.90,'door_width_m':1.05,'door_height_m':1.88,'cut_main_deck':True}
    source.setdefault('extra_hatches',[]);source.setdefault('lower_decks',[]);source.setdefault('partitions',[]);source.setdefault('companionways',[])
    return source


def _mark(obj,**props):
    for k,v in props.items():obj[k]=v
    return obj


def _join_near(ctx,objects,supports,reason,padding=.035):
    """Declare only joints whose real timber bounding boxes meet."""
    def bounds(ob):
        points=[ob.matrix_world@v.co for v in ob.data.vertices]
        return [min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]
    cache={o.name:bounds(o) for o in list(objects)+list(supports) if o.type=='MESH'}
    for ob in objects:
        if ob.type!='MESH':continue
        a,b=cache[ob.name]
        for sup in supports:
            if ob==sup or sup.type!='MESH':continue
            c,d=cache[sup.name]
            if all(a[i]<=d[i]+padding and c[i]<=b[i]+padding for i in range(3)):ctx.joint(ob,sup,reason)


def _surface_z(ctx,baseline,s,x=0,camber=.07):
    z=baseline(s) if callable(baseline) else float(baseline)
    w=max(.1,ctx.width(s,z)-.16)
    return z+camber*max(0,1-(x/w)**2)


def _subtract(intervals,lo,hi):
    result=[]
    for a,b in intervals:
        if hi<=a or lo>=b:result.append((a,b));continue
        if lo>a:result.append((a,min(b,lo)))
        if hi<b:result.append((max(a,hi),b))
    return [(a,b) for a,b in result if b-a>.008]


def gun_carriage_center(ctx,port):
    s=port['s'];definition=ctx.spec['guns']['rows'][port['row']]
    target=float(definition['z_m'])-.67+ctx.profile_curve(s,3)
    floors=[ctx.main_height(s)]+[ctx.main_height(s)+float(c['height_m']) for c in ctx.castles if c['from']*ctx.L<=s<=c['to']*ctx.L]
    nearest=min(floors,key=lambda z:abs(z-target));floor=nearest if abs(nearest-target)<.30 else target
    available=min(ctx.width(s+ds,z) for ds in(-.44,0,.44) for z in(floor+.01,floor+.15,floor+.45,port['z']))
    return min(ctx.width(s,port['z'])-.65,available-.57)-CARRIAGE_INSET_M


def shaft_holes(ctx,deck_id,a,b,baseline,holes,register=False):
    result=list(holes)
    for index,mast in enumerate(ctx.spec.get('rig',{}).get('masts',[])):
        station=float(mast['at'])*ctx.L;base=ctx.deck_height(station);heel=float(mast.get('heel_z_m',base-.20))
        z=baseline(station) if callable(baseline) else float(baseline)
        if not heel-.30<=z<=base+.10:continue
        rake=float(mast.get('rake',0))
        if 'rake_deg' in mast:rake=math.tan(math.radians(float(mast['rake_deg'])))
        center=station-rake*(z-base);radius=max(.075,float(mast['height_m'])/80)+.025
        if center+radius<a or center-radius>b:continue
        hole={'id':'mast_partner_%s_%s'%(deck_id,mast.get('name',index)),'deck_id':deck_id,'s0':center-radius,'s1':center+radius,'x0':-radius,'x1':radius,'kind':'mast_partner','z_m':z,'mast_name':mast.get('name',str(index)),'mast_radius_m':radius-.025}
        result.append(hole)
        covered=any(q.get('s0',1e9)<=hole['s0'] and q.get('s1',-1e9)>=hole['s1'] and q.get('x0',1e9)<=hole['x0'] and q.get('x1',-1e9)>=hole['x1'] for q in holes)
        if register and not covered and not any(q['id']==hole['id'] for q in ctx.mast_mortises):ctx.mast_mortises.append(hole)
    bow=ctx.spec.get('rig',{}).get('bowsprit')
    if bow:
        start=ctx.L*.40;z0=ctx.deck_height(start)+.15;slope=math.tan(math.radians(float(bow.get('angle_deg',20))));radius=max(.055,ctx.B*.035)+.025
        stations=[max(a,start)+(min(b,start+float(bow['length_m']))-max(a,start))*i/40 for i in range(41)] if b>start else []
        active=[ss for ss in stations if abs(z0+(ss-start)*slope-(baseline(ss) if callable(baseline) else baseline))<radius+.20]
        if active:
            hole={'id':'bowsprit_partner_'+deck_id,'deck_id':deck_id,'s0':max(a,min(active)-.025),'s1':min(b,max(active)+.025),'x0':-radius,'x1':radius,'kind':'bowsprit_partner','z_m':baseline(start) if callable(baseline) else float(baseline)}
            result.append(hole)
            if register and not any(q['id']==hole['id'] for q in ctx.mast_mortises):ctx.mast_mortises.append(hole)
    return result


def deck_surface(ctx,deck_id,a,b,baseline,holes=(),thickness=.075,camber=.065,material='deck',width_limit=None,board_width=None):
    """Closed individual planks clipped to hull, with exact rectangular voids."""
    if b-a<.02:return []
    holes=shaft_holes(ctx,deck_id,a,b,baseline,holes,register=True)
    p=ctx.p;plank=float(board_width or ctx.layout['plank_width_m']);gap=.0035
    maxw=ctx.B/2-.13
    if width_limit is not None:maxw=min(maxw,float(width_limit))
    cuts={-maxw,maxw}
    count=math.ceil(maxw/plank)
    for k in range(-count,count+1):
        if -maxw<k*plank<maxw:cuts.add(k*plank)
    for hole in holes:
        cuts.update(x for x in(hole['x0'],hole['x1']) if -maxw<x<maxw)
    cuts=sorted(cuts);objects=[]
    for number,(rawlo,rawhi) in enumerate(zip(cuts,cuts[1:])):
        if rawhi-rawlo<.012:continue
        xlo=rawlo+gap/2;xhi=rawhi-gap/2;mid=(xlo+xhi)/2
        runs=[(a,b)]
        for hole in holes:
            if xlo<hole['x1']-1e-6 and xhi>hole['x0']+1e-6:runs=_subtract(runs,hole['s0'],hole['s1'])
        # Butt ends stagger every four strakes and lie on a regular beam grid.
        butt_pitch=max(2.4,min(5.4,ctx.L*.15));offset=(number%4)*butt_pitch/4
        for butt in [a+offset+k*butt_pitch for k in range(-1,math.ceil((b-a)/butt_pitch)+2)]:
            if a+.03<butt<b-.03:
                split=[]
                for aa,bb in runs:
                    if aa+.03<butt<bb-.03:split.extend([(aa,butt-gap/2),(butt+gap/2,bb)])
                    else:split.append((aa,bb))
                runs=split
        for run,(aa,bb) in enumerate(runs):
            stations={aa,bb}
            n=max(2,math.ceil((bb-aa)/.50))
            stations.update(aa+(bb-aa)*i/n for i in range(n+1))
            def clearance(s):
                z=baseline(s) if callable(baseline) else float(baseline)
                return min(maxw,ctx.width(s,z)-.15)-min(abs(xlo),abs(xhi)) if xlo*xhi>0 else min(maxw,ctx.width(s,z)-.15)
            ordered=sorted(stations)
            # Add the exact station where a straight plank nibbles into the side.
            for sa,sb in zip(ordered,ordered[1:]):
                if clearance(sa)*clearance(sb)<0:
                    lo,hi=sa,sb
                    for _ in range(32):
                        m=(lo+hi)/2
                        if clearance(lo)*clearance(m)<=0:hi=m
                        else:lo=m
                    stations.add((lo+hi)/2)
            stations=sorted(s for s in stations if clearance(s)>=-1e-7)
            merged=[]
            for station in stations:
                if merged and station-merged[-1]<.00005:
                    if abs(clearance(station))<abs(clearance(merged[-1])):merged[-1]=station
                else:merged.append(station)
            stations=merged
            # A run of zero-width rings is one hull-transition tip, never a
            # vertical fin between two degenerate cross-sections.
            tips=[];last_collapsed=False
            for station in stations:
                zz=baseline(station) if callable(baseline) else float(baseline);ww=min(maxw,max(.005,ctx.width(station,zz)-.15));collapsed=min(ww,xhi)-max(-ww,xlo)<.00005
                if collapsed and last_collapsed:
                    if abs(clearance(station))<abs(clearance(tips[-1])):tips[-1]=station
                else:tips.append(station)
                last_collapsed=collapsed
            stations=tips
            if len(stations)<2:continue
            verts=[];faces=[];lookup={};rings=[]
            def vert(q):
                key=tuple(round(v,7) for v in q)
                if key not in lookup:lookup[key]=len(verts);verts.append(q)
                return lookup[key]
            for s in stations:
                zz=baseline(s) if callable(baseline) else float(baseline);w=min(maxw,max(.005,ctx.width(s,zz)-.15))
                lo=max(-w,xlo);hi=min(w,xhi)
                if hi-lo<.00005:lo=hi=(lo+hi)/2
                zl=_surface_z(ctx,baseline,s,lo,camber);zh=_surface_z(ctx,baseline,s,hi,camber)
                rings.append([vert(p(lo,s,zl-thickness)),vert(p(hi,s,zh-thickness)),vert(p(hi,s,zh)),vert(p(lo,s,zl))])
            def face(ids):
                ids=list(dict.fromkeys(ids))
                if len(ids)>=3:faces.append(tuple(ids))
            face(list(reversed(rings[0])))
            for ra,rb in zip(rings,rings[1:]):
                for k in range(4):face([ra[k],ra[(k+1)%4],rb[(k+1)%4],rb[k]])
            face(rings[-1])
            if len(verts)<6:continue
            obj=ctx.mesh('%s_plank_%03d_%02d'%(deck_id,number,run),verts,faces,material,'surface',[p(mid,aa,0),p(mid,bb,0)],collision=True)
            _mark(obj,physical_plank=True,deck_id=deck_id,structural_role='deck_plank',preserve_solid_lod=True)
            ctx.deck_nodes.append(obj);objects.append(obj)
    ctx.deck_groups[deck_id]=ctx.deck_groups.get(deck_id,[])+objects
    return objects


def _hole(ctx,definition,deck_id,default_id):
    s=float(definition.get('at',0))*ctx.L;length=float(definition.get('length_m',2.4));w=float(definition.get('width_m',1.8));x=float(definition.get('x_m',0))
    return {'id':definition.get('id',default_id),'deck_id':deck_id,'s0':s-length/2,'s1':s+length/2,'x0':x-w/2,'x1':x+w/2,'coaming_height_m':float(definition.get('coaming_height_m',.20)),'target_deck_id':definition.get('target_deck_id','hold'),'kind':definition.get('kind','hatch')}


def _beams(ctx,deck_id,a,b,baseline,holes=(),thickness=.075,camber=.065):
    holes=shaft_holes(ctx,deck_id,a,b,baseline,holes)
    spacing=max(.50,min(.78,ctx.layout['frame_spacing_m']*1.12));n=max(2,math.ceil((b-a)/spacing));nodes=[]
    for k in range(n+1):
        s=a+(b-a)*k/n;z=baseline(s) if callable(baseline) else float(baseline);w=ctx.width(s,z)-.14
        if w<.20:continue
        intervals=[(-w,w)]
        for hole in holes:
            if hole['s0']-.11<s<hole['s1']+.11:intervals=_subtract(intervals,hole['x0']-.015,hole['x1']+.015)
        for j,(lo,hi) in enumerate(intervals):
            # Cambered transverse beam is three solid scarfed pieces.
            points=[lo]+[v for v in(-w*.50,0,w*.50) if lo+.12<v<hi-.12]+[hi]
            for q,(xa,xb) in enumerate(zip(points,points[1:])):
                za=_surface_z(ctx,baseline,s,xa,camber)-thickness-.065;zb=_surface_z(ctx,baseline,s,xb,camber)-thickness-.065
                ob=ctx.beam('%s_bearing_beam_%03d_%d_%d'%(deck_id,k,j,q),ctx.p(xa,s,za),ctx.p(xb,s,zb),.14,.13,'spar','surface',collision=True)
                _mark(ob,deck_id=deck_id,structural_role='deck_beam');nodes.append(ob)
        # Hanging knees fasten the beam shoulders to the real frame heads.
        knee_top=_surface_z(ctx,baseline,s,w,camber)-thickness-.035;knee_drop=min(.60,max(.25,ctx.B*.065))
        port_bay=any(abs(s-port['s'])<port['w']/2+.12 and knee_top-knee_drop<port['z']+port['h']/2+.10 and knee_top>port['z']-port['h']/2-.10 for port in ctx.ports)
        if len(intervals)==1 and intervals[0][1]-intervals[0][0]>w*1.8 and not port_bay:
            for side in(-1,1):
                top=_surface_z(ctx,baseline,s,side*w,camber)-thickness-.035
                drop=min(.60,max(.25,ctx.B*.065));inner=side*(w-min(.54,w*.38));outer=side*(w-.02)
                bottomx=side*max(.03,ctx.width(s,top-drop)-.18)
                points=[(outer,top),(inner,top),(bottomx,top-drop)]
                verts=[ctx.p(x,s+ds,z) for ds in(-.065,.065) for x,z in points]
                faces=[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)]
                knee=ctx.mesh('%s_hanging_knee_%03d_%s'%(deck_id,k,side),verts,faces,'wood','structure',[verts[1],verts[2]],collision=True)
                nodes.append(_mark(knee,deck_id=deck_id,structural_role='deck_knee',interior=True))
    _join_near(ctx,nodes,ctx.deck_groups.get(deck_id,[]),'The actual transverse deck beam bears immediately below these individual planks.')
    _join_near(ctx,nodes,ctx.hull_nodes,'The deck beam end is housed in the inner hull ceiling and frame head.')
    ctx.structure_nodes.extend(nodes);return nodes


def port_clear_paths(ctx,points,radius):
    """Cut real rectangular port voids through rib/ceiling centreline paths."""
    result=[];current=[];padding=radius+.018
    for a,b in zip(points,points[1:]):
        a,b=Vector(a),Vector(b);intervals=[(0.,1.)];aa=(-a.y,a.z);dd=(-(b.y-a.y),b.z-a.z)
        for port in ctx.ports:
            entry,leave=0.,1.;valid=True
            for value,delta,lo,hi in zip(aa,dd,(port['s']-port['w']/2-padding,port['z']-port['h']/2-padding),(port['s']+port['w']/2+padding,port['z']+port['h']/2+padding)):
                if abs(delta)<1e-12:
                    if value<lo or value>hi:valid=False;break
                else:
                    x,y=sorted(((lo-value)/delta,(hi-value)/delta));entry=max(entry,x);leave=min(leave,y)
                    if entry>=leave:valid=False;break
            if valid and leave>0 and entry<1:
                lo,hi=max(0.,entry),min(1.,leave);remaining=[]
                for c,d in intervals:
                    if hi<=c or lo>=d:remaining.append((c,d))
                    else:
                        if lo>c:remaining.append((c,lo))
                        if hi<d:remaining.append((hi,d))
                intervals=remaining
        for lo,hi in intervals:
            if (hi-lo)*(b-a).length<.0001:continue
            start=a.lerp(b,lo);end=a.lerp(b,hi)
            if current and (current[-1]-start).length>.00001:
                if len(current)>1:result.append(current)
                current=[]
            if not current:current=[start]
            if (current[-1]-end).length>.00001:current.append(end)
            if hi<1-.000001:
                if len(current)>1:result.append(current)
                current=[]
        if not intervals and current:
            if len(current)>1:result.append(current)
            current=[]
    if len(current)>1:result.append(current)
    return [path for path in result if sum((b-a).length for a,b in zip(path,path[1:]))>.03]


def _framing(ctx):
    p=ctx.p;spacing=float(ctx.layout['frame_spacing_m']);n=max(8,math.floor(ctx.L*.91/spacing));frames=[]
    for k in range(n+1):
        s=-ctx.L*.46+ctx.L*.92*k/n;bottom=-ctx.draft+ctx.profile_curve(s,2);top=ctx.main_height(s)-.16;depth=top-bottom
        if depth<.45:continue
        radius=max(.055,min(.12,ctx.B*.012));path=[]
        # The inside face remains visibly separate from the solid outer shell.
        for side in(-1,1):
            values=[1-i/9 for i in range(10)] if side<0 else [i/9 for i in range(1,10)]
            for t in values:
                z=bottom+.22+(depth-.22)*t;x=side*max(.02,ctx.width(s,z)-.14-radius)
                path.append(p(x,s,z))
        pieces=port_clear_paths(ctx,path,radius)
        for segment,piece in enumerate(pieces):
            name='interior_frame_%03d'%k+('_piece_%02d'%segment if len(pieces)>1 else '')
            frame=ctx.tube(name,piece,radius,'wood','structure',sides=4)
            _mark(frame,structural_role='hull_frame',interior=True,real_port_clearance=True);frames.append(frame)
        # Visible top timbers flank real gun ports, never cross their opening.
        for side,label in[(1,'port'),(-1,'starboard')]:
            hi=ctx.deck_height(s)+float(ctx.hull.get('bulwark_height',.8))-.08
            if hi<=top+.2:continue
            spans=[(top,hi)]
            for port in ctx.ports:
                if abs(s-port['s'])<port['w']/2+.10:spans=_subtract(spans,port['z']-port['h']/2-.035,port['z']+port['h']/2+.035)
            for j,(za,zb) in enumerate(spans):
                if zb-za<.10:continue
                ob=ctx.beam('top_timber_%s_%03d_%d'%(label,k,j),p(side*(ctx.width(s,za)-.21),s,za),p(side*(ctx.width(s,zb)-.21),s,zb),radius*1.4,radius*1.6,'wood','structure')
                frames.append(_mark(ob,structural_role='top_timber',interior=True))
    # Lower battery ports have full inner jambs, sills and lintels around the
    # genuinely absent rib/lining sections, with closed timber cut ends.
    for port in ctx.ports:
        if port['z']-port['h']/2>=ctx.main_height(port['s'])-.10:continue
        for side,label in((1,'port'),(-1,'starboard')):
            group=[];s0=port['s']-port['w']/2-.075;s1=port['s']+port['w']/2+.075;z0=port['z']-port['h']/2-.075;z1=port['z']+port['h']/2+.075
            for j,ss in enumerate((s0,s1)):
                group.append(ctx.beam('gunport_%s_%s_%s_jamb_%s'%(port['row'],label,port['index'],j),p(side*(ctx.width(ss,z0)-.16),ss,z0),p(side*(ctx.width(ss,z1)-.16),ss,z1),.10,.12,'wood','structure'))
            for tag,zz in(('sill',z0),('lintel',z1)):
                group.append(ctx.beam('gunport_%s_%s_%s_%s'%(port['row'],label,port['index'],tag),p(side*(ctx.width(s0,zz)-.16),s0,zz),p(side*(ctx.width(s1,zz)-.16),s1,zz),.12,.10,'wood','structure'))
            for obj in group:_mark(obj,structural_role='gunport_frame',interior=True,port_row=port['row'],port_index=port['index'])
            _join_near(ctx,group,group,'These actual jamb, sill and lintel timbers frame the genuine lower battery opening.')
            frames.extend(group)
    _join_near(ctx,frames,ctx.hull_nodes,'The internal frame is fastened against the actual thick hull planking.')
    ctx.frame_nodes=frames;ctx.structure_nodes.extend(frames)
    # Keelson and bilge stringers are genuine closed timber, visible below the sole.
    ss=[-ctx.L*.44+ctx.L*.88*i/56 for i in range(57)]
    keelson=ctx.tube('interior_keelson',[p(0,s,-ctx.draft+ctx.profile_curve(s,2)+.28) for s in ss],.10,'spar','structure',sides=4)
    ctx.structure_nodes.append(_mark(keelson,structural_role='keelson',interior=True))
    for side,label in[(1,'port'),(-1,'starboard')]:
        for row,t in enumerate((.20,.48,.76) if ctx.layout.get('kind')=='open_boat' or ctx.layout.get('ceiling_planking') is False else (.15,.27,.39,.52,.65,.78,.90)):
            path=[]
            for s in ss:
                bottom=-ctx.draft+ctx.profile_curve(s,2);z=bottom+.25+(ctx.main_height(s)-bottom-.42)*t
                path.append(p(side*max(.02,ctx.width(s,z)-.16),s,z))
            radius=.045 if ctx.B<6 else .058;pieces=port_clear_paths(ctx,path,radius)
            for segment,piece in enumerate(pieces):
                name='ceiling_strake_%s_%02d'%(label,row)+('_piece_%02d'%segment if len(pieces)>1 else '')
                o=ctx.tube(name,piece,radius,'deck','structure',sides=4)
                ctx.structure_nodes.append(_mark(o,structural_role='ceiling_strake',interior=True,real_port_clearance=True))
    _join_near(ctx,ctx.structure_nodes[-15:],frames,'The inner ceiling strake is fastened along the actual hull frames.')


def _coaming(ctx,hole,baseline):
    p=ctx.p;a,b=hole['s0'],hole['s1'];lo,hi=hole['x0'],hole['x1'];h=hole['coaming_height_m'];nodes=[]
    for tag,x in [('port',hi),('starboard',lo)]:
        za=_surface_z(ctx,baseline,a,x)+h/2-.015;zb=_surface_z(ctx,baseline,b,x)+h/2-.015
        nodes.append(ctx.beam(hole['id']+'_coaming_'+tag,p(x,a-.06,za),p(x,b+.06,zb),.12,h+.03,'spar','surface',collision=True))
    # A cabin stairwell stays open at its lower door end.
    ends=[('fore',b)] if hole.get('kind')=='cabin_stairwell' else [('aft',a),('fore',b)]
    for tag,s in ends:
        z=_surface_z(ctx,baseline,s,0)+h/2-.015
        nodes.append(ctx.box(hole['id']+'_coaming_'+tag,p((lo+hi)/2,s,z),(hi-lo-.12,.12,h+.03),'spar','surface',collision=True))
    for ob in nodes:_mark(ob,structural_role='hatch_coaming',construction_kind='hatch_coaming',portal_id=hole['id'])
    _join_near(ctx,nodes,ctx.deck_groups.get(hole['deck_id'],[]),'The hatch coaming is seated into the real perimeter planks of the aperture.')
    return nodes


def _stair_tread_boxes(ctx,upper,lower,width,kind):
    upper=Vector(upper);lower=Vector(lower);count=max(3,math.ceil((upper.z-lower.z)/.235));boxes=[]
    run=abs(upper.y-lower.y);going=max(.13,min(.28,run/count+.05))
    for i in range(1,count+(0 if kind=='deck_stair' else 1)):
        t=i/count;q=lower.lerp(upper,t);q.z-=.035
        station=-q.y;inside=max(.28,min(ctx.width(ss,zz) for ss in(station-going/2,station+going/2) for zz in(q.z-.035,q.z+.035))-.30);lo=max(q.x-width/2-.03,-inside);hi=min(q.x+width/2+.03,inside)
        boxes.append((i,Vector(((lo+hi)/2,q.y,q.z)),(max(.02,hi-lo),going,.07)))
    return boxes


def _stairs(ctx,name,upper,lower,width=.95,kind='ladder',handrails=True):
    p=ctx.p;upper=Vector(upper);lower=Vector(lower);rise=upper.z-lower.z
    if rise<.13:return []
    count=max(3,math.ceil(rise/.235));nodes=[]
    # Real stringers with a closed rectangular section and individually solid treads.
    for side in(-1,1):
        a=lower+Vector((side*width/2,0,0));b=upper+Vector((side*width/2,0,.12))
        nodes.append(ctx.beam(name+'_stringer_'+str(side),a,b,.075,.15,'spar','stair',collision=True))
    for i,center,size in _stair_tread_boxes(ctx,upper,lower,width,kind):
        o=ctx.box(name+'_tread_%02d'%i,center,size,'deck','stair',collision=True)
        nodes.append(o)
    for side in((-1,1) if handrails else ()):
        # Handrails rise from the same real stringers, not unsupported floating ropes.
        for i,t in enumerate((.10,.50,.93)):
            q=lower.lerp(upper,t)+Vector((side*(width/2+.06),0,0))
            post=ctx.beam(name+'_rail_post_%s_%s'%(side,i),q,q+Vector((0,0,.82)),.045,.045,'spar','stair',collision=True);nodes.append(post)
        rail=ctx.tube(name+'_handrail_'+str(side),[lower.lerp(upper,.10)+Vector((side*(width/2+.06),0,.82)),lower.lerp(upper,.93)+Vector((side*(width/2+.06),0,.82))],.025,'rope','stair',sides=6)
        nodes.append(rail)
    for o in nodes:_mark(o,structural_role=kind,interior_access=True)
    _join_near(ctx,nodes,nodes,'These real stair treads, stringers and handrail posts are joined at their timber mountings.')
    ctx.stair_nodes.extend(nodes);return nodes


def _bulkhead(ctx,name,s,floor,ceiling,door_width=1.05,door_height=1.88,door_x=0):
    """Planked partition with an actual full-depth doorway, lintel and jambs."""
    p=ctx.p;zfloor=floor(s) if callable(floor) else float(floor);ztop=ceiling(s) if callable(ceiling) else float(ceiling)
    width=max(.12,ctx.width(s,(zfloor+ztop)/2)-.22);dh=min(float(door_height),ztop-zfloor-.10);dw=min(float(door_width),max(.6,2*width-.35));left=door_x-dw/2;right=door_x+dw/2;nodes=[]
    if ztop-zfloor<.2:return [],None
    partner_feet=[q for q in shaft_holes(ctx,'partition_floor',s-ctx.B,s+ctx.B,floor,[]) if q.get('kind')=='mast_partner']
    x=-width;index=0
    while x<width-.01:
        xx=min(x+.18,width);mid=(x+xx)/2
        segments=[(zfloor,ztop)] if xx<=left or x>=right else [(zfloor+dh,ztop)]
        # Align doorway jambs exactly, rather than clipping a visual-only portal.
        if x<left<xx:segments=[(zfloor,ztop)];xx=left;mid=(x+xx)/2
        elif x<right<xx:x=right;continue
        for lo,hi in segments:
            if lo<=zfloor+.03:
                for partner in partner_feet:
                    if partner['s0']-.11<=s<=partner['s1']+.11 and xx>partner['x0']-.11 and x<partner['x1']+.11:lo=max(lo,partner['z_m']+.125)
            if hi-lo<.025:continue
            o=ctx.box(name+'_plank_%03d'%index,p(mid,s,(lo+hi)/2),(xx-x-.002,.075,hi-lo),'wood','partition',collision=True);nodes.append(o);index+=1
        x=xx
    for tag,x in [('left',left-.055),('right',right+.055)]:
        nodes.append(ctx.box(name+'_jamb_'+tag,p(x,s,zfloor+dh/2),(.11,.14,dh),'spar','partition',collision=True))
    nodes.append(ctx.box(name+'_lintel',p(door_x,s,zfloor+dh+.045),(dw+.22,.14,.09),'spar','partition',collision=True))
    nodes.append(ctx.box(name+'_sill',p(door_x,s,zfloor+.025),(dw,.14,.05),'spar','partition',collision=True))
    for ob in nodes:_mark(ob,structural_role='bulkhead',portal_id=name+'_door',interior=True)
    ctx.interior_nodes.extend(nodes)
    portal={'id':name+'_door','from':'main','to':name,'kind':'door','center':list(p(door_x,s,zfloor+dh/2)),'axis':[0,-1,0],'width_m':dw,'height_m':dh,'frame_nodes':[o.name for o in nodes],'access_nodes':[]}
    return nodes,portal


def _waterways(ctx,deck_id,a,b,baseline):
    nodes=[];ss=[a+(b-a)*i/max(8,math.ceil((b-a)/.45)) for i in range(max(8,math.ceil((b-a)/.45))+1)]
    for side,label in[(1,'port'),(-1,'starboard')]:
        valid=[];bow=ctx.spec.get('rig',{}).get('bowsprit')
        for s in ss:
            z=baseline(s) if callable(baseline) else baseline;inside=ctx.width(s,z)-.20
            if inside<.13:continue
            if bow and s>=ctx.L*.40-.03:
                r=max(.055,ctx.B*.035);spar_z=ctx.deck_height(ctx.L*.40)+.15+(s-ctx.L*.40)*math.tan(math.radians(float(bow.get('angle_deg',20))))
                if abs(spar_z-z)<r+.12 and inside<r+.12:continue
            valid.append(s)
        if len(valid)<2:continue
        path=[ctx.p(side*(ctx.width(s,baseline(s) if callable(baseline) else baseline)-.20),s,(baseline(s) if callable(baseline) else baseline)+.025) for s in valid]
        o=ctx.tube(deck_id+'_waterway_'+label,path,.07,'spar','structure',sides=4,collision=True)
        nodes.append(_mark(o,structural_role='waterway',deck_id=deck_id))
    _join_near(ctx,nodes,ctx.deck_groups.get(deck_id,[]),'The thick waterway beds against the nibbed ends of the real deck planking.')
    ctx.structure_nodes.extend(nodes)


def _room(ctx,room_id,kind,floors,ceilings,walls,samples,minimum=1.80):
    kind={'cargo hold':'hold','aft cabin':'cabin','gun deck':'gun_deck','lower deck':'crew_space','open working boat':'open_well'}.get(kind,kind)
    record={'id':room_id,'kind':kind,'floor_nodes':[o.name for o in floors],'ceiling_nodes':[o.name for o in ceilings],'wall_nodes':[o.name for o in (walls or ctx.hull_nodes)],'frame_nodes':[o.name for o in ctx.frame_nodes],'furnishing_nodes':[],'clearance_samples':[list(q) for q in samples],'minimum_headroom_m':minimum}
    ctx.rooms.append(record);return record


def build_decks(ctx):
    ctx.layout=layout_for(ctx);ctx.openings=[];ctx.rooms=[];ctx.routes=[];ctx.deck_groups={};ctx.interior_nodes=[];ctx.structure_nodes=[];ctx.frame_nodes=[];ctx.stair_nodes=[];ctx.room_planes={};ctx.mast_mortises=[]
    p=ctx.p;L=ctx.L;layout=ctx.layout;_framing(ctx)
    if layout['kind']=='open_boat':
        cockpit=ctx.hull.get('cockpit',{'from':-.38,'to':.37,'width_factor':.65,'floor_z_m':-.2})
        a=float(cockpit['from'])*L;b=float(cockpit['to'])*L;w=ctx.B/2*float(cockpit.get('width_factor',.65));floor=float(cockpit.get('floor_z_m',-.2))
        deck_surface(ctx,'bow_platform',b,L/2,ctx.main_height,camber=.025)
        deck_surface(ctx,'stern_platform',-L/2,a,ctx.main_height,camber=.025)
        hole={'s0':a,'s1':b,'x0':-w,'x1':w}
        deck_surface(ctx,'open_side_walkways',a,b,ctx.main_height,[hole],camber=.025)
        floor_nodes=deck_surface(ctx,'open_bilge_boards',a,b,floor,camber=0,width_limit=w,thickness=.05)
        ctx.room_planes['open_boat']={'from':a,'to':b,'floor':lambda s:floor,'width_m':2*w}
        for i,t in enumerate((.19,.78)):
            s=a+(b-a)*t;z=ctx.main_height(s)-.15;ww=max(.1,ctx.width(s)-.17)
            thwart=ctx.box('open_thwart_%d'%i,p(0,s,z),(2*ww,.26,.07),'deck','structure',collision=True)
            _mark(thwart,structural_role='thwart');ctx.structure_nodes.append(thwart)
            for side in(-1,1):
                post=ctx.box('thwart_knee_%s_%s'%(i,side),p(side*(ww-.14),s,z-.18),(.12,.22,.33),'wood','structure',collision=True)
                ctx.structure_nodes.append(post);ctx.joint(thwart,post,'The open-boat thwart bears on its actual side knee.')
        _waterways(ctx,'open_side_walkways',a,b,ctx.main_height)
        room=_room(ctx,'open_boat','open working boat',floor_nodes,[],ctx.frame_nodes,[p(0,a+(b-a)*t,floor+.08) for t in(.3,.5,.7)],0)
        room['open_top']=True
        ctx.routes.append({'id':'open_boat_access','from':'main_deck','to':'open_boat','points':[list(p(0,a+(b-a)*.32,floor+.08)),list(p(0,a+(b-a)*.68,floor+.08))],'clearance_radius_m':.24,'clearance_height_m':1.60})
        ctx.detail_contract={'version':5,'research_path':ctx.spec.get('detailed_layout',{}).get('research_path','interior-research.md'),'feature_groups':[],'interiors':ctx.rooms,'portals':[],'routes':ctx.routes}
        _finalize(ctx);return ctx.layout
    main=ctx.main_height;mainholes=[];cabin=layout.get('cabin');cabin_record=None;cabin_stairwell=None
    # Full-length battery decks are derived from authored gun-floor levels.
    levels=[]
    for i,row in enumerate(ctx.spec.get('guns',{}).get('rows',[])):
        z=float(row['z_m'])-.67
        if z<ctx.freeboard-.30:levels.append({'id':'gun_deck_%d'%i,'z_m':z,'from':-.46,'to':.45})
    for row in layout.get('lower_decks',[]):
        z=float(row.get('z_m',row.get('floor_z_m',0)))
        if not any(abs(z-q['z_m'])<.18 for q in levels):levels.append(dict(row,z_m=z))
    levels=sorted(levels,key=lambda q:q['z_m'],reverse=True)
    # A lowered cabin has its own sole: the obsolete main slab is absent.
    cabin_hole=None;cabin_floor=None;cabin_ceiling=None;cabin_a=cabin_b=None
    if cabin:
        cabin_a=float(cabin.get('from',-.47))*L;cabin_b=float(cabin.get('to',-.25))*L
        ceiling_id=cabin.get('ceiling_deck_id')
        c=next((c for i,c in enumerate(ctx.castles) if ceiling_id=='castle_%d'%i),None) if ceiling_id else next((c for c in ctx.castles if c['from']*L<=cabin_a+.3 and c['to']*L>=cabin_b-.3),None)
        ceiling_add=float(c['height_m']) if c else 0
        cabin['ceiling_deck_id']=ceiling_id or ('castle_%d'%ctx.castles.index(c) if c else 'main')
        cabin_floor_z=float(cabin.get('floor_z_m',ctx.freeboard+ceiling_add-2.10))
        cabin_floor=lambda s,z=cabin_floor_z:z+ctx.profile_curve(s,3)
        cabin_ceiling=lambda s,h=ceiling_add:main(s)+h-.075
        if cabin.get('cut_main_deck',cabin['ceiling_deck_id']!='main' and cabin_floor_z<ctx.freeboard-.12):
            cabin_hole={'id':'cabin_volume','s0':cabin_a,'s1':cabin_b+.001,'x0':-ctx.B,'x1':ctx.B};mainholes.append(cabin_hole)
            run=max(1.4,min(2.4,(ctx.freeboard-cabin_floor_z)*1.55+.45));dw=float(cabin.get('door_width_m',1.05))
            doorx=float(cabin.get('door_x_m',0))
            original_doorx=doorx
            for port in ctx.ports:
                if not cabin_b-.15<port['s']<cabin_b+run+.20:continue
                cx=gun_carriage_center(ctx,port)
                maximum=max(0.,cx-.425-dw/2-.21)
                doorx=math.copysign(min(abs(doorx),maximum),doorx)
            cabin['door_x_m']=doorx
            if abs(doorx-original_doorx)>.001:layout.setdefault('derived_adjustments',[]).append({'feature':'cabin_door_offset','before':original_doorx,'after':doorx,'reason':'The entire real door and stairwell moves inboard to clear the preserved battery carriage bay.'})
            cabin_stairwell={'id':'cabin_access_well','deck_id':'main','kind':'cabin_stairwell','s0':cabin_b-.02,'s1':cabin_b+run,'x0':doorx-dw/2-.10,'x1':doorx+dw/2+.10,'coaming_height_m':.16,'target_deck_id':'cabin'}
            mainholes.append(cabin_stairwell);ctx.openings.append(cabin_stairwell)
    hatches=[]
    hatch_defs=[layout['hatch']]+list(layout.get('extra_hatches',[]))+[dict(q,kind='companion') for q in layout.get('companionways',[])]
    for i,definition in enumerate(hatch_defs):
        hole=_hole(ctx,definition,definition.get('deck_id','main'),'main_hatch' if i==0 else 'hatch_%d'%i)
        if cabin and hole['target_deck_id']=='cabin' and hole['s0']<cabin_b+.1 and hole['s1']>cabin_b-.1:
            length=hole['s1']-hole['s0'];wanted=cabin_b-length-.18
            if wanted>=cabin_a+.12:
                old=[hole['s0'],hole['s1'],hole['deck_id']];hole['s0']=wanted;hole['s1']=cabin_b-.18
                covering=[(idx,c) for idx,c in enumerate(ctx.castles) if c['from']*L<=hole['s0'] and c['to']*L>=hole['s1']]
                if covering:hole['deck_id']='castle_%d'%max(covering,key=lambda q:float(q[1]['height_m']))[0]
                layout.setdefault('derived_adjustments',[]).append({'feature':hole['id'],'reason':'The complete companion shaft is moved aft of the cabin-front wall and starts at the actual upper weather deck; no stair cuts through the bulkhead.','before':old,'after':[hole['s0'],hole['s1'],hole['deck_id']]})
        if hole['deck_id']=='main':
            covering=[(idx,c) for idx,c in enumerate(ctx.castles) if c['from']*L<=hole['s0'] and c['to']*L>=hole['s1']]
            if covering:
                original_deck=hole['deck_id'];hole['deck_id']='castle_%d'%max(covering,key=lambda q:float(q[1]['height_m']))[0]
                layout.setdefault('derived_adjustments',[]).append({'feature':hole['id'],'reason':'The actual hatch ladder and handrail transfer reach the covering forecastle or quarterdeck weather surface, through every intervening deck.','before':original_deck,'after':hole['deck_id']})
        if hole['deck_id']=='main':mainholes.append(hole)
        hatches.append(hole);ctx.openings.append(hole)
    def target_z(h):
        named=next((q for q in levels if q.get('id')==h.get('target_deck_id')),None)
        if named:return float(named['z_m'])
        target=layout.get('cabin' if h.get('target_deck_id')=='cabin' else 'hold',{}) or {}
        return float(target.get('floor_z_m',-ctx.draft+.6))
    for hole in hatches:
        if hole not in mainholes and target_z(hole)<ctx.freeboard-.1:mainholes.append(hole)
    main_nodes=deck_surface(ctx,'main',-L/2-ctx.stern_extension,L/2,main,mainholes)
    _beams(ctx,'main',-L*.48,L*.48,main,mainholes);_waterways(ctx,'main',-L*.48,L*.48,main)
    for i,c in enumerate(ctx.castles):
        deck_id='castle_%d'%i;aa=c['from']*L;bb=c['to']*L;height=lambda s,c=c:main(s)+float(c['height_m'])
        holes=[h for h in hatches if h['s1']>aa and h['s0']<bb and target_z(h)<ctx.freeboard+float(c['height_m'])-.1]
        # A modest open stair at the break keeps raised decks connected.
        nodes=deck_surface(ctx,deck_id,aa,bb,height,holes,thickness=.065,camber=.05);_beams(ctx,deck_id,aa,bb,height,holes,thickness=.065,camber=.05);_waterways(ctx,deck_id,aa,bb,height)
        for boundary,s in [('aft',aa),('fore',bb)]:
            if abs(s)>=L*.475:continue
            direction=1 if boundary=='fore' else -1
            lower_heights=[float(other['height_m']) for other in ctx.castles if other is not c and float(other['height_m'])<float(c['height_m'])-.01 and other['from']*L<=s+direction*.03<=other['to']*L]
            lower_add=max([0.]+lower_heights)
            lower_base=lambda ss,h=lower_add:main(ss)+h
            if lower_add:layout.setdefault('derived_adjustments',[]).append({'feature':'castle_%d_%s_access'%(i,boundary),'reason':'The upper poop break and its real stair start on the covering lower quarterdeck, preserving the intact deck and cabin below.','lower_height_above_main_m':lower_add,'upper_height_above_main_m':float(c['height_m'])})
            if cabin and abs(s-cabin_b)<.25 and cabin.get('ceiling_deck_id')==deck_id:
                walls,portal=_bulkhead(ctx,'aft_cabin',s,cabin_floor,cabin_ceiling,float(cabin.get('door_width_m',1.05)),float(cabin.get('door_height_m',1.88)),float(cabin.get('door_x_m',0)))
                if portal:ctx.portals.append(portal)
                cabin_record={'walls':walls,'ceiling':nodes,'portal':portal}
            else:
                # Castle break has an open working passage, not a blank timber wall.
                walls,portal=_bulkhead(ctx,'castle_break_%d_%s'%(i,boundary),s,lower_base,lambda ss,c=c:main(ss)+float(c['height_m'])-.065,1.05,min(1.85,float(c['height_m'])-lower_add-.12))
                if portal and portal['height_m']>=1.60:ctx.portals.append(portal)
            stairx=min(1.25,max(.85,ctx.B*.14));rise=float(c['height_m'])-lower_add;run=max(.44,rise*1.10)
            short_steps=rise<=.45;castle_width=.43 if short_steps else .80 if ctx.B<8 else .92;stair_half=castle_width/2+(.04 if short_steps else .10)
            stair_s0=min(s-direction*.10,s+direction*run)-.10;stair_s1=max(s-direction*.10,s+direction*run)+.10
            def stair_overlap(x):
                return sum(max(0,min(stair_s1,h['s1']+pad)-max(stair_s0,h['s0']-pad))*max(0,min(x+stair_half,h['x1']+pad)-max(x-stair_half,h['x0']-pad)) for h,pad in [(h,.12) for h in ctx.openings]+[(h,-.020 if short_steps else 0.) for h in ctx.mast_mortises])
            def gun_overlap(x):
                total=0
                for port in ctx.ports:
                    if not stair_s0-.50<port['s']<stair_s1+.50 or port['z']+.30<lower_base(port['s'])-.10:continue
                    for side in(-1,1):
                        cx=side*gun_carriage_center(ctx,port)
                        total+=max(0,min(x+stair_half,cx+.53)-max(x-stair_half,cx-.53))*5
                return total
            override=c.get('stair_x_m',ctx.layout.get('castle_stair_x_m'))
            candidates=[float(override)] if override is not None else [stairx,-stairx,1.40,-1.40,.75,-.75,0.]
            def outside_hull(xx):
                for t in(0.,.5,1.):
                    ss=s-direction*.10+direction*(run+.10)*t
                    zz=lower_base(ss)+rise*(1-t)
                    if abs(xx)+stair_half>ctx.width(ss,zz)-(.05 if short_steps else .10):return True
                    if not short_steps and abs(xx)+stair_half>ctx.width(ss,zz+.82)-.28:return True
                return False
            # Search between the authored choices as well: a narrow side lane
            # beside a real companion cannot be represented by x=0 or +/- .75.
            dense=[i*.05 for i in range(-math.ceil(ctx.B*10),math.ceil(ctx.B*10)+1)]
            candidates=list(dict.fromkeys(candidates+dense))
            # Check the same physical tread boxes used by _stairs against the
            # actual hanging knees.  An outboard lane may clear the hull yet
            # run straight through an inward-projecting knee shoulder.
            from mathutils.bvhtree import BVHTree
            kv=[];kf=[]
            for knee in ctx.structure_nodes:
                if knee.get('structural_role')!='deck_knee':continue
                points=[knee.matrix_world@v.co for v in knee.data.vertices]
                if max(-q.y for q in points)<stair_s0 or min(-q.y for q in points)>stair_s1:continue
                offset=len(kv);kv.extend(points);kf.extend(tuple(offset+j for j in face.vertices) for face in knee.data.polygons)
            knee_tree=BVHTree.FromPolygons(kv,kf) if kv else None
            def hits_knee(xx):
                if knee_tree is None:return False
                upper=p(xx,s-direction*.10,height(s));lower=p(xx,s+direction*run,lower_base(s+direction*run));vertices=[];faces=[]
                for _,center,size in _stair_tread_boxes(ctx,upper,lower,castle_width,'deck_stair'):
                    offset=len(vertices);vertices.extend(center+Vector((dx*size[0]/2,dy*size[1]/2,dz*size[2]/2)) for dz in(-1,1) for dy in(-1,1) for dx in(-1,1))
                    faces.extend(tuple(offset+j for j in face) for face in((0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)))
                return bool(knee_tree.overlap(BVHTree.FromPolygons(vertices,faces)))
            feasible=[xx for xx in candidates if not outside_hull(xx) and stair_overlap(xx)<=.0001 and not hits_knee(xx)]
            if not feasible and ctx.B<8 and not short_steps:
                # Stringer centres at 0.64 m give a real 0.70 m tread and
                # 0.715 m between the handrail posts on this compact flight.
                castle_width=.64;stair_half=castle_width/2+.10
                feasible=[xx for xx in candidates if not outside_hull(xx) and stair_overlap(xx)<=.0001 and not hits_knee(xx)]
            if feasible:stairx=min(feasible,key=lambda xx:gun_overlap(xx)+(abs(xx) if short_steps else abs(abs(xx)-stairx))*.001)
            else:stairx=min(candidates,key=lambda xx:(1000000 if outside_hull(xx) else 0)+(100000 if stair_overlap(xx)>.0001 else 0)+stair_overlap(xx)+gun_overlap(xx))
            if s*direction<L*.40:
                upper=p(stairx,s-direction*.10,height(s));lower=p(stairx,s+direction*run,lower_base(s+direction*run))
                _stairs(ctx,'castle_stair_%d_%s'%(i,boundary),upper,lower,castle_width,'deck_stair',handrails=not short_steps)
    # Lower structural gun decks receive matching open hatch shafts.
    for i,level in enumerate(levels):
        deck_id=level.get('id','lower_%d'%i);z=float(level['z_m']);base=lambda s,z=z:z+ctx.profile_curve(s,3);aa=float(level.get('from',-.45))*L;bb=float(level.get('to',.44))*L
        holes=[dict(h,deck_id=deck_id) for h in hatches if h['s1']>aa and h['s0']<bb and target_z(h)<z-.15]
        if cabin_floor is not None and abs(z-(cabin_floor(0)))<.20:holes.append(cabin_hole or {'s0':cabin_a,'s1':cabin_b,'x0':-ctx.B,'x1':ctx.B})
        floors=deck_surface(ctx,deck_id,aa,bb,base,holes);_beams(ctx,deck_id,aa,bb,base,holes);_waterways(ctx,deck_id,aa,bb,base)
        upper=main_nodes if i==0 else ctx.deck_groups[levels[i-1].get('id','lower_%d'%(i-1))]
        sample_s=min(max(L*.02,aa+.6),bb-.6)
        if any(h['s0']-.3<sample_s<h['s1']+.3 for h in holes):sample_s=aa+(bb-aa)*.26
        room=_room(ctx,deck_id,'gun deck' if deck_id.startswith('gun') else 'lower deck',floors,upper,[],[p(0,sample_s,_surface_z(ctx,base,sample_s,0)+.08)],1.65)
        ctx.room_planes[deck_id]={'from':aa,'to':bb,'floor':base,'width_m':ctx.B-.6}
    hold=layout.get('hold')
    if hold:
        aa=float(hold.get('from',-.38))*L;bb=float(hold.get('to',.34))*L;z=float(hold.get('floor_z_m',-ctx.draft+.60));base=lambda s,z=z:z+ctx.profile_curve(s,3)*.35
        if cabin_b is not None and cabin_floor(0)-z<1.70:aa=max(aa,cabin_b+.01)
        # Never duplicate a full battery floor at the same elevation.
        nearest=next((q for q in levels if abs(q['z_m']-z)<.22),None)
        floors=ctx.deck_groups.get(nearest.get('id'),[]) if nearest else deck_surface(ctx,'hold',aa,bb,base,camber=.025,thickness=.065)
        if not nearest:_beams(ctx,'hold',aa,bb,base,thickness=.065,camber=.025)
        ctx.room_planes['hold']={'from':aa,'to':bb,'floor':base,'width_m':ctx.B*.65}
        ceiling=ctx.deck_groups[levels[-1].get('id')] if levels else main_nodes
        samples=[]
        for ss in (aa+(bb-aa)*.30,aa+(bb-aa)*.67):
            if not (cabin_a is not None and cabin_a<ss<cabin_b):samples.append(p(0,ss,_surface_z(ctx,base,ss,0,.025)+.08))
        _room(ctx,'hold','cargo hold',floors,ceiling,[],samples,float(hold.get('minimum_headroom_m',1.65)))
    if cabin:
        if abs(cabin_floor(0)-ctx.freeboard)<.10 and not cabin_hole:
            floors=[o for o in main_nodes if cabin_a-.01<=-sum(v.co.y for v in o.data.vertices)/len(o.data.vertices)<=cabin_b+.01]
        else:
            floors=deck_surface(ctx,'cabin_sole',cabin_a,cabin_b,cabin_floor,camber=.025,thickness=.065)
            _beams(ctx,'cabin_sole',cabin_a,cabin_b,cabin_floor,thickness=.065,camber=.025)
        ctx.room_planes['cabin']={'from':cabin_a,'to':cabin_b,'floor':cabin_floor,'width_m':ctx.B*.70}
        if cabin_stairwell:
            doorx=float(cabin.get('door_x_m',0));dw=float(cabin.get('door_width_m',1.05));landing_a=cabin_b+.00175;landing_b=cabin_b+.55
            corridor=[{'s0':landing_a-.01,'s1':landing_b+.01,'x0':-ctx.B,'x1':doorx-dw/2-.04},{'s0':landing_a-.01,'s1':landing_b+.01,'x0':doorx+dw/2+.04,'x1':ctx.B}]
            landing=deck_surface(ctx,'cabin_entry_landing',landing_a,landing_b,cabin_floor,corridor,camber=.025,thickness=.065)
            carlings=[]
            for side in(-1,1):
                xx=doorx+side*(dw/2-.03);sa=cabin_b-.24;sb=landing_b+.02
                beam=ctx.beam('cabin_landing_carling_'+str(side),p(xx,sa,_surface_z(ctx,cabin_floor,sa,xx,.025)-.13),p(xx,sb,_surface_z(ctx,cabin_floor,sb,xx,.025)-.13),.11,.13,'spar','surface',collision=True)
                beam['structural_role']='deck_beam';beam['deck_id']='cabin_entry_landing';carlings.append(beam)
            _join_near(ctx,carlings,landing,'These real landing planks rest on the named longitudinal companion carlings.')
            _join_near(ctx,carlings,[o for o in ctx.structure_nodes if o.get('deck_id')=='cabin_sole' and o.get('structural_role')=='deck_beam'],'This cantilevered landing carling is lapped into the actual transverse cabin deck beam.')
            ctx.structure_nodes.extend(carlings)
            top=p(doorx,cabin_stairwell['s1']-.10,_surface_z(ctx,main,cabin_stairwell['s1']-.10,doorx));bottom=p(doorx,cabin_b+.45,_surface_z(ctx,cabin_floor,cabin_b+.45,doorx,.025))
            access=_stairs(ctx,'cabin_companion_stair',top,bottom,dw-.12,'companion_stair')
            for node in access:node['portal_id']='cabin_access_well'
            coaming=_coaming(ctx,cabin_stairwell,main);ctx.interior_nodes.extend(coaming)
            if cabin_record and cabin_record['portal']:cabin_record['portal']['access_nodes']=[o.name for o in access]
        if cabin_record is None:
            walls,portal=_bulkhead(ctx,'aft_cabin',cabin_b,cabin_floor,cabin_ceiling,float(cabin.get('door_width_m',1.05)),float(cabin.get('door_height_m',1.88)),float(cabin.get('door_x_m',0)))
            if portal:ctx.portals.append(portal)
            cabin_record={'walls':walls,'ceiling':ctx.deck_groups.get(cabin.get('ceiling_deck_id','main'),main_nodes),'portal':portal}
        walls=cabin_record['walls']
        ceiling=cabin_record['ceiling']
        sample=cabin_a+(cabin_b-cabin_a)*.48
        _room(ctx,'cabin','aft cabin',floors,ceiling,walls,[p(0,sample,_surface_z(ctx,cabin_floor,sample,0,.025)+.08)],float(cabin.get('minimum_headroom_m',1.70)))
    # One continuous physical ladder per shaft; each intervening real deck
    # receives its own framed aperture and a measured portal in the graph.
    for hole in hatches:
        if hole['deck_id']=='main':base=main
        elif hole['deck_id'] in ctx.room_planes:base=ctx.room_planes[hole['deck_id']]['floor']
        else:base=next((lambda s,c=c:main(s)+float(c['height_m']) for i,c in enumerate(ctx.castles) if hole['deck_id']=='castle_%d'%i),main)
        coamings=_coaming(ctx,hole,base);ctx.interior_nodes.extend(coamings)
        target=ctx.room_planes.get(hole['target_deck_id'],ctx.room_planes.get('hold'))
        access=[]
        center_s=(hole['s0']+hole['s1'])/2;x=(hole['x0']+hole['x1'])/2
        if target:
            upper=p(x,hole['s1']-.14,_surface_z(ctx,base,hole['s1']-.14,x)+.22)
            lower=p(x,hole['s0']+.12,target['floor'](hole['s0']+.12)+.04)
            access=_stairs(ctx,hole['id']+'_ladder',upper,lower,min(.98,hole['x1']-hole['x0']-.24),'hold_ladder')
            for node in access:node['portal_id']=hole['id']
        source_id='main_deck' if hole['deck_id']=='main' or hole['deck_id'].startswith('castle_') else hole['deck_id']
        chain=[(source_id,base,coamings)]
        if target:
            for level in levels:
                level_id=level.get('id');plane=ctx.room_planes[level_id]
                if level_id!=hole['target_deck_id'] and plane['from']<=center_s<=plane['to'] and target['floor'](center_s)+.3<plane['floor'](center_s)<base(center_s)-.3:
                    hd=dict(hole,id=hole['id']+'_'+level_id,deck_id=level_id)
                    cm=_coaming(ctx,hd,plane['floor']);ctx.interior_nodes.extend(cm)
                    chain.append((level_id,plane['floor'],cm))
        chain.append((hole['target_deck_id'],target['floor'] if target else base,[]))
        for j,((source,source_base,frame),(destination,dest_base,_)) in enumerate(zip(chain,chain[1:])):
            portal_id=hole['id'] if j==0 else hole['id']+'_'+source
            center=p(x,center_s,source_base(center_s))
            ctx.portals.append({'id':portal_id,'from':source,'to':destination,'kind':'hatch','center':list(center),'axis':[0,0,1],'width_m':hole['x1']-hole['x0'],'depth_m':hole['s1']-hole['s0'],'frame_nodes':[o.name for o in frame],'access_nodes':[o.name for o in access]})
            if target and access:
                # Points follow the continuous ladder inside the real shaft.
                def on_ladder(z):
                    t=max(0,min(1,(z-lower.z)/max(.01,upper.z-lower.z)))
                    q=lower.lerp(upper,t);q.z=z+.08;return q
                ztop=source_base(center_s)+.20;zbottom=dest_base(center_s)+.06
                points=[on_ladder(ztop),on_ladder(zbottom)]
                ctx.routes.append({'id':portal_id+'_access','from':source,'to':destination,'points':[list(q) for q in points],'clearance_radius_m':.24,'clearance_height_m':1.60,'mode':'climb'})
    for i,definition in enumerate(layout.get('partitions',[])):
        s=float(definition['at'])*L;room=ctx.room_planes.get(definition.get('deck_id','hold'))
        if not room:continue
        ceiling=(lambda s,z=levels[-1]['z_m']:z+ctx.profile_curve(s,3)-.075) if definition.get('deck_id','hold')=='hold' and levels else main
        walls,portal=_bulkhead(ctx,'partition_%d'%i,s,room['floor'],ceiling,float(definition.get('door_width_m',1.05)),float(definition.get('door_height_m',1.85)),float(definition.get('door_x_m',0)))
        if portal:ctx.portals.append(portal)
    ctx.detail_contract={'version':5,'research_path':layout.get('research_path','interior-research.md'),'feature_groups':[],'interiors':ctx.rooms,'portals':ctx.portals,'routes':ctx.routes}
    _finalize(ctx);return layout


def _finalize(ctx):
    ctx.interior_nodes.extend(ctx.structure_nodes);ctx.interior_nodes.extend(ctx.stair_nodes)
    # Explicit semantic groups let the independent audit distinguish genuine
    # structural detail from an inflated triangle or barrel count.
    roles=[('deck_planking','deck_plank'),('internal_frames','hull_frame'),('hatch_joinery','hatch_coaming'),('access_stairs','hold_ladder'),('cabin_joinery','bulkhead')]
    for name,role in roles:
        nodes=[o.name for o in ctx.vis if o.get('structural_role')==role]
        if nodes:ctx.detail_contract['feature_groups'].append({'id':name,'nodes':nodes,'minimum_instances':min(4 if name=='hatch_joinery' else 3,len(nodes)),'required':True})
        elif ctx.layout['kind']=='open_boat' and name in('hatch_joinery','access_stairs','cabin_joinery'):
            ctx.detail_contract['feature_groups'].append({'id':name,'required':False,'reason':'The researched tiny Tartane is an open working boat with exposed frames and bilge boards; a deck hatch, interior stair or enclosed cabin would invent an inappropriate ship structure.'})
    for room in ctx.rooms:
        marker=ctx.marker('interior_'+room['id'],Vector(room['clearance_samples'][0]) if room['clearance_samples'] else Vector(),{'room_id':room['id'],'space_kind':room['kind'],'static_interior':True})
    return ctx.detail_contract


def _supported_stair_lane(points,tread_edges,door_edges,hit,support_nodes):
    """Choose a body-clear lane on the existing physical companion flight."""
    if not tread_edges:raise ValueError('Cabin companion passage has no actual stair treads')
    radius=.24;edge_margin=.015;origin=points[0].x
    left=max([a+radius+edge_margin for a,b in tread_edges]+[door_edges[0]+radius+edge_margin])
    right=min([b-radius-edge_margin for a,b in tread_edges]+[door_edges[1]-radius-edge_margin])
    offsets=[0.]+[sign*k*.025 for k in range(1,13) for sign in(1,-1)]
    for shift in offsets:
        if not left-1e-6<=origin+shift<=right+1e-6:continue
        # The top and foot follow the chosen lane on the wide stair; the
        # existing cabin point stays centred through its narrower doorway.
        candidate=[q+Vector((shift if i<2 else 0,0,0)) for i,q in enumerate(points)];supports=[];clear=True
        for a,b in zip(candidate,candidate[1:]):
            distance=(b-a).length;shoulder=Vector((0,0,.88))
            if hit(a+shoulder,(b-a).normalized(),distance):clear=False;break
            count=max(2,math.ceil(distance/.25)+1)
            for k in range(count):
                foot=a.lerp(b,k/(count-1));center=foot+shoulder
                if any(hit(center,axis,radius+.005) for axis in((1,0,0),(-1,0,0),(0,1,0),(0,-1,0))) or hit(foot+Vector((0,0,.15)),(0,0,1),1.45):clear=False;break
                bearing=None
                # A mathematical line can fall into a caulking seam or the
                # small tread/landing joint.  Keep every bearing ray within a
                # 60 mm foot patch and require a real named walking surface.
                for dx,dy in((0,0),(.009,0),(-.009,0),(0,.03),(0,-.03)):
                    down=hit(foot+Vector((dx,dy,.15)),(0,0,-1),.55)
                    if down and down[1] in support_nodes:bearing=down;break
                if bearing is None:clear=False;break
                supports.append({'route_point':list(foot),'surface_node':bearing[1],'surface_point':list(bearing[0])})
            if not clear:break
        if clear:return candidate,{'offset_m':shift,'supported_samples':supports,'scope':'Measured static lane within the existing tread and door edges; all scene obstacles retained.'}
    raise ValueError('No supported body-clear lane within the actual cabin companion tread width')


def finalize_contract(ctx):
    """Measure useful sample positions against the finished physical scene.

    This only chooses evidence points inside already-authored rooms. It does
    not suppress obstructions, delete furniture, or relax usable headroom.
    """
    from mathutils.bvhtree import BVHTree
    vertices=[];faces=[];owners=[]
    for ob in ctx.vis:
        if ob.type!='MESH':continue
        offset=len(vertices);vertices.extend(ob.matrix_world@v.co for v in ob.data.vertices)
        for poly in ob.data.polygons:faces.append(tuple(offset+i for i in poly.vertices));owners.append(ob.name)
    tree=BVHTree.FromPolygons(vertices,faces,all_triangles=False,epsilon=.00001)
    def hit(q,d,distance):
        loc,normal,index,dist=tree.ray_cast(Vector(q),Vector(d),distance)
        return (loc,owners[index],dist) if index is not None else None
    for room in ctx.rooms:
        plane=ctx.room_planes.get(room['id'])
        if not plane:continue
        room['frame_nodes']=list(dict.fromkeys(o.name for o in ctx.vis if o.get('structural_role') in ('hull_frame','top_timber','deck_beam','deck_knee','ceiling_strake','keelson','waterway','pillar','gunport_frame')))
        floors=set(room['floor_nodes']);overheads=set(room['ceiling_nodes'])|set(room['frame_nodes']);minimum=max(1.60,float(room['minimum_headroom_m']));candidates=[]
        aa=plane['from'];bb=plane['to'];length=bb-aa
        # Spread the grid through the actual usable extent, away from endwalls.
        count=max(9,math.ceil(length/.42))
        for k in range(1,count):
            s=aa+length*k/count
            for x in (.11,-.11,.33,-.33,.77,-.77):
                if abs(x)>max(.1,plane['width_m']/2-.30):continue
                q=ctx.p(x,s,plane['floor'](s)+.19)
                down=hit(q,(0,0,-1),.36)
                if not down or down[1] not in floors:continue
                foot=down[0]+Vector((0,0,.08));up=hit(foot,(0,0,1),20)
                if room.get('open_top'):
                    if up and up[2]<1.60:continue
                elif not up or up[1] not in overheads or up[2]+.08<minimum:continue
                shoulder=foot+Vector((0,0,.88))
                if any(hit(shoulder,axis,.255) for axis in((1,0,0),(-1,0,0),(0,1,0),(0,-1,0))):continue
                candidates.append(foot)
        chosen=[]
        if candidates:
            chosen=[candidates[len(candidates)//2]]
            while len(chosen)<3:
                other=max(candidates,key=lambda q:min((q-r).length for r in chosen))
                if min((other-r).length for r in chosen)<.25:break
                chosen.append(other)
        if len(chosen)<3 or max((a-b).length for a in chosen for b in chosen)<1.2:
            raise ValueError('No three genuinely useful clear floor/headroom samples for '+room['id']+' in '+ctx.spec['id'])
        room['clearance_samples']=[list(q) for q in chosen]
    # Level cabin doors join the real lower deck/hold; lowered outside cabin
    # companions instead include their complete physical stair flight.
    cabin=ctx.layout.get('cabin')
    if cabin and 'cabin' in ctx.room_planes:
        plane=ctx.room_planes['cabin'];s=plane['to'];x=float(cabin.get('door_x_m',0));z=plane['floor'](s)+.105
        for portal in ctx.portals:
            if portal['kind']!='door' or portal.get('to')!='aft_cabin':continue
            target='cabin';floorlevel=plane['floor'](0)
            choices=[(name,q) for name,q in ctx.room_planes.items() if name not in('cabin','open_boat') and abs(q['floor'](0)-floorlevel)<.22]
            source=min(choices,key=lambda item:abs(item[1]['floor'](0)-floorlevel))[0] if choices else 'main_deck'
            portal['from']=source;portal['to']=target
            stairwell=next((h for h in ctx.openings if h.get('kind')=='cabin_stairwell'),None)
            if stairwell:
                sx=float(cabin.get('door_x_m',0));upper=ctx.p(sx,stairwell['s1']-.12,_surface_z(ctx,ctx.main_height,stairwell['s1']-.12,sx)+.10)
                lower=ctx.p(sx,s+.45,plane['floor'](s+.45)+.105)
                points=[upper,lower,ctx.p(sx,s-.78,plane['floor'](s-.78)+.105)];portal['from']='main_deck'
                treads=[o for o in ctx.vis if o.name.startswith('cabin_companion_stair_tread_')]
                edges=[(min((o.matrix_world@v.co).x for v in o.data.vertices),max((o.matrix_world@v.co).x for v in o.data.vertices)) for o in treads]
                supports={name for plane_room in ctx.rooms if plane_room['id']=='cabin' for name in plane_room['floor_nodes']}
                supports.update(o.name for o in ctx.deck_groups.get('main',[])+ctx.deck_groups.get('cabin_entry_landing',[])+treads)
                points,lane=_supported_stair_lane(points,edges,(sx-float(cabin.get('door_width_m',1.05))/2,sx+float(cabin.get('door_width_m',1.05))/2),hit,supports)
            else:points=[ctx.p(x,s+.62,z),ctx.p(x,s-.62,z)]
            route={'id':portal['id']+'_passage','from':portal['from'],'to':target,'points':[list(q) for q in points],'clearance_radius_m':.24,'clearance_height_m':1.60,'mode':'geometric_passage'}
            if stairwell:route['physical_lane']=lane
            ctx.routes.append(route)
    ctx.detail_contract['axes']='blender_world';ctx.detail_contract['interiors']=ctx.rooms;ctx.detail_contract['portals']=ctx.portals;ctx.detail_contract['routes']=ctx.routes
    return ctx.detail_contract


def build_mast_partners(ctx):
    """Real square deck mortises, compression wedges and keelson mast steps."""
    nodes=[];p=ctx.p
    from mathutils.bvhtree import BVHTree
    shell_vertices=[];shell_faces=[]
    for shell in ctx.hull_nodes:
        offset=len(shell_vertices);shell_vertices.extend(shell.matrix_world@v.co for v in shell.data.vertices)
        shell_faces.extend(tuple(offset+i for i in f.vertices) for f in shell.data.polygons)
    inner_shell_tree=BVHTree.FromPolygons(shell_vertices,shell_faces)
    def inner_step_halfwidth(station,z):
        distances=[]
        for side in(-1,1):
            point,normal,index,distance=inner_shell_tree.ray_cast(p(0,station,z),Vector((side,0,0)),ctx.B)
            if index is not None:distances.append(distance)
        return max(.035,(min(distances) if distances else ctx.width(station,z)-.20)-.025)
    for hole in ctx.mast_mortises:
        z=hole['z_m']+.065;a,b=hole['s0'],hole['s1'];lo,hi=hole['x0'],hole['x1'];group=[]
        for side,x in[('port',hi+.055),('starboard',lo-.055)]:
            group.append(ctx.beam(hole['id']+'_'+side,p(x,a-.055,z),p(x,b+.055,z),.11,.12,'spar','structure',collision=True))
        if hole['kind']=='mast_partner':
            for side,ss in[('aft',a-.055),('fore',b+.055)]:group.append(ctx.beam(hole['id']+'_'+side,p(lo-.11,ss,z),p(hi+.11,ss,z),.11,.12,'spar','structure',collision=True))
            radius=hole['mast_radius_m'];ss=(a+b)/2
            for side in(-1,1):
                group.append(ctx.box(hole['id']+'_compression_wedge_x_'+str(side),p(side*(radius+.012),ss,z),(.070,.16,.11),'wood','structure'))
                group.append(ctx.box(hole['id']+'_compression_wedge_s_'+str(side),p(0,ss+side*(radius+.012),z),(.16,.070,.11),'wood','structure'))
            mast=next((o for o in ctx.vis if o.get('rig_member')=='mast' and o.name==hole['mast_name']),None)
            if mast:_join_near(ctx,group,[mast],'The individually named compression wedge bears against this mast inside its true square deck mortise.')
        for ob in group:ob['structural_role']='mast_partner';ob['interior']=True;ob['partner_id']=hole['id']
        _join_near(ctx,group,group,'These partner carlings, crosspieces and compression wedges form the actual mortise frame.')
        _join_near(ctx,group,ctx.deck_groups.get(hole['deck_id'],[]),'The mast partner is housed into the actual perimeter planks of its open deck mortise.')
        nodes.extend(group)
    for definition in ctx.spec.get('rig',{}).get('masts',[]):
        mast=next((o for o in ctx.vis if o.get('rig_member')=='mast' and o.name==definition['name']),None)
        if mast is None:continue
        s=float(definition['at'])*ctx.L;base=ctx.deck_height(s);heel=float(definition.get('heel_z_m',base-.2));rake=float(definition.get('rake',0))
        if 'rake_deg' in definition:rake=math.tan(math.radians(float(definition['rake_deg'])))
        s=s-rake*(heel-base);bottom=-ctx.draft+ctx.profile_curve(s,2)+.36
        # A mast whose authored heel is above a castle deck bears on its local
        # structural partner instead of inventing a pedestal through the cabin.
        if heel-bottom>ctx.draft+ctx.freeboard+.2:
            width=max(.25,ctx.width(s,heel)-.10)
            bearing=ctx.beam(definition['name']+'_local_heel_bearing',p(-width,s,heel-.06),p(width,s,heel-.06),.18,.16,'spar','structure',collision=True)
            bearing['structural_role']='deck_beam';nodes.append(bearing)
            ctx.joint(bearing,mast,'This authored mast outside the hold has its heel tenoned into the actual named transverse bearing beam.')
            _join_near(ctx,[bearing],ctx.hull_nodes,'This local mast-bearing beam is housed into the real inner hull planking at its two ends.')
            continue
        radius=max(.075,float(definition['height_m'])/80)
        vertices=[];faces=[];segments=6;top=heel+.06
        for k in range(segments+1):
            ss=s-radius+2*radius*k/segments;foot=-ctx.draft+ctx.profile_curve(ss,2)+.36
            low_width=min(radius,inner_step_halfwidth(ss,foot+.005));high_width=min(radius,inner_step_halfwidth(ss,top))
            vertices.extend([p(-low_width,ss,foot),p(low_width,ss,foot),p(high_width,ss,top),p(-high_width,ss,top)])
        faces=[(3,2,1,0),tuple(segments*4+k for k in range(4))]
        for k in range(segments):
            for j in range(4):faces.append((k*4+j,k*4+(j+1)%4,(k+1)*4+(j+1)%4,(k+1)*4+j))
        step=ctx.mesh(definition['name']+'_keelson_mast_step',vertices,faces,'spar','surface',[p(0,s,bottom),p(0,s,top)],collision=True)
        step['structural_role']='mast_step';step['interior']=True;nodes.append(step)
        ctx.joint(step,mast,'The extended mast heel is housed in this real timber mast-step socket above the keelson.')
        keelson=next((o for o in ctx.vis if o.name=='interior_keelson'),None)
        if keelson:ctx.joint(step,keelson,'This mast-step pedestal bears directly on the real longitudinal keelson.')
    bow=ctx.spec.get('rig',{}).get('bowsprit');spar=next((o for o in ctx.vis if o.name=='bowsprit'),None)
    if bow and spar:
        from mathutils.bvhtree import BVHTree
        start=p(0,ctx.L*.40,ctx.deck_height(ctx.L*.40)+.15);angle=math.radians(float(bow.get('angle_deg',20)));end=start+p(0,math.cos(angle)*float(bow['length_m']),math.sin(angle)*float(bow['length_m']))
        radius=max(.055,ctx.B*.035);spar_tree=BVHTree.FromPolygons([spar.matrix_world@v.co for v in spar.data.vertices],[list(f.vertices) for f in spar.data.polygons])
        targets=[]
        socket_members=list(ctx.hull_nodes)+[o for o in ctx.vis if o.get('structural_role')=='bulkhead' and o.name.startswith('castle_break_')]
        for hull in socket_members:
            tree=BVHTree.FromPolygons([hull.matrix_world@v.co for v in hull.data.vertices],[list(f.vertices) for f in hull.data.polygons])
            if tree.overlap(spar_tree):targets.append(hull)
        if targets:
            cutter=ctx.tube('temporary_bowsprit_true_socket_cutter',[start-(end-start).normalized()*.03,end+(end-start).normalized()*.03],radius+.018,'wood','fitting',sides=12)
            for hull in targets:
                modifier=hull.modifiers.new('true_bowsprit_socket','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
                bpy.context.view_layer.objects.active=hull
                with bpy.context.temp_override(object=hull,active_object=hull):bpy.ops.object.modifier_apply(modifier=modifier.name)
                if not hull.data.vertices:
                    name=hull.name
                    for group in(ctx.vis,ctx.hull_nodes,ctx.interior_nodes,ctx.structure_nodes,ctx.deck_nodes):
                        if hull in group:group.remove(hull)
                    for collider in list(ctx.col):
                        if collider.get('visual_source')==name:ctx.col.remove(collider);bpy.data.objects.remove(collider,do_unlink=True)
                    for record in ctx.rooms+ctx.portals:
                        for field in('floor_nodes','ceiling_nodes','wall_nodes','frame_nodes','furnishing_nodes','access_nodes'):
                            if name in record.get(field,[]):record[field].remove(name)
                    for feature in ctx.detail_contract.get('feature_groups',[]):
                        if name in feature.get('nodes',[]):feature['nodes'].remove(name)
                    mesh=hull.data;bpy.data.objects.remove(hull,do_unlink=True)
                    if mesh.users==0:bpy.data.meshes.remove(mesh)
                    continue
                # Exact Boolean evaluation can expose the accepted hull's
                # collinear terminal T-junctions. Split the long edge at the
                # existing boundary vertex; this adds no cap across the socket.
                import bmesh
                bm=bmesh.new();bm.from_mesh(hull.data)
                for repair in range(6):
                    boundary=[e for e in bm.edges if e.is_boundary];boundary_verts={v for e in boundary for v in e.verts};changed=False
                    for edge in boundary:
                        a,b=edge.verts;delta=b.co-a.co
                        if delta.length_squared<1e-14:continue
                        match=None
                        for vertex in boundary_verts:
                            if vertex in edge.verts:continue
                            t=(vertex.co-a.co).dot(delta)/delta.length_squared
                            if 1e-6<t<1-1e-6 and (vertex.co-a.co-delta*t).length<1e-6:match=(vertex,t);break
                        if match:
                            vertex,t=match;_,new=bmesh.utils.edge_split(edge,a,t);new.co=vertex.co.copy();bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);changed=True;break
                    if not changed:break
                bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(hull.data);bm.free()
                from v2_boats import physical_uv
                original_path=json.loads(hull['grain_path_json'])['points'] if hull.get('grain_path_json') else None
                physical_uv(hull,Vector(hull.get('grain_axis',[0,-1,0])),[Vector(q) for q in original_path] if original_path else [p(0,-ctx.L/2,0),p(0,ctx.L/2,0)])
                # The socket is still independently tested after export.
                # Remove any sub-ten-micron Boolean sliver with the unchanged
                # repository mesh finalizer; it never caps a hull aperture.
                from v2_mesh_finish import finish_scene
                ctx.hull_finish.append({'v5_socket_mesh_finish':finish_scene([hull])})
                physical_uv(hull,Vector(hull.get('grain_axis',[0,-1,0])),[Vector(q) for q in original_path] if original_path else [p(0,-ctx.L/2,0),p(0,ctx.L/2,0)])
                hull['true_bowsprit_socket']=True
            import bpy as _bpy
            ctx.vis.remove(cutter);mesh=cutter.data;_bpy.data.objects.remove(cutter,do_unlink=True)
            if mesh.users==0:_bpy.data.meshes.remove(mesh)
        cradle=ctx.box('bowsprit_heel_cradle',start+Vector((0,0,-radius-.065)),(2*radius+.08,.26,.16),'spar','structure',collision=True)
        cradle['structural_role']='mast_partner';nodes.append(cradle);ctx.joint(cradle,spar,'The actual bowsprit heel bears in this timber cradle below its genuine deck and stem socket.')
    ctx.structure_nodes.extend(nodes);ctx.interior_nodes.extend(nodes)
    return nodes


def structural_bearing_joints(ctx):
    """Record only actual intersections between named compatible structural parts.

    The finite bearing map deliberately excludes cargo, furniture, guns and
    generic fittings. Every returned pair is measured with its actual triangles.
    """
    from mathutils.bvhtree import BVHTree
    roles={};bounds={};trees={};grid={};size=1.4
    def role(o):
        if o in ctx.hull_nodes:return 'hull'
        return o.get('structural_role')
    for o in ctx.vis:
        r=role(o)
        if o.type!='MESH' or not r:continue
        if r in ('hold_ladder','deck_stair','companion_stair'):r='stair'
        vs=[o.matrix_world@v.co for v in o.data.vertices]
        lo=[min(q[i] for q in vs) for i in range(3)];hi=[max(q[i] for q in vs) for i in range(3)]
        roles[o.name]=(o,r);bounds[o.name]=(lo,hi)
        trees[o.name]=BVHTree.FromPolygons(vs,[list(f.vertices) for f in o.data.polygons])
        for x in range(math.floor(lo[0]/size),math.floor(hi[0]/size)+1):
            for y in range(math.floor(lo[1]/size),math.floor(hi[1]/size)+1):
                for z in range(math.floor(lo[2]/size),math.floor(hi[2]/size)+1):grid.setdefault((x,y,z),[]).append(o.name)
    reasons={}
    def allow(a,bs,reason):
        for b in bs:reasons[tuple(sorted((a,b)))]=reason
    allow('hull',('hull_frame','top_timber','ceiling_strake','deck_plank','deck_beam','deck_knee','bulkhead','waterway','keelson','mast_partner','gunport_frame'), 'The named internal structural timber is housed against the actual thick hull planking at this measured bearing.')
    allow('gunport_frame',('gunport_frame','hull_frame','ceiling_strake','deck_beam','deck_knee','deck_plank'), 'The named inner port casing is housed into its actual neighboring frame, lining or deck-support timber.')
    allow('hull_frame',('ceiling_strake','deck_plank','deck_beam','deck_knee','waterway','keelson','thwart','mast_step','bulkhead'), 'The named frame receives this actual floor, ceiling, knee or transverse timber at their measured structural bearing.')
    allow('top_timber',('deck_plank','deck_beam','deck_knee','waterway','bulkhead','thwart'), 'This actual deck edge, knee or thwart is seated against its named upper frame timber.')
    allow('ceiling_strake',('deck_plank','deck_beam','deck_knee','waterway','thwart','bulkhead'), 'The named inner ceiling strake beds behind this measured floor edge, beam end or partition timber.')
    allow('deck_plank',('deck_beam','deck_knee','bulkhead','waterway','hatch_coaming','stair','thwart','mast_partner'), 'This named deck plank receives the measured foot, threshold or edge of its actual structural timber.')
    allow('waterway',('bulkhead','stair','deck_knee'), 'The named partition foot is housed against this actual perimeter waterway timber.')
    allow('deck_beam',('deck_knee','bulkhead','mast_partner','stair'), 'These named deck-support timbers meet at their measured knee or partition bearing.')
    allow('keelson',('deck_plank','mast_step','deck_beam'), 'The floor board or mast-step heel is borne by the actual named keelson timber.')
    allow('mast_step',('deck_plank','mast_partner'), 'The named floor mortise and its compression framing are housed around this actual mast-step timber.')
    allow('window_frame',('deck_knee','deck_beam','top_timber','hull_frame','bulkhead'), 'The named real window casing is housed against its measured inner structural knee, beam or frame bearing; glazing is excluded.')
    allow('mast_partner',('mast_partner','deck_knee','deck_beam','stair','bulkhead'), 'These measured partner timbers are housed together around their genuine open mast mortise.')
    checked=set();count=0
    for entries in grid.values():
        for i,first in enumerate(entries):
            for second in entries[i+1:]:
                key=tuple(sorted((first,second)))
                if first==second or key in checked:continue
                checked.add(key);a,ra=roles[first];b,rb=roles[second];why=reasons.get(tuple(sorted((ra,rb))))
                if {ra,rb}=={'hatch_coaming','stair'} and a.get('portal_id') and a.get('portal_id')==b.get('portal_id'):why='The named fixed hatch ladder is housed at its own actual coaming and handrail transfer.'
                if {ra,rb}=={'bulkhead','stair'}:
                    wall=a if ra=='bulkhead' else b;stair=b if ra=='bulkhead' else a
                    if wall.name.startswith('aft_cabin_') and stair.name.startswith('cabin_companion_stair'):why='The cabin companion handrail post is bolted to this actual named doorway jamb at its lower landing.'
                    if wall.name.startswith('aft_cabin_') and stair.name.startswith('castle_stair_') and ctx.layout.get('cabin',{}).get('ceiling_deck_id')=='castle_'+stair.name.split('_')[2]:why='The named quarterdeck stair landing is housed into the actual after-cabin front bulkhead at the raised-deck break.'
                    if wall.name.startswith('castle_break_') and stair.name.startswith('castle_stair_') and wall.name.split('_')[2]==stair.name.split('_')[2]:why='The named raised-deck stair stringer is housed into its actual castle-break bulkhead landing.'
                if {ra,rb} in ({'hull','stair'},{'top_timber','stair'}):
                    stair=a if ra=='stair' else b
                    if 'stringer' in stair.name and all(abs((stair.matrix_world@v.co).x)<=ctx.width(-(stair.matrix_world@v.co).y,(stair.matrix_world@v.co).z)+.0001 for v in stair.data.vertices):why='The named stair stringer is housed into the inner planking at this measured bearing; every vertex stays within the actual outer hull envelope.'
                if not why:continue
                lo,hi=bounds[first];aa,bb=bounds[second]
                if not all(lo[k]<=bb[k]+.0001 and aa[k]<=hi[k]+.0001 for k in range(3)):continue
                if trees[first].overlap(trees[second]):ctx.joint(a,b,why);count+=1
    return {'actual_bearing_pairs_measured':count,'method':'Finite compatible structural-member map; concrete triangle intersections, excluding all furniture and guns.'}


def bind_battery_rooms(ctx):
    """Bind actual naval gun stations to the floor supporting their trucks.

    This inventories the battery already present in a gun deck. It never adds
    cargo, changes fixture feature groups, or binds a gun by name alone.
    """
    from mathutils.bvhtree import BVHTree
    objects={o.name:o for o in ctx.vis if o.type=='MESH'};bindings=[]
    for room in ctx.rooms:
        if room['kind']!='gun_deck':continue
        plane=ctx.room_planes[room['id']];floor_names=set(room['floor_nodes']);vertices=[];faces=[];owners=[]
        for name in sorted(floor_names):
            floor=objects[name];offset=len(vertices);vertices.extend(floor.matrix_world@v.co for v in floor.data.vertices)
            for face in floor.data.polygons:faces.append(tuple(offset+i for i in face.vertices));owners.append(name)
        tree=BVHTree.FromPolygons(vertices,faces);stations=[]
        for barrel in ctx.gun_nodes:
            tag=barrel.name.removeprefix('gun_barrel_');wheels=[o for name,o in objects.items() if name.startswith('gun_wheel_'+tag+'_')];supports=[]
            if len(wheels)<2:continue
            station=-sum((w.matrix_world@v.co).y for w in wheels for v in w.data.vertices)/sum(len(w.data.vertices) for w in wheels)
            if not plane['from']<=station<=plane['to']:continue
            for wheel in wheels:
                world=[wheel.matrix_world@v.co for v in wheel.data.vertices];lo=[min(q[k] for q in world) for k in range(3)];hi=[max(q[k] for q in world) for k in range(3)];x=(lo[0]+hi[0])/2;y=(lo[1]+hi[1])/2
                for dx in(0.,-.025,.025):
                    origin=Vector((x+dx,y,lo[2]+.20));point,normal,index,distance=tree.ray_cast(origin,Vector((0,0,-1)),.40)
                    if index is not None and abs(lo[2]-point.z)<=.20:
                        supports.append({'wheel_node':wheel.name,'sample_blender_m':list(origin),'floor_node':owners[index],'wheel_bottom_z_m':lo[2],'floor_z_m':point.z,'contact_error_m':abs(lo[2]-point.z)});break
            if len({q['wheel_node'] for q in supports})<2:continue
            prefixes=tuple('gun_'+part+'_'+tag for part in('carriage','cheek','wheel','axle','trunnion'))
            assembly=[o for name,o in objects.items() if name==barrel.name or name.startswith(barrel.name+'_') or any(name==prefix or name.startswith(prefix+'_') for prefix in prefixes)]
            for obj in assembly:obj['battery_room_id']=room['id'];obj['interior_use']='Actual naval battery station supported by this measured gun-deck floor.'
            names=[o.name for o in assembly];room['furnishing_nodes']=list(dict.fromkeys(room['furnishing_nodes']+names))
            record={'room_id':room['id'],'barrel_node':barrel.name,'assembly_nodes':names,'support_samples':supports,'tolerance_m':.20,'method':'At least two actual truck-bottom samples raycast to this room\'s declared physical floor.'};stations.append(record);bindings.append(record)
        room['battery_assemblies']=stations
    ctx.detail_contract['battery_floor_bindings']=bindings
    return bindings
