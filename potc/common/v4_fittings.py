"""Physical anchors, steering and rudder fittings."""
import math
def build_fittings(spec,ctx):
    p=ctx.p
    options=ctx.spec.get('fittings',{});scale=float(options.get('scale',max(.45,min(1.25,ctx.L/26))))
    gun_bounds=[]
    for obj in ctx.vis:
        if obj.type=='MESH' and obj.name.startswith('gun_'):
            vs=[obj.matrix_world@v.co for v in obj.data.vertices]
            gun_bounds.append(([min(v[k] for v in vs) for k in range(3)],[max(v[k] for v in vs) for k in range(3)]))
    for side in ([1] if int(options.get('anchors',2))==1 else [1,-1]) if options.get('anchors',2) else []:
        s=ctx.L*.36;deck=ctx.deck_height(s);rail=float(ctx.hull.get('bulwark_height',.8));x=side*(max(ctx.width(s+v*scale) for v in(-1.05,0,1.05))+1.15*scale);top=max(ctx.deck_height(s+v*scale) for v in(-1.05,0,1.05))+max(rail,1.0*scale)+.32*scale
        shaft=ctx.beam('anchor_shank_'+str(side),p(x,s,top+.2*scale),p(x,s-.6*scale,top-1.5*scale),.12*scale,.12*scale,'iron')
        for arm in(-1,1):
            fluke=ctx.beam('anchor_fluke_%s_%s'%(side,arm),p(x,s-.6*scale,top-1.5*scale),p(x+arm*.5*scale,s-.55*scale,top-1.05*scale),.12*scale,.18*scale,'iron')
            ctx.joint(shaft,fluke,'The anchor flukes are forged onto the shank crown.')
            if arm<0:first_fluke=fluke
            else:ctx.joint(first_fluke,fluke,'The two forged fluke arms meet at their actual common crown.')
        stock=ctx.beam('anchor_stock_'+str(side),p(x,s-1.05*scale,top),p(x,s+1.05*scale,top),.14*scale,.16*scale,'spar');ctx.joint(shaft,stock,'The wooden stock passes through the upper anchor shank.')
        # Two separated shoes support the stock; the real shank passes through
        # the open gap, rather than intersecting a solid transverse cathead.
        shoes=[];used_stations=[]
        for number,wanted in enumerate((-.40,.24)):
            candidates=sorted(set([wanted]+[j/20 for j in range(-18,19)]),key=lambda lead:abs(lead-wanted))
            placement=None
            for lead in candidates:
                station=s+lead*scale
                if abs(station)>ctx.L*.46 or abs(lead+.127)<.22 or any(abs(station-old)<.30*scale for old in used_stations):continue
                floor=ctx.deck_height(station)
                for inside in [side*ctx.width(station)*.4,side*.14*scale,side*.28*scale]:
                    if abs(inside)+.10*scale>ctx.width(station):continue
                    a=p(inside,station,floor);b=p(inside,station,top-.16*scale)
                    low=[min(a[k],b[k])-.09*scale for k in range(3)];high=[max(a[k],b[k])+.09*scale for k in range(3)]
                    if not any(all(low[k]<hi[k] and high[k]>lo[k] for k in range(3)) for lo,hi in gun_bounds):
                        placement=(station,floor,inside);break
                if placement:break
            if placement is None:raise ValueError('No gun-clear anchor shoe support for '+spec['id'])
            station,floor,inside=placement;used_stations.append(station)
            post=ctx.beam('cathead_post_%s_%s'%(side,number),p(inside,station,floor),p(inside,station,top-.16*scale),.14*scale,.14*scale,'spar')
            cat=ctx.beam('cathead_shoe_%s_%s'%(side,number),p(inside,station,top-.16*scale),p(x+side*.12*scale,station,top-.16*scale),.14*scale,.16*scale,'spar')
            shoes.append(cat)
            ctx.joint(cat,post,'The stock-support shoe is housed into its actual deck post.')
            ctx.joint(cat,stock,'The stowed anchor stock rests on this separated shoe, outside the open shank gap.')
            for h in ctx.hull_nodes:ctx.joint(cat,h,'This stock-support shoe passes through the real upper planking at its mounting.')
            for d in ctx.deck_nodes:ctx.joint(post,d,'This stock-support post bears on its actual structural deck.')
    s=float(options.get('helm_at',-.40))*ctx.L;z=ctx.deck_height(s);rs=-ctx.L*.5-ctx.stern_extension-.20;rz=ctx.deck_height(-ctx.L*.5);tiller=None
    if options.get('steering','wheel')=='tiller':
        tiller=ctx.beam('steering_tiller',p(0,rs,rz+float(ctx.hull.get('bulwark_height',.8))+.12),p(0,s+.55*scale,z+float(ctx.hull.get('bulwark_height',.8))+.12),.065*scale,.08*scale,'spar')
    else:
        post=ctx.tube('steering_post',[p(0,s,z),p(0,s,z+1.0*scale)],.065*scale,'spar','fitting',sides=8)
        centre=p(0,s,z+1.0*scale)
        rim=ctx.tube('steering_rim',[centre+p(math.cos(i*math.pi/12)*.45*scale,0,math.sin(i*math.pi/12)*.45*scale) for i in range(25)],.035*scale,'spar','fitting',sides=6)
        ctx.joint(post,rim,'The wheel spindle is supported by this deck pedestal.')
        for i in range(8):
            spoke=ctx.beam('steering_spoke_%d'%i,centre,centre+p(math.cos(i*math.pi/4)*.51*scale,0,math.sin(i*math.pi/4)*.51*scale),.025*scale,.025*scale,'spar')
            ctx.joint(spoke,rim,'The spoke is housed into the actual wheel rim.');ctx.joint(spoke,post,'The spoke joins the steering wheel hub.')
        for d in ctx.deck_nodes:ctx.joint(post,d,'The steering pedestal is seated on the aft deck.')
    if options.get('capstan',True):
        cap=ctx.tube('capstan',[p(0,ctx.L*.12,ctx.deck_height(ctx.L*.12)),p(0,ctx.L*.12,ctx.deck_height(ctx.L*.12)+.75*scale)],.22*scale,'spar','fitting',sides=10)
        for d in ctx.deck_nodes:ctx.joint(cap,d,'The capstan spindle is seated in the main deck bearing.')
    rs=-ctx.L*.5-ctx.stern_extension-.20;rz=ctx.deck_height(-ctx.L*.5);rudder=ctx.box('rudder_blade',p(0,rs-.35,-ctx.draft*.35),(.12,.70,ctx.draft*.85),'spar')
    stock=ctx.tube('rudder_stock',[p(0,rs,-ctx.draft*.8),p(0,rs,rz+float(ctx.hull.get('bulwark_height',.8))+.12 if tiller else rz+.3)],.07,'spar','fitting',sides=8);ctx.joint(stock,rudder,'The real rudder blade is fixed to its stock.')
    if tiller:ctx.joint(tiller,stock,'The actual tiller is keyed to the actual rudder-stock head.')
    for i,zz in enumerate([-ctx.draft*.6,0,rz*.6]):
        hinge=ctx.beam('rudder_hinge_%d'%i,p(0,-ctx.L*.5-ctx.stern_extension,zz),p(0,rs,zz),.07,.07,'iron');ctx.joint(hinge,stock,'The hinge bears on the actual rudder stock.')
        stern=next((h for h in ctx.hull_nodes if h.name=='stern_closure'),None)
        if stern:ctx.joint(hinge,stern,'This real rudder hinge mounts to the stern structure.')
        for backbone in ctx.hull_nodes:
            if backbone.name=='keel':ctx.joint(hinge,backbone,'This real rudder gudgeon is bolted into the actual stern end of the backbone.')

