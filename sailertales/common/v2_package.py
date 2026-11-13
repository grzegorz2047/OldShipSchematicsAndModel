"""Promote audited construction outputs into independent repository asset folders.

Standard Python: python sailertales/common/v2_package.py --ids brig ...
Requires both independent geometric audit and source/export render review PASS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from v2_integrity import check_report

ROOT=Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def safe_child(parent,path):
    parent=parent.resolve();path=path.resolve()
    if not path.is_relative_to(parent):
        raise ValueError('Asset path leaves intended repository folder')
    return path


def details(row):
    value=row.get('reason') or row.get('evidence') or row.get('detail') or ''
    if not isinstance(value,str):value=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    return value.replace('|','/').replace('\n',' ')[:350]


def make_readme(asset,spec,design,audit,review):
    label=spec['label'];vessel=spec['id']
    routes=read(asset/'navigation.json')['routes']
    route_rows='\n'.join('| '+r['name']+' | '+('wspinanie po drabinie' if r.get('mode')=='climb' else 'chodzenie')+' |'
                         for r in routes)
    matrix='\n'.join('| '+str(r.get('id',''))+' | '+str(r.get('status',''))+' | '+details(r)+' |'
                     for r in audit.get('matrix',[]))
    views=[]
    for name,title in [('hero','Cała jednostka'),('deck','Pokład, takielunek ukryty tylko w podglądzie'),
                       ('cabin','Kajuta z perspektywy gracza'),('hold','Ładownia z perspektywy gracza')]:
        if (asset/'previews'/(name+'.png')).exists():
            views.append('![%s](previews/%s.png)'%(title,name))
    construction=design.get('construction') or design.get('method') or design.get('basis',{})
    if not isinstance(construction,str):construction=json.dumps(construction,ensure_ascii=False)
    game_commit=spec.get('source_commit','')
    dimensions=f"{spec['length']} × {spec['beam']} m (profil konstrukcyjny; całkowity obrys z drzewcami jest większy)"
    changes=design.get('game_deviations',design.get('deviations',design.get('limitations',[])))
    if isinstance(changes,dict):changes=[f'{k}: {v}' for k,v in changes.items()]
    if isinstance(changes,str):changes=[changes]
    deviations='\n'.join('- '+str(x) for x in changes)
    triangles=design.get('triangles',{})
    return f'''# {label}

Osobny model jednostki z SailerTales, przebudowany metodą z poradnika
OldShipSchematicsAndModel. Konstrukcja: {construction}.

Wymiary profilu: {dimensions}. Pochodzenie liczb, wzory i świadome odstępstwa
są w [design.json](design.json). Identyfikator `{vessel}` pochodzi z gry;
historyczny typ i zakres rekonstrukcji są opisane oddzielnie od nazwy używanej w grze.

{chr(10).join(views)}

## Pliki

- [Główny GLB](model/ship.glb), [LOD1](model/ship_lod1.glb), [LOD2](model/ship_lod2.glb).
- [Kolizje](model/collision.glb) — osobne statyczne siatki wklęsłe; nie otaczać całej jednostki jednym wypukłym colliderem.
- [Spakowana scena Blender](model/ship.blend).
- [Trasy i wymagania kontrolera](navigation.json).
- [Audyt geometrii i macierz rozdziału 13](validation.json).
- [Porównanie rzeczywistego eksportu ze sceną źródłową](export-review.json).

Wszystkie pokazane wyżej obrazy PNG wyrenderowano po ponownym imporcie
dostarczonego GLB. Porównanie ze spakowaną sceną wykorzystuje te same kamery
i światła. Próg różnicy jasności to 10%, udziałów kanałów koloru 0,04.
Wynik porównania: **{review['passed']}**. Wynik wymaganych kontroli audytu: **{audit['passed']}**.
To dwie oddzielne kontrole — test dojścia nie zastępuje kontroli konstrukcji i eksportu.

## Dostęp gracza

Postać testowa: promień kapsuły 0,38 m, całkowita wysokość 1,85 m, maksymalne
nachylenie chodzenia 35°. Drabiny mają osobny tryb wspinania; nie są przedstawiane
jako schodnie spełniające limit 35°.

| Trasa | Wymagany ruch |
|---|---|
{route_rows}

Ten PR dostarcza statyczny asset i metadane integracji. Kontroler postaci,
wspinanie, ruch postaci wraz z płynącym statkiem, animowanie mechanizmów,
maskowanie wody i podłączenie do aktualnej gry wymagają adaptera silnika.
Należy używać tych samych transformacji modelu, kolizji i punktów tras.
Przechył wraku jest już zapisany w geometrii — nie nakładać go drugi raz.

## Źródła i odstępstwa

Źródłem metody są rozdziały 01–09, 12–14 poradnika i wskazane moduły `blender/`.
Model jest rekonstrukcją do gry, nie pomiarem zachowanego historycznego statku
ani certyfikacją stateczności. Wariant proceduralny materiałów jest opisany
w danych; nie przypisujemy mu fotograficznych tekstur CC0.

Źródło profilu gry: [SailerTales {game_commit[:7]}](https://github.com/grzegorz2047/SailerTales/tree/{game_commit}).

{deviations}

## Macierz kontroli

`NA` oznacza wyłączenie z uzasadnieniem lub pomiar pozostający poza zakresem;
nie jest zaliczeniem kontroli. Pełne dane i zakres są w raporcie JSON.
Nie wyciągać z wyniku tras wniosku, że zweryfikowano każdy punkt pokładu,
wszystkie stanowiska załogi albo dowolny ruch takielunku.

| Punkt | Wynik | Dowód lub ograniczenie |
|---|---|---|
{matrix}

## Odtworzenie i kontrola

Instrukcje oraz wymagania narzędzi są w [common/README.md](../common/README.md).
Samodzielne sprawdzenie aktualności plików nie wymaga Blendera:

```sh
python sailertales/common/v2_integrity.py --asset-dir sailertales/{vessel} --source-root .
```

Liczby trójkątów zapisane przez eksport: `{json.dumps(triangles,ensure_ascii=False)}`.
'''


def promote(vessel,source_root=ROOT):
    asset=safe_child(source_root/'build/final',source_root/'build/final'/vessel)
    target=safe_child(source_root/'sailertales',source_root/'sailertales'/vessel)
    audit=read(asset/'validation.json');review=read(asset/'export-review.json')
    if not audit.get('passed') or not review.get('passed'):
        raise ValueError(vessel+': audit and exported render review must both PASS')
    check_report(asset,source_root)
    for name,expected in review.get('sha256',{}).items():
        rendered_input=safe_child(asset,asset/name)
        if hashlib.sha256(rendered_input.read_bytes()).hexdigest()!=expected:
            raise ValueError(vessel+': export render review is stale for '+name)
    for row in audit.get('matrix',[]):
        if row.get('required') and row.get('status')=='FAIL':
            raise ValueError(vessel+': failed required '+str(row.get('id')))
    spec=read(asset/'spec.json');design=read(asset/'design.json')
    files=set(audit.get('sha256',{}))
    files.update(('spec.json','navigation.json','design.json','validation.json','export-review.json'))
    for name in ('ship.glb','collision.glb','ship_lod1.glb','ship_lod2.glb','ship.blend'):
        files.add('model/'+name)
    for path in (asset/'previews').glob('*.png'):
        files.add(path.relative_to(asset).as_posix())
    for optional in ('rigging_paths.json','rigging-audit.json','name-map.json','material-provenance.json'):
        if (asset/optional).exists():files.add(optional)
    for name in sorted(files):
        source=safe_child(asset,asset/name);dest=safe_child(target,target/name)
        if not source.is_file():raise FileNotFoundError(source)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    (target/'README.md').write_text(make_readme(asset,spec,design,audit,review),encoding='utf-8')
    files.add('README.md')
    print('PROMOTED',vessel,len(files),'files',flush=True)
    return sorted('sailertales/'+vessel+'/'+name for name in files)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='+',required=True)
    args=parser.parse_args()
    promoted={v:promote(v) for v in args.ids}
    common=sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'sailertales/common').glob('v2_*.py'))
    common.append('sailertales/common/rebuild_reference.py')
    common.append('sailertales/common/README.md')
    common.append('sailertales/.gitignore')
    common.append('.gitattributes')
    workflow='.github/workflows/sailertales-model-integrity.yml'
    if (ROOT/workflow).exists():common.append(workflow)
    manifest={'assets':promoted,'common':common,'files':[]}
    all_paths=sorted(set(common+[p for paths in promoted.values() for p in paths]))
    for path in all_paths:
        b=(ROOT/path).read_bytes()
        manifest['files'].append({'path':path,'size':len(b),
            'git_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),
            'sha256':hashlib.sha256(b).hexdigest()})
    (ROOT/'build/publication-manifest-v2.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
