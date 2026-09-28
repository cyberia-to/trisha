from pathlib import Path
import json,hashlib,tarfile,subprocess,sys
R=Path('/Users/master/cyber/.worktrees/selfhost-0.4-full-bootstrap');b=R/'measurements/accepted-selfhost-kit/retention';out=R/'measurements/accepted-selfhost-kit/root-retention-review';out.mkdir()
def ident(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def require(ok,label):
 if not ok:raise ValueError(label)
idx=json.loads((b/'files.json').read_bytes());require(ident((b/'files.json').read_bytes())['sha256']=='4de44eda13ba417bfe4975183f7569f625039cbbbab159849d5cb5b1e5a8fc57','pinned retention index')
for row in idx:require(ident((b/row['path']).read_bytes())=={k:row[k] for k in ('bytes','sha256')},'retained file identity')
rows=json.loads((b/'evidence-files.json').read_bytes());byname={row['path']:row for row in rows};total=0
with tarfile.open(b/'evidence.tar.gz') as archive:
 require(set(archive.getnames())==set(byname),'exact member set')
 for member in archive:
  data=archive.extractfile(member).read();row=byname[member.name]
  require(data==Path(row['original_path']).read_bytes(),'exact original member')
  require(ident(data)=={k:row[k] for k in ('bytes','sha256')},'original index')
  total+=len(data)
argv=[sys.executable,'-B','-W','error',str(b/'verify.py'),'--external'];result=subprocess.run(argv,capture_output=True)
(out/'verify.stdout').write_bytes(result.stdout);(out/'verify.stderr').write_bytes(result.stderr);require(result.returncode==0 and not result.stderr,'portable retained verifier')
report=dict(status='passed',command=[sys.executable,*sys.argv],source_revision='4b81af3baf01180d95113e5d69ed8d7e5e69eb1e',retention_index=ident((b/'files.json').read_bytes()),retained_indexed_files=len(idx),raw_evidence_members=len(rows),raw_evidence_bytes=total,all_original_member_bytes_equal=True,portable_verifier=dict(argv=argv,exit_code=result.returncode,stdout=ident(result.stdout),stderr=ident(result.stderr)))
(out/'review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
