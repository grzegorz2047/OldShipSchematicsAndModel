"""Explicit post-export casting-surface revision of an existing POTC package.

No architecture builder, material/texture writer, decimator or COL writer runs.
The same repair_package(HERE) call follows future full builds in owned build.py.
"""
from __future__ import annotations
import hashlib,json,os,tempfile,struct,shutil
from contextlib import contextmanager
from pathlib import Path
import numpy as np
import gun_surface_fix as F
import gun_surface_native as N

TOLERANCE=2e-5
MAX_FILE_BYTES=99*1024*1024
HELPERS=('gun_surface_fix.py','gun_surface_native.py','gun_surface_repair.py','gun_surface_bindings.py')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

@contextmanager
def _staging_directory(asset):
    """Keep a failed transaction's journal/backups available for inspection."""
    stage=Path(tempfile.mkdtemp(prefix='.surface-stage-'+asset.name+'-',dir=asset.parent))
    try:
        yield stage
    except BaseException:
        if not(stage/'transaction.json').exists():shutil.rmtree(stage)
        raise
    else:
        shutil.rmtree(stage)

def _exact_role_names(actual,expected,context):
    actual=list(actual);expected=set(expected)
    if len(actual)!=len(set(actual))or set(actual)!=expected:
        raise ValueError(context+' cannon_barrel role set differs: missing='+str(sorted(expected-set(actual)))+' extra='+str(sorted(set(actual)-expected)))
    return {'passed':True,'count':len(actual),'names':sorted(actual)}

def _metadata_paths(asset,design):
    review=design.get('detail_contract',{}).get('visual_review_path','detail-review.json')
    paths={'build.py','spec.json','design.json','surface-repair.json',review,
           'detail-camera-overrides.json','detail-camera-closeups.json'}
    for value in paths:
        p=Path(value)
        if p.is_absolute()or'..'in p.parts:raise ValueError('Unsafe metadata path')
    return paths

def cached_repair(asset,current_files,helper_hashes,binding):
    """No writes, including no review invalidation, for an intact completed stage."""
    path=asset/'surface-repair.json'
    if not path.is_file():return None
    try:
        ledger=json.loads(path.read_text());bound=ledger['bindings']
        if ledger.get('schema')!=1 or ledger.get('passed')is not True:return None
        if ledger.get('after_files')!=current_files or ledger.get('helper_sha256')!=helper_hashes:return None
        if bound.get('binding_helper_sha256')!=helper_hashes['gun_surface_bindings.py']:return None
        sources=bound['repair_source_sha256'];root=asset.parents[1]
        for relative,sha in sources.items():
            source=(root/relative).resolve()
            if not source.is_relative_to(root)or not source.is_file()or digest(source)!=sha:return None
        required={'potc/'+asset.name+'/'+name for name in (*HELPERS,'surface-repair.json')}
        spec=json.loads((asset/'spec.json').read_text());design=json.loads((asset/'design.json').read_text())
        if not required.issubset(set(spec.get('source_paths',[]))):return None
        revision=design.get('surface_revision',{})
        if revision.get('schema')!=1 or revision.get('ledger_path')!='surface-repair.json'or revision.get('parameters')!=ledger.get('parameters'):return None
        hook=binding.check_build_hook(asset,package_module='gun_surface_repair',require_installed=True)
        if not hook.get('passed'):return None
        cameras=bound.get('camera_configs',[]);known={q['path']for q in cameras}
        actual={name for name in ('detail-camera-overrides.json','detail-camera-closeups.json')if(asset/name).is_file()}
        if known!=actual:return None
        for camera in cameras:
            config_path=asset/camera['path'];config=json.loads(config_path.read_text())
            if digest(config_path)!=camera['sha256']or config.get('model_sha256')!=current_files[config['model_path']]:return None
        return {'asset_id':asset.name,'ledger_path':str(path),'ledger_sha256':digest(path),
                'cached_surface_repair':True,'no_write':True,'review_decision':'unchanged'}
    except (KeyError,ValueError,TypeError,OSError):return None

