"""Exercise matrix pair checks against six actual producer self-consumer receipts."""
from pathlib import Path
import copy,importlib.util,json,tempfile,hashlib
M=Path(__file__).resolve().parent;O=M/'matrix-helper-six-producers';O.mkdir();spec=importlib.util.spec_from_file_location('checker',M/'check-final-corpus-matrix.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
roots=[p/'restored' for p in (M/'native-runs/36990413939').iterdir() if (p/'inspection.json').exists()];roots.append(M.parent/'local-macos-final-rust189/release-results');assert len(roots)==6
rows=[]
for p in roots:
 c=mod.load(p/'candidate.json');a=mod.load(p/'archive.json');legacy=mod.pair(p/'local-corpus-verification.json',p/'proof-corpus/corpus.json',c);structured=mod.structured_pair(p/'local-structured-verification.json',p/'structured-corpus/corpus.json',c);packaged=mod.inspector.package_candidate(p/a['archive'],c,a['target']);deadline=mod.inspector.deadline_probe(p,c,packaged,mod.inspector.WINDOWS_HELPER if 'windows' in a['target'] else mod.inspector.HELPER);rows.append(dict(target=a['target'],legacy=legacy,structured=structured,deadline=deadline))
assert {r['target'] for r in rows}==mod.TARGETS
p=roots[-1];c=mod.load(p/'candidate.json');mutations=[]
for name in ['legacy-consumer-binary','legacy-outcome','structured-producer-identity','structured-command-inventory','structured-raw-output']:
 with tempfile.TemporaryDirectory(prefix='final-matrix-mutation-') as tmp:
  legacy=name.startswith('legacy');original=p/('local-corpus-verification.json' if legacy else 'local-structured-verification.json');r=mod.load(original)
  if name=='legacy-consumer-binary':r['consumer_binaries']['joy']='0'*64
  elif name=='legacy-outcome':r['cases'][0]['exit_code']=1-r['cases'][0]['exit_code']
  elif name=='structured-producer-identity':r['producer_joy_sha256']='0'*64
  elif name=='structured-command-inventory':r['commands'][-1]=copy.deepcopy(r['commands'][0])
  else:r['commands'][0]['stdout']['sha256']='0'*64
  receipt=Path(tmp)/original.name;receipt.write_text(json.dumps(r))
  if not legacy:receipt.with_suffix('').symlink_to(original.with_suffix(''),target_is_directory=True)
  try:(mod.pair if legacy else mod.structured_pair)(receipt,p/('proof-corpus/corpus.json' if legacy else 'structured-corpus/corpus.json'),c)
  except ValueError as error:mutations.append(dict(name=name,rejected=True,error=str(error)))
  else:raise ValueError('altered receipt accepted: '+name)
report=dict(status='passed',scope='Actual six final producer self-consumer pair receipts, installed deadline evidence and five integrity mutations; full cross-platform consumer matrix remains separate',checker_sha256=mod.sha(M/'check-final-corpus-matrix.py'),script_sha256=mod.sha(Path(__file__)),native_self_pairs=len(rows),case_checks=sum(r['legacy']['cases']+r['structured']['cases'] for r in rows),pairs=rows,mutations=mutations)
(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status='passed',case_checks=report['case_checks'],mutations=len(mutations))))
