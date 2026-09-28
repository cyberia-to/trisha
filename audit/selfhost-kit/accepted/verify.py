"""Verify retained raw kit/delivery evidence without a compiler, runtime or authority rerun."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parent

def require(ok,label):
 if not ok:raise ValueError(label)
def ident(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(name):return json.loads((ROOT/name).read_bytes())
def expected(row):return {k:row[k] for k in ('bytes','sha256')}
receipt=load('receipt.json')
for key in ('kit_archive','evidence_archive'):
 require(ident((ROOT/receipt[key]['path']).read_bytes())==expected(receipt[key]),'retained archive identity')
indexed={row['path']:row for row in load('evidence-files.json')};raw={}
with tarfile.open(ROOT/'evidence.tar.gz') as tar:
 for item in tar:
  require(item.name in indexed and item.name not in raw and (item.isfile() or item.islnk()),'ordinary evidence member')
  require(item.uid==item.gid==item.mtime==0 and item.mode==0o644,'deterministic evidence metadata')
  require(not item.islnk() or item.linkname in raw,'earlier raw dedup target')
  data=tar.extractfile(item).read();require(ident(data)==expected(indexed[item.name]),'raw evidence hash/length')
  raw[item.name]=data
require(raw.keys()==indexed.keys() and len(raw)==receipt['evidence_members'],'complete raw evidence')
kit={}
with tarfile.open(ROOT/'selfhost-kit.tar.gz') as tar:
 for item in tar:
  if item.isdir():continue
  require(item.isfile() and item.name.startswith('trident-selfhost/'),'ordinary original kit member')
  name=item.name.removeprefix('trident-selfhost/');require(name not in kit,'unique original kit member')
  kit[name]=tar.extractfile(item).read()
manifest=json.loads(kit['kit.json'])
require(manifest['status']=='accepted' and set(kit)==set(manifest['files'])|{'kit.json'},'complete accepted kit')
for name,row in manifest['files'].items():require(ident(kit[name])==row,'kit manifest binding')
require(ident(kit['compiler.dag'])['sha256']=='76a07c08265bd2ef525164472b6b53ac3f0e6cbbedce3250c4202f40ffba34c8','actual C2')
require(ident(kit['kit.json'])==json.loads(raw['delivery/receipt.json'])['kit_manifest'],'original selected kit')
aliases={row['path']:row for row in load('canonical-kit-aliases.json')}
external=load('external-files.json');external_by_path={row['original_path']:row for row in external}
for row in load('delivery-files.json'):
 if row['retained']=='canonical-kit-alias':
  alias=aliases[row['path']];data=kit[alias['member'].removeprefix('trident-selfhost/')]
  require(ident(data)==expected(alias)==expected(row),'exact canonical kit alias')
 elif row['retained']=='external-identity':
  require(expected(row)==expected(external_by_path[row['original_path']]),'external delivery binding')
 elif row['retained']=='selfhost-kit.tar.gz':require(expected(row)==expected(receipt['kit_archive']),'original portable archive')
 else:require(ident(raw[row['retained'].removeprefix('evidence.tar.gz:')])==expected(row),'full delivery raw mapping')
run=json.loads(raw['delivery/receipt.json']);old=json.loads(raw['previous-full-execution/receipt.json'])
require(run['status']=='passed' and run['inputs_start']==run['inputs_end'] and len(run['commands'])==12,'real delivery completion')
for command in run['commands']:
 require(command['status']=='completed' and command['exit_code']==0,'successful actual command')
 for stream in ('stdout','stderr'):require(ident(raw['delivery/'+command['name']+'.'+stream])==command[stream],'actual raw command logs')
require(raw['delivery/assembly/validation/verification.json']==kit['acceptance.json'],'fresh real authority retained')
proof=json.loads(kit['acceptance.json'])
require(proof['status']=='passed' and proof['validator_sha256']=='72cd11ec62e410e908590a785c79011989ea2c6c32872c5db31d72a62947c0ec' and len(proof['phases'])==36,'fresh pinned authority report')
require(ident(kit['producer.json'])==expected(next(p['receipt'] for p in proof['phases'] if p['name']==manifest['producer']['name'])),'selected original producer')
for prefix in ('installed-smoke','unpacked-smoke'):
 smoke=json.loads(raw[f'delivery/{prefix}/receipt.json'])
 require(smoke['status']=='passed' and smoke['kit_status']=='accepted' and smoke['kit_manifest']==ident(kit['kit.json']),'actual production smoke')
 require(len(smoke['commands'])==5,'all five Joy routes')
 for number,command in enumerate(smoke['commands']):
  require(command['status']=='completed' and command['exit_code']==(1 if number==4 else 0),'real smoke exits')
  for stream in ('stdout','stderr'):
   require(ident(raw[f'delivery/{prefix}/{number}.{stream}'])==expected(command[stream]),'raw smoke logs')
 require(ident(raw[f'delivery/{prefix}/answer.dag'])==dict(bytes=85,sha256='348d22b1dca51095cf13e13a4674727db537c8cd07f21af53009022b5e7bb94a'),'actual atom13 bytes')
 require(raw[f'delivery/{prefix}/rejected.dag']==b'preserve existing output\n','negative output preservation')
 require(raw[f'delivery/{prefix}/4.stdout']==b'' and raw[f'delivery/{prefix}/4.stderr'].startswith(b'error: guest compilation failed:'),'real guest diagnostic')
 require(expected(smoke['joy'])==old['binary_end'],'same Joy as full run')
prep=json.loads(raw['delivery/prepared/receipt.json'])
require(prep['status']=='prepared' and prep['kit_status']=='accepted' and len(prep['sources'])==94,'actual default accepted source preparation')
for row in prep['sources'].values():require(ident(raw['delivery/prepared/'+row['copy']])==expected(row),'actual94 source bytes')
for name in ('compiler.dag','job.dag','package.json'):
 data=kit['compiler.dag'] if name=='compiler.dag' else raw['delivery/prepared/'+name]
 require(ident(data)==old['inputs_start']['files'][name]==old['inputs_end']['files'][name],'prior full-run exact input bridge')
pack=next(c for c in run['commands'] if c['name']=='pack-full-source')
require(pack['argv'][-len(old['host_flags']):]==old['host_flags'],'prior full-run exact host profile')
post=json.loads(raw['driver/postcheck.json'])
require(post['status']=='passed' and post['byte_exact_repacked_archives'] is True and run['additional_heavy_guest_runs']==0,'original package bytecheck and no repeated self-build')
checked=0
if '--external' in sys.argv:
 for row in external:
  with Path(row['original_path']).open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
  require(dict(bytes=Path(row['original_path']).stat().st_size,sha256=digest)==expected(row),'actual external dependency')
  checked+=1
print(json.dumps(dict(status='passed',evidence_members=len(raw),canonical_kit_members=len(kit),canonical_aliases=len(aliases),external_files_checked=checked,
                     actual_outer_commands=12,actual_joy_smoke_routes=10,prepared_sources=94,additional_heavy_guest_runs=0,
                     scope='Raw evidence and recorded authority/input bindings; no fresh execution or authority replay'),sort_keys=True))
