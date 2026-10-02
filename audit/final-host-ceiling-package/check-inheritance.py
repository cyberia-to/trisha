"""Actual original-worker replay plus mutations; this is not a final package verdict."""
from pathlib import Path
import argparse,copy,gzip,hashlib,importlib.util,io,json,shutil,tarfile,tempfile
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--current-family',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();O=args.output;O.mkdir()
CI=Path(__file__).resolve().parents[2];path=CI/'scripts/inherit-full-baselines.py';spec=importlib.util.spec_from_file_location('inheritance',path);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
R=args.current_family.resolve();candidate=R/'local-macos-current-rust189/temporary/cyber-candidate/candidate';archive=R/'measurements/local-rust189-complete/rehearsal-20261002-734df69d-local-rust189-evidence.tar.gz';references=CI/'audit/final-host-ceiling-package/references'
positive=helper.check(candidate,archive,references);assert positive['status']=='inherited_full198_coverage' and positive['inherited_verified_proofs']==198 and positive['fresh_run_performed'] is False
(O/'original-worker-positive.json').write_text(json.dumps(positive,indent=2)+'\n');observations=[]
with tempfile.TemporaryDirectory(prefix='inherit198-binary-') as temp:
 target=Path(temp);(target/'bin').mkdir();data=json.loads((candidate/'candidate.json').read_text())
 for row in data['binaries']:
  src=candidate/'bin'/row['name'];dst=target/'bin'/row['name']
  if row['name']=='trisha':
   shutil.copy2(src,dst)
   with dst.open('r+b') as stream:stream.seek(-1,2);last=stream.read(1);stream.seek(-1,2);stream.write(bytes([last[0]^1]))
   row['sha256']=helper.sha(dst)
  else:dst.symlink_to(src)
 (target/'candidate.json').write_text(json.dumps(data));shutil.copy2(candidate/'source-verification.json',target/'source-verification.json')
 result=helper.check(target,archive,references);assert result['status']=='needs_fresh_full198' and result['inherited_verified_proofs'] is None and result['reasons']==['actual Trisha executable is not byte-identical to original198 worker']
 observations.append(dict(name='changed-actual-Trisha-bytes',status=result['status'],reasons=result['reasons']))
previous=json.loads(gzip.decompress((references/'source734-sources.json.gz').read_bytes()))
for name,repo,file in [('manual-fixture','trisha',positive['original']['receipt']['verified_proof_events'][0]['fixture'].split('/cyber-source/trisha/')[1]),('proof-driver','trisha','scripts/check-baselines.py'),('dependency-source','nox','rs/lib.rs')]:
 current=copy.deepcopy(previous);row=next(x for x in current if x['repository']==repo);entry=next(x for x in row['files'] if x['path']==file);entry['sha256']='0'*64;changed,_=helper.compare_sources(current,previous);assert changed==[repo+'/'+file];observations.append(dict(name=name,rejected_for_inheritance=changed))
with tempfile.TemporaryDirectory(prefix='inherit198-checker-') as temp:
 target=Path(temp);shutil.copytree(references,target/'references');p=target/'references/source734-check-baselines.py';p.write_bytes(p.read_bytes()+b'\n# changed reference\n')
 try:helper.check(candidate,archive,target/'references')
 except ValueError as error:assert str(error)=='original proof checker differs';observations.append(dict(name='changed-original-checker',rejected=True,error=str(error)))
 else:raise ValueError('altered original checker accepted')
with tempfile.TemporaryDirectory(prefix='inherit198-receipt-') as temp:
 mutated=Path(temp)/'changed-prior-receipt.tar'
 with tarfile.open(archive) as source,tarfile.open(mutated,'w') as destination:
  for info in source:
   if not info.isfile():destination.addfile(info);continue
   content=source.extractfile(info)
   if info.name=='release-results/baselines/receipt.json':
    receipt=json.loads(content.read());receipt['all_checks_passed']=False;data=json.dumps(receipt).encode();info=copy.copy(info);info.size=len(data);destination.addfile(info,io.BytesIO(data))
   else:destination.addfile(info,content)
 try:helper.check(candidate,mutated,references)
 except ValueError as error:assert str(error)=='original full198 archive identity differs';observations.append(dict(name='changed-original-receipt',rejected=True,error=str(error),mutated_archive_sha256=helper.sha(mutated)))
 else:raise ValueError('altered original receipt accepted')
report=dict(status='passed',scope='Actual source734 original-worker replay and integrity mutations; final dd61 package coverage remains unmeasured',reference_archive_sha256=helper.EVIDENCE,checker_sha256=helper.sha(path),driver_sha256=helper.sha(Path(__file__)),positive='original-worker-positive.json',mutations=observations)
(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status='passed',actual_original_replay=True,mutations=len(observations))))