def _commit_with_rollback(asset,replacements,models,metadata,stage,fault_after=None):
    """Hardlink model backups, COPY metadata backups, and restore on BaseException."""
    backup=stage/'rollback';backup.mkdir(exist_ok=True);original={};backups={};committed=[]
    for relative in sorted(set(models)|set(metadata)):
        path=asset/relative;original[relative]=digest(path)if path.is_file()else None
        if not path.is_file():continue
        saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True)
        if relative in models:os.link(path,saved)
        else:shutil.copy2(path,saved)
        backups[relative]=saved
    journal=stage/'transaction.json'
    def record(state):
        temporary=journal.with_suffix('.tmp');temporary.write_text(json.dumps({'state':state,'original':original,'committed':committed},indent=2)+'\n');temporary.replace(journal)
    record('prepared')
    try:
        for relative,source in replacements.items():
            destination=asset/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            os.replace(source,destination);committed.append(relative);record('committing')
            if fault_after is not None and len(committed)==fault_after:raise KeyboardInterrupt('Injected transaction failure')
        record('committed')
    except BaseException:
        # Restore every protected path, not only those already renamed: a
        # failing metadata callback must not be able to leave a truncation.
        for relative,sha in original.items():
            destination=asset/relative
            if sha is None:
                if destination.exists():destination.unlink()
            else:
                saved=backups[relative]
                if relative in models:
                    os.replace(saved,destination)
                else:
                    temporary=destination.with_name(destination.name+'.surface-rollback.tmp')
                    shutil.copy2(saved,temporary);os.replace(temporary,destination)
        if any((digest(asset/path)if(asset/path).is_file()else None)!=sha for path,sha in original.items()):
            record('rollback_failed');raise RuntimeError('Surface rollback failed; retained journal: '+str(journal))
        record('rolled_back');raise

def glb_surface_tables(path,exact_nodes):
    doc,binary,_=F.read_glb(path);nodes={n.get('name'):i for i,n in enumerate(doc['nodes'])};result={}
    _exact_role_names([n.get('name')for n in doc['nodes']if n.get('extras',{}).get('role')=='cannon_barrel'],exact_nodes,str(path))
    for name in exact_nodes:
        ni=nodes[name];node=doc['nodes'][ni];assert node.get('extras',{}).get('role')=='cannon_barrel'
        primitive=doc['meshes'][node['mesh']]['primitives'][0];attrs=primitive['attributes'];matrix=F._world_matrix(doc,ni)
        p=F.accessor(doc,binary,attrs['POSITION']).astype(float);p=p@matrix[:3,:3].T+matrix[:3,3]
        tri=F.accessor(doc,binary,primitive['indices']).astype(int).ravel().reshape(-1,3)
        raw_normals=F.accessor(doc,binary,attrs['NORMAL']).astype(float);normals=raw_normals@np.linalg.inv(matrix[:3,:3]);normals/=np.linalg.norm(normals,axis=1)[:,None]
        uv0=F.accessor(doc,binary,attrs['TEXCOORD_0']);uv1=F.accessor(doc,binary,attrs['TEXCOORD_1'])
        material=doc['materials'][primitive['material']];texture=material['pbrMetallicRoughness']['baseColorTexture']['index'];image=doc['images'][doc['textures'][texture]['source']];view=doc['bufferViews'][image['bufferView']];offset=view.get('byteOffset',0)
        if binary[offset:offset+8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Expected the unchanged PNG PBR atlas')
        image_size=struct.unpack_from('>II',binary,offset+16)
        result[name]={'positions':p,'triangles':tri,'normals':normals[tri],
            'uv0':uv0[tri],'uv1':uv1[tri],
            'encoded_metrics':{'normal_unit_max_error':float(np.abs(np.linalg.norm(raw_normals,axis=1)-1).max()),
                'UV0_AO1_exact_equal':bool(np.array_equal(uv0,uv1)),
                'actual_basecolor_image_px':list(image_size),
                'actual_stored_UV_metrics':F.uv_metrics(p,tri,uv0[tri],image_size)}}
    return result

def keyed(surface):
    result={}
    for face,indices in enumerate(surface['triangles']):
        p=surface['positions'][indices];keys=[tuple(np.round(q,5))for q in p];order=sorted(range(3),key=lambda j:keys[j]);key=tuple(keys[j]for j in order)
        if key in result:raise ValueError('Duplicate actual geometric triangle in casting')
        result[key]={'positions':p[order],**{k:surface[k][face][order]for k in ('normals','uv0','uv1')}}
    return result

def surface_parity(native,exported):
    a,b=keyed(native),keyed(exported);same=set(a)==set(b);report={'same_actual_triangle_keys':same,'triangles':len(a)}
    if same:
        for field in ('positions','normals','uv0','uv1'):
            report[field+'_max_abs_error']=float(max(np.max(np.abs(a[key][field]-b[key][field]))for key in a))
    report['passed']=bool(same and all(report[field+'_max_abs_error']<=TOLERANCE for field in ('positions','normals','uv0','uv1')))
    return report

def _native_stage(source,destination,main_names):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(source))
    candidates=[prefix+name for prefix in ('','lod1_','lod2_')for name in main_names]
    targets=[name for name in candidates if name in bpy.data.objects]
    if not all(name in targets for name in main_names):raise ValueError('Native source is missing an exact main gun node')
    role_set=_exact_role_names([o.name for o in bpy.data.objects if o.get('role')=='cannon_barrel'],targets,str(source))
    for name in targets:
        obj=bpy.data.objects[name];assert obj.type=='MESH'and obj.get('role')=='cannon_barrel'
        users=[o.name for o in bpy.data.objects if o.type=='MESH'and o.data==obj.data]
        if any(other not in targets for other in users):raise ValueError('Casting shares mesh data with a non-target object')
    before=N.non_target_snapshot(set(targets));materials=N.materials_images_snapshot()
    changes=[N.repair_object(bpy.data.objects[name],normal_mode='free')for name in targets]
    needed=not all(row['already_fixed']for row in changes)
    if needed:
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(destination),compress=True,relative_remap=False,copy=True)
        bpy.ops.wm.open_mainfile(filepath=str(destination))
        actual=destination
    else:
        # Already correct native bytes remain untouched, including on replay.
        actual=source
        bpy.ops.wm.open_mainfile(filepath=str(source))
    after=N.non_target_snapshot(set(targets));new_materials=N.materials_images_snapshot()
    _exact_role_names([o.name for o in bpy.data.objects if o.get('role')=='cannon_barrel'],targets,'Fresh-reopened native source')
    differences=[name for name in set(before)|set(after)if before.get(name)!=after.get(name)]
    if differences or materials!=new_materials:
        raise ValueError('Native non-target or material/image invariant failed: '+str(differences[:5]))
    raw={name:N.canonical_corner_surface(bpy.data.objects[name])for name in targets}
    surfaces={name:N.evaluated_corner_surface(bpy.data.objects[name])for name in targets}
    raw_evaluated={name:surface_parity(raw[name],surfaces[name])for name in targets}
    if not all(row['passed']for row in raw_evaluated.values()):raise ValueError('Fresh native stored/evaluated casting surface mismatch')
    report={'source_objects':len(before),'targets':len(targets),
        'target_names':targets,'exact_cannon_barrel_role_set':role_set,'changed_native_bytes_required':needed,'native_reports':changes,
        'non_target_objects_and_target_geometry_invariant':True,'materials_images_invariant':True,
        'non_target_and_geometry_signatures_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
        'stored_vs_evaluated_surface_parity':raw_evaluated,
        'export_comparison_source':'Actual fresh-reopened evaluated/depsgraph corner surfaces',
        'fresh_reopen_used':True,'normal_storage':'custom_normal FLOAT_VECTOR CORNER / FREE'}
    return actual,surfaces,report

