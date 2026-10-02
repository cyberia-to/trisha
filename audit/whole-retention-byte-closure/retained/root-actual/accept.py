"""Root admission of independently replayed complete byte closure."""
import hashlib,json,time,sys
from pathlib import Path
R=Path(__file__).resolve().parent;B=R.parent
L=B/'whole-retention-remote-readback';A=L/'local-after-37047053221'
P=B/'whole-retention-byte-closure-independent'
def identity(p):
    with p.open('rb') as f:d=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(bytes=p.stat().st_size,sha256=d)
def ref(p):return dict(path=str(p),**identity(p))
def load(p):return json.loads(p.read_bytes())
def verify(p,v):assert identity(p)=={k:v[k] for k in ('bytes','sha256')},str(p)
start=time.monotonic();before=time.time_ns()
assert identity(A/'receipt.json')['sha256']=='2489e9f52e040fb1eea20695bd6b4a9186433a6adb75e429f5b7e131c65d6dcc'
assert identity(P/'peer-review.json')['sha256']=='09dfe8cfffa2ea507f7cde914e4fe09e8fd01b13c509724266b346c79495c022'
d=load(A/'receipt.json');peer=load(P/'peer-review.json')
assert d['status']=='byte-equivalent-transport-adopted-remote-replay'
assert peer['status']=='passed-evidence-review' and not peer['findings']
for key in ('closure','replay','driver','git_observation'):
    row=peer[key];verify(Path(row['path']),row)
assert load(P/'receipt.json')['status']=='passed-actual-retained-byte-closure-review'
assert d['sources']==load(L/'trisha/.github/whole-readback-sources.json')
for name,v in d['sources'].items():verify(L/'trisha'/name,v)
wrapper=load(L/'after-completed.json');assert wrapper['status']=='passed' and wrapper['exit_code']==0
for name in ('receipt.json','after.json','equivalence.json'):verify(A/name,wrapper[name])
verify(L/'after.stdout',wrapper['stdout']);verify(L/'after.stderr',wrapper['stderr']);assert wrapper['stderr']['bytes']==0
assert len(d['commands'])==50
for row in d['commands']:
    for channel in ('stdout','stderr'):
        path=Path(row[channel+'_path']);assert path.parent==A;verify(path,row[channel])
    assert row['exit_code']==row['expected_exit']
assert d['before']==load(L/'local-before-9779559/before.json') and d['after']==load(A/'after.json')
assert d['before']['prepared']==d['after']['prepared']
a=d['admitted_remote'];assert a['status']=='passed' and a['run']['id']==37047053221 and a['run']['run_attempt']==1
assert a['run']['head_sha']=='97795590613e625b6be43c5e73afff4ab87009cd'
assert a['run']['conclusion']=='success' and a['artifact']['id']==11245008879
assert a['original_zip']['sha256']==a['artifact']['digest'][7:]
assert a['checked']['status']=='passed-authenticated-remote-byte-replay' and len(a['checked']['body_commands'])==22
for key,name in [('retained_original_metadata','original-local-metadata.tar.gz'),('equivalence','equivalence.json')]:
    verify(A/name,d[key]);assert d[key]['asset']['digest']=='sha256:'+d[key]['sha256']
assert [d[k]['asset']['id'] for k in ['retained_original_metadata','equivalence']]==[606256958,606263560]
old=peer['original_failed_attempt'];verify(Path(old['receipt']['path']),old['receipt']);assert load(Path(old['receipt']['path']))['status']=='failed'
report=dict(schema='trident/root-actual-byte-closure-admission/v1',status='passed-byte-equivalence-transport',command=[sys.executable,*sys.argv],driver=ref(Path(__file__)),started_ns=before,ended_ns=time.time_ns(),elapsed_seconds=time.monotonic()-start,closure=ref(A/'receipt.json'),peer_review=ref(P/'peer-review.json'),independent_replay=ref(P/'receipt.json'),source_head=a['run']['head_sha'],source_manifest=ref(L/'trisha/.github/whole-readback-sources.json'),wrapper=ref(L/'after-completed.json'),whole_identities=peer['whole_identities'],retained_assets=[d[k] for k in ['retained_original_metadata','equivalence']],checks=['Reviewed full independent replay driver and production local/result/recorded admission predicates.','Root rehashed all38 executable/source identities, all50 original command output pairs, successful outer wrapper streams, closure scans and both uploaded metadata payloads.','Peer independently replayed original Actions ZIP and all356 remote GET observations with22 bodies, whole reconstructions,50 local operations and final draft/tag/default guards.','Original failed local adopter retained failed; local6e and remote proofdd61 remain distinct provenance.'],limitations=['No new network/fullproof scans/native workload in this root admission.','This closes durable byte-equivalence evidence only; actual SH8 adversarial/finalchecker acceptance remains pending.','Draft remains unpublished; no tag, default-branch merge or release promotion.','Raw process snapshots and signed URLs stay in private local originals; public evidence must use safe selected files or identity references.'])
with (R/'receipt.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(ref(R/'receipt.json')))
