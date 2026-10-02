"""Upload only the frozen Rust 1.89 Mac packages to existing draft transport."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess,tarfile,traceback
ROOT=Path(__file__).resolve().parent.parent
LOCAL=ROOT/'local-macos-rust189'
RESULTS=LOCAL/'release-results'
OUT=ROOT/'measurements/local-package-transport'
TARGET='aarch64-apple-darwin'
SOURCE='e4bac7ff7260a5f395febc196b3e4792653e0ff81d7887d688e16ea0959aa361'
PROVENANCE='9fddb8002ebb49ad724dfeb20972066c1de0b75b22f806b5360609bb12eaaec5'
KIT='a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd'
RELEASE_ID=389977897
TAG='candidate-20260916.1'
PREFIX='rehearsal-20261002-e4bac7ff-local-rust189-'

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def guard():
    if (RESULTS/'failure.txt').exists():raise ValueError('failed producer cannot supply accepted packages')
    archive=json.loads((RESULTS/'archive.json').read_text())
    if (archive['target']!=TARGET or archive['source']['source_sha256']!=SOURCE
        or archive['source']['selfhost_kit']['sha256']!=KIT):raise ValueError('frozen archive selection differs')
    candidate=json.loads((RESULTS/'candidate.json').read_text())
    toolchain=candidate['toolchain']
    if (not toolchain.startswith('rustc 1.89.0 ') or 'release: 1.89.0\n' not in toolchain
        or 'host: '+TARGET+'\n' not in toolchain):raise ValueError('actual native Rust 1.89 required')
    preflight=json.loads((LOCAL/'toolchain-preflight.json').read_text())
    if len(preflight['tools'])!=2:raise ValueError('both compiler and cargo observations required')
    for entry in preflight['tools']:
        name=Path(entry['command'][0]).name
        if name not in ('rustc','cargo') or not entry['stdout'].startswith(name+' 1.89.0 ') or entry['exit_code']:
            raise ValueError('actual tool preflight differs')
    if candidate['provenance_sha256']!=PROVENANCE:raise ValueError('candidate source provenance differs')
    corpus_path=RESULTS/('proof-corpus-'+TARGET+'.tar.gz')
    corpus_bytes=(RESULTS/'proof-corpus/corpus.json').read_bytes()
    if json.loads(corpus_bytes)['source_provenance_sha256']!=PROVENANCE:raise ValueError('corpus source provenance differs')
    with tarfile.open(corpus_path) as content:
        member=content.getmember('proof-corpus/corpus.json')
        if not member.isfile() or content.extractfile(member).read()!=corpus_bytes:raise ValueError('corpus package inventory differs')
    binary_path=RESULTS/archive['archive']
    if binary_path.parent!=RESULTS or sha(binary_path)!=archive['sha256']:raise ValueError('binary package hash differs')
    with tarfile.open(binary_path) as content:
        packaged=json.loads(content.extractfile('cyber-tools/candidate.json').read())
        if packaged!={key:value for key,value in candidate.items() if key!='source'}:raise ValueError('package candidate differs from documented portable inventory')
        for entry in candidate['binaries']:
            member=content.getmember('cyber-tools/bin/'+entry['name'])
            if not member.isfile() or hashlib.sha256(content.extractfile(member).read()).hexdigest()!=entry['sha256']:
                raise ValueError('packaged binary differs')
    return archive,candidate,binary_path,corpus_path

def main():
    archive,candidate,binary_path,corpus_path=guard()
    OUT.mkdir()
    report=dict(scope='Frozen e4bac7ff feature-branch rehearsal transport; no official release candidate, tag or publication',
        status='running',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),target=TARGET,
        source_sha256=SOURCE,provenance_sha256=PROVENANCE,kit_sha256=KIT,
        producer_directory=str(LOCAL),producer_driver_at_upload=json.loads((LOCAL/'driver.json').read_text()),
        proof_gate_claim='Package-producing gates completed; full 198-proof verdict is separate and must be read from final driver/baseline receipts',
        archive=archive,candidate_sha256=sha(RESULTS/'candidate.json'),commands=[],assets=[])
    def save():(OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    def api(name,endpoint,absent=False):
        cmd=['gh','api',endpoint];run=subprocess.run(cmd,capture_output=True)
        for stream in ('stdout','stderr'):(OUT/(name+'.'+stream)).write_bytes(getattr(run,stream))
        report['commands'].append(dict(command=cmd,exit_code=run.returncode));save()
        value=json.loads(run.stdout)
        if absent:
            if run.returncode!=1 or str(value.get('status'))!='404':raise ValueError('draft tag must remain absent')
        elif run.returncode:raise RuntimeError(name+' API failed')
        return value
    def draft(name):
        data=api(name,'repos/cyberia-to/trisha/releases/'+str(RELEASE_ID))
        if data['draft'] is not True or data['tag_name']!=TAG:raise ValueError('existing unpublished draft required')
        api(name+'-tag','repos/cyberia-to/trisha/git/ref/tags/'+TAG,True)
        return data
    save()
    try:
        existing={entry['name'] for entry in draft('before')['assets']}
        for kind,source in [('binary',binary_path),('corpus',corpus_path)]:
            name=PREFIX+source.name
            if name in existing:raise ValueError('unique draft asset is already occupied')
            named=OUT/name;shutil.copyfile(source,named);digest=sha(named)
            cmd=['gh','release','upload',TAG,str(named),'--repo','cyberia-to/trisha']
            with (OUT/(kind+'-upload.stdout')).open('xb') as out,(OUT/(kind+'-upload.stderr')).open('xb') as err:
                run=subprocess.run(cmd,stdout=out,stderr=err)
            report['commands'].append(dict(command=cmd,exit_code=run.returncode));save()
            if run.returncode:raise RuntimeError(kind+' upload failed')
            release=draft(kind+'-after')
            entry=next(a for a in release['assets'] if a['name']==name)
            if entry.get('digest')!='sha256:'+digest or entry['size']!=named.stat().st_size or sha(source)!=digest:
                raise ValueError('server or retained package identity differs')
            report['assets'].append(dict(kind=kind,target=TARGET,asset_id=entry['id'],name=name,sha256=digest,bytes=entry['size']));save()
            print(kind,entry['id'],digest,flush=True)
        report['status']='passed'
    except BaseException:
        report.update(status='failed',error=traceback.format_exc());raise
    finally:save()

if __name__=='__main__':main()