def repair_package(asset):
    """Repair two packed native files and six visual GLBs, then bind honestly."""
    asset=Path(asset).resolve();design=json.loads((asset/'design.json').read_text())
    names=list(design['type_contract']['gun_nodes'])
    if not names:return {'skipped':'Unarmed asset; no files changed.'}
    if len(names)!=len(set(names)):raise ValueError('Duplicate gun ledger names')
    files=['model/'+palette+'/'+name for palette in ('ochre','navy')for name in ('source.blend','ship.glb','lod1.glb','lod2.glb')]
    files+=['model/collision.glb'];before_files={name:digest(asset/name)for name in files}
    import gun_surface_bindings as binding
    modules={'gun_surface_fix.py':F.__file__,'gun_surface_native.py':N.__file__,
             'gun_surface_repair.py':__file__,'gun_surface_bindings.py':binding.__file__}
    for helper in HELPERS:
        if not(asset/helper).exists():raise ValueError('Owned helper must be present before repair: '+helper)
        if digest(asset/helper)!=digest(modules[helper]):raise ValueError('Executing/copy helper source differs: '+helper)
    helper_hashes={name:digest(asset/name)for name in HELPERS}
    cached=cached_repair(asset,before_files,helper_hashes,binding)
    if cached is not None:return cached
    binding.check_build_hook(asset,package_module='gun_surface_repair',require_installed=False)
    metadata=_metadata_paths(asset,design)
    input_paths=set(files)|metadata|set(HELPERS)
    original_inputs={p:digest(asset/p)if(asset/p).is_file()else None for p in input_paths}
    native_reports={};export_reports={};parity={};staged={};native_surfaces={}
    # A sibling staging directory guarantees same-filesystem atomic rename.
    # It is outside the asset package; failed transactions retain the journal.
    with _staging_directory(asset)as stage:
        for palette in ('ochre','navy'):
            relative='model/'+palette+'/source.blend';destination=stage/(palette+'-source.blend')
            actual,tables,report=_native_stage(asset/relative,destination,names)
            report['model_path']=relative;native_reports[palette]=report;native_surfaces[palette]=tables
            if actual!=asset/relative:staged[relative]=actual
            if actual.stat().st_size>MAX_FILE_BYTES:raise ValueError('Native source exceeds unchanged99MiB package limit')
        for palette in ('ochre','navy'):
            for level,filename in ((0,'ship.glb'),(1,'lod1.glb'),(2,'lod2.glb')):
                prefix=''if level==0 else'lod'+str(level)+'_'
                exact=[prefix+name for name in names];relative='model/'+palette+'/'+filename;destination=stage/(palette+'-'+filename)
                delta=F.patch_glb(asset/relative,destination,exact)
                if destination.stat().st_size>MAX_FILE_BYTES:raise ValueError('Patched GLB exceeds unchanged99MiB package limit')
                tables=glb_surface_tables(destination,exact);checks={}
                for target in exact:
                    metrics=tables[target]['encoded_metrics']
                    if metrics['normal_unit_max_error']>1e-6 or not np.isfinite(metrics['normal_unit_max_error']):
                        raise ValueError('Encoded casting normals are not finite unit vectors')
                    if not metrics['UV0_AO1_exact_equal']or metrics['actual_stored_UV_metrics']['degenerate_uv_triangles']:
                        raise ValueError('Encoded casting UV0/AO1 differ or contain collapsed triangles')
                for name,target in zip(names,exact):
                    native_target=target if target in native_surfaces[palette]else name
                    checks[target]=surface_parity(native_surfaces[palette][native_target],tables[target])
                if not all(row['passed']for row in checks.values()):raise ValueError('Actual fresh-native/GLB surface parity failed: '+relative)
                # Distinguish mapper-f64 diagnostics from actual serialized
                # values and actual per-LOD image dimensions in this package.
                delta['source']=relative;delta['destination']=relative
                delta['diagnostic_scope']='Mapper float64 diagnostics use a2048px reference image. Encoded metrics below decode actual delivered float32 streams and actual LOD image sizes.'
                delta['encoded_surface_metrics']={name:tables[name]['encoded_metrics']for name in exact}
                delta['exact_cannon_barrel_role_set']={'passed':True,'count':len(exact),'names':sorted(exact)}
                for target_report in delta['targets']:
                    target_report['mapper_float64_unit_normal_max_error']=target_report.pop('unit_normal_max_error')
                    target_report['mapper_float64_reference_before_UV']=target_report.pop('before_uv')
                    target_report['mapper_float64_reference_after_UV']=target_report.pop('after_uv')
                export_reports[relative]=delta;parity[relative]={'passed':True,'targets':checks,'float32_tolerance':TOLERANCE}
                staged[relative]=destination
        if digest(asset/'model/collision.glb')!=before_files['model/collision.glb']:
            raise ValueError('COL changed during a surface-only stage')
        after_files={name:digest(staged.get(name,asset/name))for name in files}
        ledger={'schema':1,'method':'Explicit post-export casting-surface revision; no architecture rebuild, no physical geometry or material/texture changes.',
        'parameters':{'normal_storage':'FREE_FLOAT3','meridian_glTF_world':[0,-1,0],
            'meridian_Blender_world':[0,0,-1],'validated_angular_stations':20,
            'authored_continuous_chart_density_compensation':1.05,'surface_parity_tolerance':TOLERANCE},
        'exact_main_gun_nodes':names,'before_files':before_files,'after_files':after_files,
        'native':native_reports,'exports':export_reports,'parity':parity,
        'COL_sha256_unchanged':before_files['model/collision.glb'],
        'helper_sha256':helper_hashes,
        'raw_frozen_export_note':'The unchanged frozen exporter can re-encode normals. This explicit surface-only stage runs after it; final delivered source/evaluated-native and GLB corner NORMAL/UV0/AO1 are independently compared.',
        'passed':True}
        # Complete binding on a disposable metadata/model view first. All
        # production inputs remain untouched if this validation fails.
        sandbox=stage/asset.name;sandbox.mkdir()
        for relative in metadata|set(HELPERS)|{'validation.json','export-review.json','detail-render.json'}:
            source=asset/relative
            if source.is_file():
                destination=sandbox/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        for relative in files:
            destination=sandbox/relative;destination.parent.mkdir(parents=True,exist_ok=True);os.link(staged.get(relative,asset/relative),destination)
        binding.bind_package(sandbox,ledger,before_files,helper_files=HELPERS,package_module='gun_surface_repair')
        for relative in metadata:
            candidate=sandbox/relative
            if candidate.is_file()and(not(asset/relative).is_file()or digest(candidate)!=digest(asset/relative)):
                staged[relative]=candidate
        if any((digest(asset/p)if(asset/p).is_file()else None)!=sha for p,sha in original_inputs.items()):
            raise ValueError('A production input changed concurrently during repair staging')
        _commit_with_rollback(asset,staged,set(files),metadata,stage)
    ledger_path=asset/'surface-repair.json'
    return {'asset_id':asset.name,'ledger_path':str(ledger_path),'ledger_sha256':digest(ledger_path),
            'review_decision':'PENDING','fresh_renders_and_full_audit_required':True,
            'all_target_source_export_parity_passed':True,'COL_sha256_unchanged':before_files['model/collision.glb']}
