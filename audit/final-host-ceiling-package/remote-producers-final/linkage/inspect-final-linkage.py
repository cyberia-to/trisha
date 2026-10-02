"""Inspect actual packaged native imports and version requirements without execution."""
from pathlib import Path
import gzip,hashlib,json,re,subprocess,tarfile,zipfile
M=Path(__file__).resolve().parent;O=M/'final-linkage';O.mkdir();tool='/opt/homebrew/opt/llvm/bin/llvm-readobj'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,command):
 r=subprocess.run(command,capture_output=True);(O/(name+'.stdout.gz')).write_bytes(gzip.compress(r.stdout,mtime=0));(O/(name+'.stderr')).write_bytes(r.stderr)
 assert r.returncode==0,(name,r.stderr)
 return r.stdout.decode(),dict(command=command,exit_code=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stdout_bytes=len(r.stdout),stderr_sha256=hashlib.sha256(r.stderr).hexdigest())
version,version_receipt=run('llvm-version',[tool,'--version']);rows=[]
roots=[p/'restored' for p in (M/'native-runs/36990413939').iterdir() if (p/'inspection.json').exists()]
roots.append(M.parent/'local-macos-final-rust189/release-results')
assert len(roots)==6
assert {json.loads((p/'archive.json').read_text())['target'] for p in roots}=={'aarch64-apple-darwin','x86_64-apple-darwin','aarch64-unknown-linux-gnu','x86_64-unknown-linux-gnu','aarch64-pc-windows-msvc','x86_64-pc-windows-msvc'}
for p in roots:
 a=json.loads((p/'archive.json').read_text());c=json.loads((p/'candidate.json').read_text());target=a['target'];assert a['source']['source_sha256']=='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8' and c['provenance_sha256']=='9334dead92b990a12acf16a2565aeb762a07311dfc2c3d6cb896c0490dc5926e';archive=p/a['archive'];assert sha(archive)==a['sha256'];d=O/target;d.mkdir()
 package=zipfile.ZipFile(archive) if archive.suffix=='.zip' else tarfile.open(archive)
 for row in c['binaries']:
  name=row['name']+('.exe' if 'windows' in target else '');member='cyber-tools/bin/'+name
  try:data=package.read(member) if archive.suffix=='.zip' else package.extractfile(member).read()
  except KeyError:raise ValueError('packaged binary path missing: '+member)
  binary=d/name;binary.write_bytes(data);assert sha(binary)==row['sha256']
  if 'windows' in target:
   assert c['rustflags']=='-C target-feature=+crt-static'
   output,command=run(target+'-'+name,[tool,'--coff-imports',str(binary)]);imports=re.findall(r'^  Name: (.+)$',output,re.M)
   assert imports and not any(re.match(r'(?:VCRUNTIME|MSVCP|MSVCR|UCRTBASE)',x,re.I) for x in imports),imports
   observation=dict(imports=imports,static_crt_policy='passed: no separate MSVC/UCRT runtime DLL import')
  elif 'linux' in target:
   output,command=run(target+'-'+name,[tool,'--needed-libs','--version-info',str(binary)]);versions=sorted({tuple(map(int,x.split('.'))) for x in re.findall(r'GLIBC_(\d+(?:\.\d+)+)',output)})
   assert versions and versions[-1]<=(2,35),versions
   observation=dict(glibc_versions=['.'.join(map(str,x)) for x in versions],observed_host=a['platform'],maximum_glibc='.'.join(map(str,versions[-1])))
  else:
   output,command=run(target+'-'+name,['otool','-l','-L',str(binary)])
   observation=dict(observed_host=a['platform'],deployment_minos=re.findall(r'^\s*minos\s+(.+)$',output,re.M),scope='Mach-O linkage only; older OS execution qualification remains separate')
  rows.append(dict(target=target,binary=name,sha256=row['sha256'],archive_sha256=a['sha256'],command=command,**observation))
 package.close()
assert len(rows)==24
report=dict(status='passed',scope='Actual packaged binary import/deployment inspection; executable OS qualification remains limited to measured hosts',source_sha256='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8',llvm=version,llvm_command=version_receipt,script_sha256=sha(Path(__file__)),binaries=rows)
(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status='passed',binaries=len(rows))))
