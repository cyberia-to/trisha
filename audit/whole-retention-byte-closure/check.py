"""Replay the privacy-safe selected delivery without network or proof execution."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from privacy import scan

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CAP=4*1024**2


def require(value,message):
    if not value:raise ValueError(message)


def identity(raw):
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def load(path):
    def unique(pairs):
        result={}
        for k,v in pairs:
            require(k not in result,'unique JSON keys');result[k]=v
        return result
    return json.loads(path.read_text(),object_pairs_hook=unique)


def original(row,raw):
    require(identity(raw)==row['original_identity'],'decoded original identity')
    scan(raw,Path(row['original']).name)


def selected(originals=False):
    manifest=load(ROOT/'retention.json')
    require(manifest['schema']=='trisha/byte-closure-selected-originals/v1' and
            manifest['source_head']=='97795590613e625b6be43c5e73afff4ab87009cd','exact delivery provenance')
    rows=manifest['records'];require(len(rows)==77,'exact selected original inventory')
    require(len({r['original'] for r in rows})==len(rows) and len({r['stored'] for r in rows})==len(rows),'unique originals and stored files')
    result={}
    for row in rows:
        relative=Path(row['stored'])
        require(not relative.is_absolute() and '..' not in relative.parts and relative.parts[0]=='retained','owned canonical stored path')
        p=ROOT/relative;require(p.is_file() and not p.is_symlink(),'regular stored original')
        require(p.stat().st_size<=CAP and row['original_identity']['bytes']<=CAP,'bounded selected original')
        raw=p.read_bytes();require(identity(raw)==row['stored_identity'],'stored file identity')
        if row['encoding']=='gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as source:raw=source.read(CAP+1)
        else:require(row['encoding']=='identity','known encoding')
        require(len(raw)<=CAP,'bounded actual decoded original');original(row,raw)
        if originals:
            source=Path(row['original']);require(source.is_file() and not source.is_symlink() and source.stat().st_size<=CAP,'bounded actual original')
            require(source.read_bytes()==raw,'current original equals retained bytes')
        key=str(relative.relative_to('retained'))
        if row['encoding']=='gzip':key=key.removesuffix('.gz')
        result[key]=raw
    actual={str(p.relative_to(ROOT)) for p in (ROOT/'retained').rglob('*') if p.is_file()}
    require(actual=={r['stored'] for r in rows},'complete retained membership')
    return manifest,result


def document(files,key):return json.loads(files[key])


def summary(files):
    closure=document(files,'local-after/receipt.json');worker=document(files,'worker/receipt.json')
    return dict(schema='trisha/actual-byte-closure-summary/v1',status=closure['status'],
        source_head='97795590613e625b6be43c5e73afff4ab87009cd',worker=worker['worker'],
        original_remote_proof_run=document(files,'local-after/equivalence.json')['original_remote_proof']['run'],
        local_joy=closure['before']['prepared']['admitted']['source_revisions']['joy'],
        remote_joy='dd61df9128f6da1f97d4698f45f154f05312fe51',
        whole_identities=[dict(generation=e['generation'],proof=e['proof'],parts=len(e['parts'])) for e in worker['entries']],
        original_artifact=closure['admitted_remote']['artifact']['id'],original_zip=closure['admitted_remote']['original_zip'],
        remote_get_commands=len(worker['commands']),local_closure_commands=len(closure['commands']),
        elapsed_seconds=worker['elapsed_monotonic_seconds'],sampled_peak_rss_bytes=worker['sampled_peak_rss_bytes'],
        retained_assets=[closure['retained_original_metadata'],closure['equivalence']],
        scope='Complete transport byte equality and separate local before/after observations; SH8 adversarial/finalchecker acceptance remains separate.')


def bindings(files):
    sources=document(files,'source-map.json')
    require(len(sources)==38,'complete activated source closure')
    for name,expected in sources.items():
        require(identity(files['source/'+name])==expected,'retained source map identity')
        require(identity((REPO/name).read_bytes())==expected,'active checking source remains exact')
    peer=document(files,'peer-activation/independent-review.json')
    require(peer['status']=='passed-source-review' and peer['sources']==sources,'exact activation review')
    root=document(files,'root-actual/receipt.json');review=document(files,'peer-actual/peer-review.json')
    replay=document(files,'peer-actual/receipt.json');closure=document(files,'local-after/receipt.json')
    require(root['status']=='passed-byte-equivalence-transport' and review['status']=='passed-evidence-review'
            and replay['status']=='passed-actual-retained-byte-closure-review','root and independent actual acceptance')
    require(identity(files['local-after/receipt.json'])=={k:root['closure'][k] for k in ('bytes','sha256')},'exact root accepted closure')
    require(identity(files['peer-actual/peer-review.json'])=={k:root['peer_review'][k] for k in ('bytes','sha256')},'root accepted peer review')
    require(identity(files['peer-actual/receipt.json'])=={k:review['replay'][k] for k in ('bytes','sha256')},'exact offline replay')
    require(identity(files['peer-actual/replay.py'])=={k:replay['driver'][k] for k in ('bytes','sha256')},'actual replay driver')
    require(identity(files['root-actual/accept.py'])=={k:root['driver'][k] for k in ('bytes','sha256')},'actual root driver')
    require(closure['status']=='byte-equivalent-transport-adopted-remote-replay' and closure['sources']==sources,'complete closure exact source')
    for phase in ('before','after'):
        key='local-before/before.json' if phase=='before' else 'local-after/after.json'
        require(document(files,key)==closure[phase],'exact local scan bytes')
    before,after=closure['before'],closure['after']
    require(before['status']==after['status']=='passed-complete-local-scan' and before['prepared']==after['prepared']
            and before['ended_ns']<after['started_ns'],'both actual local observations')
    eq=document(files,'local-after/equivalence.json');worker=document(files,'worker/receipt.json');packing=document(files,'local-after/packing.json')
    require(eq['remote_body_replay']==closure['admitted_remote'] and eq['worker_observation']==worker
            and eq['packing_observation']==packing and eq['local_closure_sources']==sources,'exact durable equivalence contents')
    for phase in ('before','after'):
        key='local-before/before.json' if phase=='before' else 'local-after/after.json'
        require(eq['local'][phase]==dict(identity=identity(files[key]),observation=closure[phase]),'equivalence binds local observation')
    require(len(worker['commands'])==356 and len(closure['commands'])==50
            and sum(len(e['parts']) for e in worker['entries'])==22,'actual command and part counts')
    require(worker['worker']['id']==37047053221 and worker['worker']['attempt']==1
            and worker['worker']['head']==retained_head() and worker['status']=='completed-byte-replay','exact completed worker')
    require(len({p['asset']['id'] for e in worker['entries'] for p in e['parts']})==22,'distinct canonical part assets')
    for e,local in zip(worker['entries'],before['prepared']['admitted']['entries']):
        require(e['proof']==e['downloaded_reconstruction']=={k:local['proof'][k] for k in ('bytes','sha256')},'both actual ordered whole identities')
    require(root['whole_identities']==summary(files)['whole_identities'],'root bound whole identities')
    require(load(ROOT/'result.json')==summary(files),'derived public summary exact')
    references=load(ROOT/'references-only.json')['entries']
    require(references[0]['status']=='failed','original local adopter remains failed')
    return sources


def retained_head():return '97795590613e625b6be43c5e73afff4ab87009cd'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--originals',action='store_true')
    args=parser.parse_args();manifest,files=selected(args.originals);sources=bindings(files)
    impact=load(ROOT/'source-equivalence.json')
    require(impact['status']=='passed-source-equivalence' and not impact['differences']
            and impact['original_head']==retained_head() and len(impact['runtime_files_exact'])==510,'unchanged runtime source scope')
    for name,wanted in impact['runtime_files_exact'].items():
        if args.originals:
            require(identity((REPO/name).read_bytes())==wanted,'actual runtime source unchanged')
            require(identity((Path(impact['accepted_archive'])/'trisha'/name).read_bytes())==wanted,'accepted archive runtime equivalent')
    inventory=load(ROOT/'files.json')
    actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p!=ROOT/'files.json'}
    require(actual==set(inventory),'complete public packet inventory')
    for name,wanted in inventory.items():
        p=ROOT/name;require(identity(p.read_bytes())==wanted,'public packet file identity')
        if not name.startswith('retained/'):scan(p.read_bytes(),p.name)
    return dict(status='passed-selected-delivery',files=len(files),sources=len(sources),originals_replayed=args.originals,
                decoded_bytes=sum(v['original_identity']['bytes'] for v in manifest['records']),
                retention=identity((ROOT/'retention.json').read_bytes()),
                scope='Curated byte integrity, privacy checks and source/result bindings. Original full ZIP/body evidence replay is recorded separately; no network, full proof or native execution.')


if __name__=='__main__':print(json.dumps(main(),indent=2))
