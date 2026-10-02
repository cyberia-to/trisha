"""Retain the actual completed current Mac consumer and all twelve corpus receipts."""
from pathlib import Path
import gzip,hashlib,importlib.util,json,tarfile,shutil
M=Path(__file__).resolve().parent;R=M.parent;CI=R/'trisha-native-ci';L=R/'local-macos-current-corpus-consumer';O=CI/'audit/current-native-package/local-corpus-consumer';O.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
s=importlib.util.spec_from_file_location('matrix',M/'check-current-corpus-matrix.py');helper=importlib.util.module_from_spec(s);s.loader.exec_module(helper)
selected=load(CI/'.github/release-candidate.json');driver=load(L/'driver.json');assert driver['status']=='passed' and driver['exit_code']==0 and driver['resource_stopped'] is False and driver['bootstrap_revision']=='a5cdd95cb652d76a023fad1e40aefe54f6387445'
expected=dict(selected,full_baselines=True,targets=['aarch64-apple-darwin']);assert driver['selector']==expected==load(L/'.github/release-candidate.json')
for name in ['driver.stdout','driver.stderr','resources.jsonl']:assert sha(L/name)==driver[name]['sha256'] and (L/name).stat().st_size==driver[name]['bytes']
producer={'aarch64-apple-darwin':R/'local-macos-current-rust189/release-results'}
for p in (M/'native-runs/36969168806').iterdir():
 if (p/'inspection.json').exists():producer[load(p/'inspection.json')['target']]=p/'restored'
assert set(producer)==helper.TARGETS;c=load(producer['aarch64-apple-darwin']/'candidate.json');results=[]
kit=load(L/'release-results/verified-selfhost-smoke/receipt.json');original=load(producer['aarch64-apple-darwin']/'unpacked-selfhost-smoke/receipt.json');assert kit['status']=='passed' and kit['joy']['sha256']==original['joy']['sha256'] and kit['kit_manifest']==original['kit_manifest']
for field,kind,stem,manifest,check in [('corpora','legacy','verification','proof-corpus/corpus.json',helper.pair),('structured_corpora','structured','structured-verification','structured-corpus/corpus.json',helper.structured_pair)]:
 for index,item in enumerate(selected[field]):results.append(dict(kind=kind,producer=item['target'],consumer='aarch64-apple-darwin',**check(L/'release-results'/f'{stem}-{index}.json',producer[item['target']]/manifest,c)))
paths=[p for p in sorted(L.rglob('*')) if p.is_file() and 'temporary' not in p.relative_to(L).parts]
paths.append(L/'temporary/cyber-candidate/installed/cyber-tools/candidate.json');files=[dict(path=p.relative_to(L).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in paths]
archive=O/'original-evidence.tar.gz'
with archive.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w') as tar:
 for row,p in zip(files,paths):
  info=tarfile.TarInfo(row['path']);info.size=row['bytes'];info.mode=0o644
  with p.open('rb') as stream:tar.addfile(info,stream)
for row,p in zip(files,paths):assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
shutil.copy2(L/'driver.json',O/'driver.json');shutil.copy2(Path(__file__),O/Path(__file__).name)
dump(O/'receipt.json',dict(status='passed',scope='Actual local Mac ARM current package consumer only; complete six-native matrix and full198 proof generation remain separate',source_sha256=helper.SOURCE,selector_revision=driver['bootstrap_revision'],selector_sha256=sha(CI/'.github/release-candidate.json'),elapsed_seconds=driver['elapsed_seconds'],peak_process_group_rss_bytes=driver['peak_process_group_rss_bytes'],case_checks=sum(r['cases'] for r in results),corpus_pairs=len(results),pairs=results,archive=dict(path=archive.name,bytes=archive.stat().st_size,sha256=sha(archive)),files=files,script_sha256=sha(Path(__file__))))
print(json.dumps(dict(status='passed',case_checks=sum(r['cases'] for r in results),files=len(files),archive_bytes=archive.stat().st_size)))
