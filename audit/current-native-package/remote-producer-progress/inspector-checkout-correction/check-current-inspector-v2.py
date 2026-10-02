"""Exercise added current receipt checks against actual local package outputs."""
from pathlib import Path
import importlib.util,json,shutil,tempfile,traceback,hashlib
M=Path(__file__).resolve().parent;R=M.parent;P=R/'local-macos-current-rust189/release-results';O=M/'current-inspector-check-v2';O.mkdir()
s=importlib.util.spec_from_file_location('inspect_current',M/'inspect-current-native-producer.py');mod=importlib.util.module_from_spec(s);s.loader.exec_module(mod)
candidate=json.loads((P/'candidate.json').read_text());archive=json.loads((P/'archive.json').read_text());result=mod.additional(P,candidate,'aarch64-apple-darwin',archive)
report=dict(scope='Actual local current package added receipt checks; whole remote producer inspector and full198 remain separate',status='passed',positive=result,mutations=[])
for name in ['wrong-cargo-version','wrong-impact-inputs','wrong-consumer-joy','swapped-case-map','changed-proof-bytes']:
 with tempfile.TemporaryDirectory(prefix='current-inspector-') as temporary:
  root=Path(temporary)
  for file in ['toolchain-paths.json','rustc.log','cargo.log','rustdoc.log','source-impact.json','local-structured-verification.json','structured-corpus-aarch64-apple-darwin.tar.gz']:shutil.copy2(P/file,root/file)
  for directory in ['structured-corpus','local-structured-verification']:shutil.copytree(P/directory,root/directory)
  if name=='wrong-cargo-version':
   path=root/'toolchain-paths.json';data=json.loads(path.read_text());data['cargo']['version']=data['cargo']['version'].replace('1.89.0','1.95.0');path.write_text(json.dumps(data))
  elif name=='wrong-impact-inputs':
   path=root/'source-impact.json';data=json.loads(path.read_text());data['selector_sha256']='0'*64;path.write_text(json.dumps(data))
  elif name=='wrong-consumer-joy':
   path=root/'local-structured-verification.json';data=json.loads(path.read_text());data['consumer_joy']['sha256']='0'*64;path.write_text(json.dumps(data))
  elif name=='swapped-case-map':
   path=root/'structured-corpus/corpus.json';data=json.loads(path.read_text());accepted=next(x for x in data['cases'] if x['expected_exit']==0);rejected=next(x for x in data['cases'] if x['expected_exit']==1);accepted['expected_exit'],rejected['expected_exit']=1,0;path.write_text(json.dumps(data));p=root/'local-structured-verification.json';v=json.loads(p.read_text());v['corpus_sha256']=mod.sha(path);p.write_text(json.dumps(v))
  else:
   path=root/'structured-corpus/add14/proof';data=path.read_bytes();path.write_bytes(bytes([data[0]^1])+data[1:])
  try:mod.additional(root,candidate,'aarch64-apple-darwin',archive)
  except ValueError as error:report['mutations'].append(dict(name=name,rejected=True,error=str(error)))
  else:raise ValueError('changed receipt was accepted: '+name)
report['inspector_sha256']=mod.sha(M/'inspect-current-native-producer.py');report['driver_sha256']=mod.sha(Path(__file__));(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status=report['status'],actual_positive=True,rejected_mutations=len(report['mutations'])),indent=2))
