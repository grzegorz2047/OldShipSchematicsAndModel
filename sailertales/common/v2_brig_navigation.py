"""Author complete brig routes through the real stair and hatch clearances."""


def finish(navigation,design):
    routes=navigation['routes']
    by_name={r['name']:r for r in routes}
    connector=by_name.get('main_deck_to_quarterdeck')
    stairs=by_name.get('quarterdeck_access')
    if connector is not None and stairs is not None:
        # The main-deck root is only 21 cm from the stair foot. Publish that
        # contiguous approach as part of the complete 4 m stair traversal.
        prefix=connector['points']
        points=stairs['points']
        same=all(abs(a-b)<1e-5 for a,b in zip(prefix[-1],points[0]))
        stairs['points']=prefix+points[1:] if same else prefix+points
        routes.remove(connector)
    ladder=by_name.get('hold_ladder')
    if ladder is None:raise RuntimeError('Brig hold ladder route missing')
    previous=float(design.get('ladder_transfer_lift_m',.50))
    lift=.30
    for p in ladder['points'][1:3]:p[1]+=lift-previous
    design['ladder_transfer_lift_m']=lift
    design['navigation_finish']={
        'quarterdeck':'The main-deck approach is concatenated with the actual stair traversal; no separate token-length corridor is published.',
        'hold_ladder':'The mounted hand-rail transfer is 0.30 m above the measured hatch deck, clearing both its physical coaming and the deployed staysail with the full-height capsule. Landings and the 0.38 m radius/1.85 m height are unchanged.'}
    return design['navigation_finish']
