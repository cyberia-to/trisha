"""Preserve compact original observations for the completed final73b50 full198 gate."""
from pathlib import Path
import gzip,hashlib,json,re,shutil
M=Path(__file__).resolve().parent;R=M.parent;CI=R/'trisha-native-ci';L=R/'local-macos-final-rust189';P=L/'release-results';O=CI/'audit/final-host-ceiling-package/local-full198';O.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((M/'local-rust189-complete/receipt.json').read_text());assert report['status']=='passed' and report['proof_gate']['fresh_verified_proofs']==198
package=M/'local-rust189-complete'/report['archive']['path'];assert sha(package)==report['archive']['sha256'] and package.stat().st_size==report['archive']['bytes']
for name in ['started.json','bench.log','memory.jsonl']:(O/(name+'.gz')).write_bytes(gzip.compress((P/'baselines'/name).read_bytes(),mtime=0))
for src,name in [(P/'baselines/receipt.json','baseline-receipt.json'),(L/'driver.json','driver.json'),(P/'candidate.json','candidate.json'),(P/'baseline-inheritance.json','baseline-inheritance.json'),(P/'source-verification.json','source-verification.json'),(M/'local-rust189-complete/receipt.json','retention.json'),(M/'retain-final-local.py','retain-final-local.py')]:shutil.copy2(src,O/name)
logs=[]
for p in sorted(P.glob('*.log')):
 if not (p.name.endswith('-tests.log') or (p.name.startswith('candidate-') and p.name.endswith('-build.log'))):continue
 normalized=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',p.read_text());assert not re.search(r'^warning(?:\[|:)',normalized,re.M);logs.append(dict(path=p.name,sha256=sha(p),bytes=p.stat().st_size))
(O/'zero-warnings.json').write_text(json.dumps(dict(status='passed',scope='Original completed local CPU/build logs; ANSI CSI removed only for diagnostic recognition',logs=logs),indent=2)+'\n');shutil.copy2(Path(__file__),O/Path(__file__).name);print(json.dumps(dict(status='passed',original_archive=report['archive'],cpu_build_logs=len(logs))))
